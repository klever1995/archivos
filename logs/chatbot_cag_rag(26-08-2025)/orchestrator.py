# core/orchestrator.py
import logging
import re
from config.settings import RAG_THRESHOLD
from cache.redis_manager import redis_cache
from cache.context_cache import context_cache

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orquestador inteligente que decide entre RAG y CAG"""

    def __init__(self):
        self.rag_threshold = RAG_THRESHOLD
        logger.info(f" Orquestador inicializado con umbral RAG: {self.rag_threshold}")

    def should_use_rag(self, query):
        """
        Decide si usar RAG basándose en la complejidad de la consulta
        """
        if self._is_complex_query(query):
            logger.debug(" Consulta compleja detectada → usar RAG")
            return True
        elif self._is_simple_query(query):
            logger.debug(" Consulta simple detectada → usar CAG")
            return False
        else:
            # Por defecto, usa RAG si no cae en ninguna categoría clara
            logger.debug(" Consulta ambigua → usar RAG por defecto")
            return True

    def _is_simple_query(self, query):
        """Determina si la consulta es simple (puede ser respondida con documentos cacheados)"""
        # Consultas muy cortas probablemente sean simples
        if len(query.split()) <= 3:
            return True

        # Patrones de consultas simples
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
        # Consultas largas probablemente sean complejas
        if len(query.split()) > 8:
            return True

        # Patrones de consultas complejas
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

    def route_query(self, query):
        """
        Decide la ruta para la consulta y devuelve el tipo de camino
        Returns:
            str: "rag" o "cag"
        """
        if self.should_use_rag(query):
            return "rag"
        else:
            return "cag"


# Instancia singleton para ser importada
orchestrator = Orchestrator()
