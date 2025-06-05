from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import JSONResponse
import os
import sys
import re
from flask import Flask
from collections import defaultdict
from insertar import Logger
from consumos.consulta_ia_openai import Consulta_ia_openai
from metodos_loprocesos import ProcesosLogger
from fastapi.middleware.cors import CORSMiddleware
from modelo.loServidores import loServidores  
from modelo.loProcesos import LoProcesos      
from modelo.loLogs import loLogs  
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

    mensaje_normalizado = re.sub(r'^\d{2}:\d{2}:\d{2},\d{3}\s*', '', mensaje_completo).strip()
    
    if "FTP MKDIR" in mensaje_normalizado:
        mensaje_normalizado = re.sub(r'FTP MKDIR.*?ERROR', 'FTP MKDIR [DIRECTORIO] ERROR', mensaje_normalizado)

    clave = (nivel, categoria, mensaje_normalizado)
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

def insertar_logs_a_bd(reporte: dict, idServidor: int, idAuditoria: int) -> int:  # ¡Nuevo parámetro idServidor!
    total_insertados = 0
    consulta = Consulta_ia_openai()
    
    for (nivel, categoria, _), datos in reporte.items():
        if nivel not in ['WARN', 'ERROR']:
            continue
            
        try:
            # ¡Ahora usa idServidor en existe_error_en_bd!
            if not Logger.existe_error_en_bd(datos['mensaje_normalizado'], idServidor, nivel):
                respuesta_openai = None
                if nivel == 'ERROR':
                    mensaje_para_ia = limitar_longitud(datos['mensaje_normalizado'], max_len=2000)
                    respuesta_openai = consulta.interpretar_logs(mensaje_para_ia)
                
                # ¡Ahora pasa idServidor a insertar_log!
                Logger.insertar_log(
                    idEmpresa=1,
                    idServidor=idServidor,  # Nuevo campo
                    idAuditoria=idAuditoria,
                    operador=0,
                    mensaje=datos['mensaje_normalizado'],
                    nivel=nivel,
                    componente=datos['componente'],
                    hilo=datos['hilo'],
                    categoria=categoria,
                    estado='ACTIVO',
                    lineas=datos['lineas'],
                    ocurrencias=datos['count'],
                    respuestaOpenai=respuesta_openai
                )
                total_insertados += 1
        except Exception as e:
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
    idServidor: int = Form(...)
):
    bloque = None
    try:
        with flask_app.app_context():
            # Validar servidor
            servidor = db.session.get(loServidores, idServidor)
            if not servidor:
                raise HTTPException(status_code=400, detail="Servidor no válido")

            ruta_completa = os.path.join(RUTA_BASE_LOGS, nombre_archivo)
            if not os.path.exists(ruta_completa):
                raise HTTPException(status_code=404, detail="Archivo no encontrado")

            # Reservar bloque (devuelve dict con idAuditoria)
            bloque = ProcesosLogger.reservar_bloque(
                ruta_archivo=ruta_completa,
                idEmpresa=1,
                operador=0,
                idServidor=idServidor,
                bloque_size=1048576
            )

            if not bloque:
                return JSONResponse(
                    status_code=200,
                    content={"status": "info", "details": "No hay logs nuevos"}
                )

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
            
            # Pasar idAuditoria al generar reporte
            reporte = generar_reporte_logs(bloques_procesados, idServidor, bloque['idAuditoria'])  # Cambio clave
            
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
                "id_auditoria": bloque['idAuditoria'],  # Para debug
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
