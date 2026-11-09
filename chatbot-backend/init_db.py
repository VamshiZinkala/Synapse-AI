import asyncio
from sqlalchemy import text
from database import engine, Base
from models import Conversation, DocumentChunk, Message, UserMemory

# The raw SQL to create our custom vector search function
MATCH_DOCS_SQL = """
DROP FUNCTION IF EXISTS match_documents(vector, text, text, int, text[]);

CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(1024),
    target_user_id text,
    target_thread_id text,
    match_limit int,
    active_files text[] DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    content text,
    source_file text,
    page_number int,
    similarity float,
    raw_topology jsonb
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        dc.id, 
        dc.content, 
        dc.source_file, 
        dc.page_number,
        1 - (dc.embedding <=> query_embedding) AS similarity,
        dc.raw_topology
    FROM document_chunks dc
    WHERE dc.user_id = target_user_id
      AND dc.conversation_id::text = target_thread_id
      AND (active_files IS NULL OR array_length(active_files, 1) IS NULL OR dc.source_file = ANY(active_files))
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$;
"""

async def create_tables():
    print("Connecting to database to build tables...")
    async with engine.begin() as conn:
        print("Enabling pgvector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        
        # print("Creating schema...")
        await conn.run_sync(Base.metadata.create_all)
        
        # ---> ADDED: Create the custom function <---
        print("Creating vector search function...")
        await conn.execute(text(MATCH_DOCS_SQL))
        
    print("All database tables and functions created successfully!")

if __name__ == "__main__":
    import selectors
    asyncio.run(create_tables(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))