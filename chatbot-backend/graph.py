from langgraph.graph.message import add_messages
import uuid
# from langgraph.graph import MessagesState
from typing import TypedDict, Annotated, List, Optional, Literal
from langchain_core.messages import BaseMessage, AIMessage, RemoveMessage, ToolMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.graph import START, END, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode, tools_condition, InjectedState
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from sqlalchemy import text
from database import AsyncSessionLocal
import os
import time
import requests
from psycopg_pool import AsyncConnectionPool
import datetime
import json
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt, Command
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
import regex as re
from langsmith import traceable
from flashrank import Ranker, RerankRequest
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
ranker = Ranker()


load_dotenv()
# main model
llm = ChatOpenAI(
    base_url=os.environ["BASE_URL"],
    model=os.environ["CHAT_MODEL"],
    api_key=os.environ["OPENAI_API_KEY"],
    streaming=True
)
# embedding model
embedding_model = HuggingFaceEmbeddings(
    model=os.environ["EMBEDDING_MODEL"]
)

# fast memory model
memory_llm = ChatOpenAI(
    base_url=os.environ["BASE_URL"],
    model=os.environ["CHAT_MODEL"],
    api_key=os.environ["OPENAI_API_KEY"],
    streaming=True
)


# DB connection
RAW_DB_URI = os.environ.get("DATABASE_URL")
DB_URI = RAW_DB_URI.replace("+asyncpg", "")


pool = AsyncConnectionPool(
    conninfo=DB_URI,
    max_size=4,
    kwargs={'autocommit': True},
    open=False
)

db = SQLDatabase.from_uri(DB_URI)
toolkit = SQLDatabaseToolkit(
    db=db,
    llm=llm,
)

sql_tools = toolkit.get_tools()
# print(sql_tools)
# 2. Initializing checkpointer
# checkpointer = AsyncPostgresSaver(pool)


# chat state/Main
class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    summary: str  # Keep track of summary
    retrieval_count: int


# tools
search_tool = DuckDuckGoSearchRun()


@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}
        return {"first_num": first_num, "second_num": second_num, "operation": operation, "result": result}
    except Exception as e:
        return {"error": str(e)}


