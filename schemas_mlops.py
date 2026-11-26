"""schemas_mlops.py - modelos de entrada/salida del contrato PB3/MLOps.

Alineado con el spec: AskIn, AskOut, ApproveIn, MessageOut.
Estos schemas reemplazan/complementan a los de api/schemas.py para las rutas
nuevas /ask, /approve y /threads/{thread_id}/messages.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
#  Entradas                                                                    #
# --------------------------------------------------------------------------- #

class AskIn(BaseModel):
    """Cuerpo de POST /ask."""
    pregunta: str = Field(min_length=1, description="Pregunta del usuario")
    thread_id: str | None = Field(default=None, description="ID del hilo/conversacion. Se genera si no se pasa.")
    auto_aprobar: bool = Field(default=True, description="Si el grafo queda en HITL, cerrar solo.")


class ApproveIn(BaseModel):
    """Cuerpo de POST /approve."""
    thread_id: str = Field(description="ID del hilo al que afecta la decision")
    aprobado: bool = Field(description="True = aprobar plan, False = rechazar")


# --------------------------------------------------------------------------- #
#  Salidas                                                                     #
# --------------------------------------------------------------------------- #

class AskOut(BaseModel):
    """Respuesta de POST /ask."""
    respuesta: str = ""
    thread_id: str
    done: bool = False
    pendiente_hitl: bool = False
    error: str | None = None


class ApproveOut(BaseModel):
    """Respuesta de POST /approve."""
    thread_id: str
    aprobado: bool
    respuesta: str = "Decision registrada"
    done: bool = True


class MessageOut(BaseModel):
    """Un mensaje individual en el historial."""
    role: str          # user | assistant | tool
    content: str
    pending_hitl: bool = False
    done: bool = False
    sequence: int = 0
    created_at: str | None = None


class MessagesOut(BaseModel):
    """Respuesta de GET /threads/{thread_id}/messages."""
    thread_id: str
    messages: list[MessageOut]
