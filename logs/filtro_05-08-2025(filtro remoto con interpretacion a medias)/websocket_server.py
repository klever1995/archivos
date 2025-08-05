import asyncio
from fastapi import WebSocket  # Importación crítica que faltaba
from typing import Dict, Set
from collections import defaultdict
import json

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, id_empresa: int):
        await websocket.accept()
        self.active_connections[id_empresa].add(websocket)

    def disconnect(self, websocket: WebSocket, id_empresa: int):
        self.active_connections[id_empresa].discard(websocket)

    async def send_personal_message(self, message: str, id_empresa: int):
        """Para mensajes de texto plano (proceso_completado)"""
        if id_empresa in self.active_connections:
            for connection in self.active_connections[id_empresa]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Error enviando mensaje: {e}")
                    self.disconnect(connection, id_empresa)
    
    async def send_json_message(self, data: dict, id_empresa: int):
        """Para mensajes JSON (metrics_update)"""
        if id_empresa in self.active_connections:
            for connection in self.active_connections[id_empresa]:
                try:
                    await connection.send_text(json.dumps(data))
                except Exception as e:
                    print(f"Error enviando mensaje JSON: {e}")
                    self.disconnect(connection, id_empresa)

# Instancia global (manteniendo tu estructura actual)
manager = WebSocketManager()
