from fastapi import FastAPI, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import hashlib
from flask import Flask 
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import time
import logging
from config import init_app, db
from datetime import datetime
from collections import defaultdict
from insertar import Logger
from metodos_loprocesos import ProcesosLogger
from modelo.loServidores import loServidores
from modelo.loProcesos import LoProcesos
from modelo.loLogs import loLogs
from modelo.loErrorconocido import loErrorconocido
from logs_procesados import router as logs_procesados_router
from logs_procesos import router as logs_procesos_router
from logs_servidor import router as servidores_router
from consumos.consulta_ia_openai import Consulta_ia_openai
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit


os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(logs_procesados_router)
app.include_router(logs_procesos_router)
app.include_router(servidores_router)

scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

flask_app = Flask(__name__)
init_app(flask_app)

RUTA_BASE_LOGS = "C:/Users/klever.robalino/Downloads/"
procesos_activos_por_archivo = {}

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())

class ProcesoConfig(BaseModel):
    activo: bool
    intervalo_minutos: int
    archivo: Optional[str] = None
    idServidor: Optional[int] = None
    tipoProceso: str = 'LOCAL'  

proceso_config = {
    "activo": False,
    "intervalo_minutos": 5,
    "archivo": None
}

def contar_logs_procesados(file_path: str) -> int:
    with open(file_path, 'r', encoding='utf-8') as file:
        return sum(1 for line in file if line.startswith('# Bloque encontrado'))

def consultar_openai_paralelo(logs: list) -> list:
    with ThreadPoolExecutor(max_workers=5) as executor:
        return list(executor.map(lambda log: Consulta_ia_openai().interpretar_logs(log), logs))

def extraer_bloques_log(chunk: str, offset_linea: int = 0) -> list:
    bloques = []
    bloque_actual = []
    linea_inicio = None
    lineas = chunk.splitlines(keepends=True)

    for i, linea in enumerate(lineas, start=offset_linea):
        if Logger.es_inicio_log(linea):
            nivel = Logger.extraer_nivel(linea)
            if nivel in ['INFO', 'DEBUG']:
                bloque_actual = []
                continue

            if bloque_actual:
                bloques.append({
                    'linea_inicio': linea_inicio,
                    'contenido': ''.join(bloque_actual)
                })
            bloque_actual = [linea]
            linea_inicio = i
        elif bloque_actual:
            if linea.startswith(("   ", "\t", "at ")):
                bloque_actual.append(linea)
            else:
                bloques.append({
                    'linea_inicio': linea_inicio,
                    'contenido': ''.join(bloque_actual)
                })
                bloque_actual = []

    if bloque_actual and Logger.extraer_nivel(bloque_actual[0]) not in ['INFO', 'DEBUG']:
        bloques.append({
            'linea_inicio': linea_inicio,
            'contenido': ''.join(bloque_actual)
        })
    return bloques

