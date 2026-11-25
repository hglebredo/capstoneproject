"""
src/models.py — Modelos de persistencia (SQLModel) para PostgreSQL.

Define las tablas de la base de datos. No confundir con schemas.py:
- schemas.py  → contratos HTTP (Pydantic). Lo que el cliente envía y recibe.
- models.py   → tablas de la BD (SQLModel). Lo que persiste en PostgreSQL.

Tablas:
- Conversation: una fila por thread_id (conversación).
- Message: un mensaje (user o assistant) asociado a una Conversation.

Relación: Conversation 1──N Message (cascade delete).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    """Fecha/hora actual en UTC, coherente en local y en Render."""
    return datetime.now(timezone.utc)


class Conversation(SQLModel, table=True):
    """Una conversación identificada por thread_id (el mismo que usa el agente)."""

    __tablename__ = "conversation"

    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: str = Field(index=True, unique=True, max_length=100)
    created_at: datetime = Field(default_factory=_utcnow)

    messages: list["Message"] = Relationship(
        back_populates="conversation",
        cascade_delete=True,
    )


class Message(SQLModel, table=True):
    """Un mensaje de la conversación: 'user' o 'assistant'."""

    __tablename__ = "message"

    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id", index=True)
    role: str = Field(max_length=20)
    content: str
    created_at: datetime = Field(default_factory=_utcnow, index=True)

    conversation: Optional[Conversation] = Relationship(back_populates="messages")