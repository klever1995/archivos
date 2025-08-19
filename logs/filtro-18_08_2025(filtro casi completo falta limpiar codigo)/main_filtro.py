from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from websocket_server import manager
from servicios import flask_app, logger
from logs_procesados import router as logs_procesados_router
from logs_procesos import router as logs_procesos_router
from logs_servidor import router as servidores_router
from logs_accesos import router as accesos_remotos_router
from logs_departamentos import router as departamentos_router
from interpretacion import router as interpretacion_router

app = FastAPI()

# Configuración CORS (incluye WebSockets)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(logs_procesados_router)
app.include_router(logs_procesos_router)
app.include_router(servidores_router)
app.include_router(accesos_remotos_router)
app.include_router(interpretacion_router)
app.include_router(departamentos_router)

@app.websocket("/ws/{id_empresa}")
async def websocket_endpoint(websocket: WebSocket, id_empresa: int):
    await manager.connect(websocket, id_empresa)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception as e:
        logger.error(f"Error en WebSocket (empresa {id_empresa}): {str(e)}")
    finally:
        manager.disconnect(websocket, id_empresa)
        logger.info(f"Conexión WebSocket cerrada para empresa {id_empresa}")

@app.on_event("startup")
async def startup_event():
    async def send_test_messages():
        while True:
            await manager.send_json_message({"eventType": "test", "data": "hola"}, id_empresa=1)
            await asyncio.sleep(5)
    asyncio.create_task(send_test_messages())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, ws_ping_interval=30, ws_ping_timeout=60)
