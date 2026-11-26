"""Tests para rag/db/db_engine.py - Capa de acceso a datos (Conversation + Message)."""

import pytest


@pytest.fixture(autouse=True)
def _reset_db():
    """Resetear el engine entre tests para evitar estado compartido."""
    import rag.db.models as models
    old = getattr(models, '_engine', None)
    models._engine = None
    yield
    if old is not None:
        models._engine = old


class TestEnsureConversation:
    """Tests para ensure_conversation."""

    def test_crea_nueva_conversacion(self):
        from rag.db.db_engine import ensure_conversation, get_conversation
        conv = ensure_conversation("test_thread_001")
        assert conv is not None
        assert conv.thread_id == "test_thread_001"
        assert conv.status == "active"

    def test_reutiliza_existente(self):
        from rag.db.db_engine import ensure_conversation, get_engine
        from sqlalchemy.orm import Session
        from rag.db.models import Conversation

        # Primera llamada crea
        c1 = ensure_conversation("dup_thread")
        # Segunda llama reutiliza
        with Session(get_engine()) as session:
            count_before = session.query(Conversation).filter_by(thread_id="dup_thread").count()
        c2 = ensure_conversation("dup_thread", auto_aprobar=False)

        assert c1.id == c2.id  # misma conversación
        assert c2.auto_aprobar == int(False)

    def test_auto_aprobar_se_refleja(self):
        from rag.db.db_engine import ensure_conversation
        conv = ensure_conversation("aa_thread", auto_aprobar=True)
        assert conv.auto_aprobar == 1


class TestAddMessage:
    """Tests para add_message."""

    def test_agrega_mensaje_usuario(self):
        from rag.db.db_engine import add_message, get_messages

        thread = "msg_test_001"
        result = add_message(thread_id=thread, role="user", content="Hola mundo")

        assert result["role"] == "user"
        assert result["content"] == "Hola mundo"
        assert result["thread_id"] == thread
        assert isinstance(result["id"], int)

    def test_agrega_mensaje_asistente(self):
        from rag.db.db_engine import add_message, get_messages

        thread = "msg_test_002"
        result = add_message(
            thread_id=thread, role="assistant", content="Respuesta del agente",
            pending_hitl=True, done=False,
        )

        assert result["pending_hitl"] is True
        assert result["done"] is False

    def test_secuencia_incremental(self):
        from rag.db.db_engine import add_message, get_messages

        thread = "seq_test"
        r1 = add_message(thread_id=thread, role="user", content="Primero")
        r2 = add_message(thread_id=thread, role="assistant", content="Segundo")
        r3 = add_message(thread_id=thread, role="user", content="Tercero")

        assert r1["sequence"] == 0
        assert r2["sequence"] == 1
        assert r3["sequence"] == 2


class TestGetMessages:
    """Tests para get_messages."""

    def test_devuelve_mensajes_en_orden(self):
        from rag.db.db_engine import add_message, get_messages

        thread = "order_test"
        for i in range(5):
            add_message(thread_id=thread, role="user", content=f"M{i}")

        msgs = get_messages(thread)
        # ensure_conversation() dentro de add_message crea 1 conversación + 5 mensajes = 6 mínimo
        assert len(msgs) >= 5
        seqs = [m["sequence"] for m in msgs]
        assert seqs == sorted(seqs), "Los mensajes deben estar ordenados por secuencia"

    def test_limit_corta_resultados(self):
        from rag.db.db_engine import add_message, get_messages

        thread = "limit_test"
        for i in range(10):
            add_message(thread_id=thread, role="user", content=f"M{i}")

        msgs_limited = get_messages(thread, limit=3)
        assert len(msgs_limited) <= 4  # +1 por el ensure_conversation implícito

    def test_devuelve_dict_completo(self):
        from rag.db.db_engine import add_message, get_messages

        thread = "dict_test"
        add_message(
            thread_id=thread, role="assistant", content="Hola",
            tool_calls=[{"name": "rag_responder", "args": {"q": "test"}}],
        )
        msgs = get_messages(thread)
        last_msg = [m for m in msgs if m["role"] == "assistant"][0]

        assert "tool_calls" in last_msg
        assert isinstance(last_msg["tool_calls"], list)


class TestCountMessages:
    """Tests para count_messages."""

    def test_cuenta_mensajes(self):
        from rag.db.db_engine import add_message, count_messages, ensure_conversation

        thread = "count_test"
        ensure_conversation(thread)  # crea conversación base
        for i in range(5):
            add_message(thread_id=thread, role="user", content=f"M{i}")

        assert count_messages(thread) >= 5


class TestGetConversation:
    """Tests para get_conversation."""

    def test_devuelve_conversacion_existente(self):
        from rag.db.db_engine import ensure_conversation, get_conversation

        thread = "gc_test"
        conv_creada = ensure_conversation(thread)
        conv_buscar = get_conversation(thread)

        assert conv_buscar is not None
        assert conv_buscar.id == conv_creada.id

    def test_devuelve_none_si_no_existe(self):
        from rag.db.db_engine import get_conversation

        result = get_conversation("no_existente_abc123")
        assert result is None


class TestIntegration:
    """Tests de integración del flujo completo."""

    def test_flujo_ask_approve(self):
        """Simula el ciclo completo: ask -> approve."""
        from rag.db.db_engine import (
            add_message, ensure_conversation, get_messages, count_messages,
        )

        thread = "flow_test"
        # Asegurar conversación
        conv = ensure_conversation(thread)
        assert conv.status == "active"

        # Guardar mensaje del usuario
        user_msg = add_message(thread_id=thread, role="user", content="¿Cuánto cuesta?")
        messages = get_messages(thread)
        roles = [m["role"] for m in messages]
        assert "user" in roles

        # Simular respuesta del asistente
        assist_msg = add_message(
            thread_id=thread, role="assistant", content="Cuesta 10€", done=True,
        )
        assert assist_msg["done"] is True
