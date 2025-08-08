import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import logging
import asyncio
from modelo.loServidores import loServidores
from websocket_server import manager
from metodos_loremotos import interpretar_logs_remotos
from config import db, init_app
from flask import Flask


router = APIRouter(prefix="/api/v1/interpretacion", tags=["Interpretación Remota"])
logger = logging.getLogger(__name__)

# Inicialización de Flask para contexto SQLAlchemy
flask_app = Flask(__name__)
init_app(flask_app)

# Scheduler para los temporizadores
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Diccionario para controlar procesos activos
procesos_activos = {}

class InterpretacionRequest(BaseModel):
    id_servidor: int
    batch_size: Optional[int] = 100
    intervalo_minutos: Optional[int] = 5  # Nuevo campo para el intervalo

def ejecutar_interpretacion(id_servidor: int, batch_size: int):
    with flask_app.app_context():
        try:
            logger.info(f"Ejecutando interpretación programada para servidor {id_servidor}")
            interpretar_logs_remotos(
                id_servidor=id_servidor,
                batch_size=batch_size
            )

            servidor = db.session.query(loServidores).filter_by(idServidor=id_servidor).first()
            if servidor:
                logger.info(f"Intentando enviar mensaje WebSocket para servidor {id_servidor} empresa {servidor.idEmpresa}")
                try:
                    asyncio.run(manager.send_personal_message(f"proceso_completado:{id_servidor}", servidor.idEmpresa))
                    logger.info(f"Mensaje WebSocket enviado: proceso_completado:{id_servidor} para empresa {servidor.idEmpresa}")
                except Exception as e:
                    logger.error(f"Error enviando mensaje WebSocket para servidor {id_servidor}: {str(e)}")
            else:
                logger.warning(f"No se encontró servidor con id {id_servidor} para enviar mensaje WebSocket")

        except Exception as e:
            logger.error(f"Error en interpretación programada: {str(e)}")

@router.post("/iniciar")
async def iniciar_interpretacion(
    request: InterpretacionRequest,
    background_tasks: BackgroundTasks
):
    try:
        with flask_app.app_context():
            # Verificar si el servidor existe y es remoto
            servidor = db.session.query(loServidores).filter_by(
                idServidor=request.id_servidor,
                esRemoto=True
            ).first()

            if not servidor:
                raise HTTPException(status_code=404, detail="Servidor remoto no encontrado")

            # Si ya hay un proceso activo, primero detenerlo
            if request.id_servidor in procesos_activos:
                scheduler.remove_job(procesos_activos[request.id_servidor])

            # Ejecutar primera interpretación inmediatamente
            background_tasks.add_task(
                interpretar_logs_remotos,
                id_servidor=request.id_servidor,
                batch_size=request.batch_size
            )

            # Programar ejecuciones periódicas
            job = scheduler.add_job(
                ejecutar_interpretacion,
                trigger=IntervalTrigger(minutes=request.intervalo_minutos),
                args=[request.id_servidor, request.batch_size],
                id=f"interpretacion_{request.id_servidor}"
            )

            # Registrar el proceso como activo
            procesos_activos[request.id_servidor] = job.id

            return {
                "status": "interpretacion_iniciada",
                "id_servidor": request.id_servidor,
                "intervalo_minutos": request.intervalo_minutos,
                "detalle": f"Procesamiento iniciado con intervalo de {request.intervalo_minutos} minutos"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al iniciar interpretación: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al iniciar el proceso")

@router.post("/detener")
async def detener_interpretacion(id_servidor: int):
    try:
        if id_servidor in procesos_activos:
            scheduler.remove_job(procesos_activos[id_servidor])
            del procesos_activos[id_servidor]
            return {
                "status": "interpretacion_detenida",
                "id_servidor": id_servidor,
                "detalle": "Procesamiento detenido correctamente"
            }
        else:
            raise HTTPException(status_code=404, detail="No hay proceso activo para este servidor")
    except Exception as e:
        logger.error(f"Error al detener interpretación: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al detener el proceso")

@router.get("/procesos-activos")
async def listar_procesos_activos() -> List[Dict]:
        # Retornamos una lista con info básica de los procesos activos
        resultado = []
        for id_servidor, job_id in procesos_activos.items():
            resultado.append({
                "id_servidor": id_servidor,
                "job_id": job_id,
            })
        return resultado
