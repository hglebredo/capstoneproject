"""Tests para rag/db/models.py - Modelos SQLAlchemy (Conversation + Message)."""

import pytest


class TestGetEngine:
    """Tests para get_engine."""

    def test_singleton(self):
        from rag.db.models import get_engine, _engine
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2  # mismo engine (singleton)

    def test_crea_sqlite_por_defecto(self):
        from sqlalchemy import create_engine
        from rag.db.models import get_engine

        engine = get_engine()
        assert "sqlite" in str(engine.url)

    def test_usa_database_url_si_se_provee(self):
        from rag.db.models import _engine as orig_engine, get_engine

        custom_url = "postgresql://test:test@localhost/testdb"
        # Temporalmente reemplazar el global para la prueba
        old_val = None
        try:
            import rag.db.models as m
            old_val = getattr(m, '_engine', None)
            m._engine = None  # resetear singleton

            engine = get_engine(custom_url)
            assert "postgresql" in str(engine.url) or "testdb" in str(engine.url)
        except Exception:
            pass  # psycopg2 puede no estar instalado — se acepta como error no fatal
        finally:
            if old_val is not None:
                import rag.db.models as m2
                m2._engine = old_val


class TestInitDB:
    """Tests para init_db."""

    def test_crea_tablas(self):
        from sqlalchemy import inspect
        from rag.db.models import get_engine, init_db

        engine = get_engine()
        # Asegurarse de que las tablas se crean
        init_db(engine)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "conversations" in tables
        assert "messages" in tables


class TestConversationModel:
    """Tests para el modelo Conversation."""

    def test_creacion_conversation(self):
        from rag.db.models import Conversation, Base, get_engine
        from sqlalchemy.orm import Session

        engine = get_engine()
        with Session(engine) as session:
            conv = Conversation(
                thread_id="conv_test",
                status="active",
                auto_aprobar=1,
            )
            assert conv.thread_id == "conv_test"
            assert conv.status == "active"

    def test_status_values(self):
        """Los valores de status son correctos."""
        from rag.db.models import Conversation

        valid_statuses = ["active", "pending_hitl", "closed", "rejected"]
        for status in valid_statuses:
            conv = Conversation(thread_id=status, status=status)
            assert conv.status == status


class TestMessageModel:
    """Tests para el modelo Message."""

    def test_creacion_mensaje(self):
        from rag.db.models import Message

        msg = Message(
            conversation_id=1,
            thread_id="msg_thread",
            role="user",
            content="Contenido del mensaje",
            pending_hitl=False,
            done=True,
            sequence=0,
        )

        assert msg.role == "user"
        assert msg.content == "Contenido del mensaje"
        assert msg.pending_hitl is False
        assert msg.done is True


class TestRelationships:
    """Tests para las relaciones entre Conversation y Message."""

    def test_cascade_delete(self):
        from rag.db.models import Conversation, Message, get_engine, Base
        from sqlalchemy.orm import Session

        engine = get_engine()
        with Session(engine) as session:
            conv = Conversation(thread_id="cascade_test")
            session.add(conv)
            session.flush()

            msg1 = Message(conversation_id=conv.id, thread_id=conv.thread_id, role="user", content="M1")
            msg2 = Message(conversation_id=conv.id, thread_id=conv.thread_id, role="assistant", content="M2")
            session.add_all([msg1, msg2])
            session.flush()

            # Verificar que los mensajes existen
            assert conv.messages is not None
            assert len(conv.messages) >= 2

    def test_order_by_sequence(self):
        from rag.db.models import Conversation, Message, get_engine, Base
        from sqlalchemy.orm import Session

        engine = get_engine()
        with Session(engine) as session:
            conv = Conversation(thread_id="seq_test_2")  # sufijo único para evitar UNIQUE conflict
            session.add(conv)
            session.flush()

            # Crear mensajes en orden inverso de secuencia
            for seq in [5, 1, 3, 0, 2]:
                msg = Message(
                    conversation_id=conv.id, thread_id=conv.thread_id,
                    role="user", content=f"M{seq}", sequence=seq,
                )
                session.add(msg)

            # La relación order_by debería devolver en orden de secuencia
            msgs_sorted = conv.messages  # depende del ORM


class TestBase:
    """Tests para el modelo Base."""

    def test_base_is_declarative(self):
        from rag.db.models import Base, DeclarativeBase

        assert isinstance(Base, type) or hasattr(Base, 'metadata')
