from fastapi import FastAPI, BackgroundTasks, Form
from typing import Optional 
from fastapi.middleware.cors import CORSMiddleware
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

# Variable global para rastrear el estado del proceso
proceso_activo = False

# Endpoints
@app.post("/proceso-detener/")
async def detener_proceso():
    global proceso_activo
    proceso_activo = False
    proceso_config["activo"] = False
    return {"status": "proceso_detenido", "activo": False}

@app.get("/proceso-estado/")  # Nuevo endpoint para consultar estado
async def obtener_estado():
    return {"activo": proceso_activo}

@app.get("/proceso-config/")
async def obtener_config():
    return {**proceso_config, "activo": proceso_activo}

@app.post("/procesar-log/")
async def procesar_log(
    background_tasks: BackgroundTasks,
    nombre_archivo: str = Form(...),
    idServidor: int = Form(...),
    bloque_size: Optional[int] = Form(default=None)
):
    global proceso_activo
    proceso_activo = True
    proceso_config["activo"] = True
    proceso_config["archivo"] = nombre_archivo
    proceso_config["idServidor"] = idServidor
    
    background_tasks.add_task(procesar_log_en_segundo_plano, nombre_archivo, idServidor, bloque_size)
    return {"status": "procesamiento_iniciado", "activo": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
