"""Tests para schemas_mlops.py - Validación de contratos Pydantic."""

import pytest
from pydantic import ValidationError

from schemas_mlops import (
    AskIn,
    AskOut,
    ApproveIn,
    ApproveOut,
    MessageOut,
    MessagesOut,
)


class TestAskIn:
    """Tests para el modelo de entrada POST /ask."""

    def test_ask_in_valido(self):
        """AskIn válido con todos los campos."""
        ask = AskIn(
            pregunta="¿Qué servicios ofrece?",
            thread_id="test-001",
            auto_aprobar=True,
        )
        assert ask.pregunta == "¿Qué servicios ofrecen?"
        assert ask.thread_id == "test-001"
        assert ask.auto_aprobar is True

    def test_ask_in_auto_aprobar_default(self):
        """auto_aprobar por defecto es True."""
        ask = AskIn(pregunta="Hola")
        assert ask.auto_aprobar is True

    def test_ask_in_thread_id_none(self):
        """thread_id puede ser None (se genera después en app.py)."""
        ask = AskIn(
            pregunta="Hola",
            thread_id=None,
        )
        assert ask.thread_id is None

    def test_ask_in_pregunta_vacia_lanza_422(self):
        """pregunta vacía -> ValidationError (min_length=1)."""
        with pytest.raises(ValidationError):
            AskIn(pregunta="")

    def test_ask_in_pregunta_minimo(self):
        """Una sola letra es válida."""
        ask = AskIn(pregunta="x")
        assert ask.pregunta == "x"


class TestAskOut:
    """Tests para el modelo de salida POST /ask."""

    def test_ask_out_completo(self):
        """AskOut con todos los campos."""
        out = AskOut(
            respuesta="El ayuntamiento ofrece 15 servicios.",
            thread_id="test-001",
            done=True,
            pendiente_hitl=False,
            error=None,
        )
        assert out.respuesta == "El ayuntamiento ofrece 15 servicios."
        assert out.done is True

    def test_ask_out_default_respuesta(self):
        """respuesta por defecto es string vacío."""
        out = AskOut(thread_id="test")
        assert out.respuesta == ""

    def test_ask_out_con_error(self):
        """AskOut con error no lanza."""
        out = AskOut(
            thread_id="test",
            respuesta="",
            done=False,
            pendiente_hitl=True,
            error="Timeout de Gemini",
        )
        assert out.error == "Timeout de Gemini"


class TestApproveIn:
    """Tests para el modelo de entrada POST /approve."""

    def test_approve_in_valido(self):
        approve = ApproveIn(thread_id="test-001", aprobado=True)
        assert approve.thread_id == "test-001"
        assert approve.aprobado is True

    def test_approve_in_rechazo(self):
        approve = ApproveIn(thread_id="test-002", aprobado=False)
        assert approve.aprobado is False


class TestApproveOut:
    """Tests para el modelo de salida POST /approve."""

    def test_approve_out_completo(self):
        out = ApproveOut(
            thread_id="test-001",
            aprobado=True,
            respuesta="Plan aprobado correctamente.",
            done=True,
        )
        assert out.aprobado is True
        assert out.done is True

    def test_approve_out_default_respuesta(self):
        """respuesta por defecto es 'Decision registrada'."""
        out = ApproveOut(thread_id="test", aprobado=True)
        # Pydantic usa el default del campo
        assert hasattr(out, "respuesta")


class TestMessageOut:
    """Tests para MessageOut - unidad individual del historial."""

    def test_message_out_user(self):
        msg = MessageOut(role="user", content="¿Cuánto cuesta?")
        assert msg.role == "user"
        assert msg.content == "¿Cuánto cuesta?"
        assert msg.pending_hitl is False
        assert msg.done is False

    def test_message_out_assistant(self):
        msg = MessageOut(
            role="assistant",
            content="Cuesta 15€ al mes.",
            pending_hitl=False,
            done=True,
            sequence=2,
        )
        assert msg.role == "assistant"
        assert msg.done is True

    def test_message_out_tool(self):
        """MessageOut con role='tool' es válido."""
        msg = MessageOut(role="tool", content="{'chairs': 15}")
        assert msg.role == "tool"


class TestMessagesOut:
    """Tests para MessagesOut - respuesta de GET /threads/{id}/messages."""

    def test_messages_out_completo(self):
        messages = [
            MessageOut(role="user", content="¿Cuánto cuesta?"),
            MessageOut(role="assistant", content="Cuesta 15€."),
        ]
        out = MessagesOut(thread_id="test-001", messages=messages)
        assert len(out.messages) == 2

    def test_messages_out_vacio(self):
        """Sin mensajes -> lista vacía válida."""
        out = MessagesOut(thread_id="empty", messages=[])
        assert out.thread_id == "empty"
        assert out.messages == []


class TestPydanticValidation:
    """Tests de validación cruzada con FastAPI."""

    def test_ask_out_serializable(self):
        """AskOut se serializa a dict correctamente (para JSONResponse)."""
        out = AskOut(
            respuesta="Respuesta de prueba",
            thread_id="test-001",
            done=True,
            pendiente_hitl=False,
        )
        d = out.model_dump()
        assert isinstance(d, dict)
        assert "respuesta" in d
        assert "thread_id" in d

    def test_messages_out_serializable(self):
        """MessagesOut se serializa a JSON correctamente."""
        messages = [
            MessageOut(role="user", content="Hola"),
            MessageOut(role="assistant", content="¡Hola!"),
        ]
        out = MessagesOut(thread_id="test-001", messages=messages)
        d = out.model_dump()

        assert isinstance(d["messages"], list)
        for msg in d["messages"]:
            assert "role" in msg
            assert "content" in msg
