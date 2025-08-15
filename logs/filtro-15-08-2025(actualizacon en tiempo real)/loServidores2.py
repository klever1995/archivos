from modelo.loAccesosremotos import loAccesosremotos
from modelo.loDepartamentos import loDepartamentos  # Nueva importación
from config import db

class loServidores(db.Model):
    __tablename__ = 'LO_SERVIDORES'
    
    # Campos existentes (NO MODIFICADOS)
    idServidor = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    ruta = db.Column(db.String(500), nullable=False)
    nombreServidor = db.Column(db.String(100), nullable=False)
    activo = db.Column(db.Boolean, default=False)
    fechaRegistro = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    
    # Campo existente de acceso remoto (NO MODIFICADO)
    idAccesoRemoto = db.Column(
        db.Integer, 
        db.ForeignKey('LO_ACCESOSREMOTOS.idAcceso'), 
        nullable=True
    )
    
    # Nuevo campo para departamento (AGREGADO)
    idDepartamento = db.Column(
        db.Integer,
        db.ForeignKey('LO_DEPARTAMENTOS.idDepartamento'),
        nullable=True,
        comment='FK a lo_departamentos'
    )

    # Relaciones existentes (NO MODIFICADAS)
    empresa = db.relationship('asEmpresa', backref='servidores')
    accesoRemoto = db.relationship(
        'loAccesosremotos', 
        backref=db.backref('servidoresAsociados', lazy='dynamic'),
        foreign_keys=[idAccesoRemoto]
    )

    # Nueva relación con departamento (AGREGADA)
    departamentoAsociado = db.relationship(
    'loDepartamentos',
    back_populates='servidores',  # Cambiado de backref
    foreign_keys=[idDepartamento]
)

    # Métodos existentes (si los tienes, se mantienen)
    def __repr__(self):
        return f'<loServidores {self.nombreServidor}>'
