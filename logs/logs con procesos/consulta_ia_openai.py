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

