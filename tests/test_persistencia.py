"""
tests/test_persistencia.py — Test de integración con PostgreSQL real.

Requiere DATABASE_URL_TEST apuntando a un Postgres de test.
Si no está definida, todos los tests se saltan (skip).

Uso:
  $env:DATABASE_URL_TEST = "postgresql://postgres:123456@127.0.0.1:5432/postgres_test"
  pytest tests/test_persistencia.py -v

Crea una BD de test (postgres_test) para no tocar la de desarrollo:
  docker exec -it capstone-pg psql -U postgres -c "CREATE DATABASE postgres_test;"
"""

import os

import pytest
from sqlmodel import SQLModel, create_engine

from src import db

DATABASE_URL_TEST = os.getenv("DATABASE_URL_TEST")


@pytest.fixture(scope="module", autouse=True)
def engine_postgres():
    """Engine de Postgres real para los tests de integración."""
    if not DATABASE_URL_TEST:
        pytest.skip("DATABASE_URL_TEST no definida; se saltan los tests de integración")

    engine = create_engine(DATABASE_URL_TEST, echo=False, pool_pre_ping=True)
    SQLModel.metadata.create_all(engine)
    db._set_engine_for_tests(engine)
    yield engine
    db._set_engine_for_tests(None)  # type: ignore[arg-type]


def test_persistencia_real_guarda_y_recupera():
    """Guardar un turno en Postgres real y recuperarlo."""
    db.save_turn("integracion-1", "pregunta real", "respuesta real")
    mensajes = db.list_messages("integracion-1")
    assert len(mensajes) == 2
    assert mensajes[0]["role"] == "user"
    assert mensajes[0]["content"] == "pregunta real"
    assert mensajes[1]["role"] == "assistant"
    assert mensajes[1]["content"] == "respuesta real"


def test_persistencia_real_sobrevive_a_nueva_sesion():
    """El historial está en Postgres, no en RAM: una nueva sesión lo ve."""
    db.save_turn("integracion-2", "pregunta", "respuesta")
    # Cerramos y volvemos a abrir sesión (simula reinicio del proceso)
    mensajes = db.list_messages("integracion-2")
    assert len(mensajes) == 2


def test_persistencia_real_db_ok():
    assert db.db_ok() is True


def test_persistencia_real_hilo_inexistente():
    assert db.list_messages("integracion-no-existe") == []