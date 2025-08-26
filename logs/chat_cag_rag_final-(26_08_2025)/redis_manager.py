import logging
import redis
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RedisCacheManager:
    """Gestor de caché usando Redis en línea"""
    
    def __init__(self, host, port, password=None, db=0, expiration_hours=24):
        self.expiration_hours = expiration_hours
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                password=password,
                db=db,
                decode_responses=True
            )
            # Test conexión
            self.redis_client.ping()
            logger.info("✅ Conectado a Redis correctamente")
        except Exception as e:
            logger.error(f"❌ Error conectando a Redis: {str(e)}")
            raise e

    def get_cached_response(self, query):
        try:
            cache_key = f"response:{query}"
            data = self.redis_client.get(cache_key)
            if data:
                cached = json.loads(data)
                expiration = datetime.fromisoformat(cached["expiration"])
                if datetime.now() < expiration:
                    logger.debug(f"✅ Respuesta encontrada en Redis para: {query}")
                    return cached["response"]
                else:
                    self.redis_client.delete(cache_key)
            return None
        except Exception as e:
            logger.error(f"❌ Error obteniendo de Redis: {str(e)}")
            return None

    def set_cached_response(self, query, response):
        try:
            cache_key = f"response:{query}"
            expiration_time = datetime.now() + timedelta(hours=self.expiration_hours)
            cached_data = {
                "response": response,
                "expiration": expiration_time.isoformat()
            }
            self.redis_client.set(cache_key, json.dumps(cached_data))
            logger.debug(f"✅ Respuesta guardada en Redis para: {query}")
        except Exception as e:
            logger.error(f"❌ Error guardando en Redis: {str(e)}")

# Instancia singleton para importar
redis_cache = RedisCacheManager(
    host="redis-19020.c99.us-east-1-4.ec2.redns.redis-cloud.com",
    port=19020,
    password='lExj68SsyMKGN8jZVPDSjLR5N6zFI1mS'
)
