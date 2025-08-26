# models/llms.py
import os
os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'
import logging
from openai import AzureOpenAI
from config.settings import AZURE_OPENAI_ENDPOINT, OPENAI_API_KEY, OPENAI_API_VERSION, OPENAI_MODEL_NAME

logger = logging.getLogger(__name__)

class AzureOpenAIClient:
    """Cliente para interactuar con Azure OpenAI"""
    
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=OPENAI_API_KEY,
            api_version=OPENAI_API_VERSION,
        )
        self.model_name = OPENAI_MODEL_NAME
        logger.info(f"✅ Cliente de Azure OpenAI configurado con modelo: {self.model_name}")
    
    def generate_response(self, messages, temperature=0.1, max_tokens=2000):
        """Genera una respuesta usando el chat completion de Azure OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"❌ Error en la generación con Azure OpenAI: {str(e)}")
            raise

# Instancia singleton para ser importada
azure_llm_client = AzureOpenAIClient()
