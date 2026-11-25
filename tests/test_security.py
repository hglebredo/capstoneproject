
"""
tests/test_security.py — Pruebas de seguridad de la API PB3.
"""

import logging

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import config
from security import RateLimitMiddleware, require_api_key


@pytest.fixture
def client(monkeypatch):
    """Crea una API aislada para probar el módulo de seguridad."""

    monkeypatch.setattr(config, "API_KEY", "test-secret")

    test_app = FastAPI()

    test_app.add_middleware(
        RateLimitMiddleware,
        limite=3,
    )

    @test_app.get("/health")
    def health():
        return {"status": "ok"}

    @test_app.get(
        "/protected",
        dependencies=[Depends(require_api_key)],
    )
    def protected():
        return {"message": "acceso autorizado"}

    return TestClient(test_app)


def test_api_key_correcta(client):
    response = client.get(
        "/protected",
        params={"api_key": "test-secret"},
    )

    assert response.status_code == 200


def test_api_key_ausente(client, caplog):
    with caplog.at_level(logging.WARNING, logger="security"):
        response = client.get("/protected")

    assert response.status_code == 401
    assert "401 GET /protected" in caplog.text
    assert "ausente" in caplog.text


def test_api_key_incorrecta(client, caplog):
    with caplog.at_level(logging.WARNING, logger="security"):
        response = client.get(
            "/protected",
            params={"api_key": "incorrecta"},
        )

    assert response.status_code == 401
    assert "incorrecta" in caplog.text


def test_api_key_servidor_no_configurada(client, monkeypatch, caplog):
    monkeypatch.setattr(config, "API_KEY", None)

    with caplog.at_level(logging.WARNING, logger="security"):
        response = client.get(
            "/protected",
            params={"api_key": "test-secret"},
        )

    assert response.status_code == 503
    assert "503 GET /protected" in caplog.text


def test_rate_limit_429(client):
    """Tres peticiones permitidas y la cuarta bloqueada."""

    for _ in range(3):
        response = client.get(
            "/protected",
            params={"api_key": "test-secret"},
        )
        assert response.status_code == 200

    response = client.get(
        "/protected",
        params={"api_key": "test-secret"},
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit superado"
    assert response.headers["Retry-After"] == "60"



def test_rate_limit_clientes_independientes(client, monkeypatch):
    """Dos clientes distintos tienen historiales independientes."""

    # Configuramos una API Key válida para cada cliente de prueba.
    # El middleware identifica a cada cliente mediante el hash de su clave.
    monkeypatch.setattr(config, "API_KEY", "cliente-a")

    for _ in range(3):
        response = client.get(
            "/protected",
            params={"api_key": "cliente-a"},
        )
        assert response.status_code == 200

    # El cuarto intento de cliente-a debe ser bloqueado.
    response = client.get(
        "/protected",
        params={"api_key": "cliente-a"},
    )
    assert response.status_code == 429

    # Simulamos que cliente-b tiene su propia API Key válida.
    monkeypatch.setattr(config, "API_KEY", "cliente-b")

    # Su contador es independiente y todavía puede realizar peticiones.
    response = client.get(
        "/protected",
        params={"api_key": "cliente-b"},
    )

    assert response.status_code == 200



def test_health_no_consumo_rate_limit(client):
    """La ruta pública /health no consume peticiones."""

    for _ in range(10):
        response = client.get("/health")
        assert response.status_code == 200


def test_api_key_no_aparece_en_logs(client, caplog):
    secreto = "test-secret"

    with caplog.at_level(logging.WARNING, logger="security"):
        client.get(
            "/protected",
            params={"api_key": "incorrecta"},
        )

    assert secreto not in caplog.text
    assert "incorrecta" in caplog.text

def test_rate_limit_registra_429(client, caplog):
    with caplog.at_level(logging.WARNING, logger="security"):
        for _ in range(4):
            client.get(
                "/protected",
                params={"api_key": "test-secret"},
            )

    assert "429 GET /protected" in caplog.text
    assert "cliente=api_key" in caplog.text
    assert "test-secret" not in caplog.text