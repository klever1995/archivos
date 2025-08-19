import re
import os
import time
from datetime import datetime
import hashlib
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from config import (
    flask_app, 
    RUTA_BASE_LOGS, 
    procesos_activos_por_archivo,
    PATRON_NIVEL,
    PATRON_COMPONENTE,
    PATRON_HILO,
    CATEGORIAS,
    PRIORIDAD,
    logger
)
from database_operations import insertar_logs_a_bd
from modelo.loServidores import loServidores
from modelo.loLogs import loLogs
from modelo.loErrorconocido import loErrorconocido
from metodos_loprocesos import ProcesosLogger
from consumos.consulta_ia_openai import Consulta_ia_openai

def es_inicio_log(linea: str) -> bool:
    return bool(re.match(r"\d{2}:\d{2}:\d{2},\d{3}", linea))

def extraer_nivel(linea: str) -> str:
    niveles = ['ERROR', 'FATAL', 'WARN', 'INFO', 'DEBUG']
    for nivel in niveles:
        if f' {nivel} ' in linea:
            return nivel
    return 'UNKNOWN'

def extraer_componente(linea: str) -> str:
    match = PATRON_COMPONENTE.search(linea)
    return match.group(1).strip() if match else "desconocido"

def extraer_hilo(linea: str) -> str:
    match = PATRON_HILO.search(linea)
    return match.group(1).strip() if match else "main"

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

def consultar_openai_paralelo(logs: list) -> list:
    with ThreadPoolExecutor(max_workers=5) as executor:
        return list(executor.map(lambda log: Consulta_ia_openai().interpretar_logs(log), logs))

def extraer_bloques_log(chunk: str, offset_linea: int = 0) -> list:
    bloques = []
    bloque_actual = []
    linea_inicio = None
    lineas = chunk.splitlines(keepends=True)

    for i, linea in enumerate(lineas, start=offset_linea):
        if es_inicio_log(linea):
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

    if bloque_actual:
        bloques.append({
            'linea_inicio': linea_inicio,
            'contenido': ''.join(bloque_actual)
        })
    return bloques

def procesar_bloque(bloque_actual, linea_inicio, reporte):
    mensaje_completo = "".join(bloque_actual).strip()
    nivel = extraer_nivel(mensaje_completo)
    categoria = categorizar_mensaje(mensaje_completo)
    componente = extraer_componente(mensaje_completo)
    hilo = extraer_hilo(mensaje_completo)

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
        logger.info(f"🔄 El archivo {nombre_archivo} ya está siendo procesado. Esperando...")
        return

    procesos_activos_por_archivo[nombre_archivo] = True
    idAuditoria = None

    try:
        with flask_app.app_context():
            servidor = db.session.get(loServidores, idServidor)
            if not servidor:
                logger.error("Servidor no válido")
                return

            ruta_completa = os.path.join(RUTA_BASE_LOGS, nombre_archivo)
            if not os.path.exists(ruta_completa):
                logger.error("Archivo no encontrado")
                return

            tamaño_archivo = os.path.getsize(ruta_completa)
            ultimo_byte_prev = ProcesosLogger.obtener_ultimo_byte_procesado(ruta_completa, idServidor)

            logger.info(f"📊 Tamaño actual del archivo: {tamaño_archivo} bytes")
            logger.info(f"📎 Último byte registrado anteriormente: {ultimo_byte_prev}")

            if tamaño_archivo <= ultimo_byte_prev:
                logger.info("🟠 El archivo no ha crecido. Registrando auditoría vacía...")

                idAuditoria = ProcesosLogger.iniciar_proceso(
                    idEmpresa=1,
                    operador=0,
                    idServidor=idServidor
                )
                if idAuditoria != -1:
                    ProcesosLogger.finalizar_proceso(
                        idAuditoria=idAuditoria,
                        totalLogs=0,
                        ultimo_byte=tamaño_archivo
                    )
                return

            bloque = ProcesosLogger.reservar_bloque(
                ruta_archivo=ruta_completa,
                idEmpresa=1,
                operador=0,
                idServidor=idServidor,
                bloque_size=bloque_size or min(tamaño_archivo // 5, 25485760),
                forzar_completo=False
            )

            if not bloque:
                logger.warning("⚠️ Error: se esperaba crecimiento pero no se pudo reservar bloque")
                return

            idAuditoria = bloque['idAuditoria']

            with open(ruta_completa, 'rb') as f:
                f.seek(bloque['byte_inicio'])
                chunk = f.read(bloque['byte_fin'] - bloque['byte_inicio'] + 1).decode('utf-8', errors='ignore')

            lineas_previas = 0
            if bloque['byte_inicio'] > 0:
                with open(ruta_completa, 'rb') as f:
                    f.seek(0)
                    lineas_previas = f.read(bloque['byte_inicio']).decode('utf-8', errors='ignore').count('\n')

            bloques_procesados = extraer_bloques_log(chunk, offset_linea=lineas_previas)
            reporte = generar_reporte_logs(bloques_procesados, idServidor, bloque['idAuditoria'])
            total_logs = sum(datos['count'] for datos in reporte.values())

            ProcesosLogger.finalizar_proceso(
                idAuditoria=bloque['idAuditoria'],
                totalLogs=total_logs,
                ultimo_byte=bloque['byte_fin']
            )

            logger.info(f"✅ Procesamiento finalizado. Total logs insertados: {total_logs}")

    except Exception as e:
        logger.error(f"❌ Error en procesamiento en background: {str(e)}", exc_info=True)
        if idAuditoria:
            with flask_app.app_context():
                ProcesosLogger.marcar_error(idAuditoria)
    finally:
        procesos_activos_por_archivo.pop(nombre_archivo, None)
