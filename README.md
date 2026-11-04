# Financial Research Agent

An agentic Retrieval-Augmented Generation (RAG) system for researching financial documents. The application ingests PDF reports, converts their contents into searchable vector data, and uses a LangGraph ReAct agent to retrieve relevant context before producing investment-risk insights.

## Video Demonstration

> **Demo video:** [Demo_Video.mp4](Demo_Video.mp4)
>
> The demonstration will show:
> 1. Ingesting `data/sgx_report.pdf`.
> 2. Watching ingestion milestones stream to the browser over WebSockets.
> 3. Asking a financial research question.
> 4. The agent retrieving relevant document chunks and presenting a source-grounded answer.

## What the System Does

The project separates document ingestion from question answering:

- **Ingestion:** A PDF is submitted to FastAPI and queued as a Celery task. The worker extracts the text, chunks it, generates Gemini embeddings, and stores the chunks and vectors in PostgreSQL with pgvector.
- **Retrieval:** A user question is converted into an embedding. PostgreSQL performs cosine-similarity search to find the five most relevant document chunks.
- **Generation:** A LangGraph ReAct agent decides when to call the retrieval tool, uses the returned financial context, and asks Gemini to synthesize an answer.
- **Progress updates:** The worker publishes ingestion milestones to Redis Pub/Sub. FastAPI forwards those events to the browser through a session-specific WebSocket.

The current answer endpoint returns the completed answer through HTTP. WebSockets are used for live ingestion progress, not token-by-token answer streaming.

## Architecture

```text
                         Document ingestion
 ┌──────────────┐   POST /start-research/{session_id}
 │ Browser UI   │ ──────────────────────────────────────┐
 └──────┬───────┘                                       │
        │ WebSocket /ws/{session_id}                    ▼
        │                                      ┌────────────────┐
        │                         task queue  │ Celery worker   │
        │                         via Redis   │ PDF → chunks   │
        │                                      │ → embeddings   │
        │                                      └───────┬────────┘
        │                                              │
        │                 progress via Redis Pub/Sub   │ vectors + text
        │ ◄────────────────────────────────────────────┤
        │                                              ▼
        │                                      ┌────────────────┐
        │                                      │ PostgreSQL +   │
        │                                      │ pgvector       │
        │                                      └────────────────┘
        │
        │                         Question answering
        │   POST /ask?query=...           ▲
        └─────────────────────────────────┘
                                           │
                                  ┌────────┴────────┐
                                  │ LangGraph ReAct │
                                  │ Gemini LLM      │
                                  └────────┬────────┘
                                           │ tool call
                                  ┌────────▼────────┐
                                  │ Vector retriever│
                                  │ top 5 chunks    │
                                  └─────────────────┘
```

## Technology Stack

| Area | Technology | Role |
| --- | --- | --- |
| API | FastAPI | HTTP endpoints, WebSocket connections, and application startup |
| Agent orchestration | LangGraph | ReAct workflow and tool-calling control flow |
| Language model | Google Gemini via LangChain | Embeddings and answer generation |
| Background processing | Celery | Asynchronous PDF ingestion |
| Messaging | Redis | Celery broker/backend and progress Pub/Sub |
| Persistence | PostgreSQL + pgvector | Chunk storage and vector similarity search |
| Document processing | PyMuPDF | PDF text extraction |
| Frontend | HTML/CSS/JavaScript | Upload controls, live progress feed, and question interface |

## Project Structure

```text
app/
├── agent.py             # LangGraph ReAct agent and retrieval tool binding
├── config.py            # Environment-backed application settings
├── database.py          # SQLAlchemy model and pgvector database initialization
├── embeddings.py        # Cached Gemini embedding client
├── main.py              # FastAPI routes and WebSocket endpoint
├── retriever.py         # Semantic search over document chunks
├── tools.py             # PDF extraction and text chunking helpers
├── websocket_manager.py # Redis-to-WebSocket event forwarding
└── worker.py            # Celery document-ingestion task
data/
└── sgx_report.pdf       # Example financial report
static/
└── index.html           # Browser test interface
docker-compose.yml       # Redis and PostgreSQL services
requirements.txt         # Python dependencies
```

## Getting Started

### Prerequisites

- Python 3.10+
- Docker Desktop
- A Google Gemini API key

### 1. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY
REDIS_URL
DATABASE_URL
```
The PostgreSQL container exposes its internal port `5432` on host port `5433`, so the host-side `DATABASE_URL` uses `5433`.

### 3. Start infrastructure

```powershell
docker compose up -d
```

This starts:

- Redis on `localhost:6379`
- PostgreSQL with pgvector on `localhost:5433`

### 4. Start the FastAPI application

```powershell
python -m uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

### 5. Start the Celery worker

On Windows, run the worker with the solo pool:

```powershell
celery -A app.celery_app worker --loglevel=info --pool=solo
```

## Using the Application

1. Open the browser interface.
2. Use **Process Document** with the default `data/sgx_report.pdf` path.
3. Confirm that PDF extraction, chunking, vectorization, and database milestones appear in the live feed.
4. Ask a question such as:

   ```text
   What are the key financial risks described in the report?
   ```

5. The ReAct agent invokes `search_financial_documents`, retrieves the most relevant chunks, and generates an answer that cites the source file name.

## API Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Serves the browser interface |
| `POST /start-research/{session_id}` | Queues PDF ingestion as a Celery task |
| `POST /test-publish/{session_id}` | Publishes a test progress event |
| `POST /ask?query=...` | Runs the agent and returns a completed answer |
| `WebSocket /ws/{session_id}` | Streams Redis ingestion events to the browser |

## Design Decisions

- **Asynchronous ingestion:** PDF processing and embedding generation can be slow, so the API queues the work instead of blocking the request.
- **Vector search in PostgreSQL:** pgvector keeps document text and embeddings in the same persistence layer and allows similarity ranking in the database.
- **Agent-controlled retrieval:** LangGraph allows the model to decide when the retrieval tool is needed, rather than forcing every request through a fixed retrieval path.
- **Session-scoped progress:** Redis channels are keyed by session ID so each browser connection receives its own ingestion events.
- **Cached model clients:** Embedding and agent clients are cached to avoid recreating external API clients for every request.

## Current Scope and Future Improvements

This project is a working prototype focused on the end-to-end RAG workflow. Potential production improvements include:

- database migrations instead of `create_all`;
- stronger request validation and structured error responses;
- automated tests for ingestion, retrieval, and agent behavior;
- deployment
