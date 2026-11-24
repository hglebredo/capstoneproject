"""
tests/test_db.py — Tests unitarios de src/db.py con SQLite en memoria.

No requieren PostgreSQL. Verifican la lógica de persistencia:
ensure_schema, save_turn, list_messages, db_ok.

Para testear db_ok() == False se usa un engine roto (mock).
"""

from datetime import datetime, timezone

import pytest
import config
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from src import db
from src.models import Conversation, Message


@pytest.fixture(autouse=True)
def engine_sqlite():
    """Engine SQLite en memoria compartido entre conexiones del test.

    StaticPool + check_same_thread=False permiten que la misma BD en memoria
    se reutilice en todas las conexiones del test (si no, cada conexión
    tendría su propia BD vacía).
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    db._set_engine_for_tests(engine)
    yield engine
    db._set_engine_for_tests(None)  # type: ignore[arg-type]


def test_ensure_schema_crea_tablas(engine_sqlite):
    """ensure_schema es idempotente y crea conversation y message."""
    db.ensure_schema()
    db.ensure_schema()  # no debe fallar

    from sqlalchemy import inspect
    inspector = inspect(engine_sqlite)
    tablas = inspector.get_table_names()
    assert "conversation" in tablas
    assert "message" in tablas


def test_save_turn_guarda_user_y_assistant():
    db.save_turn("hilo-1", "hola", "mundo")
    mensajes = db.list_messages("hilo-1")
    assert len(mensajes) == 2
    assert mensajes[0]["role"] == "user"
    assert mensajes[0]["content"] == "hola"
    assert mensajes[1]["role"] == "assistant"
    assert mensajes[1]["content"] == "mundo"


def test_save_turn_reutiliza_conversation():
    """Dos turnos en el mismo thread_id no duplican Conversation."""
    db.save_turn("hilo-1", "pregunta 1", "respuesta 1")
    db.save_turn("hilo-1", "pregunta 2", "respuesta 2")

    mensajes = db.list_messages("hilo-1")
    assert len(mensajes) == 4  # 2 turnos × 2 mensajes

    # Solo hay una Conversation para ese thread_id
    with db._sesion() as session:
        from sqlmodel import select
        convs = session.exec(
            select(Conversation).where(Conversation.thread_id == "hilo-1")
        ).all()
        assert len(convs) == 1


def test_list_messages_hilo_inexistente_devuelve_vacio():
    assert db.list_messages("no-existe") == []


def test_list_messages_ordena_por_id():
    """Aunque created_at empate, el orden es por id (user antes que assistant)."""
    db.save_turn("hilo-1", "pregunta", "respuesta")
    mensajes = db.list_messages("hilo-1")
    assert mensajes[0]["role"] == "user"
    assert mensajes[1]["role"] == "assistant"


def test_list_messages_aísla_hilos():
    """Dos thread_id distintos no se mezclan."""
    db.save_turn("hilo-a", "pregunta A", "respuesta A")
    db.save_turn("hilo-b", "pregunta B", "respuesta B")

    msgs_a = db.list_messages("hilo-a")
    msgs_b = db.list_messages("hilo-b")

    assert len(msgs_a) == 2
    assert len(msgs_b) == 2
    assert msgs_a[0]["content"] == "pregunta A"
    assert msgs_b[0]["content"] == "pregunta B"


def test_save_turn_con_created_at_explicito():
    """save_turn acepta created_at para tests deterministas."""
    fecha = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    db.save_turn("hilo-1", "pregunta", "respuesta", created_at=fecha)
    mensajes = db.list_messages("hilo-1")
    assert mensajes[0]["created_at"] == fecha
    assert mensajes[1]["created_at"] == fecha


def test_db_ok_true_con_engine_valido():
    assert db.db_ok() is True


def test_db_ok_false_con_engine_roto(monkeypatch):
    """db_ok() devuelve False si el engine falla, sin lanzar excepción."""
    from sqlalchemy.exc import OperationalError

    class EngineRoto:
        def connect(self):
            raise OperationalError("SELECT 1", {}, Exception("conexión rota"))

    monkeypatch.setattr(db, "_engine_actual", lambda: EngineRoto())
    assert db.db_ok() is False



def test_normalizar_url():
    """Las URL de PostgreSQL utilizan siempre psycopg 3."""

    assert db._normalizar_url(
        "postgres://u:p@h:5432/db"
    ) == "postgresql+psycopg://u:p@h:5432/db"

    assert db._normalizar_url(
        "postgresql://u:p@h:5432/db"
    ) == "postgresql+psycopg://u:p@h:5432/db"

    assert db._normalizar_url(
        "postgresql+psycopg://u:p@h:5432/db"
    ) == "postgresql+psycopg://u:p@h:5432/db"


def test_get_database_url_sin_variable_lanza_error(monkeypatch):
    """Sin DATABASE_URL, se produce un error al necesitar PostgreSQL."""

    monkeypatch.setattr(config, "DATABASE_URL", None)

    with pytest.raises(
        RuntimeError,
        match="DATABASE_URL no está definida"
    ):
        db._get_database_url()