def insertar_logs_a_bd(reporte: dict, idServidor: int, idAuditoria: int) -> int:
    niveles_importantes = {'ERROR', 'FATAL', 'WARN'}
    logs_nuevos = []
    logs_a_insertar = []
    fecha_actual = datetime.now()

    try:
        with flask_app.app_context():
            for (nivel, categoria, _), datos in reporte.items():
                if nivel not in niveles_importantes:
                    continue

                mensaje_normalizado = datos['mensaje_normalizado']
                hash_error = hashlib.sha256(mensaje_normalizado.encode()).hexdigest()
                
                error_conocido = db.session.query(loErrorconocido).filter(
                    loErrorconocido.hasherror == hash_error,
                    loErrorconocido.nivel == nivel
                ).first()

                if not error_conocido and nivel in {'ERROR', 'FATAL'}:
                    logs_nuevos.append({
                        'hash': hash_error,
                        'mensaje': mensaje_normalizado,
                        'nivel': nivel
                    })

                logs_a_insertar.append({
                    'idEmpresa': 1,
                    'idServidor': idServidor,
                    'idAuditoria': idAuditoria,
                    'operador': 0,
                    'mensaje': mensaje_normalizado,
                    'nivel': nivel,
                    'componente': datos['componente'],
                    'hilo': datos['hilo'][:200] if datos['hilo'] else None,
                    'categoria': categoria,
                    'estado': 'ACTIVO',
                    'lineas': datos['lineas'],
                    'ocurrencias': datos['count'],
                    'respuestaOpenai': error_conocido.respuestaopenai if error_conocido else None,
                    'fechaCreacion': fecha_actual
                })

            if logs_nuevos:
                with ThreadPoolExecutor(max_workers=5) as executor:
                    respuestas = list(executor.map(
                        lambda log: Consulta_ia_openai().interpretar_logs(log['mensaje'][:2000]),
                        logs_nuevos
                    ))

                for log, respuesta in zip(logs_nuevos, respuestas):
                    for log_insertar in logs_a_insertar:
                        if log_insertar['mensaje'] == log['mensaje'] and log_insertar['nivel'] == log['nivel']:
                            log_insertar['respuestaOpenai'] = respuesta

                db.session.bulk_insert_mappings(loErrorconocido, [{
                    'hasherror': log['hash'],
                    'mensajenormalizado': log['mensaje'],
                    'nivel': log['nivel'],
                    'respuestaopenai': respuesta,
                    'fechaCreacion': fecha_actual
                } for log, respuesta in zip(logs_nuevos, respuestas)])

            db.session.bulk_insert_mappings(loLogs, logs_a_insertar)
            db.session.commit()

            # ===== NUEVA SECCIÓN =====
            logs_por_nivel = defaultdict(int)
            for (nivel, _, _), datos in reporte.items():
                if nivel in niveles_importantes:
                    logs_por_nivel[nivel] += datos['count']

            if logs_por_nivel:
                from websocket_server import manager
                import asyncio
                
                # Consulta los logs acumulados TOTALES (no solo los nuevos)
                logs_acumulados = db.session.query(
                    loLogs.nivel,
                    db.func.count(loLogs.idLogAplicacion)
                ).filter(
                    loLogs.idServidor == idServidor  # Sin filtro por tiempo
                ).group_by(loLogs.nivel).all()
                
                asyncio.run(manager.send_json_message({
                    "eventType": "metrics_update",
                    "data": {
                        "idServidor": idServidor,
                        "idAuditoria": idAuditoria,
                        "logs_por_nivel": {nivel: count for nivel, count in logs_acumulados},  # Acumulado total
                        "total_logs": sum(count for _, count in logs_acumulados),  # Total acumulado
                        "timestamp": fecha_actual.isoformat()
                    }
                }, id_empresa=1))
            # ===== FIN NUEVA SECCIÓN =====

            return len(logs_a_insertar)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error en inserción masiva: {str(e)}")
        return 0

