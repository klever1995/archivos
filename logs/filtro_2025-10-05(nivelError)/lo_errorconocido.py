from config import db

#Clase de la tabla lo_errorconocido
class loErrorconocido(db.Model):
    __tablename__ = 'LO_ERRORCONOCIDO'
    
    iderrorconocido = db.Column(db.Integer, primary_key=True, autoincrement=True)
    hasherror = db.Column(db.String(64), nullable=False, unique=True)  
    mensajenormalizado = db.Column(db.Text, nullable=False)  
    nivel = db.Column(db.String(10), nullable=False) 
    respuestaopenai = db.Column(db.Text, nullable=True)
    nivelError = db.Column(db.String(10), nullable=True) 
    fechaprimeraocurrencia = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    fechaultimaactualizacion = db.Column(
        db.DateTime, 
        nullable=False, 
        default=db.func.current_timestamp(), 
        onupdate=db.func.current_timestamp()
    )
