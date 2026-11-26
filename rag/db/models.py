"""db/models.py -  modelos relacionales para el historial del agente (PB3/MLOps).

Tablas recomendadas: Conversation y Message, unidas por thread_id.
Compatible con SQLite y PostgreSQL (misma interfaz via SQLAlchemy Core).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List

from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Engine singleton -  compartido por models.py y db_engine.py
_engine = None


def get_engine(database_url: str | None = None):
    """Devuelve el engine de SQLAlchemy (singleton). Crea SQLite si no hay URL.

    Lee DATABASE_URL del entorno como fallback, igual que hacen health() y rag_utils().
    """
    global _engine
    if database_url and database_url.strip():
        return create_engine(database_url)
    if _engine is not None:
        return _engine
    # Leer de la variable de entorno si está definida
    env_url = os.environ.get("DATABASE_URL") or os.environ.get("PGVECTOR_DSN")
    if env_url and env_url.strip():
        _engine = create_engine(env_url)
        return _engine
    db_path = os.path.join(os.getcwd(), "rag_mlops.db")
    url = f"sqlite:///{db_path}"
    _engine = create_engine(url, connect_args={"check_same_thread": False})
    return _engine


def init_db(engine=None):
    """Crea todas las tablas si no existen (idempotente)."""
    Base.metadata.create_all(bind=engine or get_engine())


# --------------------------------------------------------------------------- #
#  Modelos SQLAlchemy                                                        #
# --------------------------------------------------------------------------- #

class Conversation(Base):
    """Una conversacion / hilo identificado por thread_id."""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)          # PK interna
    thread_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)  # ID externo (cliente)
    status: Mapped[str] = mapped_column(String(32), default="active")   # active | pending_hitl | closed | rejected
    auto_aprobar: Mapped[int] = mapped_column(default=1)      # flag para cierre automatico
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))

    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="conversation",
        cascade="all, delete-orphan", order_by="Message.sequence",
        foreign_keys="[Message.conversation_id]")


class Message(Base):
    """Un turno individual dentro de una conversacion."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), ForeignKey("conversations.thread_id"), nullable=False, index=True)  # duplicado para query facil

    role: Mapped[str] = mapped_column(String(32), nullable=False)       # user | assistant | tool
    content: Mapped[str] = mapped_column(Text, default="")
    pending_hitl: Mapped[int] = mapped_column(default=0)              # si este turno espera decision humana
    done: Mapped[int] = mapped_column(default=0)                      # turno cerrado

    sequence: Mapped[int] = mapped_column(default=0)                  # orden temporal
    tool_calls: Mapped[str] = mapped_column(Text, default="")         # JSON de llamadas a herramientas (si aplica)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages", foreign_keys="[Message.conversation_id]")
