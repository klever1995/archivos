import os
import sys
from collections import defaultdict
from datetime import datetime
import logging
import json
from flask import Flask
from sqlalchemy import text, exc
import asyncio

# Configuración de rutas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Importaciones
from config import db, init_app
from modelo.loLogsremotos import loLogsremotos
from modelo.loServidores import loServidores
from websocket_server import manager  

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
    """
    Inserta logs y notifica al frontend via WebSocket.
    Incluye mensajes de depuración para verificar conexiones.
    """
    # 1. Verificación inicial de IDs
    if not verificar_ids(idServidor, idAuditoria):
        logger.error("❌ Validación de IDs fallida")
        return 0

    niveles_validos = {'ERROR', 'FATAL', 'WARN'}
    registros = []

    try:
        # 2. Preparar datos
        for (nivel, categoria, _), datos in reporte.items():
            if nivel not in niveles_validos:
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

        if not registros:
            logger.warning("⚠️ No hay registros válidos para insertar")
            return 0

        # 3. Insertar en DB
        with app.app_context():
            db.session.execute(
                loLogsremotos.__table__.insert(),
                registros
            )
            db.session.commit()
            logger.info(f"✅ Insertados {len(registros)} registros")

            # 4. Notificación WebSocket (con depuración)
            from websocket_server import manager
            import asyncio

            # Calcular métricas
            logs_por_nivel = defaultdict(int)
            for (nivel, _, _), datos in reporte.items():
                if nivel in niveles_validos:
                    logs_por_nivel[nivel] += datos['count']

            if logs_por_nivel:
                mensaje_ws = {
                    "eventType": "evolucion_errores_update",
                    "data": {
                        "idServidor": idServidor,
                        "logs_por_nivel": dict(logs_por_nivel),
                        "total_logs": sum(logs_por_nivel.values()),
                        "timestamp": datetime.now().isoformat()
                    }
                }

                # Depuración: Verificar conexiones activas
                logger.info(f"🔌 Conexiones activas: {manager.active_connections}")

                try:
                    # Enviar mensaje
                    logger.info(f"🚀 Enviando WS: {json.dumps(mensaje_ws, indent=2)}")
                    
                    # ✅ Cambio: quitar await fuera de async y usar asyncio.run()
                    asyncio.run(manager.send_json_message(mensaje_ws, id_empresa=1))
                    
                    logger.info("📡 Mensaje WebSocket enviado")
                except Exception as e:
                    logger.error(f"💥 Error enviando WebSocket: {str(e)}", exc_info=True)

            return len(registros)

    except exc.IntegrityError as e:
        logger.error(f"🗄️ Error de DB: {str(e)}")
        db.session.rollback()
        return 0
    except Exception as e:
        logger.error(f"⚠️ Error inesperado: {str(e)}", exc_info=True)
        db.session.rollback()
        return 0


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
