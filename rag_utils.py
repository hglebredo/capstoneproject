"""
rag_utils.py - Punto de entrada portable para el RAG del PB3/MLOps.

Uso:
    from rag_utils import responder, ejecutar_pipeline, init_rag_db

    # Online: pregunta -> retrieval -> LLM -> respuesta
    resultado = responder("¿Qué servicios ofrece el ayuntamiento?")
    print(resultado["respuesta"])

    # Offline: ingestión e indexación del corpus
    info = ejecutar_pipeline("./data/corpus/")

    # Inicializar base de datos relacional (Conversation + Message)
    init_rag_db()

Este módulo se importa desde la raíz del proyecto capstoneproject/ con:
    PYTHONPATH=. python -m rag_utils
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Asegurar que el paquete rag es importable desde cualquier ubicación
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def init_rag_db():
    """Inicializa la base de datos relacional (Conversation + Message).

    Crea las tablas si no existen. Compatible con SQLite y PostgreSQL.
    DATABASE_URL se lee del entorno; si no hay, usa SQLite local.
    """
    from rag.db.models import Base, get_engine

    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    # Verificar PGVector si está configurado
    backend = os.environ.get("VECTOR_BACKEND", "json").lower()
    if backend == "pgvector":
        try:
            from rag.retrieval.pgvector_store import PGVectorStore
            store = PGVectorStore()
            print(f"  PGVector listo, tabla={store.table}, dims={store.dim}")
        except Exception as exc:
            print(f"  Warning al inicializar PGVector: {exc}")

    db_url = os.environ.get("DATABASE_URL", "") or os.environ.get("PGVECTOR_DSN", "")
    storage = "postgresql" if db_url else "sqlite/local"
    print(f"Base de datos relacional lista (storage={storage}).")


def responder(pregunta: str, top_k: int | None = None) -> dict:
    """Pipeline RAG completo: pregunta -> retrieval -> LLM -> respuesta.

    Alias para rag.logic.responder().
    """
    from rag.logic import responder as _responder
    return _responder(pregunta, top_k=top_k)


def ejecutar_pipeline(rutas="data", **kwargs):
    """Ejecuta el pipeline de indexación: LOAD → CLEAN → TAG → CHUNK → EMBED → INDEX.

    Alias para rag.pipeline.ejecutar_pipeline().
    """
    from rag.pipeline import ejecutar_pipeline as _ejecutar
    return _ejecutar(rutas, **kwargs)


def get_rag_status() -> dict:
    """Devuelve el estado actual del RAG (útil para /health)."""
    status = {
        "service": "rag-agent-mlops",
        "storage": os.environ.get("VECTOR_BACKEND", "json"),
        "db_ok": True,
        "config": {},
    }

    # Leer configuración clave desde el entorno
    from rag import config as cfg
    status["config"]["embed_provider"] = cfg.EMBED_PROVIDER
    status["config"]["gen_provider"] = cfg.GEN_PROVIDER
    status["config"]["rag_model"] = cfg.GEN_MODEL
    status["config"]["retrieval_mode"] = cfg.RETRIEVAL_MODE

    # Verificar conexión a BD si es PostgreSQL
    db_url = os.environ.get("DATABASE_URL", "") or os.environ.get("PGVECTOR_DSN", "")
    if db_url:
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(db_url.replace("postgres://", "postgresql://"))
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            status["db_ok"] = True
            status["storage"] = "postgresql"
        except Exception:
            status["db_ok"] = False
            status["status"] = "degraded"

    return status


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="RAG portable para PB3/MLOps -  capstoneproject/"
    )
    parser.add_argument(
        "--mode", choices=["test", "pipeline", "health"], default="test",
        help="Modo de ejecución: test (pregunta demo), pipeline (indexar), health (estado)"
    )
    parser.add_argument("--query", default="¿Qué servicios ofrece el ayuntamiento?",
                        help="Pregunta para modo 'test'")

    args = parser.parse_args()

    if args.mode == "health":
        status = get_rag_status()
        print(f"Estado RAG: {status}")

    elif args.mode == "pipeline":
        init_rag_db()
        info = ejecutar_pipeline("data")
        print(f"Pipeline completado: {info.get('num_documentos_cargados')} docs, "
              f"{info.get('num_chunks_post_dedup')} chunks")

    else:  # test
        init_rag_db()
        resultado = responder(args.query)
        print(f"Pregunta: {args.query}")
        print(f"Respuesta: {resultado['respuesta']}")
        if resultado.get("chunks"):
            print(f"Fuentes: {resultado['fuentes'][:3]}...")
