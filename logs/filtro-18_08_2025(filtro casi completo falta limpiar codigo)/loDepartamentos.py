from config import db
from datetime import datetime

#Clase de la tabla lo_departamentos
class loDepartamentos(db.Model):
    __tablename__ = 'LO_DEPARTAMENTOS'
    
    idDepartamento = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    fechaRegistro = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    empresa = db.relationship('asEmpresa', backref='departamentos')
    servidores = db.relationship(
    'loServidores', 
    back_populates='departamentoAsociado',  
    foreign_keys='loServidores.idDepartamento'
)
