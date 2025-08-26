# core/rag_engine.py
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
import chromadb
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import logging

# =============================
# Configuración de logging
# =============================
logger = logging.getLogger(__name__)

# =============================
# Cargar variables de entorno
# =============================
load_dotenv()

# =============================
# Cliente Azure OpenAI
# =============================
openai_client = AzureOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION", "2024-08-01-preview")
)

# =============================
# RAG Engine
# =============================
class RAGEngine:
    def __init__(self, chroma_client: chromadb.Client, collection_name: str, openai_client: AzureOpenAI):
        self.chroma_client = chroma_client
        self.collection = chroma_client.get_or_create_collection(collection_name)
        self.openai_client = openai_client
        self.documents_store = {}  # Almacenamiento de textos completos {doc_id: full_text}
        logger.info("✅ RAG Engine inicializado con almacenamiento de documentos")

    # Ingestar documentos con chunking jerárquico
    def ingest_document(self, doc_id: str, text: str):
        """Ingesta documento y almacena texto completo"""
        try:
            # Almacenar texto completo
            self.documents_store[doc_id] = text
            logger.info(f"📄 Documento {doc_id} almacenado ({len(text)} caracteres)")

            # Procesar chunks jerárquicos
            large_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            large_chunks = large_splitter.split_text(text)

            for section_id, large_chunk in enumerate(large_chunks):
                self.collection.add(
                    ids=[f"{doc_id}_L{section_id}"],
                    documents=[large_chunk],
                    metadatas=[{
                        "doc_id": doc_id,
                        "section_id": section_id,
                        "chunk_id": -1,
                        "level": "large"
                    }]
                )

                small_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
                small_chunks = small_splitter.split_text(large_chunk)

                for chunk_id, small_chunk in enumerate(small_chunks):
                    self.collection.add(
                        ids=[f"{doc_id}_L{section_id}_S{chunk_id}"],
                        documents=[small_chunk],
                        metadatas=[{
                            "doc_id": doc_id,
                            "section_id": section_id,
                            "chunk_id": chunk_id,
                            "level": "small"
                        }]
                    )
            
            logger.info(f"✅ Documento {doc_id} procesado: {len(large_chunks)} chunks grandes, {sum([len(small_splitter.split_text(chunk)) for chunk in large_chunks])} chunks pequeños")

        except Exception as e:
            logger.error(f"❌ Error ingiriendo documento {doc_id}: {str(e)}")
            raise

    def get_document_text(self, doc_id: str = None) -> str:
        """
        Obtiene texto completo de documento(s)
        
        Args:
            doc_id: ID específico del documento o None para todos
        
        Returns:
            str: Texto completo del documento o concatenación de todos
        """
        try:
            if doc_id:
                return self.documents_store.get(doc_id, "")
            else:
                # Concatenar todos los documentos
                return "\n\n".join([f"[DOCUMENTO: {doc_id}]\n{content}" 
                                  for doc_id, content in self.documents_store.items()])
        except Exception as e:
            logger.error(f"❌ Error obteniendo texto completo: {str(e)}")
            return ""

    # Recuperación jerárquica
    def _build_context(self, query: str, top_k: int = 5) -> str:
        """Recupera contexto relevante usando chunks jerárquicos"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where={"level": "small"}
            )

            retrieved_chunks = []
            seen_large_sections = set()

            for doc, metadata in zip(results["documents"][0], results["metadatas"][0]):
                retrieved_chunks.append(doc)
                section_id = metadata["section_id"]
                doc_id = metadata["doc_id"]

                if (doc_id, section_id) not in seen_large_sections:
                    parent = self.collection.query(
                        query_texts=[query],
                        n_results=1,
                        where={"$and": [
                            {"doc_id": doc_id},
                            {"section_id": section_id},
                            {"level": "large"}
                        ]}
                    )
                    if parent["documents"]:
                        retrieved_chunks.append(parent["documents"][0][0])
                    seen_large_sections.add((doc_id, section_id))

            return "\n\n".join(retrieved_chunks)
            
        except Exception as e:
            logger.error(f"❌ Error construyendo contexto: {str(e)}")
            return ""

    # Generación de respuesta
    def generate_answer(self, query: str, top_k: int = 5) -> str:
        """Genera respuesta usando RAG"""
        try:
            context = self._build_context(query, top_k=top_k)
            
            if not context:
                return "No lo sé"
            
            prompt = f"""
Usa el siguiente contexto para responder la pregunta.
Si no encuentras la respuesta en el contexto, responde "No lo sé".

Contexto:
{context}

Pregunta: {query}

Respuesta:
"""
            response = self.openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
                messages=[
                    {"role": "system", "content": "Eres un asistente experto en recuperación de información."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Error generando respuesta RAG: {str(e)}")
            return "No lo sé"

# =============================
# Inicializar cliente Chroma y crear instancia singleton
# =============================
chroma_client = chromadb.Client()
rag_engine = RAGEngine(chroma_client, "docs_collection", openai_client)
