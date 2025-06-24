

------------------------------------------------------respaldo de antes del temporizador----------------------------------------------
----------------------lo_procesos
from config import db
from datetime import datetime

#Clase de la tabla lo_procesos

class LoProcesos(db.Model):
    __tablename__ = 'LO_PROCESOS'
    
    idAuditoria = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    idServidor = db.Column(db.Integer, db.ForeignKey('LO_SERVIDORES.idServidor'), nullable=True)
    operador = db.Column(db.Integer, nullable=False)
    fechaInicio = db.Column(db.DateTime, default=datetime.now, nullable=False)
    fechaFin = db.Column(db.DateTime, nullable=True)
    totalLogsProcesados = db.Column(db.Integer, default=0, nullable=False)
    byte_inicio = db.Column(db.BigInteger, default=0)
    byte_fin = db.Column(db.BigInteger, nullable=True)
    ultimo_byte_procesado = db.Column(db.BigInteger, nullable=True)
    archivo = db.Column(db.String(255))
    checksum = db.Column(db.String(64))
    bloque_size = db.Column(db.Integer, default=1048576)
    estado = db.Column(db.String(20), nullable=True)

    empresa = db.relationship('asEmpresa', backref='procesos')
    servidor = db.relationship('loServidores', foreign_keys=[idServidor], backref='procesos')  # Relación explícita
    
    @property
    def duracionSegundos(self):
        if self.fechaFin and self.fechaInicio:
            return (self.fechaFin - self.fechaInicio).total_seconds()
        return None


---------------------insertar
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import re
import hashlib
from datetime import datetime
from difflib import SequenceMatcher
from collections import defaultdict
from flask import Flask
from config import init_app, db
from modelo.loLogs import loLogs
from modelo.loErrorconocido import loErrorconocido
from modelo.asEmpresa import asEmpresa



app = Flask(__name__)
init_app(app)

class Logger:
    PATRON_NIVEL = re.compile(r'\b(ERROR|FATAL|WARN|INFO|DEBUG)\b')
    PATRON_COMPONENTE = re.compile(r'\b(?:ERROR|WARN|INFO|DEBUG)\s+\[([^\]]+)\]')
    PATRON_HILO = re.compile(r'\(([^)]+)\)')
    PRIORIDAD = ['ERROR', 'FATAL', 'WARN', 'INFO', 'DEBUG', 'UNKNOWN']
    CATEGORIAS = {
        'start_send': re.compile(r'inicia envio', re.IGNORECASE),
        'end_send': re.compile(r'fin envio', re.IGNORECASE),
        'ftp_error': re.compile(r'FTP.*ERROR', re.IGNORECASE),
        'general_error': re.compile(r'ERROR', re.IGNORECASE),
    }

    @staticmethod
    def es_inicio_log(linea: str) -> bool:
        return bool(re.match(r"\d{2}:\d{2}:\d{2},\d{3}", linea))

    @staticmethod
    def extraer_componente(linea: str) -> str:
        match = re.search(r'\b(?:ERROR|WARN|INFO|DEBUG)\s+\[([^\]]+)\]', linea)
        return match.group(1).strip() if match else "desconocido"

    @staticmethod
    def extraer_hilo(linea: str) -> str:
        match = re.search(r'\(([^)]+)\)', linea)
        return match.group(1).strip() if match else "main"

    @staticmethod
    def extraer_nivel(linea: str) -> str:
        niveles = ['ERROR', 'FATAL', 'WARN', 'INFO', 'DEBUG']
        for nivel in niveles:
            if f' {nivel} ' in linea:
                return nivel
        return 'UNKNOWN'

    @staticmethod
    def categorizar_mensaje(texto: str) -> str:
        for categoria, patron in Logger.CATEGORIAS.items():
            if patron.search(texto):
                return categoria
        return 'otros'

    @staticmethod
    def limitar_longitud(texto: str, max_len=30000) -> str:
        return texto if len(texto) <= max_len else texto[:max_len] + '...'

    @staticmethod
    def prioridad_nivel(nivel: str) -> int:
        return Logger.PRIORIDAD.index(nivel) if nivel in Logger.PRIORIDAD else len(Logger.PRIORIDAD)

    @staticmethod
    def procesar_bloque(bloque_actual, linea_inicio, reporte):
        mensaje_completo = "".join(bloque_actual).strip()
        nivel = Logger.extraer_nivel(mensaje_completo)
        categoria = Logger.categorizar_mensaje(mensaje_completo)
        componente = Logger.extraer_componente(mensaje_completo)
        hilo = Logger.extraer_hilo(mensaje_completo)

        mensaje_normalizado = re.sub(r'^\d{2}:\d{2}:\d{2},\d{3}\s*', '', mensaje_completo).strip()
        mensaje_normalizado = re.sub(r'\([^)]+\)', '(THREAD)', mensaje_normalizado)
        mensaje_normalizado = re.sub(r'\d+', '[NUM]', mensaje_normalizado)
        mensaje_normalizado = mensaje_normalizado.lower()

        clave_existente = None
        for clave_actual in reporte:
            if (nivel == clave_actual[0] and 
                categoria == clave_actual[1] and 
                SequenceMatcher(None, mensaje_normalizado, clave_actual[2]).ratio() >= 0.8):
                clave_existente = clave_actual
                break

        clave = clave_existente if clave_existente else (nivel, categoria, mensaje_normalizado)
        reporte[clave].update({
            'count': reporte[clave]['count'] + 1,
            'lineas': reporte[clave]['lineas'] + [linea_inicio],
            'nivel': nivel,
            'categoria': categoria,
            'componente': componente,
            'hilo': hilo,
            'mensaje': mensaje_completo,
            'mensaje_normalizado': mensaje_normalizado
        })



