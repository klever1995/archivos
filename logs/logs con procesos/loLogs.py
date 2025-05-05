-----------------------clase que representa la tabla loLogs -------------------- archivo loLogs.py----------------------
from config import db

# Clase que representa la tabla LO_LOGS en la base de datos para almacenar registros de logs
class loLogs(db.Model):
    __tablename__ = 'LO_LOGS'
    
    idLogAplicacion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    operador = db.Column(db.Integer, nullable=False)
    fechaCreacion = db.Column(db.DateTime, nullable=False)
    estado = db.Column(db.String(20), default='ACTIVO', nullable=True)
    nivel = db.Column(db.String(10), nullable=False)
    componente = db.Column(db.String(255), nullable=True)
    hilo = db.Column(db.String(100), nullable=True)
    mensaje = db.Column(db.Text, nullable=True)
    categoria = db.Column(db.String(100), nullable=True)
    ocurrencias = db.Column(db.Integer, default=1, nullable=True)
    respuestaOpenai = db.Column(db.Text, nullable=True)
    lineas = db.Column(db.JSON, nullable=True)

    empresa = db.relationship('asEmpresa', backref='logs')
    
