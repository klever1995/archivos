from fastapi import FastAPI, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uvicorn
from config import flask_app, proceso_config, logger, procesos_activos_por_archivo
from log_processor import procesar_log_en_segundo_plano
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProcesoConfig(BaseModel):
    activo: bool
    intervalo_minutos: int
    archivo: Optional[str] = None
    idServidor: Optional[int] = None

proceso_activo = False

@app.post("/proceso-detener/")
async def detener_proceso():
    global proceso_activo
    proceso_activo = False
    proceso_config["activo"] = False
    return {"status": "proceso_detenido", "activo": False}

@app.get("/proceso-estado/")
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
    bloque_size: Optional[int] = Form(None)
):
    global proceso_activo
    proceso_activo = True
    proceso_config.update({
        "activo": True,
        "archivo": nombre_archivo,
        "idServidor": idServidor
    })
    
    background_tasks.add_task(
        procesar_log_en_segundo_plano,
        nombre_archivo,
        idServidor,
        bloque_size
    )
    return {"status": "procesamiento_iniciado", "activo": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
