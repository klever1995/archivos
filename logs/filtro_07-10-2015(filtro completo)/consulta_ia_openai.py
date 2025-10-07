import logging
import os
from openai import AzureOpenAI

class Consulta_ia_openai:
    def __init__(self):
        # Configuración de Azure OpenAI (LEE DEL .ENV)
        self.azure_endpoint = "https://recursoazureopenaimupi.openai.azure.com/"
        self.api_key = os.getenv('AZURE_OPENAI_API_KEY')
        self.api_version = "2024-08-01-preview"
        self.model_name = "gpt-35-turbo-16k"

        # Inicializar el cliente
        self.client = AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.azure_endpoint,
            api_version=self.api_version
        )

    def interpretar_logs(self, texto_logs):
        """Método único y esencial para interpretar bloques de logs"""
        if not self.client:
            return "Error: Cliente no inicializado"

        try:
            # Hecho explícito del formato para facilitar el parseo en el backend
            system_prompt = """Eres un técnico experto en resolver problemas de servidores.
            Analiza los siguientes logs, identifica errores y para CADA error proporciona:

            LOG X (ID: [id]):
            PROBLEMA: **Causa principal:** [explicación técnica específica]
            SOLUCIÓN: **Solución concreta:** [solución específica]
            - Si la solución incluye código: **SIEMPRE** usa bloques de código con sintaxis
            - Para consultas SQL/HQL: muestra la consulta COMPLETA corregida
            - Para configuraciones: muestra la configuración exacta
            NIVEL: [leve|normal|crítico]

            CRITERIOS DE CRITICIDAD:
            - **CRÍTICO**: Errores que detienen el sistema, causan pérdida de datos, caídas completas del servicio, security breaches, o imposibilitan operaciones esenciales
            - **NORMAL**: Errores que afectan funcionalidades específicas pero permiten continuar operaciones, fallos en módulos no críticos, problemas de rendimiento significativos
            - **LEVE**: Warnings, timeouts temporales, problemas cosméticos, logs informativos, degradación menor de performance que no afecta funcionalidad core

            IMPORTANTE: 
            - **NO omitas** los bloques de código cuando sean necesarios
            - Usa ```language para envolver el código
            - Sé técnico y específico en las soluciones
            - Aplica los criterios de criticidad consistentemente

            Los logs están separados por '🔹🔹🔹'. Responde SOLO con el análisis de cada error.
            """


            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analiza estos logs:\n\n{texto_logs}"}
                ],
                temperature=0.5,
                max_tokens=4000
            )

            # Compatibilidad segura con la estructura de respuesta esperada
            content = None
            if hasattr(response, "choices") and response.choices:
                # Azure/OpenAI puede exponerlo como message.content o text — lo comprobamos
                choice = response.choices[0]
                if hasattr(choice, "message") and getattr(choice.message, "content", None):
                    content = choice.message.content
                elif getattr(choice, "text", None):
                    content = choice.text

            if not content:
                return "Error: Respuesta de IA vacía"

            return content.strip()

        except Exception as e:
            logging.error(f"Error en interpretar_logs: {e}", exc_info=True)
            return f"Error al procesar los logs: {e}"
