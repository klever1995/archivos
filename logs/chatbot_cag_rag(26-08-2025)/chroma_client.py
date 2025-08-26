# databases/chroma_client.py
import logging
import chromadb
from chromadb.config import Settings
from config.settings import CHROMA_HOST, CHROMA_PORT, CHROMA_COLLECTION_NAME
from models.embeddings import embedding_model

logger = logging.getLogger(__name__)

class ChromaClient:
    """Cliente para interactuar con ChromaDB"""
    
    def __init__(self):
        try:
            # Configurar cliente de Chroma
            self.client = chromadb.HttpClient(
                host=CHROMA_HOST,
                port=CHROMA_PORT,
                settings=Settings(allow_reset=True)
            )
            
            # Crear o obtener la colección
            self.collection = self.client.get_or_create_collection(
                name=CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info(f"✅ Cliente ChromaDB conectado a {CHROMA_HOST}:{CHROMA_PORT}")
            logger.info(f"✅ Colección '{CHROMA_COLLECTION_NAME}' lista")
            
        except Exception as e:
            logger.error(f"❌ Error conectando con ChromaDB: {str(e)}")
            raise
    
    def add_documents(self, documents, ids=None, metadatas=None):
        """Añade documentos a la colección con sus embeddings"""
        if not documents:
            return
        
        try:
            # Generar embeddings
            embeddings = embedding_model.get_embeddings(documents)
            
            # Si no se proporcionan IDs, generar automáticamente
            if ids is None:
                ids = [f"doc_{i}" for i in range(len(documents))]
            
            # Añadir a la colección
            self.collection.add(
                documents=documents,
                embeddings=embeddings,
                ids=ids,
                metadatas=metadatas
            )
            
            logger.info(f"✅ Añadidos {len(documents)} documentos a la colección")
            
        except Exception as e:
            logger.error(f"❌ Error añadiendo documentos: {str(e)}")
            raise
    
    def search(self, query_text, n_results=5):
        """Busca documentos similares a la consulta"""
        try:
            # Generar embedding de la consulta
            query_embedding = embedding_model.get_embeddings(query_text)[0]
            
            # Realizar búsqueda
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error en búsqueda: {str(e)}")
            return {'documents': [[]], 'ids': [[]]}
    
    def reset_collection(self):
        """Elimina todos los documentos de la colección (para desarrollo)"""
        try:
            # Método alternativo: obtener todos los IDs y eliminarlos
            existing_docs = self.collection.get()
            if existing_docs['ids']:
                self.collection.delete(ids=existing_docs['ids'])
                logger.warning(f"🔄 Colección limpiada: {len(existing_docs['ids'])} documentos eliminados")
            else:
                logger.info("ℹ️ La colección ya está vacía")
                
        except Exception as e:
            logger.error(f"❌ Error reseteando colección: {str(e)}")
            raise

# Instancia singleton para ser importada
chroma_client = ChromaClient()
