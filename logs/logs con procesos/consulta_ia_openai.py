----------------------metodo para consultar los errores en openai------------archivo consulta_ia_openai.py------------------------
#Interpretación de logs
    def interpretar_logs(self, texto_logs):

        if not self.client:
            return "Error: Cliente no inicializado"
            
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Eres un técnico experto en servidores. Analiza estos logs, identifica errores y provee soluciones concretas en máximo 3 pasos. Sé técnico y directo."},
                    {"role": "user", "content": texto_logs}
                ],
                temperature=0.3,
                max_tokens=500  # Reducido para respuestas más concisas
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"Error en interpretar_logs: {e}")
            return f"Error al procesar los logs: {e}"
        
    def respuesta_rapida(self, texto):
        if not self.client:
            return "Error: Cliente no inicializado"
            
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Responde de manera concisa y útil"},
                    {"role": "user", "content": texto}
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"Error en respuesta_rapida: {e}")
            return f"Error al procesar la solicitud: {e}"

-----------------------clase que representa la tabla loLogs -------------------- archivo loLogs.py----------------------
from config import db

# Clase que representa la tabla LO_LOGS en la base de datos para almacenar registros de logs
class loLogs(db.Model):
    __tablename__ = 'LO_LOGS'
    
    idLogAplicacion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
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
    lineas = db.Column(db.JSON, nullable=True)

    empresa = db.relationship('asEmpresa', backref='logs')
    
