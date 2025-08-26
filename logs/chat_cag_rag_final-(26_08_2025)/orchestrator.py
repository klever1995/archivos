# core/orchestrator.py
import logging
import re
from config.settings import RAG_THRESHOLD
from cache.redis_manager import redis_cache
from core.rag_engine import rag_engine
from core.cag_engine import cag_engine

logger = logging.getLogger(__name__)

class Orchestrator:
    """Orquestador inteligente que decide entre RAG y CAG con cache Redis"""

    def __init__(self):
        self.rag_threshold = RAG_THRESHOLD
        logger.info(f"✅ Orquestador inicializado con umbral RAG: {self.rag_threshold}")

    def should_use_rag(self, query):
        """Decide si usar RAG basándose en la complejidad de la consulta"""
        if self._is_complex_query(query):
            logger.debug("🔍 Consulta compleja detectada → usar RAG")
            return True
        elif self._is_simple_query(query):
            logger.debug("🔍 Consulta simple detectada → usar CAG")
            return False
        else:
            # Por defecto, usa RAG si no cae en ninguna categoría clara
            logger.debug("🔍 Consulta ambigua → usar RAG por defecto")
            return True

    def _is_simple_query(self, query):
        """Determina si la consulta es simple (puede ser respondida con documentos cacheados)"""
        if len(query.split()) <= 3:
            return True

        simple_patterns = [
            r"qué es.*",
            r"quien es.*",
            r"cómo funciona.*",
            r"definición de.*",
            r"explica.*",
            r"habla sobre.*"
        ]
        query_lower = query.lower()
        for pattern in simple_patterns:
            if re.match(pattern, query_lower):
                return True
        return False

    def _is_complex_query(self, query):
        """Determina si la consulta es compleja (requiere RAG)"""
        if len(query.split()) > 8:
            return True

        complex_patterns = [
            r"comparar.*",
            r"ventajas y desventajas.*",
            r"pros y contras.*",
            r"diferencia entre.*",
            r"ejemplo de.*",
            r"cómo hacer.*",
            r"pasos para.*",
            r"mejor manera de.*",
            r"qué pasa si.*"
        ]
        query_lower = query.lower()
        for pattern in complex_patterns:
            if re.match(pattern, query_lower):
                return True
        return False

    def _should_fallback_to_cag(self, response):
        """Determina si la respuesta del RAG requiere fallback a CAG"""
        if not response or not response.strip():
            return True
        
        negative_indicators = [
            "no lo sé",
            "no encuentro",
            "no tengo información",
            "no está en el contexto",
            "no aparece en el texto",
            "no se menciona"
        ]
        
        response_lower = response.lower()
        return any(indicator in response_lower for indicator in negative_indicators)

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

    def _cache_response_if_valid(self, query, response):
        """Cachea la respuesta solo si no es negativa"""
        if not self._is_negative_response(response):
            redis_cache.set_cached_response(query, response)
            logger.debug("✅ Respuesta válida cacheada en Redis")
        else:
            logger.debug("⏩ Respuesta negativa NO cacheada en Redis")

    def route_query(self, query):
        """
        Ruta principal que decide entre Redis, RAG y CAG
        Returns:
            dict: {"response": str, "route": str, "source": str}
        """
        try:
            # 1️⃣ Revisar si ya existe en Redis
            cached = redis_cache.get_cached_response(query)
            if cached:
                logger.info("✅ Respuesta obtenida desde Redis")
                return {"response": cached, "route": "redis", "source": "redis_cache"}

            # 2️⃣ Decidir si usar RAG o CAG
            use_rag = self.should_use_rag(query)
            
            if use_rag:
                # Intentar con RAG primero
                response = rag_engine.generate_answer(query)
                
                if not self._should_fallback_to_cag(response):
                    # RAG tuvo éxito → Cachear si es válida
                    self._cache_response_if_valid(query, response)
                    return {"response": response, "route": "rag", "source": "chroma_db"}
                else:
                    # RAG falló → Fallback a CAG con contexto completo
                    logger.warning("⚠️ RAG no encontró contexto → fallback a CAG con texto completo")
                    full_text = rag_engine.get_document_text()
                    logger.debug(f"📊 Longitud del texto completo: {len(full_text)} caracteres")
                    
                    response = cag_engine.generate_response(query, external_context=full_text)
                    # Cachear solo si es válida
                    self._cache_response_if_valid(query, response)
                    return {"response": response, "route": "cag", "source": "full_context"}
                    
            else:
                # Ruta simple: CAG directo (sin contexto externo)
                logger.debug("🟡 Ruta simple → CAG directo")
                response = cag_engine.generate_response(query)
                # Cachear solo si es válida
                self._cache_response_if_valid(query, response)
                return {"response": response, "route": "cag", "source": "context_cache"}
                
        except Exception as e:
            logger.error(f"❌ Error en route_query: {str(e)}")
            # Fallback de emergencia (NO cachear errores)
            emergency_response = "Lo siento, ocurrió un error al procesar tu consulta."
            return {"response": emergency_response, "route": "error", "source": "fallback"}

# Instancia singleton para importar
orchestrator = Orchestrator()
