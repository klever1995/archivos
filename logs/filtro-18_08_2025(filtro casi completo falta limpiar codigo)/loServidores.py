from modelo.loAccesosremotos import loAccesosremotos
from modelo.loDepartamentos import loDepartamentos  
from config import db

#Clase de la tabla lo_servidores
class loServidores(db.Model):
    __tablename__ = 'LO_SERVIDORES'
    idServidor = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    ruta = db.Column(db.String(500), nullable=False)
    nombreServidor = db.Column(db.String(100), nullable=False)
    activo = db.Column(db.Boolean, default=False)
    fechaRegistro = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    idAccesoRemoto = db.Column(
        db.Integer, 
        db.ForeignKey('LO_ACCESOSREMOTOS.idAcceso'), 
        nullable=True
    )
    idDepartamento = db.Column(
        db.Integer,
        db.ForeignKey('LO_DEPARTAMENTOS.idDepartamento'),
        nullable=True,
        comment='FK a lo_departamentos'
    )
    empresa = db.relationship('asEmpresa', backref='servidores')
    accesoRemoto = db.relationship(
        'loAccesosremotos', 
        backref=db.backref('servidoresAsociados', lazy='dynamic'),
        foreign_keys=[idAccesoRemoto]
    )
    departamentoAsociado = db.relationship(
    'loDepartamentos',
    back_populates='servidores', 
    foreign_keys=[idDepartamento]
)

    def __repr__(self):
        return f'<loServidores {self.nombreServidor}>'