def generar_reporte_logs(bloques: list, idServidor: int, idAuditoria: int) -> dict:
    logger.info(f"⏳ Inicio generación reporte para {len(bloques)} bloques")
    inicio_tiempo = time.time()
    
    reporte = defaultdict(lambda: {
        'count': 0,
        'lineas': [],
        'nivel': '',
        'categoria': '',
        'componente': '',
        'hilo': '',
        'mensaje': '',
        'mensaje_normalizado': ''
    })

    for i, bloque in enumerate(bloques, start=1):
        nivel = Logger.extraer_nivel(bloque['contenido'])
        if nivel not in ['WARN', 'ERROR', 'FATAL']:  
            continue
            
        lineas_bloque = bloque['contenido'].split('\n')
        Logger.procesar_bloque(lineas_bloque, str(bloque['linea_inicio']), reporte)
        
        if i % max(1, len(bloques)//10) == 0:
            logger.info(f"   🔹 Procesados {i}/{len(bloques)} bloques ({(i/len(bloques))*100:.1f}%)")

    duracion = time.time() - inicio_tiempo
    logger.info(f"✅ Reporte generado en {duracion:.2f} segundos. Logs únicos: {len(reporte)}")

    total_insertados = insertar_logs_a_bd(reporte, idServidor, idAuditoria)
    logger.info(f"✅ Insertados {total_insertados} logs en la BD")

    return reporte

def procesar_log_en_segundo_plano(nombre_archivo: str, idServidor: int, bloque_size: Optional[int] = None, intervalo_minutos: int = 1, tipoProceso: str = "LOCAL"):
    try:
        with flask_app.app_context():
            # 1. Verificar si ya está en proceso en BD
            proceso_activo = db.session.query(LoProcesos).filter(
                LoProcesos.archivo == nombre_archivo,
                LoProcesos.procesoActivo == True,
                LoProcesos.idServidor == idServidor
            ).first()
            
            if proceso_activo:
                logger.info("⏸️ El archivo %s ya está siendo procesado (ID Auditoría: %s)", nombre_archivo, proceso_activo.idAuditoria)
                return

            ruta_completa = os.path.join(RUTA_BASE_LOGS, nombre_archivo)
            
            # 2. Verificación de existencia del archivo
            if not os.path.exists(ruta_completa):
                logger.error("❌ Archivo no encontrado: %s", ruta_completa)
                return

            # 3. Reservar bloque, ahora pasando el intervalo
            bloque = ProcesosLogger.reservar_bloque(
                ruta_archivo=ruta_completa,
                idEmpresa=1,
                operador=0,
                idServidor=idServidor,
                bloque_size=bloque_size or min(os.path.getsize(ruta_completa) // 5, 25485760),
                forzar_completo=False,
                intervaloMinutos=intervalo_minutos,
                tipoProceso=tipoProceso 
            )

            if not bloque:
                logger.warning("⚠️ No se pudo reservar bloque. Posibles causas:\n"
                             "- El archivo está siendo usado por otro proceso\n"
                             "- No hay nuevos logs para procesar\n"
                             "- Error de conexión con la base de datos")
                return

            idAuditoria = bloque['idAuditoria']

            # 4. Verificación de servidor existente
            if not db.session.get(loServidores, idServidor):
                logger.error("🆔 Servidor no encontrado con ID: %d", idServidor)
                ProcesosLogger.marcar_error(idAuditoria)
                return

            tamaño_actual = os.path.getsize(ruta_completa)
            
            # 5. Verificación para archivo sin crecimiento
            if bloque['byte_fin'] >= tamaño_actual:
                if bloque['byte_fin'] == tamaño_actual:
                    logger.info("🔄 Archivo sin cambios | Tamaño actual: %d bytes | Último byte procesado: %d", 
                              tamaño_actual, bloque['byte_fin'])
                else:
                    logger.warning("⚠️ Archivo reducido de tamaño | Original: %d bytes | Actual: %d bytes",
                                 bloque['byte_fin'], tamaño_actual)
                
                ProcesosLogger.finalizar_proceso(
                    idAuditoria=idAuditoria,
                    totalLogs=0,
                    ultimo_byte=tamaño_actual
                )
                return

            # 6. Procesamiento de chunk de logs
            with open(ruta_completa, 'rb') as f:
                f.seek(bloque['byte_inicio'])
                chunk = f.read(bloque['byte_fin'] - bloque['byte_inicio'] + 1).decode('utf-8', errors='ignore')

            # 7. Conteo de líneas previas
            lineas_previas = 0
            if bloque['byte_inicio'] > 0:
                with open(ruta_completa, 'rb') as f:
                    f.seek(0)
                    lineas_previas = f.read(bloque['byte_inicio']).decode('utf-8', errors='ignore').count('\n')

            # 8. Extracción y procesamiento de bloques
            bloques_procesados = extraer_bloques_log(chunk, offset_linea=lineas_previas)
            if not bloques_procesados:
                logger.warning("ℹ️ No se encontraron bloques procesables en el chunk")
                ProcesosLogger.marcar_error(idAuditoria)
                return

            # 9. Generación de reporte
            reporte = generar_reporte_logs(bloques_procesados, idServidor, idAuditoria)
            total_logs = sum(datos['count'] for datos in reporte.values())

            # 10. Finalización del proceso y programación de siguiente ejecución
            proceso = db.session.query(LoProcesos).get(idAuditoria)
            mantener_activo = proceso.intervaloMinutos > 0 if proceso else False

            ProcesosLogger.finalizar_proceso(
                idAuditoria=idAuditoria,
                totalLogs=total_logs,
                ultimo_byte=bloque['byte_fin'],
                mantenerActivo=mantener_activo
            )
            
            logger.info("✅ Procesados %d logs | Archivo: %s", total_logs, nombre_archivo)

            # 11. Programar siguiente ejecución si mantener_activo es True
            if mantener_activo and proceso:
                intervalo = proceso.intervaloMinutos
                scheduler.add_job(
                    procesar_log_en_segundo_plano,
                    trigger=IntervalTrigger(minutes=intervalo),
                    args=[nombre_archivo, idServidor, bloque_size, intervalo],
                    id=f'log_processor_{idAuditoria}',
                    replace_existing=True
                )
                logger.info(f"⏳ Proceso {idAuditoria} programado para reprocesar en {intervalo} minutos")

    except Exception as e:
        logger.error("🔥 Error procesando %s: %s", nombre_archivo, str(e), exc_info=True)
        if 'idAuditoria' in locals():
            with flask_app.app_context():
                ProcesosLogger.marcar_error(idAuditoria)
    finally:
        logger.debug("🏁 Finalizado procesamiento para %s", nombre_archivo)
