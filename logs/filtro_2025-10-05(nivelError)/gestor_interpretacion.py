from dotenv import load_dotenv
load_dotenv()
import os
import sys
import re
import time
import hashlib
from sqlalchemy import func
from datetime import datetime
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from modelo.asEmpresa import asEmpresa
from modelo.loServidores import loServidores
from modelo.loProcesos import LoProcesos
from modelo.loLogsremotos import loLogsremotos
from modelo.loErrorconocido import loErrorconocido
from modelo.loLogs import loLogs
from modelo.loInterpretacionremota import loInterpretacionremota
from config import db, init_app
from flask import Flask

from servicios.consulta_ia_openai import Consulta_ia_openai

os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'

app = Flask(__name__)
init_app(app)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def determinar_nivel_error_automatico(nivel_original, mensaje):
    """Determina el nivel de error automáticamente basado en el nivel original y contenido"""
    if nivel_original == 'WARN':
        return 'leve'

    mensaje_lower = (mensaje or "").lower()

    criticos = ['fatal', 'crash', 'shutdown', 'out of memory', 'memory leak',
                'data loss', 'corruption', 'cannot start', 'failed to start',
                'unable to connect', 'connection refused', 'access denied']

    leves = ['timeout', 'retry', 'temporary', 'warning', 'deprecated', 'slow']

    if any(p in mensaje_lower for p in criticos):
        return 'crítico'
    elif any(p in mensaje_lower for p in leves):
        return 'leve'
    else:
        return 'crítico' if nivel_original == 'FATAL' else 'normal'


def extraer_nivel_error_respuesta(respuesta_ia):
    """
    Extrae el nivel de error de la respuesta de IA y lo remueve del texto.
    Soporta variantes: "NIVEL: ...", "NIVEL DE CRITICIDAD: ...", con/without acentos,
    con ":" o "-" u otros separadores y en mayúsculas/minúsculas.
    Retorna (nivel_extraido_o_None, respuesta_limpia).
    """

    if not respuesta_ia:
        return None, respuesta_ia

    texto = respuesta_ia

    # Patron multiline para líneas que empiecen por "NIVEL" o "NIVEL DE CRITICIDAD" o "CRITICIDAD"
    patron_linea = re.compile(
        r'(?im)^\s*(?:nivel(?:\s+de\s+cr[ií]ticidad)?|criticidad)\s*[:\-–—]?\s*(leve|normal|cr[ií]tico|critico)\b.*$',
        flags=re.UNICODE | re.MULTILINE
    )

    match = patron_linea.search(texto)
    nivel = None
    if match:
        raw = match.group(1).lower()
        if raw.startswith('crit'):
            nivel = 'crítico'
        elif raw.startswith('nor'):
            nivel = 'normal'
        elif raw.startswith('lev'):
            nivel = 'leve'
        else:
            nivel = raw
        # quitar todas las ocurrencias de este tipo
        texto = patron_linea.sub('', texto).strip()
    else:
        # si no encontramos como línea, probamos a buscar inline en cualquier parte del texto
        patron_inline = re.compile(r'(?i)(?:nivel(?:\s+de\s+cr[ií]ticidad)?|criticidad)\s*[:\-–—]?\s*(leve|normal|cr[ií]tico|critico)\b')
        m2 = patron_inline.search(texto)
        if m2:
            raw = m2.group(1).lower()
            if raw.startswith('crit'):
                nivel = 'crítico'
            elif raw.startswith('nor'):
                nivel = 'normal'
            elif raw.startswith('lev'):
                nivel = 'leve'
            else:
                nivel = raw
            texto = patron_inline.sub('', texto).strip()

    # limpiar saltos de línea múltiples dejados por la eliminación
    texto = re.sub(r'\n{2,}', '\n', texto).strip()

    return nivel, texto


