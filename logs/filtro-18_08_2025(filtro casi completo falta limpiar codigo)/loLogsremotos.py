from config import db

#Clase de la tabla lo_logsremotos
class loLogsremotos(db.Model):
    __tablename__ = 'LO_LOGSREMOTOS'  
    
    idLogRemoto = db.Column(db.Integer, primary_key=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    idServidor = db.Column(db.Integer, db.ForeignKey('LO_SERVIDORES.idServidor'), nullable=False)
    idAuditoria = db.Column(db.Integer, db.ForeignKey('LO_PROCESOS.idAuditoria'), nullable=False)
    fechaCreacion = db.Column(db.DateTime, nullable=False)
    nivel = db.Column(db.String(10), nullable=False)
    mensaje = db.Column(db.Text)
    categoria = db.Column(db.String(100))
    ocurrencias = db.Column(db.Integer, default=1)
    componente = db.Column(db.String(255))  
    hilo = db.Column(db.String(200))    
    lineas = db.Column(db.JSON)   

    empresa = db.relationship('asEmpresa', backref='logsremotos')  
    servidor = db.relationship('loServidores', foreign_keys=[idServidor], backref='logsremotos')  
    proceso = db.relationship('LoProcesos', foreign_keys=[idAuditoria], backref='logsremotos')
