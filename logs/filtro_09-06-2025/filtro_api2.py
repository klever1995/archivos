from fastapi import FastAPI, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse
import os
import sys
import re
import hashlib
from datetime import datetime
from difflib import SequenceMatcher
from flask import Flask
from collections import defaultdict
import asyncio
from insertar import Logger
from consumos.consulta_ia_openai import Consulta_ia_openai
from metodos_loprocesos import ProcesosLogger
from fastapi.middleware.cors import CORSMiddleware
from modelo.loServidores import loServidores  
from modelo.loProcesos import LoProcesos      
from modelo.loLogs import loLogs  
from modelo.loErrorconocido import loErrorconocido
from logs_procesados import router as logs_procesados_router
from logs_procesos import router as logs_procesos_router
from logs_servidor import router as servidores_router
import logging
from config import init_app, db
from pydantic import BaseModel
from typing import Optional

# --- Configuración inicial ---
os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

flask_app = Flask(__name__)
init_app(flask_app)

RUTA_BASE_LOGS = "C:/Users/Klever/Downloads/"

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(logs_procesados_router)
app.include_router(logs_procesos_router) 
app.include_router(servidores_router)

# --- Variables globales para control de procesos ---
procesos_activos = {}  # {id_servidor: {'tarea': task, 'intervalo': int}}

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

# --- Copia exacta de todas tus funciones originales ---
PRIORIDAD = ['ERROR', 'WARN', 'INFO', 'DEBUG', 'UNKNOWN']

CATEGORIAS = {
    'start_send': re.compile(r'inicia envio', re.IGNORECASE),
    'end_send': re.compile(r'fin envio', re.IGNORECASE),
    'ftp_error': re.compile(r'FTP.*ERROR', re.IGNORECASE),
    'general_error': re.compile(r'ERROR', re.IGNORECASE),
}

def es_inicio_log(linea: str) -> bool:
    return bool(re.match(r"\d{2}:\d{2}:\d{2},\d{3}", linea))

def extraer_componente(linea: str) -> str:
    match = re.search(r'\b(?:ERROR|WARN|INFO|DEBUG)\s+\[([^\]]+)\]', linea)
    return match.group(1).strip() if match else "desconocido"

def extraer_hilo(linea: str) -> str:
    match = re.search(r'\(([^)]+)\)', linea)
    return match.group(1).strip() if match else "main"

def extraer_nivel(linea: str) -> str:
    niveles = ['ERROR', 'WARN', 'INFO', 'DEBUG']
    for nivel in niveles:
        if f' {nivel} ' in linea:
            return nivel
    return 'UNKNOWN'

def categorizar_mensaje(texto: str) -> str:
    for categoria, patron in CATEGORIAS.items():
        if patron.search(texto):
            return categoria
    return 'otros'

def limitar_longitud(texto: str, max_len=30000):
    return texto if len(texto) <= max_len else texto[:max_len] + '...'

def prioridad_nivel(nivel):
    return PRIORIDAD.index(nivel) if nivel in PRIORIDAD else len(PRIORIDAD)

def contar_logs_procesados(file_path: str) -> int:
    with open(file_path, 'r', encoding='utf-8') as file:
        return sum(1 for line in file if line.startswith('# Bloque encontrado'))

def extraer_bloques_log(chunk: str, offset_linea: int = 0) -> list:
    bloques = []
    lineas = chunk.splitlines(keepends=True)
    bloque_actual = []
    en_bloque = False
    linea_inicio = None

    for i, linea in enumerate(lineas, start=offset_linea):
        if es_inicio_log(linea):
            if en_bloque:  
                bloques.append({
                    'linea_inicio': linea_inicio,
                    'contenido': "".join(bloque_actual)
                })
            bloque_actual = [linea]
            en_bloque = True
            linea_inicio = i
        elif en_bloque:
            if linea.startswith(("   ", "\t", "at ")):
                bloque_actual.append(linea)
            else:
                bloques.append({
                    'linea_inicio': linea_inicio,
                    'contenido': "".join(bloque_actual)
                })
                en_bloque = False
                bloque_actual = []

    if en_bloque and bloque_actual:
        bloques.append({
            'linea_inicio': linea_inicio,
            'contenido': "".join(bloque_actual)
        })
    return bloques

