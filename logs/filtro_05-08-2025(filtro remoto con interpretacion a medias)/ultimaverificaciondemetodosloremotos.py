# metodos_loremotos.py
import os
import sys
import re
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import logging

# Configuración CRUCIAL de rutas
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

# Inicialización de la app (como en tus otros archivos)
app = Flask(__name__)
init_app(app)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def interpretar_logs_remotos(id_servidor: int, batch_size: int = 100) -> bool:
    """Interpretación remota con IA y guardado de resultados por servidor."""
    with app.app_context():
        try:
            # 1. Validar servidor
            servidor = db.session.get(loServidores, id_servidor)
            if not servidor or not servidor.esRemoto:
                raise ValueError("ID de servidor remoto inválido")

            # 2. Obtener último proceso de filtrado
            ultimo_proceso = db.session.query(LoProcesos.idAuditoria)\
                .filter_by(idServidor=id_servidor, tipoProceso='FILTRADOREMOTO')\
                .order_by(LoProcesos.idAuditoria.desc())\
                .first()
            
            if not ultimo_proceso:
                raise ValueError("No existe proceso FILTRADOREMOTO para este servidor")

            # 3. Crear nueva interpretación
            interpretacion = loInterpretacionremota(
                idProcesoFiltrado=ultimo_proceso.idAuditoria,
                idServidor=id_servidor,
                fechaInicio=datetime.now(),
                estado='PROCESANDO',
                ultimoLogProcesado=0,
                totalLogsInterpretados=0
            )
            db.session.add(interpretacion)
            db.session.flush()

            # 4. Obtener logs nuevos
            logs = db.session.query(loLogsremotos).filter(
                loLogsremotos.idServidor == id_servidor,
                loLogsremotos.idLogRemoto > interpretacion.ultimoLogProcesado
            ).order_by(loLogsremotos.idLogRemoto).limit(batch_size).all()

            if not logs:
                interpretacion.estado = 'COMPLETADO'
                interpretacion.fechaFin = datetime.now()
                db.session.commit()
                logger.info(f"No hay logs nuevos en servidor {id_servidor}.")
                return True

            # 5. Procesamiento de logs
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
                        'mensaje_normalizado': mensaje_normalizado,
                        'hash_error': hash_error,
                        'needs_ia': True
                    })
                    logger.debug(f"📡 Log {log.idLogRemoto} marcado para consulta IA (nivel: {log.nivel})")
                else:
                    logs_nuevos.append({
                        'log': log,
                        'mensaje_normalizado': mensaje_normalizado,
                        'hash_error': hash_error,
                        'needs_ia': False
                    })

                logs_a_guardar.append({
                    'log': log,
                    'hash_error': hash_error,
                    'error_conocido': error_conocido
                })

            # 6. Consulta IA para logs nuevos - Con confirmación explícita
            respuestas_ia = []
            logs_para_ia = [log for log in logs_nuevos if log['needs_ia']]
            
            if logs_para_ia:
                logger.info(f"🔎 Preparando consulta IA para {len(logs_para_ia)} logs...")
                try:
                    # Diagnóstico de conexión completo
                    logger.info("🛜 Verificando conexión con OpenAI...")
                    if not consulta_ia.verificar_conexion():
                        logger.critical("❌ OpenAI no responde - Verifique:")
                        logger.critical(f"• Endpoint: {consulta_ia.endpoint}")
                        logger.critical("• API Key configurada")
                        logger.critical("• Conexión a internet")
                        raise ConnectionError("Servicio IA no disponible")
                    logger.info("🌐 Conexión con OpenAI verificada")

                    # Procesamiento con confirmación
                    with ThreadPoolExecutor(max_workers=5) as executor:
                        logger.info(f"🚀 Enviando {len(logs_para_ia)} consultas a IA...")
                        future_to_log = {
                            executor.submit(
                                consulta_ia.interpretar_logs, 
                                log['mensaje_normalizado'][:2000]
                            ): log for log in logs_para_ia
                        }
                        
                        for future in future_to_log:
                            log = future_to_log[future]
                            try:
                                inicio = time.time()
                                respuesta = future.result(timeout=30)
                                duracion = time.time() - inicio
                                
                                if not respuesta or not isinstance(respuesta, str):
                                    logger.error(f"🛑 Respuesta inválida de IA para log {log['log'].idLogRemoto}")
                                    raise ValueError("Respuesta vacía o en formato incorrecto")
                                
                                logger.info(f"✅ IA respondió en {duracion:.2f}s - Log {log['log'].idLogRemoto}")
                                logger.debug(f"Respuesta IA: {respuesta[:100]}...")  # Preview
                                respuestas_ia.append((log['hash_error'], respuesta))
                                
                                # Guardado con confirmación
                                nuevo_error = loErrorconocido(
                                    hasherror=log['hash_error'],
                                    mensajenormalizado=log['mensaje_normalizado'],
                                    nivel=log['log'].nivel,
                                    respuestaopenai=respuesta,
                                    fechaprimeraocurrencia=fecha_actual,
                                    fechaultimaactualizacion=fecha_actual
                                )
                                db.session.add(nuevo_error)
                                db.session.commit()
                                logger.debug(f"💾 Guardado en BD para log {log['log'].idLogRemoto}")
                                
                            except Exception as e:
                                logger.error(f"❌ Fallo en log {log['log'].idLogRemoto}: {type(e).__name__} - {str(e)}")
                                db.session.rollback()
                                raise

                except Exception as e:
                    logger.critical("🔥 ERROR EN CONSULTA IA")
                    logger.critical(f"Tipo: {type(e).__name__}")
                    logger.critical(f"Mensaje: {str(e)}")
                    logger.critical("🛑 Proceso cancelado - No se guardaron datos inconsistentes")
                    interpretacion.estado = 'FALLIDO'
                    db.session.commit()
                    return False

            # 7. Guardar en loLogs con confirmación
            logs_insertar = []
            for item in logs_a_guardar:
                respuesta = None
                
                if item['error_conocido']:
                    respuesta = item['error_conocido'].respuestaopenai
                    logger.debug(f"♻️ Usando caché para log {item['log'].idLogRemoto}")
                else:
                    for hash_err, resp in respuestas_ia:
                        if hash_err == item['hash_error']:
                            respuesta = resp
                            logger.debug(f"🔄 Usando nueva respuesta IA para log {item['log'].idLogRemoto}")
                            break
                
                if respuesta:
                    logs_insertar.append(loLogs(
                        idEmpresa=servidor.idEmpresa,
                        idServidor=id_servidor,
                        idAuditoria=item['log'].idAuditoria,
                        operador=0,
                        nivel=item['log'].nivel,
                        mensaje=item['log'].mensaje,
                        respuestaOpenai=respuesta,
                        fechaCreacion=fecha_actual
                    ))
                    interpretacion.ultimoLogProcesado = item['log'].idLogRemoto
                    interpretacion.totalLogsInterpretados += 1
                else:
                    logger.warning(f"⏭️ Omitiendo log {item['log'].idLogRemoto} - Sin interpretación disponible")

            if logs_insertar:
                db.session.bulk_save_objects(logs_insertar)
                logger.info(f"💽 Guardados {len(logs_insertar)} logs en BD")
            
            # 8. Actualizar estado final
            interpretacion.estado = 'COMPLETADO' if len(logs) < batch_size else 'PROCESANDO'
            interpretacion.fechaFin = datetime.now() if interpretacion.estado == 'COMPLETADO' else None
            db.session.commit()
            
            logger.info(f"📊 Interpretación {interpretacion.idInterpretacion} finalizada")
            logger.info(f"• Logs procesados: {len(logs_insertar)}")
            logger.info(f"• Logs omitidos: {len(logs) - len(logs_insertar)}")
            return True

        except Exception as e:
            logger.error(f"💥 Error en servidor {id_servidor}: {str(e)}", exc_info=True)
            db.session.rollback()
            if 'interpretacion' in locals():
                interpretacion.estado = 'FALLIDO'
                db.session.commit()
            return False

# Prueba con diagnóstico completo
if __name__ == "__main__":
    print("\n=== DIAGNÓSTICO IA ===")
    print("Iniciando prueba de interpretación...")
    if interpretar_logs_remotos(id_servidor=109):
        print("✅ Proceso completado - Ver logs para detalles")
    else:
        print("❌ Falla crítica - Ver logs para diagnóstico")
