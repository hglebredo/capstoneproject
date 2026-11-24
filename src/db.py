
"""
src/db.py — Persistencia PostgreSQL con SQLModel.

Funciones públicas:
- ensure_schema()                            → crea las tablas
- save_turn(thread_id, pregunta, respuesta)  → guarda user + assistant
- list_messages(thread_id)                   → recupera el historial
- db_ok()                                    → comprueba la conexión

El engine se crea bajo demanda, no al importar el módulo.
"""

from contextlib import contextmanager
from datetime import datetime
from threading import Lock
from typing import Iterator, Optional

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

import config
from src.models import Conversation, Message


# --- Configuración ------------------------------------------------------------

def _normalizar_url(url: str) -> str:
    """
    Fuerza el driver psycopg 3 independientemente del formato de origen.

    Render puede proporcionar postgres:// o postgresql://.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]

    return url


def _get_database_url() -> str:
    """Obtiene DATABASE_URL desde la configuración compartida."""
    url = config.DATABASE_URL

    if not url:
        raise RuntimeError(
            "DATABASE_URL no está definida. Sin Postgres la app no arranca."
        )

    return _normalizar_url(url)


# --- Engine global ------------------------------------------------------------

_engine = None
_ENGINE_LOCK = Lock()

# Engine alternativo utilizado exclusivamente por los tests.
_TEST_ENGINE = None


def _engine_actual():
    """
    Devuelve el engine de tests si está inyectado.
    Si no, crea el engine de producción únicamente cuando se necesita.
    """
    global _engine

    if _TEST_ENGINE is not None:
        return _TEST_ENGINE

    if _engine is None:
        with _ENGINE_LOCK:
            if _engine is None:
                _engine = create_engine(
                    _get_database_url(),
                    echo=False,
                    pool_pre_ping=True,
                    connect_args={"connect_timeout": 3},
                    pool_timeout=5,
                )

    return _engine


# --- Sesiones -----------------------------------------------------------------

@contextmanager
def _sesion() -> Iterator[Session]:
    with Session(_engine_actual()) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


# --- API pública --------------------------------------------------------------

def ensure_schema() -> None:
    """Crea las tablas si todavía no existen."""
    SQLModel.metadata.create_all(_engine_actual())


def save_turn(
    thread_id: str,
    pregunta: str,
    respuesta: str,
    *,
    created_at: Optional[datetime] = None,
) -> None:
    """
    Guarda la pregunta y la respuesta en una única transacción.
    """
    with _sesion() as session:
        conv = session.exec(
            select(Conversation).where(
                Conversation.thread_id == thread_id
            )
        ).first()

        if conv is None:
            conv = Conversation(thread_id=thread_id)
            session.add(conv)
            session.flush()

        kwargs = (
            {"created_at": created_at}
            if created_at is not None
            else {}
        )

        session.add(
            Message(
                conversation_id=conv.id,
                role="user",
                content=pregunta,
                **kwargs,
            )
        )

        session.add(
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=respuesta,
                **kwargs,
            )
        )


def list_messages(thread_id: str) -> list[dict]:
    """Devuelve los mensajes de un hilo ordenados por ID."""
    with _sesion() as session:
        conv = session.exec(
            select(Conversation).where(
                Conversation.thread_id == thread_id
            )
        ).first()

        if conv is None:
            return []

        mensajes = session.exec(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.id)
        ).all()

        return [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at,
            }
            for m in mensajes
        ]


def db_ok() -> bool:
    """Comprueba PostgreSQL. Nunca propaga errores de conexión."""
    try:
        with _engine_actual().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# --- Inyección de engine para tests -------------------------------------------

def _set_engine_for_tests(engine) -> None:
    """
    Permite sustituir PostgreSQL por SQLite en memoria durante los tests.
    """
    global _TEST_ENGINE
    _TEST_ENGINE = engine
