"""Paquete rag - RAG pipeline de Deporte Municipal Madrid.

Submódulos principales:
    config      · Variables de entorno (proveedores, modelos, rutas)
    logic       · Orquestador online: responder(), rag_ask()
    pipeline    · Pipeline offline completo: ejecutar_pipeline()
    load        · Carga de documentos (PDF, CSV, TXT, MD)
    clean       · Limpieza y normalización por formato
    chunk       · Troceado en fragmentos (RecursiveCharacterTextSplitter)
    embed       · Embeddings con Ollama / HuggingFace / Google GenAI
    generate    · Generación de texto con LLM (Gemini, Ollama, HF)
    retrieve    · Recuperación híbrida: vectorial + BM25 fusionada por RRF
    prompts     · Construcción del prompt para el LLM
    index       · Indexación en ChromaDB
    vision      · Carga de imágenes con OCR y Gemini Vision
    pdf_tabular · Procesamiento especial de PDFs TAB/OCR
    csv_advisor · Clasificación heurística de CSVs (policy-aware)
    csv_transform · Transformación de filas a Documents según política

Paquetes internos:
    tsd         · Tagging, Scoring y Deduplicación (offline)
    db          · Capa relacional: Conversation + Message (Postgres/SQLite)
    tools       · Utilidades: métricas, debugging, reporting

API pública (desde la raíz):
    from rag import responder, ejecutar_pipeline
    from rag_utils import init_rag_db  # punto de entrada portable
"""
from .logic import rag_ask, responder
from .pipeline import ejecutar_pipeline
from .load import _formato_documento

__all__ = ["responder", "rag_ask", "ejecutar_pipeline", "_formato_documento"]

