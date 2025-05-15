-----------clase de la tabla lo_procesos----------------------
from config import db
from datetime import datetime

# Clase que representa la tabla LO_PROCESOS para registrar procesos de logs

class LoProcesos(db.Model):
    __tablename__ = 'LO_PROCESOS'
    
    idAuditoria = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    operador = db.Column(db.Integer, nullable=False)
    fechaInicio = db.Column(db.DateTime, default=datetime.now, nullable=False)
    fechaFin = db.Column(db.DateTime, nullable=True)
    totalLogsProcesados = db.Column(db.Integer, default=0, nullable=False)
    
    # Nuevos campos para el procesamiento asíncrono por bytes
    byte_inicio = db.Column(db.BigInteger, default=0)  # BIGINT equivalente en SQLAlchemy
    byte_fin = db.Column(db.BigInteger, nullable=True)
    ultimo_byte_procesado = db.Column(db.BigInteger, nullable=True)
    archivo = db.Column(db.String(255))  # Ruta del archivo de log
    checksum = db.Column(db.String(64))  # Para verificar integridad del archivo
    bloque_size = db.Column(db.Integer, default=1048576)  # 1MB por defecto
    estado = db.Column(db.Enum('PENDIENTE', 'PROCESANDO', 'COMPLETADO', 'FALLIDO'), default='PENDIENTE')
    
    empresa = db.relationship('asEmpresa', backref='procesos')
    
    @property
    def duracionSegundos(self):
        if self.fechaFin and self.fechaInicio:
            return (self.fechaFin - self.fechaInicio).total_seconds()
        return None
