import sys
import os
from flask import Flask
import re
import hashlib
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import init_app, db 
from modelo.loLogs import loLogs
from datetime import datetime
from difflib import SequenceMatcher
from modelo.asEmpresa import asEmpresa
from modelo.loErrorconocido import loErrorconocido

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
        """
        Verifica si el log ya está registrado en la BD para un servidor específico.
        
        Args:
            mensaje_normalizado (str): Mensaje de error normalizado.
            idServidor (int): ID del servidor asociado al log.
            nivel (str, optional): Nivel de gravedad (ERROR, WARN, etc.).
            
        Returns:
            bool: True si el error ya existe, False si no.
        """
        with app.app_context():
            query = db.session.query(loLogs).filter(
                loLogs.mensaje == mensaje_normalizado,
                loLogs.idServidor == idServidor
            )
            
            if nivel:
                query = query.filter(loLogs.nivel == nivel.upper())
                
            return query.first() is not None
        
    @classmethod
    def normalizar_mensaje(cls, mensaje):
        """Versión como classmethod para usarla desde otros métodos de clase"""
        if not mensaje:
            return ""
        mensaje = re.sub(r'\d{2}:\d{2}:\d{2},\d{3}', '', mensaje)  # Timestamps
        mensaje = re.sub(r'\([^)]+\)', '(THREAD)', mensaje)  # Hilos
        mensaje = re.sub(r'\d+', '[NUM]', mensaje)  # Números
        mensaje = re.sub(r'0x[0-9a-fA-F]+', '[HEX]', mensaje)  # Hexadecimal
        return mensaje.lower().strip()
        
    @classmethod
    def obtener_respuesta_existente(cls, mensaje_normalizado: str, idServidor: int, nivel: str):
        """Busca un error similar en BD y devuelve su respuestaOpenai si existe"""
        with app.app_context():
            logs = db.session.query(loLogs).filter(
                loLogs.idServidor == idServidor,
                loLogs.nivel == nivel
            )
            for log in logs:
                if SequenceMatcher(None, mensaje_normalizado, cls.normalizar_mensaje(log.mensaje)).ratio() >= 0.8:
                    return log.respuestaOpenai
            return None
        
    @classmethod
    def obtener_respuesta_de_error_conocido(cls, mensaje_normalizado: str, nivel: str):
        """Busca en LO_ERRORCONOCIDO usando hash del mensaje"""
        hash_error = hashlib.sha256(mensaje_normalizado.encode()).hexdigest()
        return db.session.query(loErrorconocido).filter(
            loErrorconocido.hasherror == hash_error,
            loErrorconocido.nivel == nivel
        ).first()
