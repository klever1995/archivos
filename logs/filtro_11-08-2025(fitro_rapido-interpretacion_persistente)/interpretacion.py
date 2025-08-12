import os
import sys
import asyncio
import atexit
import logging
from datetime import datetime
from datetime import timedelta
from typing import Optional, List, Dict
from threading import Lock, Thread

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from modelo.loServidores import loServidores
from websocket_server import manager
from metodos_loremotos import interpretar_logs_remotos
from config import db, init_app
from flask import Flask

router = APIRouter(prefix="/api/v1/interpretacion", tags=["Interpretación Remota"])
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)
init_app(flask_app)

scheduler = BackgroundScheduler({
    'job_defaults': {
        'misfire_grace_time': 60,  
        'coalesce': True,        
        'max_instances': 1         
    },
    'apscheduler.job_defaults.max_instances': 1
})
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

procesos_activos = {}
procesos_lock = Lock()
ejecuciones_activas = {}  

class InterpretacionRequest(BaseModel):
    id_servidor: int
    batch_size: Optional[int] = 100
    intervalo_minutos: Optional[int] = 5

async def enviar_mensaje_websocket(id_servidor: int, id_empresa: int) -> bool:
    """Envía mensaje WebSocket con confirmación y reintentos."""
    max_retries = 3
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            await manager.send_personal_message(f"proceso_completado:{id_servidor}", id_empresa)
            logger.info(f"✅ WebSocket confirmado para servidor {id_servidor}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Intento {attempt + 1} fallido: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
    
    logger.error(f"❌ Fallo definitivo al enviar WebSocket para servidor {id_servidor}")
    return False

def _interpretacion_worker(id_servidor: int, batch_size: int) -> bool:
    """Trabajo real de interpretación en un hilo independiente."""
    if id_servidor in ejecuciones_activas and ejecuciones_activas[id_servidor]:
        logger.warning(f"Ya hay una ejecución en curso para el servidor {id_servidor}. Saltando...")
        return False

    ejecuciones_activas[id_servidor] = True
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        with flask_app.app_context():
            logger.info(f"🚀 Iniciando interpretación para servidor {id_servidor}")
            
            if not interpretar_logs_remotos(id_servidor, batch_size):
                raise RuntimeError("interpretar_logs_remotos() falló")

            servidor = db.session.query(loServidores).filter_by(idServidor=id_servidor).first()
            if not servidor:
                logger.warning(f"Servidor {id_servidor} no existe en BD")
                return False

            if servidor.idEmpresa in manager.active_connections:
                success = loop.run_until_complete(
                    enviar_mensaje_websocket(id_servidor, servidor.idEmpresa)
                )
                if not success:
                    logger.error("Fallo crítico en WebSocket")
                    return False
            else:
                logger.warning(f"No hay conexiones para empresa {servidor.idEmpresa}")
            
            return True

    except Exception as e:
        logger.error(f"Error en ejecución: {str(e)}", exc_info=True)
        return False
    finally:
        ejecuciones_activas[id_servidor] = False
        loop.close()
        logger.info(f"🏁 Finalizada interpretación para servidor {id_servidor}")

def ejecutar_interpretacion_sincrona(id_servidor: int, batch_size: int) -> None:
    """Lanza la interpretación en un hilo separado para no bloquear FastAPI."""
    Thread(
        target=_interpretacion_worker,
        args=(id_servidor, batch_size),
        daemon=True
    ).start()

@router.post("/iniciar")
async def iniciar_interpretacion(
    request: InterpretacionRequest,
    background_tasks: BackgroundTasks
):
    try:
        with flask_app.app_context():
            servidor = db.session.query(loServidores).filter_by(
                idServidor=request.id_servidor,
                esRemoto=True
            ).first()

            if not servidor:
                raise HTTPException(status_code=404, detail="Servidor remoto no encontrado")

            with procesos_lock:
                if request.id_servidor in procesos_activos:
                    try:
                        scheduler.remove_job(procesos_activos[request.id_servidor])
                        del procesos_activos[request.id_servidor]
                    except JobLookupError:
                        pass

                # Primera ejecución en segundo plano
                background_tasks.add_task(
                    ejecutar_interpretacion_sincrona,
                    request.id_servidor,
                    request.batch_size
                )

                # Programar ejecuciones periódicas
                job = scheduler.add_job(
                    ejecutar_interpretacion_sincrona,
                    trigger=IntervalTrigger(
                        minutes=request.intervalo_minutos,
                        jitter=10
                    ),
                    args=[request.id_servidor, request.batch_size],
                    id=f"interpretacion_{request.id_servidor}",
                    next_run_time=datetime.now() + timedelta(minutes=request.intervalo_minutos)
                )

                procesos_activos[request.id_servidor] = job.id

            return {
                "status": "interpretacion_iniciada",
                "id_servidor": request.id_servidor,
                "intervalo_minutos": request.intervalo_minutos,
                "next_run": job.next_run_time.isoformat()
            }

    except Exception as e:
        logger.error(f"Error al iniciar: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detener")
async def detener_interpretacion(id_servidor: int):
    try:
        with procesos_lock:
            if id_servidor in procesos_activos:
                scheduler.remove_job(procesos_activos[id_servidor])
                del procesos_activos[id_servidor]
                if id_servidor in ejecuciones_activas:
                    ejecuciones_activas[id_servidor] = False
                return {"status": "interpretacion_detenida"}
            raise HTTPException(status_code=404, detail="Proceso no encontrado")
    except Exception as e:
        logger.error(f"Error al detener: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/procesos-activos")
async def listar_procesos_activos() -> List[Dict]:
    with procesos_lock:
        return [{
            "id_servidor": k, 
            "job_id": v,
            "en_ejecucion": ejecuciones_activas.get(k, False)
        } for k, v in procesos_activos.items()]
