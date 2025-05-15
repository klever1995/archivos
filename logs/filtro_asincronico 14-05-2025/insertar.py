-------------metodos de la tabla lo_logs------------------------
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

# Clase con métodos para interactuar con la tabla LO_LOGS
class Logger:

#Método para inserta un nuevo registro de log en la tabla LO_LOGS
    @staticmethod
    def insertar_log(**kwargs):
        with app.app_context():
            try:
                nuevo_log = loLogs(
                    idEmpresa=kwargs.get('idEmpresa'),
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
                print("✅ Log insertado correctamente.")
                return True
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error al insertar log: {e}")
                return False

#Método que verifica si un mensaje de error ya existe en la base de datos
    @classmethod
    def existe_error_en_bd(cls, mensaje_normalizado, nivel=None):
        """Verifica si el log ya está registrado en la BD"""
        with app.app_context():
            query = db.session.query(loLogs).filter(
                loLogs.mensaje == mensaje_normalizado
            )
            
            if nivel:
                query = query.filter(loLogs.nivel == nivel.upper())
                
            return query.first() is not None