def procesar_bloque(bloque_actual, linea_inicio, reporte):
    mensaje_completo = "".join(bloque_actual).strip()
    nivel = extraer_nivel(mensaje_completo)
    categoria = categorizar_mensaje(mensaje_completo)
    componente = extraer_componente(mensaje_completo)
    hilo = extraer_hilo(mensaje_completo)

    # Normalización mejorada (agresiva con variables)
    mensaje_normalizado = re.sub(r'^\d{2}:\d{2}:\d{2},\d{3}\s*', '', mensaje_completo).strip()
    mensaje_normalizado = re.sub(r'\([^)]+\)', '(THREAD)', mensaje_normalizado)  # Normaliza todos los hilos
    mensaje_normalizado = re.sub(r'\d+', '[NUM]', mensaje_normalizado)
    if "FTP MKDIR" in mensaje_normalizado:
        mensaje_normalizado = re.sub(r"FTP MKDIR '.+?'", "FTP MKDIR '[DIR]'", mensaje_normalizado)
    mensaje_normalizado = mensaje_normalizado.lower()

    # Buscar clave existente similar (80%+)
    clave_existente = None
    for clave_actual in reporte:
        if (nivel == clave_actual[0] and 
            categoria == clave_actual[1] and 
            SequenceMatcher(None, mensaje_normalizado, clave_actual[2]).ratio() >= 0.8):
            clave_existente = clave_actual
            break

    clave = clave_existente if clave_existente else (nivel, categoria, mensaje_normalizado)

    # Actualizar reporte (sumar ocurrencias y líneas)
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

def insertar_logs_a_bd(reporte: dict, idServidor: int, idAuditoria: int) -> int:
    total_insertados = 0
    consulta = Consulta_ia_openai()
    
    for (nivel, categoria, _), datos in reporte.items():
        if nivel not in ['WARN', 'ERROR']:
            continue
            
        try:
            with flask_app.app_context():  # Asegurar contexto Flask
                # 1. Generar hash del mensaje normalizado
                mensaje_normalizado = datos['mensaje_normalizado']
                hash_error = hashlib.sha256(mensaje_normalizado.encode()).hexdigest()
                
                # 2. Buscar primero en errores conocidos (rápido)
                error_conocido = db.session.query(loErrorconocido).filter(
                    loErrorconocido.hasherror == hash_error,
                    loErrorconocido.nivel == nivel
                ).first()
                
                # 3. Determinar respuesta
                respuesta_openai = None
                if error_conocido:
                    respuesta_openai = error_conocido.respuestaopenai
                elif nivel == 'ERROR':
                    # Consultar IA solo para errores nuevos
                    mensaje_para_ia = limitar_longitud(mensaje_normalizado, max_len=2000)
                    respuesta_openai = consulta.interpretar_logs(mensaje_para_ia)
                    
                    # Registrar nuevo error conocido
                    nuevo_error = loErrorconocido(
                        hasherror=hash_error,
                        mensajenormalizado=mensaje_normalizado,
                        nivel=nivel,
                        respuestaopenai=respuesta_openai
                    )
                    db.session.add(nuevo_error)
                
                # 4. Insertar en logs (siempre)
                Logger.insertar_log(
                    idEmpresa=1,
                    idServidor=idServidor,
                    idAuditoria=idAuditoria,
                    operador=0,
                    mensaje=mensaje_normalizado,
                    nivel=nivel,
                    componente=datos['componente'],
                    hilo=datos['hilo'],
                    categoria=categoria,
                    estado='ACTIVO',
                    lineas=datos['lineas'],
                    ocurrencias=datos['count'],
                    respuestaOpenai=respuesta_openai
                )
                
                db.session.commit()  # Confirmar ambos inserts
                total_insertados += 1
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error insertando log: {str(e)}")
    
    return total_insertados

def generar_reporte_logs(bloques: list, idServidor: int, idAuditoria: int) -> dict: 
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

    for bloque in bloques:
        lineas_bloque = bloque['contenido'].split('\n')
        procesar_bloque(lineas_bloque, str(bloque['linea_inicio']), reporte)
    
    insertar_logs_a_bd(reporte, idServidor, idAuditoria)   # ¡Pasamos idServidor!
    return reporte

async def ejecutar_proceso_periodico(id_servidor: int, ruta_archivo: str, intervalo_minutos: int):
    """Ejecuta el proceso de monitoreo periódicamente con logging"""
    while id_servidor in procesos_activos:
        try:
            logger.info(f"🚀 Iniciando procesamiento periódico | Servidor {id_servidor} | Archivo: {ruta_archivo}")
            
            # Ejecutar el procesamiento del log
            inicio = datetime.now()
            resultado = await procesar_log_background(ruta_archivo, id_servidor)
            
            duracion = (datetime.now() - inicio).total_seconds()
            
            if resultado['success']:
                logger.info(f"✅ Procesamiento completado | Servidor {id_servidor} | "
                          f"Logs procesados: {resultado.get('total_logs', 0)} | "
                          f"Duración: {duracion:.2f}s")
            else:
                logger.error(f"❌ Error en procesamiento | Servidor {id_servidor} | "
                           f"Error: {resultado.get('error', 'Desconocido')}")
                
        except Exception as e:
            logger.error(f"🔥 Excepción no controlada | Servidor {id_servidor} | "
                        f"Error: {str(e)}")
            
        # Esperar el intervalo especificado
        logger.info(f"⏳ Esperando {intervalo_minutos} minuto(s) para próximo ciclo | Servidor {id_servidor}")
        await asyncio.sleep(intervalo_minutos * 60)

