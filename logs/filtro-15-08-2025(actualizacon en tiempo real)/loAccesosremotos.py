from config import db

class loAccesosremotos(db.Model):
    __tablename__ = 'LO_ACCESOSREMOTOS'  

    idAcceso = db.Column('idAcceso', db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column('idEmpresa', db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    usuario = db.Column('usuario', db.String(100), nullable=False)
    contrasena = db.Column('contrasena', db.String(255), nullable=False)
    activo = db.Column('activo', db.Boolean, default=True)
    fechaRegistro = db.Column('fechaRegistro', db.DateTime, server_default=db.func.current_timestamp())
    hostname = db.Column('hostname', db.String(255), nullable=False, unique=True)

    empresa = db.relationship('asEmpresa', backref='accesos_remotos')
