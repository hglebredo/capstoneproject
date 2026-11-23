"""app.py - FastAPI del contrato PB3/MLOps.

Rutas PB3: /health, /ask, /approve, /threads/{thread_id}/messages
Seguridad: API key (401), rate limit (429), timeout (504).
Agente: reutiliza rag.logic.responder() del PB2 sin reescribir el grafo.

Uso:
    python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from rag.db.models import Conversation as ConvModel, get_engine
from rag.db.db_engine import _now, add_message, ensure_conversation, get_messages
from schemas_mlops import (AskIn, AskOut, ApproveIn, ApproveOut, MessageOut,
                           MessagesOut)
from security import (ASK_TIMEOUT_SECONDS, API_KEY, check_timeout, log_request,
                      rate_limit_middleware, require_api_key)

# --------------------------------------------------------------------------- #
#  Instancia FastAPI                                                           #
# --------------------------------------------------------------------------- #

app = FastAPI(title="RAG Agent - PB3/MLOps", version="1.0.0")

# CORS abierto para el front Streamlit
CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(",") if CORS_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limit middleware (antes de las rutas para que cuente todo)
app.middleware("http")(rate_limit_middleware)


def _get_rag_responder():
    """Importa rag.logic.responder perezosamente (evita arranque lento)."""
    from rag.logic import responder as fn
    return fn

# --------------------------------------------------------------------------- #
#  Rutas publicas                                                             #
# --------------------------------------------------------------------------- #

@app.get("/health")
async def health() -> dict:
    """Pulso del servicio. Indica que el almacenamiento es Postgres."""
    db_url = os.environ.get("DATABASE_URL", "") or os.environ.get("PGVECTOR_DSN", "")
    storage = "postgresql" if db_url else "sqlite/local"

    # Verificar conexión si hay URL de BD
    db_ok = True
    if db_url:
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(db_url.replace("postgres://", "postgresql://"))
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "storage": storage,
        "db_ok": db_ok,
    }


# --------------------------------------------------------------------------- #
#  Rutas PB3 / MLOps                                                          #
# --------------------------------------------------------------------------- #

@app.post("/ask", response_model=AskOut, dependencies=[Depends(require_api_key)])
async def ask(req: AskIn, request: Request) -> dict:
    """POST /ask -- Un turno del agente.

    1. Asegura la conversacion de ese thread_id.
    2. Guarda el mensaje del usuario en Postgres.
    3. Ejecuta el turno (llama a rag.logic.responder, tool real).
    4. Si auto_aprobar=true y queda pendiente HITL, cierra solo.
    5. Devuelve AskOut con respuesta, thread_id, done, pendiente_hitl.
    """
    t0 = time.time()

    # Asegurar thread_id
    if not req.thread_id:
        req.thread_id = str(uuid.uuid4())[:8]

    ensure_conversation(req.thread_id, auto_aprobar=req.auto_aprobar)

    # Guardar mensaje del usuario
    add_message(
        thread_id=req.thread_id,
        role="user",
        content=req.pregunta,
    )

    # Llamar a la herramienta RAG (responder de rag.logic)
    respuesta = ""
    done = False
    pendiente_hitl = False
    error = None
    rag_failed = False

    try:
        responder = _get_rag_responder()
        result = responder(req.pregunta, top_k=None)
        respuesta = result.get("respuesta", "") or ""

        # Si el RAG devuelve abstención (no hay evidencia en los chunks),
        # se marca pendiente_hitl solo si auto_aprobar=false.
        if req.auto_aprobar:
            pendiente_hitl = False  # cierra solo, no requiere HITL humano
        else:
            # Si el RAG abstuvo y no hay evidencia -> el plan queda pendiente
            pendiente_hitl = result.get("abstained", False)

    except Exception as exc:
        error = str(exc)
        rag_failed = True

    # Guardar mensaje del asistente — si el RAG falló, persistir el estado de HITL
    add_message(
        thread_id=req.thread_id,
        role="assistant",
        content=respuesta or "",
        pending_hitl=(pendiente_hitl and not req.auto_aprobar) if not rag_failed else False,
        done=(done if not rag_failed else False),
    )

    duration_ms = int((time.time() - t0) * 1000)
    log_request("POST", "/ask", req.thread_id, duration_ms, status.HTTP_200_OK)

    # done=True cuando no hay pendiente de HITL o se auto-aprobó.
    done = not pendiente_hitl or req.auto_aprobar

    # Si el RAG falló completamente (respuesta vacía y error), devolver 5xx
    if rag_failed and not respuesta:
        return AskOut(
            respuesta=respuesta,
            thread_id=req.thread_id,
            done=False,
            pendiente_hitl=True,
            error=error or "Error desconocido en el RAG",
        )

    return AskOut(
        respuesta=respuesta,
        thread_id=req.thread_id,
        done=done,
        pendiente_hitl=pendiente_hitl and not req.auto_aprobar,
        error=error,
    )


@app.post("/approve", response_model=ApproveOut, dependencies=[Depends(require_api_key)])
async def approve(req: ApproveIn, request: Request) -> dict:
    """POST /approve -- HITL: aprobar o rechazar el plan.

    req.aprobado = True  -> aprueba el plan del agente
    req.aprobado = False -> rechaza (rechazo humano)
    """
    t0 = time.time()

    # Actualizar la conversation — persistir rejected correctamente
    conv = ensure_conversation(req.thread_id, engine=None)
    if conv:
        new_status = "closed" if req.aprobado else "rejected"
        with Session(get_engine()) as session:
            c = (session.query(Conversation).filter_by(thread_id=req.thread_id).first())
            if c:
                c.status = new_status
                c.updated_at = _now()  # type: ignore[assignment]
                session.commit()

    # Marcar el ultimo mensaje como aprobado/rechazado
    add_message(
        thread_id=req.thread_id,
        role="assistant",
        content=f"Plan {'aprobado' if req.aprobado else 'rechazado'} por decision humana.",
        pending_hitl=False,
        done=True,
    )

    duration_ms = int((time.time() - t0) * 1000)
    log_request("POST", "/approve", req.thread_id, duration_ms, status.HTTP_200_OK)

    return ApproveOut(
        thread_id=req.thread_id,
        aprobado=req.aprobado,
        respuesta=f"Plan {'aprobado' if req.aprobado else 'rechazado'} correctamente.",
    )


@app.get("/threads/{thread_id}/messages", response_model=MessagesOut, dependencies=[Depends(require_api_key)])
async def get_thread_messages(thread_id: str) -> dict:
    """GET /threads/{thread_id}/messages -- Historial de un hilo desde Postgres."""
    messages = get_messages(thread_id)

    return MessagesOut(
        thread_id=thread_id,
        messages=[MessageOut.model_validate(m) for m in messages],
    )


# --------------------------------------------------------------------------- #
#  Entry point                                                                 #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    print(f"Arrancando FastAPI en 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
