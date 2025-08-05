from config import db
from datetime import datetime

class loInterpretacionremota(db.Model):
    __tablename__ = 'LO_INTERPRETACIONREMOTA'
    
    idInterpretacion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idProcesoFiltrado = db.Column(
        db.Integer, 
        db.ForeignKey('LO_PROCESOS.idAuditoria'), 
        nullable=False,
        comment='FK a LO_PROCESOS.idAuditoria (solo procesos con tipoProceso=FILTRADOREMOTO)'
    )
    idServidor = db.Column(
        db.Integer, 
        db.ForeignKey('LO_SERVIDORES.idServidor'), 
        nullable=False
    )
    fechaInicio = db.Column(db.DateTime, nullable=False, default=datetime.now)
    fechaFin = db.Column(db.DateTime)
    ultimoLogProcesado = db.Column(
        db.Integer, 
        default=0, 
        comment='ID del último registro procesado en LO_LOGSREMOTOS'
    )
    totalLogsInterpretados = db.Column(db.Integer, default=0)
    estado = db.Column(db.String(20))

    # Relaciones exactas (con nombres exactos de clase)
    proceso_filtrado = db.relationship(
        'LoProcesos',  
        foreign_keys=[idProcesoFiltrado],
        backref=db.backref('interpretaciones_remotas', lazy='dynamic')
    )
    servidor = db.relationship(
        'loServidores',  
        foreign_keys=[idServidor],
        backref=db.backref('interpretaciones_remotas', lazy='dynamic')
    )

    @property
    def duracionSegundos(self):
        if self.fechaFin:
            return (self.fechaFin - self.fechaInicio).total_seconds()
        return None

    def __repr__(self):
        return f'<loInterpretacionremota {self.idInterpretacion} (Proceso: {self.idProcesoFiltrado})>'
