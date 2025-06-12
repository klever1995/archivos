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

# Endpoints
@app.post("/proceso-detener/")
async def detener_proceso():
    proceso_config["activo"] = False
    return {"status": "proceso_detenido"}

@app.get("/proceso-config/")
async def obtener_config():
    return proceso_config

@app.post("/procesar-log/")
async def procesar_log(
    background_tasks: BackgroundTasks,
    nombre_archivo: str = Form(...),
    idServidor: int = Form(...),
    bloque_size: Optional[int] = Form(default=None)
):
    background_tasks.add_task(procesar_log_en_segundo_plano, nombre_archivo, idServidor, bloque_size)
    return {"status": "procesamiento_iniciado"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
