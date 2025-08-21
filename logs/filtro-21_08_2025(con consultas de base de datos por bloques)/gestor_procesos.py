import sys
import os
import hashlib
import asyncio
from flask import Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import init_app, db 
from typing import Optional, Dict, Union
from modelo.loProcesos import LoProcesos
from websocket_server import manager
import logging
from datetime import datetime

app = Flask(__name__)
init_app(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class ProcesosLogger:

#Método que registra el inicio de un nuevo proceso
    @staticmethod
    def iniciar_proceso(
        idEmpresa: int,
        operador: int,
        idServidor: int = None,
        procesoActivo: bool = False,  
        intervaloMinutos: int = 5    
    ) -> int:
        """Registra el inicio de un nuevo proceso, ahora con soporte para ejecución periódica."""
        with app.app_context():
            try:
                nuevo_proceso = LoProcesos(
                    idEmpresa=idEmpresa,
                    operador=operador,
                    idServidor=idServidor,
                    fechaInicio=datetime.now(),
                    totalLogsProcesados=0,
                    estado='PROCESANDO',
                    procesoActivo=procesoActivo,      
                    intervaloMinutos=intervaloMinutos
                )
                db.session.add(nuevo_proceso)
                db.session.commit()
                logger.info(f"✅ Proceso {nuevo_proceso.idAuditoria} iniciado (Activo: {procesoActivo}, Intervalo: {intervaloMinutos} min)")
                return nuevo_proceso.idAuditoria
            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ Error al iniciar proceso: {str(e)}", exc_info=True)
                return -1

#Método que finaliza proceso y envía notificación websocket
    @staticmethod
    def finalizar_proceso(idAuditoria: int, totalLogs: int, ultimo_byte: int, mantenerActivo: bool = False) -> bool:
        with app.app_context():
            try:
                proceso = LoProcesos.query.get(idAuditoria)
                if proceso:
                    proceso.fechaFin = datetime.now()
                    proceso.totalLogsProcesados = totalLogs
                    proceso.ultimo_byte_procesado = ultimo_byte
                    proceso.estado = 'COMPLETADO'
                    proceso.procesoActivo = mantenerActivo
                    db.session.commit()

                    try:
                        if hasattr(manager, 'send_personal_message'): 
                            asyncio.run(manager.send_personal_message(
                                f"proceso_completado:{idAuditoria}",
                                proceso.idEmpresa
                            ))
                        else:
                            logger.warning("WebSocketManager no tiene send_personal_message")
                    except Exception as ws_error:
                        logger.error(f"Error en WebSocket: {str(ws_error)}")

                    logger.info(f"✅ Proceso {idAuditoria} finalizado. Notificación WebSocket enviada.")
                    return True
                return False
            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ Error al finalizar proceso {idAuditoria}: {str(e)}", exc_info=True)
                return False

#Método que obtiene la lista de procesos activos
    @staticmethod
    def obtener_procesos_activos() -> list:

        with app.app_context():
            try:
                return db.session.query(LoProcesos).filter(
                    LoProcesos.procesoActivo == True,
                    LoProcesos.estado.in_(['PROCESANDO', 'COMPLETADO'])
                ).all()
            except Exception as e:
                logger.error(f"❌ Error obteniendo procesos activos: {str(e)}")
                return []

#Método que calcula el checksum del archivo
    @staticmethod
    def calcular_checksum(ruta_archivo: str) -> str:

        hash_sha256 = hashlib.sha256()
        with open(ruta_archivo, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

#metodo que reserva el bloque para el procesamiento
    @staticmethod
    def reservar_bloque(
        ruta_archivo: str,
        idEmpresa: int,
        operador: int,
        idServidor: int = None,
        bloque_size: int = None,
        forzar_completo: bool = False,
        intervaloMinutos: int = 5
    ) -> Optional[Dict[str, Union[int, str]]]:
        with app.app_context():
            try:
                if not os.path.exists(ruta_archivo):
                    logger.error(f"Archivo no encontrado: {ruta_archivo}")
                    return None

                checksum = ProcesosLogger.calcular_checksum(ruta_archivo)
                tamano_archivo = os.path.getsize(ruta_archivo)

                if forzar_completo or tamano_archivo < 1024:
                    ultimo_proceso = db.session.query(LoProcesos).filter(
                        LoProcesos.archivo == ruta_archivo,
                        LoProcesos.estado.in_(['COMPLETADO', 'PROCESANDO']),
                        LoProcesos.idServidor == (idServidor if idServidor else LoProcesos.idServidor)
                    ).order_by(LoProcesos.byte_fin.desc()).first()

                    if ultimo_proceso and ultimo_proceso.byte_fin >= tamano_archivo:
                        logger.info("Archivo ya procesado completamente")
                        return None

                    nuevo_proceso = LoProcesos(
                        idEmpresa=idEmpresa,
                        operador=operador,
                        idServidor=idServidor,
                        archivo=ruta_archivo,
                        byte_inicio=0,
                        byte_fin=tamano_archivo,
                        estado='PROCESANDO',
                        checksum=checksum,
                        bloque_size=tamano_archivo,
                        fechaInicio=datetime.now(),
                        intervaloMinutos=intervaloMinutos
                    )
                    db.session.add(nuevo_proceso)
                    db.session.commit()
                    return {
                        'idAuditoria': nuevo_proceso.idAuditoria,
                        'byte_inicio': 0,
                        'byte_fin': tamano_archivo,
                        'bloque_size': tamano_archivo
                    }

                bloque_size = bloque_size or 10485760 
                ultimo_proceso = db.session.query(LoProcesos).filter(
                    LoProcesos.archivo == ruta_archivo,
                    LoProcesos.estado.in_(['COMPLETADO', 'PROCESANDO']),
                    LoProcesos.idServidor == (idServidor if idServidor else LoProcesos.idServidor)
                ).with_for_update().order_by(LoProcesos.byte_fin.desc()).first()

                byte_inicio = ultimo_proceso.byte_fin + 1 if ultimo_proceso else 0

                if byte_inicio >= tamano_archivo:
                    nuevo_proceso = LoProcesos(
                        idEmpresa=idEmpresa,
                        operador=operador,
                        idServidor=idServidor,
                        archivo=ruta_archivo,
                        byte_inicio=ultimo_proceso.byte_fin if ultimo_proceso else 0,
                        byte_fin=tamano_archivo,
                        estado='COMPLETADO',
                        checksum=checksum,
                        bloque_size=0,
                        fechaInicio=datetime.now(),
                        fechaFin=datetime.now(),
                        totalLogsProcesados=0,
                        intervaloMinutos=intervaloMinutos
                    )
                    db.session.add(nuevo_proceso)
                    db.session.commit()
                    logger.info("Registro creado para archivo sin cambios")
                    return {
                        'idAuditoria': nuevo_proceso.idAuditoria,
                        'byte_inicio': nuevo_proceso.byte_inicio,
                        'byte_fin': nuevo_proceso.byte_fin,
                        'bloque_size': 0
                    }

                byte_fin = min(byte_inicio + bloque_size - 1, tamano_archivo)

                if (tamano_archivo - byte_fin) < 1048576:
                    byte_fin = tamano_archivo - 1

                nuevo_proceso = LoProcesos(
                    idEmpresa=idEmpresa,
                    operador=operador,
                    idServidor=idServidor,
                    archivo=ruta_archivo,
                    byte_inicio=byte_inicio,
                    byte_fin=byte_fin,
                    estado='PROCESANDO',
                    checksum=checksum,
                    bloque_size=bloque_size,
                    fechaInicio=datetime.now(),
                    intervaloMinutos=intervaloMinutos
                )
                db.session.add(nuevo_proceso)
                db.session.commit()
                return {
                    'idAuditoria': nuevo_proceso.idAuditoria,
                    'byte_inicio': byte_inicio,
                    'byte_fin': byte_fin,
                    'bloque_size': bloque_size
                }

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error al reservar bloque: {str(e)}")
                return None

#Método que marca proceso como fallido y lo desactiva
    @staticmethod
    def marcar_error(idAuditoria: int):
        """Marca un proceso como fallido y lo desactiva."""
        with app.app_context():
            proceso = LoProcesos.query.get(idAuditoria)
            if proceso:
                proceso.estado = 'FALLIDO'
                proceso.procesoActivo = False 
                proceso.fechaFin = datetime.now()  
                db.session.commit()
                logger.info(f"❌ Proceso {idAuditoria} marcado como FALLIDO y desactivado")

    
