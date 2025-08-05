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

# Importar la clase para interpretar con IA
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
            # 1. Validar servidor (reemplaza validación de proceso)
            servidor = db.session.get(loServidores, id_servidor)
            if not servidor or not servidor.esRemoto:
                raise ValueError("ID de servidor remoto inválido")

            # 2. Iniciar/recuperar interpretación por servidor
            interpretacion = db.session.query(loInterpretacionremota).filter_by(
                idServidor=id_servidor
            ).first()

            if not interpretacion:
                interpretacion = loInterpretacionremota(
                    idServidor=id_servidor,
                    fechaInicio=datetime.now(),
                    estado='PROCESANDO',
                    ultimoLogProcesado=0,
                    totalLogsInterpretados=0
                )
                db.session.add(interpretacion)
                db.session.flush()

            # 3. Obtener logs nuevos por servidor
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

            # 4. Procesamiento de logs (igual que antes pero optimizado)
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
                        'hash_error': hash_error
                    })

                logs_a_guardar.append({
                    'log': log,
                    'hash_error': hash_error,
                    'error_conocido': error_conocido
                })

            # 5. Consulta IA para logs nuevos
            respuestas_ia = []
            if logs_nuevos:
                with ThreadPoolExecutor(max_workers=5) as executor:
                    respuestas_ia = list(executor.map(
                        lambda x: consulta_ia.interpretar_logs(x['mensaje_normalizado'][:2000]),
                        logs_nuevos
                    ))
                
                db.session.bulk_save_objects([
                    loErrorconocido(
                        hasherror=item['hash_error'],
                        mensajenormalizado=item['mensaje_normalizado'],
                        nivel=item['log'].nivel,
                        respuestaopenai=respuesta,
                        fechaCreacion=fecha_actual
                    ) for item, respuesta in zip(logs_nuevos, respuestas_ia)
                ])

            # 6. Guardar en loLogs (directamente desde loLogsremotos)
            logs_insertar = []
            for item in logs_a_guardar:
                respuesta = (
                    item['error_conocido'].respuestaopenai
                    if item['error_conocido']
                    else next(
                        (r for r, ln in zip(respuestas_ia, logs_nuevos) 
                         if ln['hash_error'] == item['hash_error']),
                        "Sin interpretación IA"
                    )
                )

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

            db.session.bulk_save_objects(logs_insertar)
            
            # 7. Actualizar estado
            interpretacion.estado = 'COMPLETADO' if len(logs) < batch_size else 'PROCESANDO'
            interpretacion.fechaFin = datetime.now() if interpretacion.estado == 'COMPLETADO' else None
            db.session.commit()
            
            logger.info(f"Interpretación completada para servidor {id_servidor}. Logs: {len(logs_insertar)}")
            return True

        except Exception as e:
            logger.error(f"Error en servidor {id_servidor}: {str(e)}", exc_info=True)
            db.session.rollback()
            if 'interpretacion' in locals():
                interpretacion.estado = 'FALLIDO'
                db.session.commit()
            return False

# Prueba actualizada
if __name__ == "__main__":
    print("\n=== PRUEBA CON IA (por servidor) ===")
    if interpretar_logs_remotos(id_servidor=108):  # Ejemplo con ID de servidor
        print("✅ Interpretación completada")
    else:
        print("❌ Falló la interpretación")

