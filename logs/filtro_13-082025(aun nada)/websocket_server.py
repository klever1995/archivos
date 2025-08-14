import asyncio
from fastapi import WebSocket
from typing import Dict, Set
from collections import defaultdict
import json
from threading import Lock
import logging
from starlette.websockets import WebSocketState  # Nueva importación

class WebSocketManager:
    def __init__(self):
        self._lock = Lock()  # Lock para operaciones thread-safe
        self.active_connections: Dict[int, Set[WebSocket]] = defaultdict(set)
        self.logger = logging.getLogger(__name__)

    async def connect(self, websocket: WebSocket, id_empresa: int):
        """Acepta conexiones y las registra de manera segura."""
        await websocket.accept()
        with self._lock:
            self.active_connections[id_empresa].add(websocket)
        self.logger.info(f"Conexión WebSocket establecida para empresa {id_empresa}")

    def disconnect(self, websocket: WebSocket, id_empresa: int):
        """Elimina conexiones de forma segura verificando su estado."""
        with self._lock:
            connections = self.active_connections.get(id_empresa, set())
            if websocket in connections and websocket.client_state != WebSocketState.DISCONNECTED:
                connections.discard(websocket)
                self.logger.debug(f"Desconectado WebSocket de empresa {id_empresa}")

    async def _safe_send(self, websocket: WebSocket, message: str, is_json: bool):
        """Envía mensajes con manejo robusto de errores."""
        try:
            if is_json:
                await websocket.send_text(json.dumps(message))
            else:
                await websocket.send_text(message)
            return True
        except RuntimeError as e:  # Conexión cerrada
            self.logger.error(f"Error en envío (conexión cerrada): {str(e)}")
            self.disconnect(websocket, id_empresa=None)  # El id_empresa se obtendrá en send_*
            return False
        except Exception as e:
            self.logger.error(f"Error inesperado en envío: {str(e)}")
            return False

    async def cleanup_dead_connections(self):
        """Limpia conexiones desconectadas en todas las empresas."""
        with self._lock:
            for id_empresa, connections in list(self.active_connections.items()):
                alive_connections = {
                    ws for ws in connections 
                    if ws.client_state != WebSocketState.DISCONNECTED
                }
                self.active_connections[id_empresa] = alive_connections
                if not alive_connections:
                    del self.active_connections[id_empresa]

    async def send_personal_message(self, message: str, id_empresa: int):
        """Envía mensajes de texto plano con limpieza previa."""
        await self.cleanup_dead_connections()
        with self._lock:
            connections = self.active_connections.get(id_empresa, set()).copy()
        
        for connection in connections:
            success = await self._safe_send(connection, message, is_json=False)
            if not success:
                self.disconnect(connection, id_empresa)

    async def send_json_message(self, data: dict, id_empresa: int):
        """Envía mensajes JSON con limpieza previa."""
        await self.cleanup_dead_connections()
        with self._lock:
            connections = self.active_connections.get(id_empresa, set()).copy()
        
        for connection in connections:
            success = await self._safe_send(connection, data, is_json=True)
            if not success:
                self.disconnect(connection, id_empresa)
                

# Instancia global
manager = WebSocketManager()