-----------------------------metodos_loprocesos
import sys
import os
import hashlib
from flask import Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import init_app, db 
from typing import Optional, Dict, Union
from modelo.loProcesos import LoProcesos
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

    @staticmethod
    def iniciar_proceso(idEmpresa: int, operador: int, idServidor: int = None) -> int:
        """Registra el inicio de un nuevo proceso, opcionalmente asociado a un servidor."""
        with app.app_context():
            try:
                nuevo_proceso = LoProcesos(
                    idEmpresa=idEmpresa,
                    operador=operador,
                    idServidor=idServidor,
                    fechaInicio=datetime.now(),
                    totalLogsProcesados=0,
                    estado='PROCESANDO'
                )
                db.session.add(nuevo_proceso)
                db.session.commit()
                print("✅ Proceso iniciado correctamente.")
                return nuevo_proceso.idAuditoria
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error al iniciar proceso: {e}")
                return -1

    @staticmethod
    def finalizar_proceso(idAuditoria: int, totalLogs: int, ultimo_byte: int) -> bool:
        """Marca el fin de un proceso y actualiza métricas de forma ATÓMICA."""
        with app.app_context():
            db.session.begin()  # Inicia transacción explícita
            try:
                proceso = LoProcesos.query.get(idAuditoria)
                if proceso:
                    proceso.fechaFin = datetime.now()
                    proceso.totalLogsProcesados = totalLogs
                    proceso.ultimo_byte_procesado = ultimo_byte
                    proceso.estado = 'COMPLETADO'
                    db.session.commit()  # Confirmar cambios
                    print(f"✅ Proceso {idAuditoria} finalizado y persistido en DB.")
                    return True
                return False
            except Exception as e:
                db.session.rollback()  # Revertir en caso de error
                print(f"❌ Error al finalizar proceso {idAuditoria}: {e}")
                return False

    @staticmethod
    def calcular_checksum(ruta_archivo: str) -> str:
        """Genera SHA-256 del archivo."""
        hash_sha256 = hashlib.sha256()
        with open(ruta_archivo, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    @staticmethod
    def reservar_bloque(
        ruta_archivo: str,
        idEmpresa: int,
        operador: int,
        idServidor: int = None,
        bloque_size: int = None,
        forzar_completo: bool = False
    ) -> Optional[Dict[str, Union[int, str]]]:
        with app.app_context():
            try:
                if not os.path.exists(ruta_archivo):
                    logger.error(f"Archivo no encontrado: {ruta_archivo}")
                    return None

                checksum = ProcesosLogger.calcular_checksum(ruta_archivo)
                tamano_archivo = os.path.getsize(ruta_archivo)

                # Procesamiento completo para archivos pequeños o forzados
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
                        fechaInicio=datetime.now()
                    )
                    db.session.add(nuevo_proceso)
                    db.session.commit()
                    return {
                        'idAuditoria': nuevo_proceso.idAuditoria,
                        'byte_inicio': 0,
                        'byte_fin': tamano_archivo,
                        'bloque_size': tamano_archivo
                    }

                # Procesamiento por bloques
                bloque_size = bloque_size or 10485760  # 10MB por defecto
                ultimo_proceso = db.session.query(LoProcesos).filter(
                    LoProcesos.archivo == ruta_archivo,
                    LoProcesos.estado.in_(['COMPLETADO', 'PROCESANDO']),
                    LoProcesos.idServidor == (idServidor if idServidor else LoProcesos.idServidor)
                ).with_for_update().order_by(LoProcesos.byte_fin.desc()).first()

                byte_inicio = ultimo_proceso.byte_fin + 1 if ultimo_proceso else 0

                # MODIFICACIÓN CLAVE: Registrar incluso si no hay crecimiento
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
                        totalLogsProcesados=0
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
                
                # Si queda menos de 1MB, procesar hasta el final
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
                    fechaInicio=datetime.now()
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

    @staticmethod
    def marcar_error(idAuditoria: int):
        """Marca un proceso como fallido."""
        with app.app_context():
            proceso = LoProcesos.query.get(idAuditoria)
            if proceso:
                proceso.estado = 'FALLIDO'
                db.session.commit()

    @staticmethod
    def obtener_ultimo_byte_procesado(ruta_archivo: str, idServidor: int = None) -> int:
        """Obtiene el último byte procesado para un archivo (y servidor, si se especifica)."""
        with app.app_context():
            try:
                query = db.session.query(LoProcesos).filter(
                    LoProcesos.archivo == ruta_archivo,
                    LoProcesos.estado == 'COMPLETADO'
                )
                if idServidor:
                    query = query.filter(LoProcesos.idServidor == idServidor)

                ultimo_proceso = query.order_by(LoProcesos.byte_fin.desc()).first()
                return ultimo_proceso.byte_fin if ultimo_proceso else 0
            except Exception as e:
                print(f"❌ Error obteniendo último byte: {e}")
                return 0


