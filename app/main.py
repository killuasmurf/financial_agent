import asyncio
import json
from pathlib import Path
from typing import Any, cast
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
from app.websocket_manager import manager
from app.config import settings
from app.worker import process_document_task
from langchain_core.messages import HumanMessage
from app.agent import get_react_agent
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database table and vector extension on startup 🗄️
    init_db()
    yield

app = FastAPI(title="Financial Research AI Agent Gateway", lifespan=lifespan)

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

@app.get("/")
async def get_test_ui():
    static_index = Path(__file__).resolve().parent.parent / "static" / "index.html"
    with static_index.open(encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    
    # Start Redis listener task as a background process for this connection
    listener_task = asyncio.create_task(manager.start_redis_listener(session_id))
    
    try:
        # Acknowledge connection
        await websocket.send_json({
            "status": "connected",
            "message": f"Connected to session: {session_id}"
        })

        while True:
            # Keep connection alive and handle incoming client messages
            data = await websocket.receive_text()
            await websocket.send_json({"echo": f"Server received: {data}"})

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        listener_task.cancel()

@app.post("/test-publish/{session_id}")
async def test_publish(session_id: str, message: str = "Extracting risk factors..."):
    """
    Simulates our future Celery worker publishing a progress event to Redis.
    """
    channel_name = f"channel:{session_id}"
    payload = {
        "event": "milestone",
        "detail": message
    }
    await redis_client.publish(channel_name, json.dumps(payload))
    return {"status": "published", "channel": channel_name, "data": payload}

@app.post("/start-research/{session_id}")
async def start_research(session_id: str, file_path: str = "data/sgx_report.pdf"):
    """
    Receives the request and hands the heavy lifting off to Celery via .delay()
    """
    # .delay() pushes the job to Redis and returns immediately
    task = cast(Any, process_document_task).delay(session_id, file_path)
    
    return {
        "status": "Task queued successfully",
        "task_id": task.id,
        "session_id": session_id
    }
    
@app.post("/ask")
async def ask_agent(query: str):
    """
    Triggers the LangGraph ReAct agent to answer a financial question.
    """
    initial_state = {"messages": [HumanMessage(content=query)]}
    
    # The agent will loop autonomously until it decides it has a final answer
    final_state = get_react_agent().invoke(cast(Any, initial_state))
    
    # The final message in the state is the LLM's synthesized response
    ai_response = final_state["messages"][-1].content
    
    return {
        "query": query,
        "response": ai_response
    }