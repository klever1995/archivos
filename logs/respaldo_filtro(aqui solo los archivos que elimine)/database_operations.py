from datetime import datetime
import hashlib
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from config import flask_app, db, logger
from modelo.loLogs import loLogs
from modelo.loErrorconocido import loErrorconocido
from consumos.consulta_ia_openai import Consulta_ia_openai

def consultar_openai_paralelo(logs: list) -> list:
    """Consulta OpenAI en paralelo para múltiples logs."""
    with ThreadPoolExecutor(max_workers=5) as executor:
        return list(executor.map(lambda log: Consulta_ia_openai().interpretar_logs(log), logs))

def insertar_logs_a_bd(reporte: dict, idServidor: int, idAuditoria: int) -> int:
    # Implementación original completa
    total_insertados = 0
    consulta = Consulta_ia_openai()
    total_logs = len(reporte)
    inicio_tiempo = time.time()
    logs_nuevos = []
    logs_a_insertar = []
    fecha_actual = datetime.now()

    try:
        with flask_app.app_context():
            # ... (resto de la implementación original)
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en inserción masiva: {str(e)}")
    finally:
        # ... (código final original)
    
    return total_insertados