------------------------------------servicios
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

def procesar_log_en_segundo_plano(nombre_archivo: str, idServidor: int, bloque_size: Optional[int] = None):
    global procesos_activos_por_archivo

    if nombre_archivo in procesos_activos_por_archivo:
        logger.info("⏸️ El archivo %s ya está siendo procesado", nombre_archivo)
        return

    procesos_activos_por_archivo[nombre_archivo] = True
    idAuditoria = None

    try:
        with flask_app.app_context():
            ruta_completa = os.path.join(RUTA_BASE_LOGS, nombre_archivo)
            
            # Verificación mejorada de existencia del archivo
            if not os.path.exists(ruta_completa):
                logger.error("❌ Archivo no encontrado: %s", ruta_completa)
                procesos_activos_por_archivo.pop(nombre_archivo, None)
                return

            # 1. Reservar bloque con verificación mejorada
            bloque = ProcesosLogger.reservar_bloque(
                ruta_archivo=ruta_completa,
                idEmpresa=1,
                operador=0,
                idServidor=idServidor,
                bloque_size=bloque_size or min(os.path.getsize(ruta_completa) // 5, 25485760),
                forzar_completo=False
            )

            if not bloque:
                logger.warning("⚠️ No se pudo reservar bloque. Posibles causas:\n"
                             "- El archivo está siendo usado por otro proceso\n"
                             "- No hay nuevos logs para procesar\n"
                             "- Error de conexión con la base de datos")
                procesos_activos_por_archivo.pop(nombre_archivo, None)
                return

            # 2. Verificación de servidor existente
            if not db.session.get(loServidores, idServidor):
                logger.error("🆔 Servidor no encontrado con ID: %d", idServidor)
                ProcesosLogger.marcar_error(bloque['idAuditoria'])
                procesos_activos_por_archivo.pop(nombre_archivo, None)
                return

            tamaño_actual = os.path.getsize(ruta_completa)
            
            # 3. Verificación MEJORADA para archivo sin crecimiento
            if bloque['byte_fin'] >= tamaño_actual:
                if bloque['byte_fin'] == tamaño_actual:
                    logger.info("🔄 Archivo sin cambios | Tamaño actual: %d bytes | Último byte procesado: %d", 
                              tamaño_actual, bloque['byte_fin'])
                else:
                    logger.warning("⚠️ Archivo reducido de tamaño | Original: %d bytes | Actual: %d bytes",
                                 bloque['byte_fin'], tamaño_actual)
                
                ProcesosLogger.finalizar_proceso(
                    idAuditoria=bloque['idAuditoria'],
                    totalLogs=0,
                    ultimo_byte=tamaño_actual
                )
                procesos_activos_por_archivo.pop(nombre_archivo, None)
                return

            # 4. Procesamiento de chunk de logs
            with open(ruta_completa, 'rb') as f:
                f.seek(bloque['byte_inicio'])
                chunk = f.read(bloque['byte_fin'] - bloque['byte_inicio'] + 1).decode('utf-8', errors='ignore')

            # 5. Conteo de líneas previas
            lineas_previas = 0
            if bloque['byte_inicio'] > 0:
                with open(ruta_completa, 'rb') as f:
                    f.seek(0)
                    lineas_previas = f.read(bloque['byte_inicio']).decode('utf-8', errors='ignore').count('\n')

            # 6. Extracción y procesamiento de bloques
            bloques_procesados = extraer_bloques_log(chunk, offset_linea=lineas_previas)
            if not bloques_procesados:
                logger.warning("ℹ️ No se encontraron bloques procesables en el chunk")
                ProcesosLogger.marcar_error(bloque['idAuditoria'])
                procesos_activos_por_archivo.pop(nombre_archivo, None)
                return

            # 7. Generación de reporte
            reporte = generar_reporte_logs(bloques_procesados, idServidor, bloque['idAuditoria'])
            total_logs = sum(datos['count'] for datos in reporte.values())

            # 8. Finalización del proceso
            ProcesosLogger.finalizar_proceso(
                idAuditoria=bloque['idAuditoria'],
                totalLogs=total_logs,
                ultimo_byte=bloque['byte_fin']
            )
            logger.info("✅ Procesados %d logs | Archivo: %s", total_logs, nombre_archivo)

    except Exception as e:
        logger.error("🔥 Error procesando %s: %s", nombre_archivo, str(e), exc_info=True)
        if idAuditoria:
            with flask_app.app_context():
                ProcesosLogger.marcar_error(idAuditoria)
    finally:
        if nombre_archivo in procesos_activos_por_archivo:
            procesos_activos_por_archivo.pop(nombre_archivo, None)
        logger.debug("🏁 Finalizado procesamiento para %s", nombre_archivo)


--------------------main 
from fastapi import FastAPI, BackgroundTasks, Form, HTTPException
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

# Variables globales
proceso_activo = False
procesos_activos_por_archivo = {}  # Nuevo: Para sincronización entre endpoints

@app.post("/proceso-detener/")
async def detener_proceso():
    global proceso_activo
    proceso_activo = False
    proceso_config["activo"] = False
    return {"status": "proceso_detenido", "activo": False}

@app.get("/proceso-estado/")  
async def obtener_estado():
    return {
        "activo": proceso_activo,
        "archivos_procesando": list(procesos_activos_por_archivo.keys())  # Nuevo
    }

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
    global proceso_activo, procesos_activos_por_archivo
    
    if nombre_archivo in procesos_activos_por_archivo:  # Nuevo: Verificación
        raise HTTPException(
            status_code=400,
            detail=f"El archivo {nombre_archivo} ya está siendo procesado"
        )
    
    proceso_activo = True
    proceso_config["activo"] = True
    proceso_config["archivo"] = nombre_archivo
    proceso_config["idServidor"] = idServidor
    
    background_tasks.add_task(
        procesar_log_en_segundo_plano, 
        nombre_archivo, 
        idServidor, 
        bloque_size
    )
    
    return {
        "status": "procesamiento_iniciado",
        "activo": True,
        "archivo": nombre_archivo
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
