

# Interpretación de logs por BLOQUES
    def interpretar_logs(self, texto_logs):

        if not self.client:
            return "Error: Cliente no inicializado"
            
        try:
            # Sistema prompt optimizado para procesamiento masivo
            system_prompt = """Eres un técnico experto en resolver problemas de servidores. 
            Analiza los siguientes logs, identifica errores y para CADA error proporciona:
            - Una explicación clara y concisa del problema
            - La solución específica para resolverlo

            Los logs están separados por '🔹🔹🔹'. Responde SOLO con el análisis de cada error, 
            manteniendo el mismo orden de los logs proporcionados. Evita texto introductorio o conclusiones generales."""
 
            # Llamada a API de OpenAI
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": system_prompt
                    },
                    {
                        "role": "user", 
                        "content": f"Analiza estos logs:\n\n{texto_logs}"
                    }
                ],
                temperature=0.3,
                max_tokens=4000  
            )

            # Validaciones de respuesta
            if not response.choices:
                logging.error("La API no devolvió choices en la respuesta")
                return "Error: No se obtuvo respuesta de la IA"
                
            if not response.choices[0].message.content:
                logging.error("La respuesta de la IA está vacía")
                return "Error: Respuesta de IA vacía"
                
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logging.error(f"Error crítico en interpretar_logs: {e}")
            return f"Error al procesar los logs: {e}"
