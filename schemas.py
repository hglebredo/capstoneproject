"""Contrato HTTP de la API (ver docs/contrato_api.md §3)."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class AskIn(BaseModel):
    pregunta: str = Field(..., min_length=1, examples=["¿Qué piscinas de verano abren en Madrid?"])
    thread_id: str = Field(..., min_length=1, examples=["deportes-demo-1"])
    auto_aprobar: bool = True


class AskOut(BaseModel):
    respuesta: str
    thread_id: str
    done: bool
    pendiente_hitl: bool
    plan: list[str] = []
    error: Optional[str] = None


class ApproveIn(BaseModel):
    thread_id: str = Field(..., min_length=1, examples=["deportes-demo-1"])
    aprobado: bool


class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    storage: Literal["postgres"]
    db_ok: bool
