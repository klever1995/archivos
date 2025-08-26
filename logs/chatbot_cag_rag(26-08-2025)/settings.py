# config/settings.py
import os
from dotenv import load_dotenv

# Carga las variables del archivo .env
load_dotenv()

# ============================
# Configuración de Azure OpenAI (tu LLM principal)
# ============================
AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT",
    "https://recursoazureopenaimupi.openai.azure.com/"
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "poner el api de opneay aqui"
)

OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION", "2024-08-01-preview")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

# ============================
# Configuración para Embeddings LOCAL Y GRATUITO
# ============================
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "all-MiniLM-L6-v2"  # Modelo de SentenceTransformers
)

# ============================
# Configuración de ChromaDB (base de datos vectorial LOCAL)
# ============================
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", 8000))
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "documentos")

# ============================
# Configuración de Redis para caché de respuestas (opcional, puede ser local)
# ============================
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# ============================
# Configuración de Langfuse para monitoreo (tiene plan gratis)
# ============================
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# ============================
# Configuración de Caché de Contexto (para documentos estáticos, alternativa simple a vLLM)
# ============================
CONTEXT_CACHE_TYPE = os.getenv("CONTEXT_CACHE_TYPE", "memory")  # 'memory' o 'disk'
CONTEXT_CACHE_PATH = os.getenv("CONTEXT_CACHE_PATH", "./.cache_context")  # Si usa disk

# ============================
# Valores por defecto para el orquestador
# ============================
RAG_THRESHOLD = float(os.getenv("RAG_THRESHOLD", 0.7))  # Umbral de confianza para usar RAG
