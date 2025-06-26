# websocket_server.py
import asyncio
from fastapi import WebSocket
from typing import Dict, Set
from collections import defaultdict  # Importación faltante

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = defaultdict(set)  # Por empresa o proceso

    async def connect(self, websocket: WebSocket, id_empresa: int):
        await websocket.accept()
        self.active_connections[id_empresa].add(websocket)

    def disconnect(self, websocket: WebSocket, id_empresa: int):
        self.active_connections[id_empresa].discard(websocket)

    async def send_personal_message(self, message: str, id_empresa: int):
        if id_empresa in self.active_connections:
            for connection in self.active_connections[id_empresa]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Error enviando mensaje: {e}")
                    self.disconnect(connection, id_empresa)

manager = WebSocketManager()
