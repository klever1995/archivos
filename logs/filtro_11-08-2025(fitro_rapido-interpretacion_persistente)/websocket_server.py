import asyncio
from fastapi import WebSocket
from typing import Dict, Set
from collections import defaultdict
import json
from threading import Lock
import logging

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
        """Elimina conexiones de forma segura."""
        with self._lock:
            if websocket in self.active_connections.get(id_empresa, set()):
                self.active_connections[id_empresa].discard(websocket)
                self.logger.debug(f"Desconectado WebSocket de empresa {id_empresa}")

    async def _safe_send(self, websocket: WebSocket, message: str, is_json: bool):
        """Envía mensajes con reintentos y manejo de errores."""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                if is_json:
                    await websocket.send_text(json.dumps(message))
                else:
                    await websocket.send_text(message)
                return True
            except Exception as e:
                self.logger.warning(f"Intento {attempt + 1} fallido: {str(e)}")
                if attempt == max_retries - 1:
                    self.logger.error(f"Error enviando mensaje: {str(e)}")
                    return False
                await asyncio.sleep(0.5)

    async def send_personal_message(self, message: str, id_empresa: int):
        """Envía mensajes de texto plano con manejo seguro."""
        with self._lock:
            connections = self.active_connections.get(id_empresa, set()).copy()
        
        for connection in connections:
            success = await self._safe_send(connection, message, is_json=False)
            if not success:
                self.disconnect(connection, id_empresa)

    async def send_json_message(self, data: dict, id_empresa: int):
        """Envía mensajes JSON con manejo seguro."""
        with self._lock:
            connections = self.active_connections.get(id_empresa, set()).copy()
        
        for connection in connections:
            success = await self._safe_send(connection, data, is_json=True)
            if not success:
                self.disconnect(connection, id_empresa)

# Instancia global (como en tu implementación original)
manager = WebSocketManager()