@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA')
    using Alpha Vantage with API key in the URL.
    """
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&api_key=FVN10EZ97DI2KJPI"
    r = requests.get(url)
    return r.json()


@tool
def get_today_Date() -> dict:
    """
    This method will provide you today's date according to the system date
    """
    return {"date_of_today": datetime.date.today()}


@tool
def get_current_time() -> dict:
    """
    This method will provide you the current time according to the system time (IST format)"
    """
    return {"current_time": time.ctime()}


@tool
async def retrieve_docs(query: str, state: Annotated[ChatState, InjectedState], config: RunnableConfig):
    """
    Search the user's uploaded documents for context to answer their question.
    Use this tool whenever the user asks about files, manuals, or uploaded data.

    Args:
        query: The specific search string or keywords extracted from user's request to search inside files.
    """
    current_count = state.get("retrieval_count", 0) + 1

    if current_count >= 4:
        return (
            "System Notice: You have already checked the internal documents twice for this specific question. "
            "No further matching context was found in the database. Do NOT call 'retrieve_docs' again. "
            "You may now use the DuckDuckGo search tool to find external information on the web to answer the user, "
            "or conclude your answer using your existing knowledge."
        )
    configurable = config.get('configurable', {})
    thread_id = configurable.get('thread_id')
    user_id = configurable.get('user_id', "")
    active_files = configurable.get("active_files", [])
    if not thread_id:
        return "System Error: No active thread ID found."

    # embed user query
    query_vector = await embedding_model.aembed_query(query)
    all_candidates = []
    print(query)
    try:
        stmt = text("""
            select id, content, source_file, page_number, similarity, raw_topology
            from match_documents(CAST(:emb AS vector), :uid, :tid, :limit, CAST(:files AS text[]))
        """)
        if active_files:
            async with AsyncSessionLocal() as db:
                active_response = await db.execute(stmt, {
                    "emb": str(query_vector),
                    "uid": user_id,
                    "tid": thread_id,
                    "limit": 15,
                    "files": active_files
                })

                all_candidates.extend(active_response.mappings().all())
        print("Searching general context")

        async with AsyncSessionLocal() as db:
            general_response = await db.execute(stmt, {
                "emb": str(query_vector),
                "uid": user_id,
                "tid": thread_id,
                "limit": 10,
                "files": None
            })

            existing_ids = {chunk['id'] for chunk in all_candidates}
            for chunk in general_response.mappings().all():
                if chunk['id'] not in existing_ids:
                    all_candidates.append(chunk)

        if not all_candidates:
            return "No relevant context found"

        # rerank
        passages = []
        for chunk in all_candidates:
            passages.append({
                "id": chunk.get("id"),
                "text": chunk.get("content", ""),
                'meta': {
                    "source_file": chunk.get("source_file"),
                    "page_number": chunk.get('page_number'),
                    "raw_topology": chunk.get("raw_topology")
                }
            })

        rereank_request = RerankRequest(query=query, passages=passages)
        rerank_results = ranker.rerank(rereank_request)

        top_n_results = rerank_results[:5]
        formatted_results = []
        extracted_topology_map = None
        extracted_source_file = None
        for result in top_n_results:
            meta = result.get("meta", {})
            source = meta.get("source_file", "Unknown Source")
            page = f" (Page {meta.get('page_number')})" if meta.get(
                "page_number") else ""
            content = result.get("text", "")
            score = result.get("score", 0.0)

            if meta.get("raw_topology") and not extracted_topology_map:
                extracted_topology_map = meta.get("raw_topology")
                extracted_source_file = meta.get("source_file")
                
            formatted_results.append(
                f"--- Context Source: {source}{page} [Relevance Score: {score:.3f}] ---\n{content}")
            # print(formatted_results)


        shared_container = configurable.get("_shared_payload_container")
        if shared_container is not None and extracted_topology_map:
            shared_container["topology"] = extracted_topology_map
            shared_container["source_file"] = extracted_source_file

        
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Database search failed: {str(e)}"


class HighlighTarget(BaseModel):
    entity_name: str = Field(
        description="The exact case-sensetive name of the Table or Entity node from the raw_topology map (e.,g., 'EMPLOYEE')"
    )
    attribute_name: Optional[str] = Field(
        default=None,
        description="If the user's question focuses on a specific column/field, provide its exact name here (e.g., 'Ssn). Leave as None if highlighting the entire table."
    )
    status: Literal["highlight", "error", "dim"] = Field(
        description="The visual UI state: 'error' for dropped/failing/missing items, 'highlight' for selected/queried active fields, and 'dim' to mute background noise."
    )

class EdgeHighlight(BaseModel):
    source: str
    target: str
    status: Literal["highlight","error","dim"]
    
class VisualDirectives(BaseModel):
    actions: List[HighlighTarget] = Field(
        description="A list of specific tables or table columns that must be styled dynamically on the UI canvas."
    )
    edges: List[EdgeHighlight] = Field(description="A list of edges that will be styled dynamically on the UI")
    reason: str = Field(
        description="A concise technical summary explaining why these specific graph elements are being highlighted."
    )


@tool(args_schema=VisualDirectives)
async def highlight_components(actions: List[HighlighTarget], edges: List[EdgeHighlight], reason: str, config: RunnableConfig) -> str:
    """
    Call this tool IMMEDIATELY whenever the user asks to visualize an action path,
    analyze what happens if an entity/attribute fails/is missing, or trace a connection
    within a technical database schema or circuit diagram.
    This tool triggers the frontend canvas to dynamically color, pulse, or dim targets.
    """

    serialized_actions = [action.model_dump() for action in actions]
    serialized_edges = [
        edge.model_dump()
        for edge in edges
    ]


    configurable = config.get('configurable', {})
    shared_container = configurable.get("_shared_payload_container")
    if shared_container is not None:
        shared_container["actions"] = serialized_actions
        shared_container['edges'] = serialized_edges

    return f"Visual canvas action tracking updated successfully for path: {reason}"

tools=[get_stock_price, search_tool,
         calculator, get_today_Date, retrieve_docs, get_current_time, highlight_components, *sql_tools]
# bind
# llm_with_tools = llm.bind_tools(tools)


class ExtractedTrait(BaseModel):
    key: str=Field(
        description="The category of information (e.g., 'tech_stack', 'location', 'academic_status, 'interest'). lowercase only with underscores.")
    value: str=Field(
        description="The explicit factual statement to remember. Be concise. Example: 'Pursuing B.Tech in Computer Science Engineering'")


class LongTermMemorySchema(BaseModel):
    has_enduring_facts: bool=Field(
        description="True if the user revealed core permanent facts, skills, tech preferences, or background attributes about themselves.")
    extracted_traits: list[ExtractedTrait]=Field(
        default=[], description="List of structured traits extracted from the input message.")


# long term memory prompt
memory_prompt=ChatPromptTemplate.from_messages([
    ('system', (
        "You are an invisible background cognitive analyzer for a personal assistant platform.\n"
        "Analyze the provided message text and pull out ONLY long-term, enduring traits, personal preferences, "
        "academic background, location details, or distinct professional focus points.\n\n"
        "CRITICAL CRITERIA:\n"
        "- Do NOT save temporary conversational chatter, casual statements, or task-specific questions.\n"
        "- Do NOT duplicate information if it seems broad.\n"
        "- If the user says 'I am a CS student' or 'I prefer building apps with React Native', track it immediately.\n\n"
        "{format_instructions}"
    )),
    ("user", "User Message: {user_msg}")
])
memory_parser=PydanticOutputParser(pydantic_object=LongTermMemorySchema)
# Extract user memory for LTM


async def trigger_async_memory_update(user_msg: str, user_id: str):
    """
    Fire-and-forget background task to parse user inputs for permanent facts.
    """
    try:
        chain=memory_prompt | memory_llm | memory_parser
        result=await chain.ainvoke({
            'format_instructions': memory_parser.get_format_instructions(),
            'user_msg': user_msg
        })
        print(result)
        if result and result.has_enduring_facts:
            query=text("""
                INSERT INTO user_memories (id, user_id, memory_key, memory_value, updated_at)
                VALUES (:id, :uid, :key, :val, NOW())
                ON CONFLICT (user_id, memory_key)
                DO UPDATE SET
                    memory_value = EXCLUDED.memory_value,
                    updated_at = NOW();
            """)

            async with AsyncSessionLocal() as db:
                for trait in result.extracted_traits:
                    await db.execute(query, {
                        "id": str(uuid.uuid4()),
                        "uid": user_id,
                        "key": trait.key,
                        "val": trait.value
                    })

                    await db.commit()
    except Exception as e:
        print(f"Background memory ingestion trace error: {str(e)}")

# long term memory loader


@traceable
async def fetch_compiled_user_context(user_id: str) -> str:
    try:
        query=text("""
            select memory_key, memory_value from user_memories where user_id = :uid
        """)
        async with AsyncSessionLocal() as db:
            result=await db.execute(query, {"uid": user_id})
            rows=result.mappings().all()  # returns list
        if not rows:
            return "No prior personal profile background attributes recorded for this user yet."

        compiled_traits=[]
        for row in rows:
            compiled_traits.append(
                f"- {row['memory_key'].replace('_', ' ').title()}: {row['memory_value']}")

        return "KNOWN USER BACKGROUND CONTEXT:\n" + "\n".join(compiled_traits)
    except Exception:
        return "Profile system context currently unreachable."


# main llm prompt
prompt=ChatPromptTemplate.from_messages([
    ("system", """You are a highly reliable, truthful, and personalized engineering and technical AI assistant.

    {user_context}

    {summary_context}

    PERSONALIZATION & BEHAVIOR RULES:
    - Address the user naturally using the 'KNOWN USER BACKGROUND CONTEXT' provided above.
    - If the user asks for code, architecture, or solutions, automatically tailor your examples to their preferred technology stack listed in their context unless instructed otherwise.
    - Never say "Based on your memory" or "According to my data." Behave seamlessly as an assistant who inherently remembers them.
    - Do NOT use emojis, icons, or special symbols (such as 🔌 🧠 🎯 ⚙️ ...) while giving response

    VISUAL & STRUCTURAL REASONING:
    - When 'retrieve_docs' returns context marked with `[FILE_TYPE: IMAGE_TOPOLOGY]`, you are interacting with a verified technical schematic or ERD.
    - Treat everything under 'IDENTIFIED COMPONENTS/NODES' and 'EXPLICIT CONNECTIONS/EDGES' as mathematically certain facts.
    - MULTI-HOP PATH TRACING RULES:
      * For Circuits: If asked what is affected by a component failure, systematically follow the edge outputs. Follow `Source ===(relationship)===> Target`. If A connects to B, and B connects to C, a failure at A affects B and C sequentially.
      * For ER Diagrams: When generating SQL queries based on the diagram, explicitly trace primary keys to foreign keys using the 'Metadata' blocks provided in the nodes. Do not guess table columns.
    - If a user asks about a connection path that cannot be found by tracing the explicit edges list step-by-step, you MUST state: "According to the graph structure, no physical or logical connection is mapped between component X and component Y."

    CRITICAL DYNAMIC VISUALIZATION RULES:
    - You are connected to an interactive frontend canvas. Whenever a user asks questions about schema or circuit behaviors (e.g., "What if column X is missing?", "Trace how Employee connects to Department", or "What happens if this component fails?"), you MUST execute the `highlight_components` tool.
    - Cross-reference the query with the data returned via `retrieve_docs`:
      * Map status to 'error' (turns element red/pulses) for fields or entities that are missing, dropping, breaking, or failing.
      * Map status to 'highlight' (turns element green) for components actively involved in data lookups, joins, columns under discussion, or selections.
      * Map status to 'dim' (fades element out) for completely irrelevant peripheral tables to decrease layout noise.
    - You must call `highlight_components` BEFORE writing your final textual answer so that the frontend canvas layout updates instantly for the user.

    TOOL ROUTING & USAGE:
    - You have access to a suite of specialized tools. Analyze the user's request and autonomously invoke the necessary tool(s).
    - HIERARCHY OF TRUTH: Always prioritize information from 'retrieve_docs' (internal documents/images) over web searches. Only use the DuckDuckGo web search if the internal documents lack the necessary information.
    - CITATION RULES:
      * For PDF/Text chunks, append: '[filename.pdf, pg. X]'
      * For Image Topology chunks, append: '[filename.jpg]'
      * For DuckDuckGo searches, explicitly state: "According to the internet..."
    - If a tool returns a 'System Notice', obey its instructions immediately.

    GENERAL RULES:
    - Never hallucinate. If unsure, say "I don't know."
    - Be concise and structured.
    """),
    MessagesPlaceholder(variable_name="messages")
])


def build_graph(mcp_tools: List=None):
    if mcp_tools is None:
        mcp_tools=[]

    all_tools=tools + mcp_tools

    llm_with_tools=llm.bind_tools(all_tools)

    async def chat_node(state: ChatState, config: RunnableConfig):
        # user_id = config.get("configurable", {}).get("user_id", "") # get user_id for LTM
        summary=state.get("summary", "")
        summary_context=f"\n\nContext of older past conversations:\n{summary}" if summary else ""
        user_context=config.get("configurable", {}).get('user_context')

        chain=prompt.partial(summary_context=summary_context,
                               user_context=user_context) | llm_with_tools
        response=await chain.ainvoke(state)
        return {'messages': [response]}

    async def summarize_history_node(state: ChatState):
        messages=state.get('messages')
        existing_summary=state.get('summary')

        if len(messages) > 30:
            # summarize last frequently used
            messages_to_summarize=messages[:-4]

            summary_prompt=(
                f"Current summary of earlier conversation:\n{existing_summary}\n\nExtend the summary above by distilling the following chat messages into it:\n"
            )

            for msg in messages_to_summarize:
                summary_prompt += f"{'AI' if isinstance(msg, AIMessage) else 'Human'}:{msg.content}"

            # calling a fast model to update summary
            new_summary_response=await llm.ainvoke(summary_prompt)
            new_summary=new_summary_response.content
            delete_messages_instruction=[RemoveMessage(
                id=msg.id) for msg in messages_to_summarize]
            return {
                'summary': new_summary,
                'messages': delete_messages_instruction
            }

        return {}

    async def route_chat(state: ChatState):
        # If the LLM wants to run a tool
        if state['messages'][-1].tool_calls:
            return "tools"
        return "summarize"

    graph=StateGraph(ChatState)
    # executes tool node (already asynchronous inside)
    tool_node=ToolNode(all_tools)

    # add nodes
    graph.add_node('chat_node', chat_node)
    graph.add_node('tools', tool_node)
    graph.add_node('summarize', summarize_history_node)

    # add edges
    graph.add_edge(START, 'chat_node')
    graph.add_conditional_edges("chat_node", route_chat)  # tools_condition
    graph.add_edge("tools", "chat_node")
    graph.add_edge('summarize', END)
    return graph
# chatbot = graph.compile(checkpointer=checkpointer)
