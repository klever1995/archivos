# metodos_loremotos.py
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

            # 2. Obtener último ID procesado de ejecuciones anteriores
            ultimo_id = db.session.query(
                func.max(loInterpretacionremota.ultimoLogProcesado)
            ).filter_by(idServidor=id_servidor).scalar() or 0

            # 3. Crear nueva interpretación con el último ID real
            interpretacion = loInterpretacionremota(
                idProcesoFiltrado=db.session.query(LoProcesos.idAuditoria)
                    .filter_by(idServidor=id_servidor, tipoProceso='FILTRADOREMOTO')
                    .order_by(LoProcesos.idAuditoria.desc())
                    .first().idAuditoria,
                idServidor=id_servidor,
                fechaInicio=datetime.now(),
                estado='PROCESANDO',
                ultimoLogProcesado=ultimo_id,  # Usa el último ID real
                totalLogsInterpretados=0
            )
            db.session.add(interpretacion)
            db.session.flush()

            # 4. Obtener SOLO logs no procesados
            logs = db.session.query(loLogsremotos).filter(
                loLogsremotos.idServidor == id_servidor,
                loLogsremotos.idLogRemoto > ultimo_id  # Filtro clave
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
                        'mensaje_normalizado': log.mensaje[:2000],
                        'hash_error': hash_error
                    })

                logs_a_guardar.append({
                    'log': log,
                    'hash_error': hash_error,
                    'error_conocido': error_conocido
                })

            # 6. Consulta IA para logs nuevos
            respuestas_ia = []
            if logs_nuevos:
                try:
                    logger.info(f"🔎 Enviando {len(logs_nuevos)} consultas a IA...")
                    
                    for log in logs_nuevos:
                        try:
                            inicio = time.time()
                            respuesta = consulta_ia.interpretar_logs(log['mensaje_normalizado'])
                            duracion = time.time() - inicio
                            
                            if not respuesta or not isinstance(respuesta, str):
                                logger.error(f"🛑 Respuesta inválida de IA para log {log['log'].idLogRemoto}")
                                continue
                            
                            logger.info(f"✅ IA respondió en {duracion:.2f}s - Log {log['log'].idLogRemoto}")
                            respuestas_ia.append((log['hash_error'], respuesta))
                            
                            nuevo_error = loErrorconocido(
                                hasherror=log['hash_error'],
                                mensajenormalizado=log['mensaje_normalizado'],
                                nivel=log['log'].nivel,
                                respuestaopenai=respuesta,
                                fechaprimeraocurrencia=fecha_actual,
                                fechaultimaactualizacion=fecha_actual
                            )
                            db.session.add(nuevo_error)
                            
                        except Exception as e:
                            logger.error(f"❌ Fallo en log {log['log'].idLogRemoto}: {type(e).__name__} - {str(e)}")
                            continue

                    db.session.commit()

                except Exception as e:
                    logger.error(f"Error al consultar IA: {str(e)}")
                    db.session.rollback()

            # 7. Guardar en loLogs (CORRECCIÓN CRÍTICA)
            logs_insertar = []
            for item in logs_a_guardar:
                respuesta = item['error_conocido'].respuestaopenai if item['error_conocido'] else \
                    next((r for r in respuestas_ia if r[0] == item['hash_error']), None)
                
                if respuesta:
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
                        lineas=item['log'].lineas,
                        respuestaOpenai=respuesta,
                        fechaCreacion=fecha_actual
                    ))
                    # Actualiza con el máximo ID del batch
                    interpretacion.ultimoLogProcesado = max(
                        interpretacion.ultimoLogProcesado,
                        item['log'].idLogRemoto
                    )

            # Asignación final del contador
            interpretacion.totalLogsInterpretados = len(logs_insertar)

            if logs_insertar:
                db.session.bulk_save_objects(logs_insertar)
                logger.info(f"💽 Guardados {len(logs_insertar)} logs nuevos (IDs desde {min(log.idLogRemoto for log in logs)} hasta {max(log.idLogRemoto for log in logs)})")
            
            # 8. Actualizar estado final
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

# Prueba con diagnóstico completo
if __name__ == "__main__":
    print("\n=== DIAGNÓSTICO IA ===")
    print("Iniciando prueba de interpretación...")
    if interpretar_logs_remotos(id_servidor=110):
        print("✅ Proceso completado - Ver logs para detalles")
    else:
        print("❌ Falla crítica - Ver logs para diagnóstico")
