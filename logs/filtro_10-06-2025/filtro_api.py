from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import JSONResponse
import os
import sys
import re
import time
from difflib import SequenceMatcher
import hashlib
from flask import Flask
from collections import defaultdict
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


# --- Configuración idéntica a tu original ---
os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

flask_app = Flask(__name__)
init_app(flask_app)

RUTA_BASE_LOGS = "C:/Users/klever.robalino/Downloads/"

# Configuración para mantener tus prints en consola
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # URL de tu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(logs_procesados_router)
app.include_router(logs_procesos_router) 
app.include_router(servidores_router)

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

    # Normalización mejorada (como en tu código nuevo)
    mensaje_normalizado = re.sub(r'^\d{2}:\d{2}:\d{2},\d{3}\s*', '', mensaje_completo).strip()
    mensaje_normalizado = re.sub(r'\([^)]+\)', '(THREAD)', mensaje_normalizado)  # Normaliza hilos
    mensaje_normalizado = re.sub(r'\d+', '[NUM]', mensaje_normalizado)  # Normaliza números
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

    # Actualizar reporte
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
    total_logs = len(reporte)
    inicio_tiempo = time.time()

    for i, ((nivel, categoria, _), datos) in enumerate(reporte.items(), start=1):
        if nivel not in ['WARN', 'ERROR']:
            continue

        try:
            with flask_app.app_context():
                mensaje_normalizado = datos['mensaje_normalizado']
                hash_error = hashlib.sha256(mensaje_normalizado.encode()).hexdigest()

                error_conocido = db.session.query(loErrorconocido).filter(
                    loErrorconocido.hasherror == hash_error,
                    loErrorconocido.nivel == nivel
                ).first()

                respuesta_openai = None
                if error_conocido:
                    respuesta_openai = error_conocido.respuestaopenai
                elif nivel == 'ERROR':
                    mensaje_para_ia = limitar_longitud(mensaje_normalizado, max_len=2000)
                    respuesta_openai = consulta.interpretar_logs(mensaje_para_ia)

                    nuevo_error = loErrorconocido(
                        hasherror=hash_error,
                        mensajenormalizado=mensaje_normalizado,
                        nivel=nivel,
                        respuestaopenai=respuesta_openai
                    )
                    db.session.add(nuevo_error)

                hilo = datos['hilo'][:200] if datos['hilo'] else None  # Truncar hilo

                Logger.insertar_log(
                    idEmpresa=1,
                    idServidor=idServidor,
                    idAuditoria=idAuditoria,
                    operador=0,
                    mensaje=mensaje_normalizado,
                    nivel=nivel,
                    componente=datos['componente'],
                    hilo=hilo,
                    categoria=categoria,
                    estado='ACTIVO',
                    lineas=datos['lineas'],
                    ocurrencias=datos['count'],
                    respuestaOpenai=respuesta_openai
                )

                db.session.commit()
                total_insertados += 1

                # Log de progreso cada 10%
                if i % max(1, total_logs // 10) == 0:
                    logger.info(f"   🗃️ Insertados {i}/{total_logs} logs ({(i/total_logs)*100:.1f}%)")

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error insertando log: {str(e)}")

    duracion = time.time() - inicio_tiempo
    logger.info(f"⏳ Inserción finalizada en {duracion:.2f} segundos.")

    return total_insertados

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
        lineas_bloque = bloque['contenido'].split('\n')
        procesar_bloque(lineas_bloque, str(bloque['linea_inicio']), reporte)
        if i % max(1, len(bloques)//10) == 0:  # log cada 10%
            logger.info(f"   🔹 Procesados {i}/{len(bloques)} bloques ({(i/len(bloques))*100:.1f}%)")

    duracion = time.time() - inicio_tiempo
    logger.info(f"✅ Reporte generado en {duracion:.2f} segundos. Logs únicos: {len(reporte)}")

    # Luego insertar logs
    total_insertados = insertar_logs_a_bd(reporte, idServidor, idAuditoria)
    logger.info(f"✅ Insertados {total_insertados} logs en la BD")

    return reporte

# Endpoint para detener (Asegúrate de que sea POST)
@app.post("/proceso-detener/")
async def detener_proceso():
    proceso_config["activo"] = False
    return {"status": "proceso_detenido"}

# Endpoint para obtener configuración (verifica archivo)
@app.get("/proceso-config/")
async def obtener_config():
    return proceso_config

# --- Endpoints modificados ---
@app.post("/procesar-log/")
async def procesar_log(
    nombre_archivo: str = Form(...),
    idServidor: int = Form(...),
    bloque_size: int = Form(default=None)  # Parámetro opcional para tamaño personalizado
):
    bloque = None
    try:
        with flask_app.app_context():
            # 1. Validar servidor
            servidor = db.session.get(loServidores, idServidor)
            if not servidor:
                raise HTTPException(status_code=400, detail="Servidor no válido")

            # 2. Validar archivo
            ruta_completa = os.path.join(RUTA_BASE_LOGS, nombre_archivo)
            if not os.path.exists(ruta_completa):
                raise HTTPException(status_code=404, detail="Archivo no encontrado")

            # 3. Calcular tamaño de bloque dinámico (si no se especifica)
            tamaño_archivo = os.path.getsize(ruta_completa)
            bloque_size_recomendado = min(tamaño_archivo // 10, 10485760)  # 10% del archivo o 10MB máximo

            # 4. Reservar bloque de procesamiento
            bloque = ProcesosLogger.reservar_bloque(
                ruta_archivo=ruta_completa,
                idEmpresa=1,
                operador=0,
                idServidor=idServidor,
                bloque_size=bloque_size if bloque_size else bloque_size_recomendado
            )

            if not bloque:
                return JSONResponse(
                    status_code=200,
                    content={"status": "info", "details": "No hay logs nuevos para procesar"}
                )

            logger.info(f"🔷 Bloque procesado: bytes {bloque['byte_inicio']}-{bloque['byte_fin']} "
                       f"(Tamaño: {(bloque['byte_fin'] - bloque['byte_inicio']) / 1024 / 1024:.2f} MB)")

            # 5. Leer el chunk del archivo
            with open(ruta_completa, 'rb') as f:
                f.seek(bloque['byte_inicio'])
                chunk = f.read(bloque['byte_fin'] - bloque['byte_inicio'] + 1).decode('utf-8', errors='ignore')

            # 6. Contar líneas previas (para numeración exacta)
            lineas_previas = 0
            if bloque['byte_inicio'] > 0:
                with open(ruta_completa, 'rb') as f:
                    f.seek(0)
                    lineas_previas = f.read(bloque['byte_inicio']).decode('utf-8', errors='ignore').count('\n')

            # 7. Extraer y procesar bloques de logs
            bloques_procesados = extraer_bloques_log(chunk, offset_linea=lineas_previas)
            reporte = generar_reporte_logs(bloques_procesados, idServidor, bloque['idAuditoria'])
            total_logs = sum(datos['count'] for datos in reporte.values())

            # 8. Marcar como completado
            ProcesosLogger.finalizar_proceso(
                idAuditoria=bloque['idAuditoria'],
                totalLogs=total_logs,
                ultimo_byte=bloque['byte_fin']
            )

            return JSONResponse({
                "status": "success",
                "total_logs": total_logs,
                "bloque_procesado": {
                    "inicio": bloque['byte_inicio'],
                    "fin": bloque['byte_fin'],
                    "size_bytes": bloque['byte_fin'] - bloque['byte_inicio'],
                    "size_mb": round((bloque['byte_fin'] - bloque['byte_inicio']) / 1024 / 1024, 2)
                },
                "id_servidor": idServidor,
                "id_auditoria": bloque['idAuditoria']
            })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"⛔ Error en procesar-log: {str(e)}", exc_info=True)
        if bloque and 'idAuditoria' in bloque:
            with flask_app.app_context():
                ProcesosLogger.marcar_error(bloque['idAuditoria'])
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar el archivo: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
