# clear_redis_memory.py
import logging
from cache.redis_manager import redis_cache  # importa tu instancia existente

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_all_redis():
    """Elimina todas las claves almacenadas en Redis."""
    try:
        redis_cache.redis_client.flushdb()  # borra todo el contenido de la base de datos actual
        logger.info("✅ Todas las entradas en Redis han sido eliminadas correctamente.")
    except Exception as e:
        logger.error(f"❌ Error borrando Redis: {str(e)}")

if __name__ == "__main__":
    clear_all_redis()
