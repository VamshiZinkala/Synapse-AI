# Synapse AI

**Synapse AI** is an advanced, multimodal Agentic AI platform designed for technical diagram comprehension, document intelligence (RAG), dynamic schema visualization, and autonomous task execution. Powered by **LangGraph**, **FastAPI**, **Next.js 16**, **PostgreSQL with pgvector**, and the **Model Context Protocol (MCP)**, Synapse AI bridges the gap between conversational assistance, deep schematic analysis, and interactive real-time visual canvases.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Project Folder Structure](#project-folder-structure)
- [Database Design](#database-design)
  - [Entity-Relationship Diagram](#entity-relationship-diagram)
  - [Database Tables & Schemas](#database-tables--schemas)
  - [Custom Vector Search Function](#custom-vector-search-function)
- [API Documentation](#api-documentation)
  - [FastAPI Backend Endpoints](#fastapi-backend-endpoints)
  - [Streaming Protocol Specification](#streaming-protocol-specification)
  - [Next.js Route Handlers](#nextjs-route-handlers)
- [Agent & Tooling Architecture](#agent--tooling-architecture)
  - [LangGraph State Machine](#langgraph-state-machine)
  - [Integrated Tools](#integrated-tools)
  - [Model Context Protocol (MCP)](#model-context-protocol-mcp)
- [Environment Variables](#environment-variables)
- [Installation and Setup](#installation-and-setup)
  - [Prerequisites](#prerequisites)
  - [1. Database Configuration](#1-database-configuration)
  - [2. Backend Setup](#2-backend-setup)
  - [3. MCP Server Setup](#3-mcp-server-setup)
  - [4. Frontend Setup](#4-frontend-setup)
- [Running the Project](#running-the-project)
- [Future Enhancements](#future-enhancements)

---

## Project Overview

Modern technical documentation rarely consists of raw prose alone; it is dense with database entity-relationship diagrams (ERDs), system architectures, circuit schematics, tables, and domain-specific records. Standard RAG pipelines discard or mangle this structural topology.

**Synapse AI** solves this problem by providing:
1. **Multimodal Topological Ingestion**: Extracts text and embedded schematic drawings from documents (PDF, DOCX, CSV, XLSX, Markdown, Images).
2. **Visual Decomposition**: Translates technical schematics into structured graphs (nodes, edges, attributes, constraints, primary/foreign keys) using Vision Language Models (VLMs).
3. **Interactive Visual Canvas**: Dynamically renders and manipulates interactive diagrams on the frontend via React Flow (`@xyflow/react`) as the AI reasons through connections, paths, dependencies, or points of failure.
4. **Contextual Retrieval & Neural Reranking**: Uses pgvector HNSW indexing combined with FlashRank reranking for maximum precision.
5. **Persistent Cognitive Memory**: Asynchronously parses user conversations to extract and maintain persistent user profiles and preferences across chat threads.
6. **Extensible Tooling with MCP**: Integrates external capabilities seamlessly via Model Context Protocol servers (e.g., automated expense management).

---

## Key Features

- **Agentic Multi-Turn Graph (LangGraph)**:
  - Cyclic state graph with autonomous tool execution.
  - State checkpointing backed by PostgreSQL (`AsyncPostgresSaver`).
  - Automated history distillation and token pruning when conversations exceed 30 turns.
- **Multimodal Diagram & Document Ingestion**:
  - Ingests `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.xlsx`, and images (`.png`, `.jpg`, `.jpeg`).
  - Uses `pymupdf` and `pymupdf4llm` to extract both text blocks and embedded image diagrams from PDF pages.
  - VLM-driven topology parser (`qwen-3.6-27b`) that extracts structured node-edge-attribute relationships from ERDs and circuits.
- **Dynamic Interactive Canvas**:
  - Resizable side-panel canvas built with React Flow (`@xyflow/react`).
  - Directly controllable by the agent via `highlight_components`: turns active path nodes green (`highlight`), highlights schema drop/failure cascades in red (`error`), and dims background noise (`dim`).
- **Hybrid RAG & Neural Reranking**:
  - 1024-dimensional vector embeddings with HNSW cosine distance index in PostgreSQL (`pgvector`).
  - Two-stage retrieval: pgvector candidate retrieval via custom `match_documents` plpgsql function, followed by `FlashRank` neural reranking (top 5 results).
  - Target-file scoping to restrict document lookups to specific active files.
- **Cognitive Long-Term Memory (LTM)**:
  - Background asynchronous task parses conversational inputs to detect permanent user traits (engineering stack, background, location, preferences).
  - Upserts into `user_memories` table on conflict.
  - Seamlessly injects user background into system prompts without repetitive declarations.
- **Model Context Protocol (FastMCP)**:
  - Integrates `MultiServerMCPClient` over standard I/O (stdio).
  - Ships with an asynchronous expense management MCP server (`expense-mcp-server`) with JSON category validation.
- **Custom Real-Time Wire Protocol**:
  - Chunked text streaming incorporating inline delimiters for tool lifecycle announcements (`__TOOL_START__...__TOOL_END__`) and dynamic graph updates (`__GRAPH_METADATA_START__...__GRAPH_METADATA_END__`).

---

## Technology Stack

### Frontend
| Technology | Version | Purpose |
| :--- | :--- | :--- |
| **Next.js** | `16.2.7` | React framework with App Router |
| **React** | `19.2.4` | Component UI library |
| **React Flow / @xyflow/react** | `11.11.4` / `12.11.1` | Interactive graph & schema canvas |
| **Tailwind CSS** | `^4.0.0` | Utility-first responsive styling |
| **React Markdown & Remark GFM** | `^10.1.0` / `^4.0.1` | Markdown rendering with GitHub flavor |
| **React Syntax Highlighter** | `^16.1.1` | Prism code block syntax highlighting |
| **Lucide React & React Icons** | `^1.22.0` / `^5.6.0` | Application iconography |
| **Supabase JS** | `^2.107.0` | Supabase client integration |

### Backend
| Technology | Purpose |
| :--- | :--- |
| **Python** (3.11+ / 3.13) | Backend runtime environment |
| **FastAPI** | High-performance asynchronous web framework |
| **Uvicorn** | ASGI server |
| **LangGraph** | Stateful agentic orchestration & checkpointing |
| **LangChain Core & Community** | Prompt templating, tool management, and SQL toolkit |
| **FlashRank** | Ultra-fast neural reranking engine |
| **PyMuPDF & PyMuPDF4LLM** | PDF text extraction and embedded image scraping |
| **python-docx & pandas & openpyxl**| Document parsing (Word, CSV, Excel) |
| **Pillow (PIL)** | Image decoding and buffer processing |
| **DuckDuckGo Search** | Live web search fallback |

### Database & Vector Engine
| Technology | Purpose |
| :--- | :--- |
| **PostgreSQL** | Primary relational datastore |
| **pgvector** | Vector similarity search with HNSW cosine distance indexing |
| **SQLAlchemy 2.0 (Async)** | Async ORM database engine |
| **asyncpg** | High-performance asynchronous PostgreSQL driver |
| **psycopg & psycopg-pool** | Connection pooling for LangGraph checkpoint persistence |

### MCP Server (Expense Tracker)
| Technology | Purpose |
| :--- | :--- |
| **FastMCP** (`>=3.4.2`) | Model Context Protocol implementation |
| **uv** | Python package and virtual environment manager |
| **SQLAlchemy / asyncpg** | Asynchronous ORM connection to PostgreSQL |

---

## System Architecture

```mermaid
flowchart TB
    subgraph Client ["Frontend (Next.js 16 + React 19)"]
        UI["Chat Interface (/chat)"]
        Canvas["Interactive Schema Canvas (@xyflow/react)"]
        Uploader["Document & Image Uploader"]
        StreamParser["Wire Protocol Stream Parser"]
    end

    subgraph API ["Backend API (FastAPI)"]
        ChatRouter["POST /chat"]
        UploadRouter["POST /upload/uploadfile & /upload/uploadimage"]
        ConvRouter["GET /conversations & GET /messages"]
        TopologyRouter["GET /conversation/{id}/topologies"]
    end

    subgraph LangGraph ["LangGraph Execution Engine"]
        ChatNode["chat_node (DeepSeek-V4-Flash)"]
        ToolNode["tools (ToolNode)"]
        SummarizeNode["summarize_history_node"]
        Checkpointer["AsyncPostgresSaver"]
    end

    subgraph Tools ["Agent Tool Suite"]
        Retriever["retrieve_docs (pgvector + FlashRank)"]
        Visualizer["highlight_components"]
        Calculator["calculator"]
        StockTool["get_stock_price (Alpha Vantage)"]
        WebSearch["DuckDuckGoSearchRun"]
        SQLToolkit["SQLDatabaseToolkit"]
        MCPAdapter["MultiServerMCPClient"]
    end

    subgraph MCPServer ["MCP Server (stdio)"]
        ExpenseServer["expense-mcp-server (FastMCP)"]
        CatJSON[("categories.json")]
    end

    subgraph Storage ["PostgreSQL Datastore + pgvector"]
        T_Conv[("conversations")]
        T_Msg[("messages")]
        T_Chunks[("document_chunks (pgvector 1024)")]
        T_Mem[("user_memories")]
        T_Exp[("expenses")]
        T_Checkpoints[("checkpoints & writes")]
    end

    subgraph VisionPipeline ["Multimodal VLM Pipeline"]
        PyMuPDF["PyMuPDF Image Extractor"]
        VLM["Vision LLM (Qwen-3.6-27B)"]
    end

    %% Interactions
    UI -->|"Message Stream Request"| ChatRouter
    Uploader -->|"Multipart File Upload"| UploadRouter
    ChatRouter -->|"Run Graph Stream"| ChatNode

    UploadRouter --> PyMuPDF
    PyMuPDF --> VLM
    VLM -->|"Topology Nodes & Edges"| T_Chunks

    ChatNode -->|"Conditional Routing"| ToolNode
    ChatNode -->|"Message Count > 30"| SummarizeNode
    ToolNode --> Retriever
    ToolNode --> Visualizer
    ToolNode --> Calculator
    ToolNode --> StockTool
    ToolNode --> WebSearch
    ToolNode --> SQLToolkit
    ToolNode --> MCPAdapter

    MCPAdapter <-->|"stdio JSON-RPC"| ExpenseServer
    ExpenseServer --> CatJSON
    ExpenseServer --> T_Exp

    Retriever -->|"Cosine Vector Match"| T_Chunks
    Retriever -->|"Neural Reranking"| ChatNode

    ChatRouter -->|"Streaming Response"| StreamParser
    StreamParser -->|"Markdown Tokens"| UI
    StreamParser -->|"Tool Status Events"| UI
    StreamParser -->|"Dynamic Graph Payload"| Canvas

    ChatNode -.->|"State Persistence"| Checkpointer
    Checkpointer --> T_Checkpoints
    ChatRouter -->|"Store Human & AI Msgs"| T_Msg
    ChatRouter -.->|"Async Background Task"| T_Mem
```

### Complete Workflow Walkthrough

1. **Document Upload**:
   - The user drops a document (`.pdf`, `.txt`, `.docx`, etc.) or image into the chat interface.
   - For PDFs, `pymupdf4llm` extracts markdown page-by-page while extracting embedded raster diagrams.
   - For images or diagrams, a Vision Language Model (`qwen-3.6-27b`) extracts an `ImageTopology` schema containing nodes (entities, attributes, types, PK/FK flags) and edges (relations, cardinalities).
   - Chunks and topologies are embedded with `qwen3-embedding-0.6b` (1024 dimensions) and stored in `document_chunks`.
2. **User Query & Context Assembly**:
   - The user submits a question.
   - The backend retrieves enduring profile facts from `user_memories` and formats them into system prompts.
   - In parallel, an asynchronous background task (`trigger_async_memory_update`) extracts newly disclosed user attributes from the input.
3. **LangGraph Processing & Retrieval**:
   - `chat_node` determines whether internal documents, web information, or tools are needed.
   - If documents are required, `retrieve_docs` queries PostgreSQL via `match_documents` and reranks candidates with `FlashRank`.
   - If technical diagrams exist in the context, topology metadata is extracted into a shared payload container.
4. **Dynamic Visual Steering**:
   - When questions touch on schema paths, table relationships, or component failures, the agent invokes `highlight_components`.
   - The tool sets visual flags (`highlight`, `error`, `dim`) for individual tables, columns, or edges.
5. **Streaming & Client-Side Rendering**:
   - The backend streams text tokens, tool execution indicators (`__TOOL_START__`), and topology updates (`__GRAPH_METADATA_START__`).
   - The Next.js client renders tool execution accordions, markdown responses, and activates the resizable React Flow canvas side-by-side.

---

## Project Folder Structure

```
Synapse-AI/
├── .gitignore
├── LICENSE
├── chatbot/                        # Next.js 16 Frontend Application
│   ├── app/
│   │   ├── api/
│   │   │   └── chat/
│   │   │       └── route.js       # Next.js API proxy route to backend /chat
│   │   ├── chat/
│   │   │   └── page.tsx           # Primary chat & canvas interface
│   │   ├── favicon.ico
│   │   ├── globals.css            # Tailwind CSS 4 root styles
│   │   ├── layout.tsx             # Root layout with Geist font configuration
│   │   └── page.tsx               # Index route placeholder
│   ├── components/
│   │   ├── AILoader.tsx           # AI thinking skeleton indicator
│   │   ├── ChatMessages.tsx       # Message list with Markdown & code highlighting
│   │   ├── CodeLoader.tsx         # Code syntax block skeleton loader
│   │   ├── DocumentUploader.tsx   # Drag-and-drop file upload button & modal
│   │   ├── Header.tsx             # Chat header and sidebar toggle
│   │   ├── InteractiveSchemaCanvas.tsx # React Flow dynamic node/edge canvas
│   │   ├── MessageComponent.tsx   # Human message bubble component
│   │   ├── MessageLoader.tsx      # Skeleton loader for messages
│   │   ├── Sidebar.tsx            # Conversation thread sidebar
│   │   ├── sidebarLoader.tsx      # Skeleton loader for conversation items
│   │   └── ToolComponent.tsx      # Expandable tool execution status accordion
│   ├── hooks/
│   │   └── useConversations.tsx   # Custom React hook for thread & message state
│   ├── public/                    # Static assets & SVG icons
│   ├── services/
│   │   └── supabase.ts            # Supabase JS client configuration
│   ├── AGENTS.md                  # Next.js 16 guidance notes
│   ├── CLAUDE.md
│   ├── eslint.config.mjs          # ESLint configuration
│   ├── next.config.ts             # Next.js framework configuration
│   ├── package.json               # Frontend dependencies & scripts
│   ├── postcss.config.mjs         # PostCSS configuration for Tailwind v4
│   └── tsconfig.json              # TypeScript compiler configuration
├── chatbot-backend/               # FastAPI Backend & Agent Core
│   ├── database.py                # Async SQLAlchemy engine & session factory
│   ├── graph.py                   # LangGraph definition, tool bindings & memory
│   ├── init_db.py                 # DB schema initialization & vector SQL function
│   ├── main.py                    # FastAPI application, streaming & chat router
│   ├── mcp_manager.py             # MultiServerMCPClient manager for stdio servers
│   ├── models.py                  # SQLAlchemy ORM models (Conversation, Chunk, etc.)
│   └── upload.py                  # Document & image parsing, VLM extraction & embedding
└── expense-mcp-server/            # Model Context Protocol (MCP) Server
    ├── categories.json            # 20 standard expense categories & subcategories
    ├── main.py                    # FastMCP tool declarations (add, list, summarize)
    ├── pyproject.toml             # uv / PEP 621 package metadata
    └── uv.lock                    # Locked dependency manifest
```

---

## Database Design

### Entity-Relationship Diagram

```mermaid
erDiagram
    conversations ||--o{ messages : "contains"
    conversations ||--o{ document_chunks : "has context"
    user_memories }o--|| conversations : "scoped to user"

    conversations {
        uuid id PK
        text title
        timestamptz created_at
        timestamptz updated_at
        text user_id
    }

    messages {
        uuid id PK
        uuid conversation_id FK
        text role
        text content
        text user_id
        timestamptz created_at
    }

    document_chunks {
        uuid id PK
        uuid conversation_id FK
        text content
        vector_1024 embedding
        int page_number
        text source_file
        text user_id
        jsonb raw_topology
        timestamptz created_at
    }

    user_memories {
        uuid id PK
        text user_id
        text memory_key
        text memory_value
        timestamptz updated_at
    }

    expenses {
        int id PK
        text user_id
        timestamp date
        float amount
        text category
        text subcategory
        text note
    }
```

### Database Tables & Schemas

#### 1. `conversations`
Maintains conversational threads.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Thread identifier (default `uuid4`) |
| `title` | `TEXT` | `NOT NULL`, default `'New Chat'` | Thread title (auto-generated from first message) |
| `user_id` | `TEXT` | `NOT NULL`, default `'legacy_user'` | User identifier |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL`, default `now()` | Timestamp of thread creation |
| `updated_at` | `TIMESTAMPTZ`| `NOT NULL`, default `now()` | Last modification timestamp |
- **Indexes**: `idx_conversations_user_thread` on `(user_id, id)`.

#### 2. `messages`
Stores individual chat messages in a conversation.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Message unique identifier |
| `conversation_id` | `UUID` | `NOT NULL`, `FOREIGN KEY (conversations.id) ON DELETE CASCADE` | Associated thread |
| `role` | `VARCHAR` | `NOT NULL` | Message author: `'human'` or `'ai'` |
| `content` | `TEXT` | `NOT NULL` | Markdown or raw text content |
| `user_id` | `TEXT` | `NOT NULL`, default `'legacy_user'` | User identifier |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL`, default `now()` | Timestamp of message creation |
- **Indexes**: `idx_messages_user_thread` on `(user_id, conversation_id)`.

#### 3. `document_chunks`
Vector store table for embedded file chunks and diagram topologies.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Chunk identifier |
| `conversation_id` | `UUID` | `NOT NULL`, `FOREIGN KEY (conversations.id) ON DELETE CASCADE` | Scoped thread identifier |
| `content` | `TEXT` | `NOT NULL` | Chunk textual content or topology text |
| `embedding` | `vector(1024)`| `NULLABLE` | Vector representation (Qwen-3 embedding model) |
| `page_number` | `INTEGER` | `NULLABLE` | Document page origin (for PDFs) |
| `source_file` | `TEXT` | `NULLABLE` | Original uploaded filename |
| `user_id` | `TEXT` | `NOT NULL`, default `'legacy_user'` | User identifier |
| `raw_topology` | `JSONB` | `NULLABLE` | Structured nodes and edges extracted via VLM |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL`, default `now()` | Creation timestamp |
- **Indexes**:
  - `idx_document_chunks_lookup` on `(user_id, conversation_id)`.
  - `idx_document_chunks_user_vector` on `embedding` using HNSW index (`m=16`, `ef_construction=64`, cosine distance operator `vector_cosine_ops`).

#### 4. `user_memories`
Cognitive memory store tracking long-term user traits.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Memory entry identifier |
| `user_id` | `TEXT` | `NOT NULL` | Target user identifier |
| `memory_key` | `TEXT` | `NOT NULL` | Trait category (e.g. `tech_stack`, `academic_status`) |
| `memory_value` | `TEXT` | `NOT NULL` | Explicit factual statement |
| `updated_at` | `TIMESTAMPTZ`| `NOT NULL`, default `now()` | Last update timestamp |
- **Indexes**: Unique index `user_memories_user_id_memory_key` on `(user_id, memory_key)`.

#### 5. `expenses`
Financial tracker table managed directly by the MCP server and SQL tools.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY`, `AUTOINCREMENT` | Expense record identifier |
| `user_id` | `TEXT` | `NOT NULL`, default `'legacy_user'` | Owner user identifier |
| `date` | `TIMESTAMP` | `NOT NULL` | Expense date |
| `amount` | `FLOAT` | `NOT NULL` | Monetary value |
| `category` | `TEXT` | `NOT NULL` | Top-level category (e.g. `food`, `travel`) |
| `subcategory` | `TEXT` | default `''` | Subcategory identifier |
| `note` | `TEXT` | default `''` | Optional descriptive note |

#### 6. LangGraph Checkpointing Tables
Created automatically by `AsyncPostgresSaver.setup()`:
- `checkpoints`: Thread checkpoint state metadata.
- `checkpoint_blobs`: Serialized state data.
- `checkpoint_writes`: Intermediate step write operations.
- `checkpoint_migrations`: Schema version control.

### Custom Vector Search Function

Executed during `init_db.py` to support high-performance cosine similarity retrieval with optional file filtering:

```sql
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
    similarity float
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
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM document_chunks dc
    WHERE dc.user_id = target_user_id
      AND dc.conversation_id::text = target_thread_id
      AND (active_files IS NULL OR array_length(active_files, 1) IS NULL OR dc.source_file = ANY(active_files))
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$;
```

---

## API Documentation

### FastAPI Backend Endpoints

Base URL: `http://localhost:8000`

#### 1. Chat Generation (Streaming)
- **Endpoint**: `POST /chat`
- **Description**: Streams the agent's real-time reasoning, tool executions, and visual metadata.
- **Request Body** (`application/json`):
  ```json
  {
    "message": "Trace what happens if the Department table is dropped.",
    "thread_id": "c71a396b-4e12-4217-9c98-137a1f59efbc",
    "human_msg_id": "b6a7a72d-4530-4be6-a4c3-a3d54f67c5b6",
    "ai_msg_id": "84a32997-d86b-42fa-a429-0ec6179b3cb1",
    "user_id": "test_user_id",
    "active_files": ["company_schema.png"]
  }
  ```
- **Response**: `text/plain` chunked stream.

#### 2. Upsert Conversation
- **Endpoint**: `POST /conversation`
- **Description**: Creates or updates a thread title.
- **Request Body** (`application/json`):
  ```json
  {
    "id": "c71a396b-4e12-4217-9c98-137a1f59efbc",
    "title": "System Architecture Review",
    "user_id": "test_user_id"
  }
  ```
- **Response**: `{"status": "success", "id": "..."}`

#### 3. List Conversations
- **Endpoint**: `GET /conversations?user_id={user_id}`
- **Description**: Retrieves all conversation threads for a specific user, ordered by most recently updated.
- **Response**:
  ```json
  [
    {
      "id": "c71a396b-4e12-4217-9c98-137a1f59efbc",
      "title": "System Architecture Review",
      "updated_at": "2026-11-03T06:30:00+00:00"
    }
  ]
  ```

#### 4. List Thread Messages
- **Endpoint**: `GET /messages?conversation_id={id}&user_id={user_id}`
- **Description**: Fetches all persisted messages for a given thread, ordered chronologically.
- **Response**:
  ```json
  [
    {
      "id": "b6a7a72d-4530-4be6-a4c3-a3d54f67c5b6",
      "role": "human",
      "content": "What is the schema for our users table?"
    },
    {
      "id": "84a32997-d86b-42fa-a429-0ec6179b3cb1",
      "role": "ai",
      "content": "The users table contains..."
    }
  ]
  ```

#### 5. Retrieve Thread Topologies
- **Endpoint**: `GET /conversation/{thread_id}/topologies`
- **Description**: Returns all cached graph topologies extracted from uploaded documents within a thread.
- **Response**:
  ```json
  {
    "topologies": {
      "database_schema.png": {
        "nodes": [...],
        "edges": [...]
      }
    }
  }
  ```

#### 6. Upload Document
- **Endpoint**: `POST /upload/uploadfile`
- **Content-Type**: `multipart/form-data`
- **Form Fields**:
  - `file`: File binary (`.pdf`, `.txt`, `.md`, `.docx`, `.csv`, `.xlsx`)
  - `thread_id`: Target conversation UUID
  - `user_id`: Target user ID string
- **Response**: `{"status": "success", "chunks": 12}`

#### 7. Upload Image / Schematic
- **Endpoint**: `POST /upload/uploadimage`
- **Content-Type**: `multipart/form-data`
- **Form Fields**:
  - `file`: Image binary (`.png`, `.jpg`, `.jpeg`, `.webp`)
  - `thread_id`: Target conversation UUID
  - `user_id`: Target user ID string
- **Response**: `{"status": "success", "message": "Image processed and indexed successfully"}`

---

### Streaming Protocol Specification

The `POST /chat` stream delivers real-time textual and metadata frames using delimiter tags:

1. **Tool Invocation Blocks**:
   Emitted when a tool begins running and upon completion.
   ```
   __TOOL_START__{"tool_id": "call_123", "tool_name": "retrieve_docs", "content": "waiting for the tool_response", "status": "running"}__TOOL_END__
   __TOOL_START__{"tool_id": "call_123", "tool_name": "retrieve_docs", "content": "Found 3 matching chunks...", "status": "completed"}__TOOL_END__
   ```
2. **Text Tokens**:
   Raw markdown response tokens streamed directly to the chat window.
3. **Graph Metadata Frames**:
   Appended at the end of the stream when visual components are updated:
   ```
   __GRAPH_METADATA_START__
   {
     "source_file": "schema.png",
     "topology": {
       "nodes": [{"name": "EMPLOYEE", "attributes": [{"name": "Ssn", "data_type": "INT", "is_key": "PK"}]}],
       "edges": [{"source": "EMPLOYEE", "target": "DEPARTMENT", "cardinality_or_type": "many-to-one"}]
     },
     "actions": [
       {"entity_name": "EMPLOYEE", "attribute_name": null, "status": "highlight"}
     ],
     "edges": [
       {"source": "EMPLOYEE", "target": "DEPARTMENT", "status": "highlight"}
     ]
   }
   __GRAPH_METADATA_END__
   ```

---

### Next.js Route Handlers

- **Endpoint**: `POST /api/chat`
- **Description**: Next.js App Router edge/node proxy forwarding `{ message, thread_id }` directly to `http://localhost:8000/chat`.

---

## Agent & Tooling Architecture

### LangGraph State Machine

```mermaid
stateDiagram-v2
    [*] --> chat_node
    chat_node --> tools : tool_calls present
    tools --> chat_node : return tool output
    chat_node --> summarize : no tool calls
    summarize --> [*] : messages <= 30
    summarize --> [*] : distill history & prune
```

The LangGraph agent maintains `ChatState`:
- `messages`: List of messages (`HumanMessage`, `AIMessage`, `ToolMessage`) managed with `add_messages`.
- `summary`: Conversation summary distilled from earlier turns.
- `retrieval_count`: Loop guard preventing repetitive retrieval calls (caps at 4 attempts).

When the conversation exceeds 30 messages, `summarize_history_node` invokes a fast model to compress older turns into `summary` and emits `RemoveMessage` operations to prune the context window.

### Integrated Tools

1. **`retrieve_docs(query)`**: Vector similarity search in PostgreSQL via `match_documents`, followed by FlashRank reranking. Injects topology into the shared frontend payload container.
2. **`highlight_components(actions, edges, reason)`**: Visual canvas controller. Instructs the React Flow frontend to color or dim specific schema entities, attributes, or connections.
3. **`calculator(first_num, second_num, operation)`**: Precise arithmetic computation (`add`, `sub`, `mul`, `div`).
4. **`get_stock_price(symbol)`**: Retrieves daily market quotes for tickers via Alpha Vantage.
5. **`get_today_Date()`**: Retrieves the server's current date.
6. **`get_current_time()`**: Retrieves the server's current timestamp (IST/system format).
7. **`DuckDuckGoSearchRun`**: Real-time web search fallback when internal documents lack context.
8. **`SQLDatabaseToolkit`**: LangChain toolkit enabling the LLM to inspect tables, query schemas, and run read operations on the relational database.
9. **MCP Dynamic Tools**: Extensible dynamic tools fetched via `MultiServerMCPClient`.

### Model Context Protocol (MCP)

Synapse AI includes a dedicated MCP server located in `expense-mcp-server/`. Built with **FastMCP**, it exposes tools over standard input/output (stdio):

- **`add_expense(user_id, date, amount, category, subcategory, note)`**: Records an expense into the `expenses` table.
- **`list_expenses(user_id, start_date, end_date)`**: Fetches all expenses within a given date range.
- **`summarize(user_id, start_date, end_date, category)`**: Calculates category-wise expense totals.
- **`get_allowed_categories()`**: Reads and returns standard accepted categories from `categories.json`.

---

## Environment Variables

### Backend Configuration (`chatbot-backend/.env`)

| Variable | Required | Description | Example |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | **Yes** | PostgreSQL connection string with asyncpg driver | `postgresql+asyncpg://postgres:password@localhost:5432/synapse_db` |
| `OPENAI_API_KEY` | **Yes** | API key for the primary LLM, memory model, and embeddings | `sk-...` |
| `BASE_URL` | **Yes** | Base endpoint URL for the OpenAI-compatible model API | `https://api.openai.com/v1` or `https://openrouter.ai/api/v1` |
| `IMAGE_BASE_URL` | **Yes** | Base endpoint URL for the Vision Language Model | `https://api.openai.com/v1` or private vLLM endpoint |
| `LANGCHAIN_TRACING_V2` | No | Enable LangSmith execution tracing | `true` |
| `LANGCHAIN_API_KEY` | No | LangSmith API key | `lsv2_pt_...` |
| `LANGCHAIN_PROJECT` | No | LangSmith project name | `synapse-ai` |

### Frontend Configuration (`chatbot/.env.local`)

| Variable | Required | Description | Example |
| :--- | :--- | :--- | :--- |
| `NEXT_PUBLIC_SUPABASE_URL` | Optional | Supabase project URL (if using Supabase Auth/DB) | `https://xyzcompany.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_KEY` | Optional | Supabase public anonymous API key | `eyJhbGciOi...` |

### MCP Server Configuration (`expense-mcp-server/.env`)

| Variable | Required | Description | Example |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | **Yes** | PostgreSQL connection string for asyncpg | `postgresql+asyncpg://postgres:password@localhost:5432/synapse_db` |

---

## Installation and Setup

### Prerequisites

Ensure you have the following installed on your machine:
- **Node.js** (v20.x or later) and **npm** / **pnpm**
- **Python** (v3.11 or later; Python 3.13 recommended)
- **uv** (Modern Python package manager: [Installation Guide](https://docs.astral.sh/uv/))
- **PostgreSQL** (v15 or later) with the **pgvector** extension installed

---

### 1. Database Configuration

1. Launch your PostgreSQL service.
2. Create a dedicated database:
   ```sql
   CREATE DATABASE synapse_db;
   ```
3. Connect to `synapse_db` and verify or install the `vector` extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

---

### 2. Backend Setup

1. Open a terminal and navigate to `chatbot-backend`:
   ```bash
   cd chatbot-backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install the required backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file inside `chatbot-backend/` following the [Environment Variables](#backend-configuration-chatbot-backendenv) section.
5. Initialize database tables and vector functions:
   ```bash
   python init_db.py
   ```
   *Expected output: "All database tables and functions created successfully!"*

---

### 3. MCP Server Setup

1. Navigate to the `expense-mcp-server` directory:
   ```bash
   cd ../expense-mcp-server
   ```
2. Sync dependencies using `uv`:
   ```bash
   uv sync
   ```
3. Create a `.env` file in `expense-mcp-server/` containing your `DATABASE_URL`.
4. **Important**: Configure the path to `expense-mcp-server` in the backend.
   Open `chatbot-backend/mcp_manager.py` and verify lines 12–19:
   ```python
   "expense_tracker": {
       "command": "uv",  # Or absolute path to uv.exe
       "args": [
           "--directory",
           r"/absolute/path/to/expense-mcp-server",
           "run",
           "main.py"
       ],
       "transport": "stdio"
   }
   ```
   *Ensure the directory argument matches the absolute path to `expense-mcp-server` on your machine.*

---

### 4. Frontend Setup

1. Navigate to the `chatbot` directory:
   ```bash
   cd ../chatbot
   ```
2. Install Node.js dependencies:
   ```bash
   npm install
   ```
3. Create a `.env.local` file in `chatbot/` with your Supabase credentials if required.

---

## Running the Project

To run the complete application, run the backend and frontend in separate terminals:

### Terminal 1: Backend Service
```bash
cd chatbot-backend
# Activate your virtual environment
.venv\Scripts\Activate.ps1   # Or 'source .venv/bin/activate' on Unix
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
The FastAPI server will start on `http://localhost:8000`. You can inspect the OpenAPI documentation at `http://localhost:8000/docs`.

### Terminal 2: Frontend Service
```bash
cd chatbot
npm run dev
```
The Next.js application will start on `http://localhost:3000`.

### Using the Application
1. Open your browser and navigate to **`http://localhost:3000/chat`**.
2. Click the **`+`** upload button in the input bar to attach a document (`.pdf`, `.docx`, `.csv`, `.xlsx`) or technical schematic image (`.png`, `.jpg`).
3. Once processed, ask questions about the diagram (e.g., *"Show the entity relationships and explain foreign keys"* or *"Trace what happens if table X is dropped"*).
4. The interactive schema canvas will automatically open on the right-hand panel, highlighting entities and relations in real time!

---

## Future Enhancements

Based on codebase analysis, the following architectural and functional improvements are planned:

- [ ] **Dynamic MCP Configuration**: Replace hardcoded machine paths in `mcp_manager.py` with dynamic relative paths or environment variables (`MCP_EXPENSE_SERVER_PATH`).
- [ ] **Externalized API Credentials**: Move the Alpha Vantage API key in `graph.py` from hardcoded string to an environment variable (`ALPHA_VANTAGE_API_KEY`).
- [ ] **User Authentication & Session Scoping**: Connect the frontend `useConversations` hook to active authenticated Supabase/OAuth user sessions instead of the static `'test_user_id'`.
- [ ] **Canvas Export & Layout Controls**: Add capabilities to download or export the interactive React Flow canvas diagram as PNG or SVG, with automated Dagre layout re-centering.
- [ ] **Batch Document Deletion**: Add an API route and UI control to delete or manage uploaded files and clear vector embeddings for a specific thread.
- [ ] **Multi-Model Provider Selector**: Provide an interface toggle allowing users to select between DeepSeek, Claude, and GPT model backends dynamically per thread.
