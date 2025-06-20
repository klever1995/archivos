import sys
import os
from flask import Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import init_app, db 
from modelo.loLogs import loLogs
from datetime import datetime
from modelo.asEmpresa import asEmpresa

app = Flask(__name__)
init_app(app)

class Logger:

    @staticmethod
    def insertar_log(**kwargs):
        with app.app_context():
            try:
                nuevo_log = loLogs(
                    idEmpresa=kwargs.get('idEmpresa'),
                    idServidor=kwargs.get('idServidor'),
                    idAuditoria=kwargs.get('idAuditoria'),  # Cambiado de idProceso
                    operador=kwargs.get('operador'),
                    fechaCreacion=datetime.utcnow(),
                    estado=kwargs.get('estado', 'ACTIVO'),
                    nivel=kwargs.get('nivel', 'INFO'),
                    componente=kwargs.get('componente', 'SistemaGeneral'),
                    hilo=kwargs.get('hilo', 'MainThread'),
                    mensaje=kwargs.get('mensaje'),
                    categoria=kwargs.get('categoria', 'General'),
                    ocurrencias=kwargs.get('ocurrencias', 1),
                    respuestaOpenai=kwargs.get('respuestaOpenai'),
                    lineas=kwargs.get('lineas')
                )
                db.session.add(nuevo_log)
                db.session.commit()
                print(f"✅ Log insertado (ID: {nuevo_log.idLogAplicacion}, Auditoría: {nuevo_log.idAuditoria})")  # Log detallado
                return True
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error al insertar log: {e}")
                return False

    @classmethod
    def existe_error_en_bd(cls, mensaje_normalizado, idServidor, nivel=None):
        with app.app_context():
            query = db.session.query(loLogs).filter(
                loLogs.mensaje == mensaje_normalizado,
                loLogs.idServidor == idServidor
            )
            
            if nivel:
                query = query.filter(loLogs.nivel == nivel.upper())
                
            return query.first() is not None
