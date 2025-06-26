from fastapi import FastAPI, BackgroundTasks, Form, HTTPException
from typing import Optional 
from fastapi.middleware.cors import CORSMiddleware
from fastapi import WebSocket
from websocket_server import manager

import uvicorn
from servicios import (
    flask_app, logger, proceso_config,
    procesar_log_en_segundo_plano, ProcesoConfig
)
from logs_procesados import router as logs_procesados_router
from logs_procesos import router as logs_procesos_router 
from logs_servidor import router as servidores_router

app = FastAPI()

# Configuración CORS
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

# Variables globales
proceso_activo = False
procesos_activos_por_archivo = {}  # Nuevo: Para sincronización entre endpoints

@app.post("/proceso-detener/")
async def detener_proceso():
    global proceso_activo
    proceso_activo = False
    proceso_config["activo"] = False
    return {"status": "proceso_detenido", "activo": False}

@app.websocket("/ws/{id_empresa}")
async def websocket_endpoint(websocket: WebSocket, id_empresa: int):
    await manager.connect(websocket, id_empresa)
    try:
        while True:
            data = await websocket.receive_text()
            # Opcional: Manejar mensajes entrantes del cliente si es necesario
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
    finally:
        manager.disconnect(websocket, id_empresa)

@app.get("/proceso-config/")
async def obtener_config():
    return {**proceso_config, "activo": proceso_activo}

@app.post("/procesar-log/")
async def procesar_log(
    background_tasks: BackgroundTasks,
    nombre_archivo: str = Form(...),
    idServidor: int = Form(...),
    intervalo_minutos: int = Form(...),  # nuevo parámetro
    bloque_size: Optional[int] = Form(default=None)
):
    global proceso_activo, procesos_activos_por_archivo, proceso_config
    
    if nombre_archivo in procesos_activos_por_archivo:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo {nombre_archivo} ya está siendo procesado"
        )
    
    proceso_activo = True
    proceso_config["activo"] = True
    proceso_config["archivo"] = nombre_archivo
    proceso_config["idServidor"] = idServidor
    
    # Actualiza el intervalo aquí:
    proceso_config["intervalo_minutos"] = intervalo_minutos
    
    background_tasks.add_task(
        procesar_log_en_segundo_plano, 
        nombre_archivo, 
        idServidor, 
        bloque_size
    )
    
    return {
        "status": "procesamiento_iniciado",
        "activo": True,
        "archivo": nombre_archivo,
        "intervalo_minutos": intervalo_minutos
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
