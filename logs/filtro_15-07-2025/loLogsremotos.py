from config import db
from datetime import datetime

class LoLogsRemotos(db.Model):
    __tablename__ = 'LO_LOGSREMOTOS'

    idLogRemoto = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    idServidor = db.Column(db.Integer, db.ForeignKey('LO_SERVIDORES.idServidor'), nullable=False)
    idAuditoria = db.Column(db.Integer, db.ForeignKey('LO_PROCESOS.idAuditoria'), nullable=False)
    fechaCreacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    nivel = db.Column(db.String(10), nullable=False)
    mensaje = db.Column(db.Text, nullable=True)
    categoria = db.Column(db.String(100), nullable=True)
    ocurrencias = db.Column(db.Integer, default=1, nullable=True)

    # Relaciones
    empresa = db.relationship('AsEmpresa', backref='logs_remotos')
    servidor = db.relationship('LoServidores', backref='logs_remotos')
    proceso = db.relationship('LoProcesos', backref='logs_remotos')

    def __repr__(self):
        return f"<LoLogsRemotos idLogRemoto={self.idLogRemoto} nivel={self.nivel} fecha={self.fechaCreacion}>"
