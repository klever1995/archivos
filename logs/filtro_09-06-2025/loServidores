from config import db

class loServidores(db.Model):
    __tablename__ = 'LO_SERVIDORES'
    
    idServidor = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    ruta = db.Column(db.String(500), nullable=False)
    nombreServidor = db.Column(db.String(100), nullable=False)
    activo = db.Column(db.Boolean, default=False)
    fechaRegistro = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Relación con empresa
    empresa = db.relationship('asEmpresa', backref='servidores')