def _parsear_respuesta_bloque_con_logs(respuesta_bloque, logs_nuevos):
    """
    Parsing robusto: divide la respuesta de la IA por bloques 'LOG X (ID: Y):' usando lookahead.
    Devuelve (dict_respuestas_por_hash, dict_niveles_por_hash).
    """
    respuestas = {}
    niveles = {}

    if not respuesta_bloque or not logs_nuevos:
        return respuestas, niveles

    # Eliminar separadores visuales que pudo devolver la IA
    texto = respuesta_bloque.replace('🔹🔹🔹', '\n')

    # Dividir tomando cada bloque que empiece por "LOG <n>"
    chunks = re.split(r'(?im)(?=^\s*log\s+\d+\b)', texto.strip())
    for chunk in chunks:
        if not chunk.strip():
            continue
        header_match = re.match(r'(?im)^\s*log\s+(\d+)\s*(?:\(\s*id\s*[:\s]*([0-9]+)\s*\))?\s*[:\-–—]?\s*', chunk)
        if not header_match:
            # no es un bloque encabezado; saltarlo
            continue

        numero_log = int(header_match.group(1))
        id_en_header = header_match.group(2)
        contenido = chunk[header_match.end():].strip()

        nivel_extraido, respuesta_limpia = extraer_nivel_error_respuesta(contenido)

        # intentar emparejar por ID del header si existe
        match_index = None
        if id_en_header:
            for idx, l in enumerate(logs_nuevos):
                if str(l.get('id_log_remoto')) == str(id_en_header):
                    match_index = idx
                    break

        # si no hay ID, intentar por posición (LOG 1 -> index 0)
        if match_index is None and 0 <= (numero_log - 1) < len(logs_nuevos):
            match_index = numero_log - 1

        # fallback: si no encontramos por id o numero, intentar tomar siguiente no asignado por orden
        if match_index is None:
            # intentar encontrar primer índice de logs_nuevos que aún no esté en respuestas
            for idx, l in enumerate(logs_nuevos):
                if l['hash_error'] not in respuestas:
                    match_index = idx
                    break

        if match_index is None:
            # ya no hay donde asignar: saltamos
            continue

        log_actual = logs_nuevos[match_index]
        respuestas[log_actual['hash_error']] = respuesta_limpia
        niveles[log_actual['hash_error']] = nivel_extraido

    return respuestas, niveles


