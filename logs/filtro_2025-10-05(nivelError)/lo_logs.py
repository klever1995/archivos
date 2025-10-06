from config import db

#Clase de la tabla lo_logs
class loLogs(db.Model):
    __tablename__ = 'LO_LOGS'
    
    idLogAplicacion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    idServidor = db.Column(db.Integer, db.ForeignKey('LO_SERVIDORES.idServidor'), nullable=True)
    idAuditoria = db.Column(db.Integer, db.ForeignKey('LO_PROCESOS.idAuditoria'), nullable=True) 
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
    nivelError = db.Column(db.String(10), nullable=True) 
    lineas = db.Column(db.JSON, nullable=True)

    empresa = db.relationship('asEmpresa', backref='logs')
    servidor = db.relationship('loServidores', foreign_keys=[idServidor], backref='logs')
    proceso = db.relationship('LoProcesos', foreign_keys=[idAuditoria], backref='logs')
