# config/settings.py
import os
from dotenv import load_dotenv

# Carga las variables del archivo .env
load_dotenv()

# ============================
# Configuración de Azure OpenAI (tu LLM principal)
# ============================
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION", "2024-08-01-preview")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

# Validación de variables críticas
if not AZURE_OPENAI_ENDPOINT:
    raise ValueError("❌ AZURE_OPENAI_ENDPOINT no está configurado en las variables de entorno")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY no está configurado en las variables de entorno")

# ============================
# Configuración para Embeddings LOCAL Y GRATUITO
# ============================
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# ============================
# Configuración de ChromaDB (base de datos vectorial LOCAL)
# ============================
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", 8000))
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "documentos")

# ============================
# Configuración de Redis para caché de respuestas
# ============================
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# ============================
# Configuración de Langfuse para monitoreo (opcional)
# ============================
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# ============================
# Configuración de Caché de Contexto (ahora eliminado)
# ============================
# CONTEXT_CACHE_TYPE y CONTEXT_CACHE_PATH ya no se usan

# ============================
# Valores por defecto para el orquestador
# ============================
RAG_THRESHOLD = float(os.getenv("RAG_THRESHOLD", 0.7))

# ============================
# Configuración del servidor FastAPI
# ============================
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 9000))
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# ============================
# Logging configuration
# ============================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ============================
# Validación final
# ============================
def validate_settings():
    """Valida que las configuraciones críticas estén presentes"""
    required_settings = {
        "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
        "OPENAI_API_KEY": OPENAI_API_KEY,
    }
    
    for name, value in required_settings.items():
        if not value:
            raise ValueError(f"❌ Configuración requerida faltante: {name}")
    
    print("✅ Todas las configuraciones son válidas")

# Ejecutar validación al importar
validate_settings()