# Método que interpreta logs remotos con IA
def interpretar_logs_remotos(id_servidor: int, batch_size: int = 100) -> bool:
    with app.app_context():
        try:
            servidor = db.session.get(loServidores, id_servidor)
            if not servidor:
                raise ValueError("ID de servidor inválido")

            # Obtengo el último log procesado (valor inicial 0 si no hay)
            ultimo_id = db.session.query(
                func.max(loInterpretacionremota.ultimoLogProcesado)
            ).filter_by(idServidor=id_servidor).scalar() or 0

            ultimo_proceso_id = db.session.query(LoProcesos.idAuditoria).filter_by(
                idServidor=id_servidor
            ).order_by(LoProcesos.idAuditoria.desc()).first()
            if ultimo_proceso_id:
                id_proceso_filtrado = ultimo_proceso_id.idAuditoria
            else:
                id_proceso_filtrado = None

            interpretacion = loInterpretacionremota(
                idProcesoFiltrado=id_proceso_filtrado,
                idServidor=id_servidor,
                fechaInicio=datetime.now(),
                estado='PROCESANDO',
                ultimoLogProcesado=ultimo_id,
                totalLogsInterpretados=0
            )
            db.session.add(interpretacion)
            db.session.flush()

            logs = db.session.query(loLogsremotos).filter(
                loLogsremotos.idServidor == id_servidor,
                loLogsremotos.idLogRemoto > ultimo_id
            ).order_by(loLogsremotos.idLogRemoto).limit(batch_size).all()

            if not logs:
                interpretacion.estado = 'COMPLETADO'
                interpretacion.fechaFin = datetime.now()
                db.session.commit()
                logger.info(f"No hay logs nuevos en servidor {id_servidor}.")
                return True

            logs_nuevos = []
            logs_a_guardar = []
            fecha_actual = datetime.now()
            consulta_ia = Consulta_ia_openai()

            for log in logs:
                # Normalizar mensaje antes de hashear y de enviar a IA
                mensaje_normalizado = re.sub(r'\d+', '[NUM]', (log.mensaje or "").lower())
                hash_error = hashlib.sha256(mensaje_normalizado.encode()).hexdigest()

                error_conocido = db.session.query(loErrorconocido).filter_by(
                    hasherror=hash_error,
                    nivel=log.nivel
                ).first()

                if not error_conocido and log.nivel in {'ERROR', 'FATAL'}:
                    # Guardar la versión normalizada (truncada para IA si hace falta)
                    logs_nuevos.append({
                        'log': log,
                        'mensaje_normalizado': mensaje_normalizado[:2000],
                        'hash_error': hash_error,
                        'id_log_remoto': log.idLogRemoto
                    })

                logs_a_guardar.append({
                    'log': log,
                    'hash_error': hash_error,
                    'error_conocido': error_conocido
                })

            respuestas_ia = {}
            niveles_error_ia = {}

            if logs_nuevos:
                try:
                    logger.info(f"🔎 Preparando bloque de {len(logs_nuevos)} logs para IA...")

                    bloque_logs = ""
                    for i, loginfo in enumerate(logs_nuevos):
                        bloque_logs += f"LOG {i+1} (ID: {loginfo['id_log_remoto']}):\n{loginfo['mensaje_normalizado']}\n🔹🔹🔹\n"

                    # quitar último separador si existe
                    bloque_logs = bloque_logs.rsplit('🔹🔹🔹', 1)[0]

                    inicio = time.time()
                    respuesta_bloque = consulta_ia.interpretar_logs(bloque_logs)
                    duracion = time.time() - inicio

                    if not respuesta_bloque or not isinstance(respuesta_bloque, str):
                        logger.error("🛑 Respuesta inválida de IA para el bloque de logs")
                        raise ValueError("Respuesta de IA inválida")

                    logger.info(f"✅ IA respondió en {duracion:.2f}s para {len(logs_nuevos)} logs")

                    # Parsing robusto usando la función dedicada
                    respuestas_ia, niveles_error_ia = _parsear_respuesta_bloque_con_logs(respuesta_bloque, logs_nuevos)

                    # Persistir errores nuevos
                    for loginfo in logs_nuevos:
                        hash_e = loginfo['hash_error']
                        nivel_error = niveles_error_ia.get(hash_e)
                        respuesta_limpia = respuestas_ia.get(hash_e)
                        if respuesta_limpia:
                            nuevo_error = loErrorconocido(
                                hasherror=hash_e,
                                mensajenormalizado=loginfo['mensaje_normalizado'],
                                nivel=loginfo['log'].nivel,
                                respuestaopenai=respuesta_limpia,
                                nivelError=nivel_error,
                                fechaprimeraocurrencia=fecha_actual,
                                fechaultimaactualizacion=fecha_actual
                            )
                            db.session.add(nuevo_error)

                    db.session.commit()

                except Exception as e:
                    logger.error(f"Error al consultar IA en bloque: {str(e)}", exc_info=True)
                    db.session.rollback()

                    # Fallback individual por log
                    logger.info("🔄 Intentando procesamiento individual como fallback...")
                    respuestas_ia = {}
                    niveles_error_ia = {}
                    for loginfo in logs_nuevos:
                        try:
                            respuesta_individual = consulta_ia.interpretar_logs(loginfo['mensaje_normalizado'])
                            if respuesta_individual and isinstance(respuesta_individual, str):
                                nivel_error, respuesta_limpia = extraer_nivel_error_respuesta(respuesta_individual)
                                respuestas_ia[loginfo['hash_error']] = respuesta_limpia
                                niveles_error_ia[loginfo['hash_error']] = nivel_error

                                nuevo_error = loErrorconocido(
                                    hasherror=loginfo['hash_error'],
                                    mensajenormalizado=loginfo['mensaje_normalizado'],
                                    nivel=loginfo['log'].nivel,
                                    respuestaopenai=respuesta_limpia,
                                    nivelError=nivel_error,
                                    fechaprimeraocurrencia=fecha_actual,
                                    fechaultimaactualizacion=fecha_actual
                                )
                                db.session.add(nuevo_error)
                        except Exception as e_individual:
                            logger.error(f"❌ Fallo individual en log {loginfo['log'].idLogRemoto}: {str(e_individual)}", exc_info=True)
                    db.session.commit()

            # Guardar logs procesados (todos)
            logs_insertar = []
            for item in logs_a_guardar:
                if item['error_conocido']:
                    respuesta = item['error_conocido'].respuestaopenai
                    nivel_error = item['error_conocido'].nivelError
                else:
                    respuesta = respuestas_ia.get(item['hash_error'])
                    nivel_error = niveles_error_ia.get(item['hash_error'])

                # Si IA no dio nivel, determinamos automáticamente
                nivel_error_final = nivel_error if nivel_error else determinar_nivel_error_automatico(
                    item['log'].nivel,
                    item['log'].mensaje
                )

                logs_insertar.append(loLogs(
                    idEmpresa=servidor.idEmpresa,
                    idServidor=id_servidor,
                    idAuditoria=item['log'].idAuditoria,
                    operador=0,
                    nivel=item['log'].nivel,
                    componente=item['log'].componente,
                    hilo=item['log'].hilo,
                    mensaje=item['log'].mensaje,
                    categoria=item['log'].categoria,
                    ocurrencias=item['log'].ocurrencias,
                    lineas=[str(l) for l in item['log'].lineas] if item['log'].lineas else [],
                    respuestaOpenai=respuesta if (item['log'].nivel in {'ERROR', 'FATAL'} and respuesta) else None,
                    nivelError=nivel_error_final,
                    fechaCreacion=fecha_actual
                ))

                interpretacion.ultimoLogProcesado = max(
                    interpretacion.ultimoLogProcesado or 0,
                    item['log'].idLogRemoto
                )

            interpretacion.totalLogsInterpretados = len(logs_insertar)

            if logs_insertar:
                db.session.bulk_save_objects(logs_insertar)
                logger.info(f"💽 Guardados {len(logs_insertar)} logs nuevos (IDs desde {min(log.idLogRemoto for log in logs)} hasta {max(log.idLogRemoto for log in logs)})")

            interpretacion.estado = 'COMPLETADO'
            interpretacion.fechaFin = datetime.now()
            db.session.commit()

            logger.info(f"📊 Interpretación completada. Logs nuevos procesados: {len(logs_insertar)}")
            return True

        except Exception as e:
            logger.error(f"💥 Error en servidor {id_servidor}: {str(e)}", exc_info=True)
            db.session.rollback()
            if 'interpretacion' in locals():
                try:
                    interpretacion.estado = 'FALLIDO'
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            return False
