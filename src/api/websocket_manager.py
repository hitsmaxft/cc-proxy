from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
import asyncio
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

class WebSocketManager:
    def __init__(self):
        self.connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.connections)}")
        await self.broadcast({
            "type": "connection_status",
            "payload": {"status": "connected", "timestamp": datetime.now().isoformat()}
        })
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to websocket: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        if self.connections:
            tasks = []
            for connection in self.connections:
                tasks.append(self.send_personal_message(message, connection))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

manager = WebSocketManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle messages
            data = await websocket.receive_json()
            logger.debug(f"Received WebSocket message: {data}")
            
            # Echo back received messages for testing
            if data.get("type") == "ping":
                await manager.send_personal_message({
                    "type": "pong", 
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

async def broadcast_message(message_type: str, payload: dict):
    """Helper function to broadcast messages to all connected clients"""
    message = {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now().isoformat()
    }
    await manager.broadcast(message)

async def broadcast_model_update(big_model: str, middle_model: str, small_model: str):
    """Broadcast model configuration updates"""
    await broadcast_message("model_update", {
        "big_model": big_model,
        "middle_model": middle_model,
        "small_model": small_model
    })

async def broadcast_health_update(status: dict):
    """Broadcast health status updates"""
    await broadcast_message("health_update", status)

async def broadcast_history_update(history_data: dict):
    """Broadcast history updates"""
    await broadcast_message("history_update", history_data)