async def procesar_log_background(nombre_archivo: str, id_servidor: int):
    """Versión adaptada de tu función procesar_log para ejecución en background"""
    try:
        with flask_app.app_context():
            # Validar servidor
            servidor = db.session.get(loServidores, id_servidor)
            if not servidor:
                return {'success': False, 'error': 'Servidor no válido'}

            ruta_completa = os.path.join(RUTA_BASE_LOGS, nombre_archivo)
            if not os.path.exists(ruta_completa):
                return {'success': False, 'error': 'Archivo no encontrado'}

            # Procesamiento del log (igual que tu lógica original)
            bloque = ProcesosLogger.reservar_bloque(
                ruta_archivo=ruta_completa,
                idEmpresa=1,
                operador=0,
                idServidor=id_servidor,
                bloque_size=100_000_000
            )

            if not bloque:
                return {'success': True, 'message': 'No hay logs nuevos'}

            with open(ruta_completa, 'rb') as f:
                f.seek(bloque['byte_inicio'])
                chunk = f.read(bloque['byte_fin'] - bloque['byte_inicio'] + 1).decode('utf-8', errors='ignore')

            lineas_previas = 0
            if bloque['byte_inicio'] > 0:
                with open(ruta_completa, 'rb') as f:
                    f.seek(0)
                    lineas_previas = f.read(bloque['byte_inicio']).decode('utf-8', errors='ignore').count('\n')

            bloques_procesados = extraer_bloques_log(chunk, offset_linea=lineas_previas)
            reporte = generar_reporte_logs(bloques_procesados, id_servidor, bloque['idAuditoria'])
            total_logs = sum(datos['count'] for datos in reporte.values())

            ProcesosLogger.finalizar_proceso(
                idAuditoria=bloque['idAuditoria'],
                totalLogs=total_logs,
                ultimo_byte=bloque['byte_fin']
            )

            return {'success': True, 'total_logs': total_logs}
            
    except Exception as e:
        if bloque:
            with flask_app.app_context():
                ProcesosLogger.marcar_error(bloque.get('idAuditoria', 0))
        return {'success': False, 'error': str(e)}
    
# --- Endpoints modificados/agregados ---
@app.post("/monitoreo/iniciar/")
async def iniciar_monitoreo(
    background_tasks: BackgroundTasks,
    idServidor: int = Form(...),
    archivo: str = Form(...),
    intervalo_minutos: int = Form(5)
):
    """Inicia el monitoreo continuo para un servidor"""
    with flask_app.app_context():
        # Verificar si el servidor existe
        servidor = db.session.get(loServidores, idServidor)
        if not servidor:
            raise HTTPException(status_code=404, detail="Servidor no encontrado")

        # Registrar proceso en BD
        proceso_activo = db.session.query(LoProcesos).filter(
            LoProcesos.estado == "EN_EJECUCION",
            LoProcesos.fechaFin == None,
            LoProcesos.idServidor == idServidor
        ).first()
        
        if not proceso_activo:
            nuevo_proceso = LoProcesos(
                idEmpresa=1,
                idServidor=idServidor,
                operador=0,
                estado="EN_EJECUCION",
                fechaInicio=datetime.now()
            )
            db.session.add(nuevo_proceso)
            db.session.commit()

        # Iniciar tarea en background si no está ya activa
        if idServidor not in procesos_activos:
            procesos_activos[idServidor] = {
                'intervalo': intervalo_minutos,
                'archivo': archivo
            }
            background_tasks.add_task(
                ejecutar_proceso_periodico, 
                idServidor, 
                archivo, 
                intervalo_minutos
            )
            
            # Ejecutar inmediatamente el primer procesamiento
            await procesar_log_background(archivo, idServidor)
            
        return {"status": "monitoreo_iniciado", "id_servidor": idServidor}

@app.post("/monitoreo/detener/{idServidor}")
async def detener_monitoreo(idServidor: int):
    """Detiene el monitoreo para un servidor específico"""
    with flask_app.app_context():
        # Marcar proceso como detenido en BD
        db.session.query(LoProcesos).filter(
            LoProcesos.estado == "EN_EJECUCION",
            LoProcesos.fechaFin == None,
            LoProcesos.idServidor == idServidor
        ).update({
            "estado": "DETENIDO",
            "fechaFin": datetime.now()
        })
        db.session.commit()

        # Eliminar de procesos activos
        if idServidor in procesos_activos:
            del procesos_activos[idServidor]
            
        return {"status": "monitoreo_detenido", "id_servidor": idServidor}

