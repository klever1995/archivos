# evaluation/langfuse_monitoring.py
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LangfuseMonitor:
    """Mock de Langfuse para monitoreo (implementación dummy)"""
    
    def __init__(self):
        logger.info("✅ Langfuse monitor inicializado (modo dummy)")
    
    def trace_query(self, query: str, response: str, route: str, user_id: Optional[str] = None):
        """
        Simula el tracing de una consulta sin enviar datos a Langfuse
        """
        try:
            # Solo loguear localmente para debugging
            logger.debug(f"📊 Tracing dummy - Query: '{query}', Ruta: {route}, User: {user_id}")
            logger.debug(f"📊 Response: {response[:100]}...")
            
        except Exception as e:
            logger.warning(f"⚠️ Error en tracing dummy: {e}")

# Instancia singleton para ser importada
langfuse_monitor = LangfuseMonitor()
