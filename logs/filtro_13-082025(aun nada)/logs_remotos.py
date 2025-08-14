import os
import sys
from collections import defaultdict
from datetime import datetime
import logging
from flask import Flask
from sqlalchemy import text, exc

# Configuración de rutas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Importaciones
from config import db, init_app
from modelo.loLogsremotos import loLogsremotos

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Inicialización Flask
app = Flask(__name__)
init_app(app)

def verificar_ids(id_servidor, id_auditoria):
    """Verifica que los IDs existan en las tablas relacionadas"""
    with app.app_context():
        try:
            # Verificar servidor
            if not db.session.execute(
                text("SELECT 1 FROM LO_SERVIDORES WHERE idServidor = :id"),
                {'id': id_servidor}
            ).scalar():
                logger.error(f"ID Servidor {id_servidor} no existe")
                return False

            # Verificar auditoría
            if not db.session.execute(
                text("SELECT 1 FROM LO_PROCESOS WHERE idAuditoria = :id"),
                {'id': id_auditoria}
            ).scalar():
                logger.error(f"ID Auditoría {id_auditoria} no existe")
                return False

            return True

        except Exception as e:
            logger.error(f"Error verificando IDs: {str(e)}")
            return False

def insertar_logs_remotos(reporte, idServidor, idAuditoria):
    import time  # Añadir al inicio del archivo si no existe
    start_total = time.perf_counter()
    
    # Debug: Verificación inicial
    start = time.perf_counter()
    if not verificar_ids(idServidor, idAuditoria):
        logger.info(f"⏱️ [DEBUG] verificar_ids: {time.perf_counter() - start:.4f}s | Resultado: IDs inválidos")
        return 0
    logger.info(f"⏱️ [DEBUG] verificar_ids: {time.perf_counter() - start:.4f}s | Resultado: IDs válidos")

    niveles_validos = {'ERROR', 'FATAL', 'WARN'}
    registros = []
    registros_filtrados = 0

    try:
        # Debug: Preparación de datos
        start_preparacion = time.perf_counter()
        for (nivel, categoria, _), datos in reporte.items():
            if nivel not in niveles_validos:
                registros_filtrados += 1
                continue

            registros.append({
                'idEmpresa': 1,
                'idServidor': idServidor,
                'idAuditoria': idAuditoria,
                'fechaCreacion': datetime.now(),
                'nivel': nivel,
                'mensaje': str(datos.get('mensaje_normalizado', ''))[:65535],
                'categoria': categoria,
                'ocurrencias': int(datos.get('count', 1)),
                'componente': datos.get('componente', None),
                'hilo': datos.get('hilo', None),
                'lineas': datos.get('lineas', None)
            })
        
        tiempo_preparacion = time.perf_counter() - start_preparacion
        logger.info(f"⏱️ [DEBUG] preparar_datos: {tiempo_preparacion:.4f}s | "
                   f"Registros válidos: {len(registros)} | "
                   f"Filtrados: {registros_filtrados}")

        if not registros:
            logger.info("⏱️ [DEBUG] Sin registros válidos para insertar")
            return 0

        # Debug: Inserción en BD
        start_insercion = time.perf_counter()
        with app.app_context():
            db.session.execute(
                loLogsremotos.__table__.insert(),
                registros
            )
            db.session.commit()
            tiempo_insercion = time.perf_counter() - start_insercion
            
            logger.info(f"⏱️ [DEBUG] insercion_bd: {tiempo_insercion:.4f}s | "
                       f"Registros insertados: {len(registros)} | "
                       f"Tasa: {len(registros)/max(tiempo_insercion, 0.0001):.1f} reg/s")
            
            return len(registros)

    except exc.IntegrityError as e:
        logger.error(f"⏱️ [DEBUG] Error de integridad: {str(e)} | Tiempo hasta error: {time.perf_counter() - start_total:.4f}s")
        db.session.rollback()
        return 0
    except Exception as e:
        logger.error(f"⏱️ [DEBUG] Error inesperado: {str(e)} | Tiempo hasta error: {time.perf_counter() - start_total:.4f}s")
        db.session.rollback()
        return 0
    finally:
        logger.info(f"⏱️ [DEBUG] TIEMPO TOTAL insertar_logs_remotos: {time.perf_counter() - start_total:.4f}s")

if __name__ == "__main__":
    # Configurar contexto de aplicación para pruebas
    with app.app_context():
        # Datos de prueba con IDs válidos
        test_data = {
            ('ERROR', 'database', 'test'): {
                'mensaje_normalizado': '[TEST] Conexión fallida',
                'count': 1
            }
        }

        # Obtener IDs válidos de la base de datos
        id_servidor_valido = db.session.execute(
            text("SELECT idServidor FROM LO_SERVIDORES LIMIT 1")
        ).scalar() or 1

        id_auditoria_valido = db.session.execute(
            text("SELECT idAuditoria FROM LO_PROCESOS LIMIT 1")
        ).scalar() or 1

        print("\n=== PRUEBA CON DATOS REALES ===")
        resultado = insertar_logs_remotos(
            reporte=test_data,
            idServidor=id_servidor_valido,
            idAuditoria=id_auditoria_valido
        )
        print(f"Resultado: {resultado} registros insertados")
