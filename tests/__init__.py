"""Tests del entorno RAG PB3/MLOps.

Cobertura:
    - security.py       : API key, rate limit, timeout
    - schemas_mlops.py  : Validación de Pydantic (AskIn/Out, ApproveIn/Out, MessageOut)
    - app.py            : Rutas FastAPI (/health, /ask, /approve, /threads/{id}/messages)
    - rag/config.py     : Resoluciones de proveedores y modelos
    - rag/logic.py      : Pipeline online (responder, rag_ask, validación, abstención)
    - rag/embed.py      : Embeddings por proveedor + checkpointing
    - rag/generate.py   : Generación por proveedor con retry
    - rag/retrieve.py   : Recuperación vectorial y híbrida RRF
    - rag/db/           : ensure_conversation, add_message, get_messages (SQLite)
"""
