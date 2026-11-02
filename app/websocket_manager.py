import asyncio
import json
import redis.asyncio as aioredis
from fastapi import WebSocket
from app.config import settings

class ConnectionManager:
    def __init__(self):
        # Maps session_id -> active WebSocket instance
        self.active_connections: dict[str, WebSocket] = {}
        self.redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_personal_message(self, message: dict, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_json(message)

    async def start_redis_listener(self, session_id: str):
        """
        Listens on a Redis channel specific to this session_id 
        and forwards incoming messages to the client WebSocket.
        """
        pubsub = self.redis_client.pubsub()
        channel_name = f"channel:{session_id}"
        await pubsub.subscribe(channel_name)

        try:
            while session_id in self.active_connections:
                # Non-blocking check for messages from Celery
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    payload = json.loads(message["data"])
                    await self.send_personal_message(payload, session_id)
                # Yield control back to the FastAPI event loop
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()

manager = ConnectionManager()