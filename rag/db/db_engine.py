"""db/db_engine.py -  capa de acceso a datos para el historial del agente.

Opera sobre Conversation + Message en PostgreSQL (o SQLite como fallback).
Sustituye al init_db.py antiguo para el flujo PB3: POST /ask guarda mensajes,
GET /threads/{id}/messages los devuelve.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from rag.db.models import Base, Conversation, Message, get_engine


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
#  Conversaciones                                                              #
# --------------------------------------------------------------------------- #

def ensure_conversation(thread_id: str, auto_aprobar: bool = True, *, engine=None):
    """Asegura que existe una Conversation para este thread_id. La crea si no."""
    eng = engine or get_engine()
    # Crear tablas si no existen (idempotente)
    Base.metadata.create_all(bind=eng)
    with Session(eng, expire_on_commit=True) as session:
        conv = session.query(Conversation).filter_by(thread_id=thread_id).first()
        if not conv:
            conv = Conversation(
                thread_id=thread_id,
                auto_aprobar=int(auto_aprobar),
                status="active",
            )
            session.add(conv)
            session.flush()  # asigna id

        else:
            conv.auto_aprobar = int(auto_aprobar)
            conv.updated_at = _now()

        session.commit()
        # Refresh para evitar DetachedInstanceError al acceder a atributos despues
        session.refresh(conv)
        return conv


def get_conversation(thread_id: str, engine=None):
    """Devuelve la Conversation de un thread_id o None."""
    eng = engine or get_engine()
    with Session(eng) as session:
        return session.query(Conversation).filter_by(thread_id=thread_id).first()


# --------------------------------------------------------------------------- #
#  Mensajes                                                                    #
# --------------------------------------------------------------------------- #

def add_message(thread_id: str, role: str, content: str, *,
                pending_hitl: bool = False, done: bool = False,
                tool_calls: list[dict] | None = None) -> dict:
    """Agrega un mensaje al final de la conversacion."""
    engine = get_engine()
    with Session(engine) as session:
        try:
            conv = session.query(Conversation).filter_by(thread_id=thread_id).first()
            if not conv:
                conv = Conversation(
                    thread_id=thread_id,
                    auto_aprobar=int(True),
                    status="active",
                )
                session.add(conv)
                session.flush()

            # siguiente secuencia (dentro de esta sesion)
            last = session.query(Message).filter_by(conversation_id=conv.id).order_by(Message.sequence.desc()).first()
            seq = (last.sequence + 1) if last else 0

            msg = Message(
                conversation_id=conv.id,
                thread_id=thread_id,
                role=role,
                content=content or "",
                pending_hitl=int(pending_hitl),
                done=int(done),
                sequence=seq,
                tool_calls=json.dumps(tool_calls) if tool_calls else "",
            )
            session.add(msg)

            # actualizar status de la conversation si es necesario
            if role == "assistant" and pending_hitl:
                conv.status = "pending_hitl"
            elif role == "assistant" and done:
                conv.status = "closed"
            conv.updated_at = _now()

            session.commit()

            # Recargar para evitar DetachedInstanceError
            msg_refreshed = (session.query(Message)
                            .filter_by(id=msg.id)
                            .first())
            return {
                "id": msg_refreshed.id,
                "thread_id": thread_id,
                "role": role,
                "content": content or "",
                "pending_hitl": pending_hitl,
                "done": done,
                "sequence": seq,
            }
        except Exception:
            session.rollback()
            raise


def get_messages(thread_id: str, limit: int = 50) -> list[dict]:
    """Devuelve los mensajes de un hilo en orden cronologico."""
    engine = get_engine()
    with Session(engine) as session:
        rows = (session.query(Message)
                .filter_by(thread_id=thread_id)
                .order_by(Message.sequence.asc())
                .limit(limit)
                .all())
        return [
            {
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "pending_hitl": bool(r.pending_hitl),
                "done": bool(r.done),
                "sequence": r.sequence,
                "tool_calls": json.loads(r.tool_calls) if r.tool_calls else [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


def count_messages(thread_id: str) -> int:
    """Cuenta mensajes de un hilo."""
    engine = get_engine()
    with Session(engine) as session:
        return session.query(Message).filter_by(thread_id=thread_id).count()
