from modelo.loAccesosremotos import loAccesosremotos
from config import db

class loServidores(db.Model):
    __tablename__ = 'LO_SERVIDORES'
    
    # Campos existentes (NO MODIFICAR)
    idServidor = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    ruta = db.Column(db.String(500), nullable=False)
    nombreServidor = db.Column(db.String(100), nullable=False)
    activo = db.Column(db.Boolean, default=False)
    fechaRegistro = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    
    # Campo modificado (se mantiene idAccesoRemoto)
    idAccesoRemoto = db.Column(
        db.Integer, 
        db.ForeignKey('LO_ACCESOSREMOTOS.idAcceso'), 
        nullable=True
    )
    
    # Relaciones existentes (NO MODIFICAR)
    empresa = db.relationship('asEmpresa', backref='servidores')
    
    # Relación con accesos remotos (se mantiene)
    accesoRemoto = db.relationship(
        'loAccesosremotos', 
        backref=db.backref('servidoresAsociados', lazy='dynamic'),
        foreign_keys=[idAccesoRemoto]
    )
