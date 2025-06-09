from config import db
from datetime import datetime

#Clase de la tabla lo_procesos

class LoProcesos(db.Model):
    __tablename__ = 'LO_PROCESOS'
    
    idAuditoria = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    idServidor = db.Column(db.Integer, db.ForeignKey('LO_SERVIDORES.idServidor'), nullable=True)
    operador = db.Column(db.Integer, nullable=False)
    fechaInicio = db.Column(db.DateTime, default=datetime.now, nullable=False)
    fechaFin = db.Column(db.DateTime, nullable=True)
    totalLogsProcesados = db.Column(db.Integer, default=0, nullable=False)
    byte_inicio = db.Column(db.BigInteger, default=0)
    byte_fin = db.Column(db.BigInteger, nullable=True)
    ultimo_byte_procesado = db.Column(db.BigInteger, nullable=True)
    archivo = db.Column(db.String(255))
    checksum = db.Column(db.String(64))
    bloque_size = db.Column(db.Integer, default=10_000_000)
    estado = db.Column(db.String(20), nullable=True)

    empresa = db.relationship('asEmpresa', backref='procesos')
    servidor = db.relationship('loServidores', foreign_keys=[idServidor], backref='procesos')  # Relación explícita
    
    @property
    def duracionSegundos(self):
        if self.fechaFin and self.fechaInicio:
            return (self.fechaFin - self.fechaInicio).total_seconds()
        return None
