import os
import sys
import re
import time
import hashlib
from sqlalchemy import func
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
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

from consumos.consulta_ia_openai import Consulta_ia_openai

os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'


app = Flask(__name__)
init_app(app)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

#Método que interpreta logs remotos con IA
def interpretar_logs_remotos(id_servidor: int, batch_size: int = 100) -> bool:
   
    with app.app_context():
        try:
            # Validar servidor
            servidor = db.session.get(loServidores, id_servidor)
            if not servidor:
                raise ValueError("ID de servidor inválido")
            # Obtener último ID procesado
            ultimo_id = db.session.query(
                func.max(loInterpretacionremota.ultimoLogProcesado)
            ).filter_by(idServidor=id_servidor).scalar() or 0
            # Obtener último proceso de auditoría
            ultimo_proceso_id = db.session.query(LoProcesos.idAuditoria).filter_by(
                idServidor=id_servidor
            ).order_by(LoProcesos.idAuditoria.desc()).first()
            if ultimo_proceso_id:
                id_proceso_filtrado = ultimo_proceso_id.idAuditoria
            else:
                id_proceso_filtrado = None 
            # Crear registro de interpretación
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
            # Obtener logs nuevos
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
                mensaje_normalizado = re.sub(r'\d+', '[NUM]', log.mensaje.lower())
                hash_error = hashlib.sha256(mensaje_normalizado.encode()).hexdigest()

                error_conocido = db.session.query(loErrorconocido).filter_by(
                    hasherror=hash_error,
                    nivel=log.nivel
                ).first()

                if not error_conocido and log.nivel in {'ERROR', 'FATAL'}:
                    logs_nuevos.append({
                        'log': log,
                        'mensaje_normalizado': log.mensaje[:2000],
                        'hash_error': hash_error,
                        'id_log_remoto': log.idLogRemoto 
                    })

                logs_a_guardar.append({
                    'log': log,
                    'hash_error': hash_error,
                    'error_conocido': error_conocido
                })
            # Procesar con IA
            respuestas_ia = {}
            if logs_nuevos:
                try:
                    logger.info(f"🔎 Preparando bloque de {len(logs_nuevos)} logs para IA...")
                    
                    bloque_logs = ""
                    for i, log in enumerate(logs_nuevos):
                        bloque_logs += f"LOG {i+1} (ID: {log['id_log_remoto']}):\n{log['mensaje_normalizado']}\n🔹🔹🔹\n"

                    bloque_logs = bloque_logs.rsplit('🔹🔹🔹', 1)[0]
                    
                    inicio = time.time()

                    respuesta_bloque = consulta_ia.interpretar_logs(bloque_logs)
                    duracion = time.time() - inicio
                    
                    if not respuesta_bloque or not isinstance(respuesta_bloque, str):
                        logger.error("🛑 Respuesta inválida de IA para el bloque de logs")
                        raise ValueError("Respuesta de IA inválida")
                    
                    logger.info(f"✅ IA respondió en {duracion:.2f}s para {len(logs_nuevos)} logs")
                    # Procesar respuesta masiva
                    lineas_respuesta = respuesta_bloque.split('\n')
                    current_log_index = -1
                    current_response = []
                    
                    for linea in lineas_respuesta:
                        if linea.strip().startswith('LOG ') and ':' in linea:

                            if current_log_index >= 0 and current_response:
                                log_actual = logs_nuevos[current_log_index]
                                respuesta_completa = '\n'.join(current_response).strip()
                                respuestas_ia[log_actual['hash_error']] = respuesta_completa

                                nuevo_error = loErrorconocido(
                                    hasherror=log_actual['hash_error'],
                                    mensajenormalizado=log_actual['mensaje_normalizado'],
                                    nivel=log_actual['log'].nivel,
                                    respuestaopenai=respuesta_completa,
                                    fechaprimeraocurrencia=fecha_actual,
                                    fechaultimaactualizacion=fecha_actual
                                )
                                db.session.add(nuevo_error)

                            current_log_index += 1
                            current_response = []
                        elif current_log_index >= 0:
                            current_response.append(linea)
                    # Guardar último log procesado
                    if current_log_index >= 0 and current_response:
                        log_actual = logs_nuevos[current_log_index]
                        respuesta_completa = '\n'.join(current_response).strip()
                        respuestas_ia[log_actual['hash_error']] = respuesta_completa
                        
                        nuevo_error = loErrorconocido(
                            hasherror=log_actual['hash_error'],
                            mensajenormalizado=log_actual['mensaje_normalizado'],
                            nivel=log_actual['log'].nivel,
                            respuestaopenai=respuesta_completa,
                            fechaprimeraocurrencia=fecha_actual,
                            fechaultimaactualizacion=fecha_actual
                        )
                        db.session.add(nuevo_error)

                    db.session.commit()

                except Exception as e:
                    logger.error(f"Error al consultar IA en bloque: {str(e)}")
                    db.session.rollback()

                    logger.info("🔄 Intentando procesamiento individual como fallback...")
                    respuestas_ia = {}
                    for log in logs_nuevos:
                        try:
                            respuesta_individual = consulta_ia.interpretar_logs(log['mensaje_normalizado'])
                            if respuesta_individual and isinstance(respuesta_individual, str):
                                respuestas_ia[log['hash_error']] = respuesta_individual
                                nuevo_error = loErrorconocido(
                                    hasherror=log['hash_error'],
                                    mensajenormalizado=log['mensaje_normalizado'],
                                    nivel=log['log'].nivel,
                                    respuestaopenai=respuesta_individual,
                                    fechaprimeraocurrencia=fecha_actual,
                                    fechaultimaactualizacion=fecha_actual
                                )
                                db.session.add(nuevo_error)
                        except Exception as e_individual:
                            logger.error(f"❌ Fallo individual en log {log['log'].idLogRemoto}: {str(e_individual)}")
                    db.session.commit()
            # Guardar logs procesados
            logs_insertar = []
            for item in logs_a_guardar:
                if item['error_conocido']:
                    respuesta = item['error_conocido'].respuestaopenai
                else:
                    respuesta = respuestas_ia.get(item['hash_error'])
                
                if respuesta or item['log'].nivel == 'WARN':
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
                        respuestaOpenai=respuesta if item['log'].nivel in {'ERROR', 'FATAL'} else None,
                        fechaCreacion=fecha_actual
                    ))
                    interpretacion.ultimoLogProcesado = max(
                        interpretacion.ultimoLogProcesado,
                        item['log'].idLogRemoto
                    )
            # Actualizar estadísticas y finalizar
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
                interpretacion.estado = 'FALLIDO'
                db.session.commit()
            return False
