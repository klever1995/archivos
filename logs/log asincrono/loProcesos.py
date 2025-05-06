------------dos nuevos campos en la tabla----------------------------archivo loProcesos.py-----------------------
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
    lineaInicio = db.Column(db.Integer, default=1, nullable=False) 
    lineaFin = db.Column(db.Integer, nullable=True) 
    empresa = db.relationship('asEmpresa', backref='procesos')
    
#Método que calcula la duración total del proceso en segundos
    @property
    def duracionSegundos(self):
        if self.fechaFin and self.fechaInicio:
            return (self.fechaFin - self.fechaInicio).total_seconds()
        return None
