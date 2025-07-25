from fastapi import FastAPI, BackgroundTasks, Form, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uvicorn
from websocket_server import manager
from servicios import (
    flask_app, logger, proceso_config,
    procesar_log_en_segundo_plano, ProcesoConfig
)
from logs_procesados import router as logs_procesados_router
from logs_procesos import router as logs_procesos_router 
from logs_servidor import router as servidores_router
from logs_accesos import router as accesos_remotos_router 
from modelo.loAccesosremotos import loAccesosremotos  

app = FastAPI()

# Configuración CORS mejorada (incluye WebSockets)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers (sin duplicados)
app.include_router(logs_procesados_router)
app.include_router(logs_procesos_router)
app.include_router(servidores_router)
app.include_router(accesos_remotos_router) 

# Variables globales
proceso_activo = False
procesos_activos_por_archivo = {}

@app.websocket("/ws/{id_empresa}")
async def websocket_endpoint(websocket: WebSocket, id_empresa: int):
    await manager.connect(websocket, id_empresa)
    try:
        while True:
            # Mantener conexión activa
            data = await websocket.receive_text()
            # Opcional: Registrar pings del cliente
            if data == "ping":
                await websocket.send_text("pong")
    except Exception as e:
        logger.error(f"Error en WebSocket (empresa {id_empresa}): {str(e)}")
    finally:
        manager.disconnect(websocket, id_empresa)
        logger.info(f"Conexión WebSocket cerrada para empresa {id_empresa}")

@app.post("/proceso-detener/")
async def detener_proceso():
    global proceso_activo
    proceso_activo = False
    proceso_config["activo"] = False
    return {"status": "proceso_detenido", "activo": False}

@app.get("/proceso-config/")
async def obtener_config():
    return {**proceso_config, "activo": proceso_activo}

@app.post("/procesar-log/")
async def procesar_log(
    background_tasks: BackgroundTasks,
    nombre_archivo: str = Form(...),
    idServidor: int = Form(...),
    intervalo_minutos: int = Form(5),
    bloque_size: Optional[int] = Form(default=None)
):
    global proceso_activo, procesos_activos_por_archivo, proceso_config

    if nombre_archivo in procesos_activos_por_archivo:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo {nombre_archivo} ya está siendo procesado"
        )

    # Actualizar estado
    proceso_activo = True
    proceso_config.update({
        "activo": True,
        "archivo": nombre_archivo,
        "idServidor": idServidor,
        "intervalo_minutos": intervalo_minutos
    })

    # Usar BackgroundTasks nativo de FastAPI
    background_tasks.add_task(
        procesar_log_en_segundo_plano,
        nombre_archivo,
        idServidor,
        bloque_size,
        intervalo_minutos
    )

    return {
        "status": "procesamiento_iniciado",
        "activo": True,
        "archivo": nombre_archivo,
        "intervalo_minutos": intervalo_minutos
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, ws_ping_interval=30, ws_ping_timeout=60)
