# models/embeddings.py
import logging
from sentence_transformers import SentenceTransformer
from config.settings import EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)

class EmbeddingModel:
    """Cliente para generar embeddings usando SentenceTransformers localmente"""
    
    def __init__(self):
        try:
            self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            self.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"✅ Modelo de embeddings '{EMBEDDING_MODEL_NAME}' cargado. Dimensión: {self.dimension}")
        except Exception as e:
            logger.error(f"❌ Error cargando el modelo de embeddings: {str(e)}")
            raise
    
    def get_embeddings(self, texts):
        """Genera embeddings para una lista de textos"""
        if isinstance(texts, str):
            texts = [texts]
        
        try:
            embeddings = self.model.encode(texts, normalize_embeddings=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"❌ Error generando embeddings: {str(e)}")
            raise

# Instancia singleton para ser importada
embedding_model = EmbeddingModel()
