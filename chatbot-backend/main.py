from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import time
import uuid
import json
from dotenv import load_dotenv
# from supabase import create_client, Client
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, text
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from graph import build_graph, trigger_async_memory_update, fetch_compiled_user_context, pool
from contextlib import asynccontextmanager
from upload import router as upload_router
import asyncio
import traceback
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from mcp_manager import mcp_manager, SERVERS
from database import AsyncSessionLocal
from models import Message, Conversation

load_dotenv()
chatbot = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global chatbot
    print("Opening async database connection pool...")
    await pool.open()

    try:
        mcp_tools = await mcp_manager.initialize(SERVERS)
    except Exception as e:
        print(f"Failed to load mcp tools: {e}")
        mcp_tools = []

    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()

    graph = build_graph(mcp_tools)
    chatbot = graph.compile(checkpointer=checkpointer)
    print('langgraph compiled successfully')

    yield

    print("Closing mcp connections")
    # await mcp_manager.cleanup()

    print("Closing database connection pool...")
    await pool.close()

app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000'],
    allow_methods=['*'],
    allow_headers=['*']
)
app.include_router(upload_router, prefix='/upload')


async def stream_response(message: str, thread_id: str, human_msg_id: str, ai_msg_id: str, user_id: str, user_context: str, active_files: list[str]):

    try:
        async with AsyncSessionLocal() as db:
            new_human_msg = Message(
                id=human_msg_id,
                conversation_id=thread_id,
                content=message,
                role="human",
                user_id=user_id
            )
            db.add(new_human_msg)
            await db.commit()
    except Exception as e:
        print(f"Failed to save human message: {e}")

    # to avoid duplicates
    announced_tools = set()

    last_tool_id = None
    last_tool_name = None

    full_ai_response = ""

    shared_payload_container = {
        "source_file": None,
        "topology": None,
        "actions": None,
        "edges": None
    }
    try:
        async for event in chatbot.astream(
            {"messages": [HumanMessage(content=message)],
             "retrieval_count": 0,
             "summary": ""
             },
            config={"configurable": {'thread_id': thread_id,
                                     "user_id": user_id, "user_context": user_context,
                                     "active_files": active_files,
                                     "_shared_payload_container": shared_payload_container
                                     }
                    },
            stream_mode="messages"
        ):

            last_msg, _ = event

            # ai will call tool (response)
            if hasattr(last_msg, "tool_call_chunks") and last_msg.tool_call_chunks:
                for tool_call in last_msg.tool_call_chunks:
                    call_id = tool_call.get('id')
                    if call_id and call_id not in announced_tools:
                        announced_tools.add(call_id)
                        tool_name = tool_call.get('name')

                        last_tool_id = call_id
                        last_tool_name = tool_name

                        yield (
                            "__TOOL_START__" + json.dumps({
                                "tool_id": call_id,
                                "tool_name": tool_name,
                                "content": "waiting for the tool_response",
                                "status": "running"
                            }) + "__TOOL_END__"
                        )

            if isinstance(last_msg, ToolMessage) and last_msg.content:
                yield (
                    "__TOOL_START__" + json.dumps({
                        "tool_id": last_msg.tool_call_id,
                        "tool_name": getattr(last_msg, "name", "Unknown Tool"),
                        "content": str(last_msg.content),
                        "status": "completed"
                    }) + "__TOOL_END__"
                )
            elif isinstance(last_msg, AIMessage) and last_msg.content:
                # print(last_msg)
                content = last_msg.content.replace("\r", "")
                full_ai_response += content
                yield content

        if shared_payload_container["topology"] or shared_payload_container["actions"] or shared_payload_container['edges']:
            combined_frontend_payload = {
                "source_file": shared_payload_container["source_file"],
                "topology": shared_payload_container["topology"],
                "actions": shared_payload_container["actions"],
                "edges": shared_payload_container['edges']
            }
            print(f"edges: {shared_payload_container['edges']}")
            print(f"actions: {shared_payload_container['actions']}")
            yield f"\n__GRAPH_METADATA_START__\n{json.dumps(combined_frontend_payload)}\n__GRAPH_METADATA_END__"
    except asyncio.CancelledError:
        print("Frontend stream aborted by user")
        full_ai_response += '\n\nYou stopped the response'
    except Exception as e:
        traceback.print_exc()

        if last_tool_id:
            yield (
                "__TOOL_START__" + json.dumps({
                    "tool_id": last_tool_id,
                    "tool_name": last_tool_name,
                    "content": str(e),
                    "status": "error"
                }) + "__TOOL_END__"
            )
        else:
            yield f"\n\n[ERROR]: {str(e)}"
    finally:
        if full_ai_response:
            try:
                async with AsyncSessionLocal() as db:
                    new_ai_msg = Message(
                        id=ai_msg_id,
                        conversation_id=thread_id,
                        role="ai",
                        content=full_ai_response,
                        user_id=user_id
                    )
                    db.add(new_ai_msg)
                    await db.commit()
                print("Response saved to database")
            except Exception as e:
                print(f"Failed to save AI message: {e}")


@app.post("/chat")
async def chat(payload: dict, background_tasks: BackgroundTasks):
    message = payload.get("message", "")
    thread_id = payload.get('thread_id', "default_thread")
    human_msg_id = payload.get('human_msg_id')
    ai_msg_id = payload.get('ai_msg_id')
    user_id = payload.get("user_id", "")

    active_files = payload.get("active_files")

    if not thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required")

    background_tasks.add_task(trigger_async_memory_update, message, user_id)
    compiled_memory = await fetch_compiled_user_context(user_id)
    return StreamingResponse(stream_response(message, thread_id, human_msg_id, ai_msg_id, user_id, compiled_memory, active_files), media_type="text/plain")


class ConversationPayload(BaseModel):
    id: str
    title: str
    user_id: str


@app.post('/conversation')  # for inserting a conversation
async def upsert_conversation(payload: ConversationPayload):
    try:
        async with AsyncSessionLocal() as db:
            stmt = insert(Conversation).values(
                id=payload.id,
                title=payload.title,
                user_id=payload.user_id
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['id'],
                set_={'title': stmt.excluded.title}
            )
            await db.execute(stmt)
            await db.commit()
        return {'status': 'success', 'id': payload.id}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to upsert conversation: {str(e)}")


@app.get('/conversations')
async def get_conversations(user_id: str):
    """Fetch all conversation threads for the user"""
    try:
        async with AsyncSessionLocal() as db:
            query = (
                select(Conversation).where(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
            )
            result = await db.execute(query)
            conversations = result.scalars().all()

            return [
                {
                    "id": str(c.id),
                    "title": c.title,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None
                } for c in conversations
            ]
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/messages')
async def get_messages(conversation_id: str, user_id: str):
    """Fetch all messages for a conversation_id"""
    try:
        conv_uuid = uuid.UUID(conversation_id)

        async with AsyncSessionLocal() as db:
            query = (
                select(Message)
                .where(Message.user_id == user_id, Message.conversation_id == conv_uuid)
                .order_by(Message.created_at.asc())
            )

            result = await db.execute(query)
            messages = result.scalars().all()

            return [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content
                } for m in messages
            ]
    except ValueError:
        return []
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversation/{thread_id}/topologies")
async def get_thread_topologies(thread_id: str):
    stmt = text("""
        SELECT source_file, raw_topology
        FROM document_chunks
        WHERE conversation_id = :tid
        AND raw_topology IS NOT NULL
    """)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            stmt,
            {"tid": thread_id}
        )

        rows = result.mappings().all()

    return {
        "topologies": {
            row["source_file"]: row["raw_topology"]
            for row in rows
        }
    }
