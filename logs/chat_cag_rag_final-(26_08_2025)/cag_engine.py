# core/cag_engine.py
import logging
from models.llms import azure_llm_client
from cache.redis_manager import redis_cache

logger = logging.getLogger(__name__)

class CAGEngine:
    """Motor CAG para respuestas con contexto externo"""

    def __init__(self):
        logger.info("✅ Motor CAG inicializado")

    def generate_response(self, query, external_context=None):
        """
        Genera una respuesta usando contexto externo desde RAG.
        
        Parámetros:
            query (str): Pregunta del usuario.
            external_context (str, opcional): Contexto completo pasado desde RAG.
        """
        try:
            # 1. Verificar si existe respuesta en Redis
            cached_response = redis_cache.get_cached_response(query)
            if cached_response:
                logger.debug(f"✅ Respuesta recuperada de Redis: {query}")
                return cached_response

            # 2. Validar que tenemos contexto externo
            if not external_context:
                logger.debug("❌ No se proporcionó contexto externo")
                return "No tengo información suficiente para responder esta pregunta."

            # 3. Generar prompt para el LLM
            messages = self._build_messages(query, external_context)

            # 4. Obtener respuesta del LLM
            logger.debug("🔄 Generando respuesta con Azure OpenAI...")
            response = azure_llm_client.generate_response(messages)

            # 5. Cachear respuesta en Redis SOLO si es una respuesta válida
            if response and not self._is_negative_response(response):
                redis_cache.set_cached_response(query, response)
                logger.debug("✅ Respuesta válida cacheada en Redis")
            else:
                logger.debug("⏩ Respuesta negativa NO cacheada en Redis")

            logger.info("✅ Respuesta CAG generada exitosamente")
            return response

        except Exception as e:
            logger.error(f"❌ Error en el motor CAG: {str(e)}")
            return "Lo siento, ocurrió un error al procesar tu consulta."

    def _is_negative_response(self, response):
        """Determina si la respuesta es negativa (no debe cachearse)"""
        if not response or not response.strip():
            return True
            
        negative_phrases = [
            "no lo sé",
            "no tengo información",
            "no está en el contexto",
            "no encuentro",
            "no se menciona",
            "no aparece",
            "no puedo responder"
        ]
        response_lower = response.lower()
        return any(phrase in response_lower for phrase in negative_phrases)

    def _build_messages(self, query, context):
        """Construye los mensajes para el LLM con el contexto"""
        system_message = """Eres un asistente útil que responde preguntas basándose ÚNICAMENTE 
en el contexto proporcionado. 
Sigue estas reglas:
1. Responde solo con la información del contexto
2. Si la información no está en el contexto, di "No lo sé"
3. Sé conciso y directo
4. Usa el mismo idioma de la pregunta"""

        # Limitar el tamaño del contexto para no exceder tokens
        limited_context = context[:12000]  # ~3000 tokens aprox

        user_message = f"""Contexto:
{limited_context}

Pregunta: {query}

Por favor, responde basándote solo en el contexto anterior. Si la información no está en el contexto, di "No lo sé"."""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

    def process_query(self, query, external_context=None):
        """Método principal para procesar consultas CAG"""
        return self.generate_response(query, external_context=external_context)

# Instancia singleton para ser importada
cag_engine = CAGEngine()
