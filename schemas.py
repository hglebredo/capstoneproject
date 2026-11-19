"""Contrato HTTP de la API (docs/contrato_api.md §3).

FastAPI usa estas clases para validar el JSON y generar /docs (Swagger).
Body inválido → 422 automático.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class AskIn(BaseModel):
    """Body de POST /ask — una pregunta al agente."""

    pregunta: str = Field(
        ..., min_length=1, max_length=2000,
        examples=["¿Qué piscinas de verano hay en Madrid y cuánto cuesta la entrada?"],
    )
    thread_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Id de la conversación. Lo genera el front (uuid).",
        examples=["demo-1"],
    )
    auto_aprobar: bool = Field(
        default=True,
        description="Si el grafo queda en HITL, la API aprueba el plan sola (cómodo en Swagger).",
    )


class AskOut(BaseModel):
    """Respuesta de POST /ask y POST /approve."""

    respuesta: str
    thread_id: str
    done: bool = False
    pendiente_hitl: bool = Field(
        default=False, description="True → el front debe llamar a POST /approve.",
    )
    plan: list[str] = Field(
        default_factory=list, description="Viñetas del plan a aprobar o rechazar.",
    )
    error: Optional[str] = None


class ApproveIn(BaseModel):
    """Body de POST /approve — HITL manual."""

    thread_id: str = Field(..., min_length=1, max_length=100, examples=["demo-hitl"])
    aprobado: bool = Field(..., description="True = aprobar el plan; False = rechazar")


class MessageOut(BaseModel):
    """Un mensaje del historial (leído de Postgres)."""

    role: Literal["user", "assistant"]
    content: str
    created_at: Optional[datetime] = None


class HealthOut(BaseModel):
    """Respuesta de GET /health."""

    status: Literal["ok", "degraded"]
    storage: Literal["postgres"]
    db_ok: bool
