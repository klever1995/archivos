# ============================
# CONFIGURACIÓN SSL GLOBAL - DESACTIVAR VERIFICACIÓN
# ============================
import os
import warnings

warnings.filterwarnings("ignore", message="Unverified HTTPS request")
os.environ['SSL_CERT_FILE'] = ""
os.environ['REQUESTS_CA_BUNDLE'] = ""
os.environ['CURL_CA_BUNDLE'] = ""
os.environ['PYTHONHTTPSVERIFY'] = "0"
os.environ['NO_PROXY'] = '*'

# ============================
# IMPORTACIONES
# ============================
import logging
import ssl
import urllib3
import requests
from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
from pathlib import Path
from PyPDF2 import PdfReader

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests_session = requests.Session()
requests_session.verify = False

# ============================
# MÓDULOS PROPIOS
# ============================
from core.orchestrator import orchestrator
from core.rag_engine import rag_engine
from core.cag_engine import cag_engine
from evaluation.langfuse_monitoring import langfuse_monitor

# ============================
# LOGGING
# ============================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================
# FASTAPI
# ============================
app = FastAPI(title="Sistema RAG + CAG", version="1.0.0")

# ============================
# MODELOS
# ============================
class QueryRequest(BaseModel):
    query: str
    user_id: str = "anonymous"

class QueryResponse(BaseModel):
    response: str
    route: str
    source: str

# ============================
# ENDPOINTS
# ============================
@app.post("/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Sube un PDF y lo indexa en Chroma con chunking jerárquico"""
    try:
        file_path = Path("uploaded_docs") / file.filename
        file_path.parent.mkdir(exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(await file.read())

        reader = PdfReader(str(file_path))
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"

        doc_id = file.filename.replace(".", "_")
        rag_engine.ingest_document(doc_id, full_text)

        return {"status": "success", "message": f"Documento {file.filename} indexado correctamente."}
    except Exception as e:
        logger.error(f" Error subiendo PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Procesa consultas con fallback RAG → CAG"""
    try:
        logger.info(f" Consulta recibida: '{request.query}'")

        # 1. Decidir la ruta (string garantizado)
        route = orchestrator.route_query(request.query)
        if isinstance(route, dict):
            route = route.get("route", "rag")  # fallback por si devuelve dict
        logger.info(f" Ruta inicial decidida: {route.upper()}")

        # 2. Procesar según la ruta
        response = None
        source = ""

        if route == "rag":
            response = rag_engine.generate_answer(request.query)
            source = "chroma_db"

            # Fallback a CAG si RAG no devuelve respuesta significativa
            if not response or "No lo sé" in response or "no encuentro" in response.lower():
                logger.info(" RAG no encontró respuesta → fallback a CAG")
                response = cag_engine.process_query(request.query)
                source = "context_cache"
                route = "cag"
        else:
            response = cag_engine.process_query(request.query)
            source = "context_cache"

        # 3. Monitoreo Langfuse opcional
        try:
            langfuse_monitor.trace_query(
                query=request.query,
                response=response,
                route=route,
                user_id=request.user_id
            )
        except Exception as e:
            logger.warning(f" Error en monitoreo Langfuse: {e}")

        logger.info(f" Respuesta generada vía {source}")

        return QueryResponse(
            response=response,
            route=route,
            source=source
        )

    except Exception as e:
        logger.error(f" Error procesando consulta: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "rag-cag-system"}

@app.get("/")
async def root():
    return {
        "message": "Sistema RAG + CAG funcionando",
        "endpoints": {
            "health": "/health",
            "query": "/query (POST)"
        }
    }

# ============================
# MAIN
# ============================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000, ssl_certfile=None)