@app.get("/monitoreo/estado/{idServidor}")
async def estado_monitoreo(idServidor: int):
    """Verifica el estado del monitoreo para un servidor"""
    activo = idServidor in procesos_activos
    return {
        "activo": activo,
        "detalles": procesos_activos.get(idServidor, {})
    }

# Endpoint para detener (Asegúrate de que sea POST)
@app.post("/proceso-iniciar/")
async def iniciar_proceso():
    with flask_app.app_context():
        # Verificar si ya hay un proceso activo
        proceso_activo = db.session.query(LoProcesos).filter(
            LoProcesos.estado == "EN_EJECUCION",
            LoProcesos.fechaFin == None
        ).first()
        
        if not proceso_activo:
            nuevo_proceso = LoProcesos(
                idEmpresa=1,
                operador=0,
                estado="EN_EJECUCION",
                fechaInicio=datetime.now()
            )
            db.session.add(nuevo_proceso)
            db.session.commit()
            proceso_config["activo"] = True  # Mantenemos compatibilidad
        return {"status": "proceso_iniciado"}

@app.post("/proceso-detener/")
async def detener_proceso():
    with flask_app.app_context():
        # Marcar TODOS los procesos activos como detenidos
        db.session.query(LoProcesos).filter(
            LoProcesos.estado == "EN_EJECUCION",
            LoProcesos.fechaFin == None
        ).update({
            "estado": "DETENIDO",
            "fechaFin": datetime.now()
        })
        db.session.commit()
        proceso_config["activo"] = False  # Para compatibilidad
        return {"status": "proceso_detenido"}

@app.get("/proceso-estado/")
async def estado_proceso():
    with flask_app.app_context():
        activo = db.session.query(LoProcesos).filter(
            LoProcesos.estado == "EN_EJECUCION",
            LoProcesos.fechaFin == None
        ).first() is not None
        return {"activo": activo}

@app.post("/procesar-log/")
async def procesar_log(
    nombre_archivo: str = Form(...),
    idServidor: int = Form(...)
):
    bloque = None
    try:
        with flask_app.app_context():
            # --- 1. Validar estado persistente (nuevo) ---
            proceso_activo = db.session.query(LoProcesos).filter(
                LoProcesos.estado == "EN_EJECUCION",
                LoProcesos.fechaFin == None
            ).first()
            
            if not proceso_activo:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "details": "Proceso no iniciado o fue detenido"}
                )

            # --- 2. Validaciones originales ---
            servidor = db.session.get(loServidores, idServidor)
            if not servidor:
                raise HTTPException(status_code=400, detail="Servidor no válido")

            ruta_completa = os.path.join(RUTA_BASE_LOGS, nombre_archivo)
            if not os.path.exists(ruta_completa):
                raise HTTPException(status_code=404, detail="Archivo no encontrado")

            # --- 3. Procesamiento original (sin cambios) ---
            bloque = ProcesosLogger.reservar_bloque(
                ruta_archivo=ruta_completa,
                idEmpresa=1,
                operador=0,
                idServidor=idServidor,
                bloque_size=10_000_000
            )

            if not bloque:
                return JSONResponse(
                    status_code=200,
                    content={"status": "info", "details": "No hay logs nuevos"}
                )
            logger.info(f"📌 Procesando bloque: bytes {bloque['byte_inicio']} a {bloque['byte_fin']}")

            # Procesar archivo
            with open(ruta_completa, 'rb') as f:
                f.seek(bloque['byte_inicio'])
                chunk = f.read(bloque['byte_fin'] - bloque['byte_inicio'] + 1).decode('utf-8', errors='ignore')

            lineas_previas = 0
            if bloque['byte_inicio'] > 0:
                with open(ruta_completa, 'rb') as f:
                    f.seek(0)
                    lineas_previas = f.read(bloque['byte_inicio']).decode('utf-8', errors='ignore').count('\n')

            bloques_procesados = extraer_bloques_log(chunk, offset_linea=lineas_previas)
            
            # --- 4. Insertar logs (con la mejora de errores conocidos que ya tienes) ---
            reporte = generar_reporte_logs(bloques_procesados, idServidor, bloque['idAuditoria'])
            total_logs = sum(datos['count'] for datos in reporte.values())

            ProcesosLogger.finalizar_proceso(
                idAuditoria=bloque['idAuditoria'],
                totalLogs=total_logs,
                ultimo_byte=bloque['byte_fin']
            )

            return JSONResponse({
                "status": "success",
                "total_logs": total_logs,
                "id_servidor": idServidor,
                "id_auditoria": bloque['idAuditoria'],
                "details": "Procesamiento completado"
            })

    except HTTPException:
        raise
    except Exception as e:
        if bloque:
            with flask_app.app_context():
                ProcesosLogger.marcar_error(bloque.get('idAuditoria', 0))
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
