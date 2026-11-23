"""
src/db.py — Persistencia PostgreSQL con SQLModel.

Funciones que app.py espera:
- ensure_schema()                            → crea tablas al arrancar (idempotente)
- save_turn(thread_id, pregunta, respuesta)  → guarda user + assistant en una transacción
- list_messages(thread_id)                   → historial ordenado por id
- db_ok()                                    → SELECT 1 para /health, nunca lanza

Diseño:
- Engine global (pool reutilizado). pool_pre_ping reconecta si Render cierra la conexión.
- Normaliza postgres:// → postgresql:// (Render entrega el prefijo antiguo).
- Sesiones con contextmanager: commit/rollback/close garantizados.
- save_turn en una transacción: user + assistant juntos o nada.
- list_messages ordena por id (determinista aunque created_at empate).
"""

import os
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from src.models import Conversation, Message


# --- Configuración del engine ------------------------------------------------


def _normalizar_url(url: str) -> str:
    """Render entrega postgres://; SQLAlchemy quiere postgresql://."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _get_database_url() -> str:
    """Lee DATABASE_URL del entorno. Sin ella, la app no arranca."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL no está definida. Sin Postgres la app no arranca."
        )
    return _normalizar_url(url)


# Engine global: pool de conexiones reutilizado por todo el proceso.
# - pool_pre_ping=True  → si la conexión murió (Render la cierra por inactividad),
#                         el pool la detecta y reconecta antes de usarla.
# - connect_timeout=3   → si Postgres no responde, falla en ≤3 s (no se cuelga).
# - pool_timeout=5      → si el pool está lleno, falla en ≤5 s.
_engine = create_engine(
    _get_database_url(),
    echo=False,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
    pool_timeout=5,
)


# --- Sesiones ----------------------------------------------------------------

@contextmanager
def _sesion() -> Iterator[Session]:
    with Session(_engine_actual()) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise





def db_ok() -> bool:
    try:
        with _engine_actual().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False



# --- API pública -------------------------------------------------------------



def ensure_schema() -> None:
    SQLModel.metadata.create_all(_engine_actual())


def save_turn(
    thread_id: str,
    pregunta: str,
    respuesta: str,
    *,
    created_at: Optional[datetime] = None,
) -> None:
    """Guarda la pregunta (user) y la respuesta (assistant) en una transacción.

    Asegura la Conversation de ese thread_id (la crea si no existe).
    created_at es opcional: solo para tests deterministas.
    """
    with _sesion() as session:
        conv = session.exec(
            select(Conversation).where(Conversation.thread_id == thread_id)
        ).first()
        if conv is None:
            conv = Conversation(thread_id=thread_id)
            session.add(conv)
            session.flush()  # asigna conv.id sin commit

        kwargs = {"created_at": created_at} if created_at is not None else {}
        session.add(Message(
            conversation_id=conv.id, role="user", content=pregunta, **kwargs,
        ))
        session.add(Message(
            conversation_id=conv.id, role="assistant", content=respuesta, **kwargs,
        ))


def list_messages(thread_id: str) -> list[dict]:
    """Devuelve los mensajes del hilo en orden cronológico (por id).

    Formato compatible con schemas.MessageOut: role, content, created_at.
    """
    with _sesion() as session:
        conv = session.exec(
            select(Conversation).where(Conversation.thread_id == thread_id)
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
    try:
        with _engine_actual().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# --- Solo para tests: inyectar un engine alternativo ------------------------

_TEST_ENGINE = None


def _set_engine_for_tests(engine) -> None:
    """Permite a los tests usar SQLite en memoria en lugar de Postgres.

    No se usa en producción. El engine global (_engine) sigue siendo el de
    DATABASE_URL; esta función solo redirige las operaciones a un engine
    alternativo durante los tests.
    """
    global _TEST_ENGINE
    _TEST_ENGINE = engine


def _engine_actual():
    """Devuelve el engine de tests si está inyectado; si no, el global."""
    return _TEST_ENGINE if _TEST_ENGINE is not None else _engine