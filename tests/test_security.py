"""Tests para security.py - API key, rate limit y timeout."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Asegurar que .env se carga antes de los tests
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class TestAPIKey:
    """Tests para require_api_key."""

    def test_sin_api_key_configurada(self):
        """Si API_KEY está vacía, no valida (modo dev)."""
        with patch.dict(os.environ, {"API_KEY": ""}, clear=False):
            from security import require_api_key
            request = MagicMock()
            # No debe lanzar excepción
            result = require_api_key(request)
            assert result is None

    def test_con_api_key_correcta_en_header(self):
        """Validación correcta con X-API-Key header."""
        with patch.dict(os.environ, {"API_KEY": "mi-clave-test"}, clear=False):
            from security import require_api_key
            request = MagicMock()
            request.query_params.get.return_value = None
            request.headers.get.side_effect = lambda k: "mi-clave-test" if k == "X-API-Key" else None

            result = require_api_key(request)
            assert result is None

    def test_con_api_key_correcta_en_query(self):
        """Validación correcta con api_key query param."""
        with patch.dict(os.environ, {"API_KEY": "mi-clave-test"}, clear=False):
            from security import require_api_key
            request = MagicMock()
            request.query_params.get.side_effect = lambda k: "mi-clave-test" if k == "api_key" else None
            request.headers.get.return_value = None

            result = require_api_key(request)
            assert result is None

    def test_api_key_incorrecta_lanza_401(self):
        """API key incorrecta -> HTTPException 401."""
        with patch.dict(os.environ, {"API_KEY": "mi-clave-test"}, clear=False):
            from fastapi import HTTPException
            from security import require_api_key

            request = MagicMock()
            request.query_params.get.return_value = None
            request.headers.get.side_effect = lambda k: "clave-mal" if k == "X-API-Key" else None

            with pytest.raises(HTTPException) as exc_info:
                require_api_key(request)
            assert exc_info.value.status_code == 401

    def test_api_key_falsa_lanza_401(self):
        """API key vacía -> HTTPException 401."""
        with patch.dict(os.environ, {"API_KEY": "mi-clave-test"}, clear=False):
            from fastapi import HTTPException
            from security import require_api_key

            request = MagicMock()
            request.query_params.get.return_value = None
            request.headers.get.side_effect = lambda k: "" if k == "X-API-Key" else None

            with pytest.raises(HTTPException) as exc_info:
                require_api_key(request)
            assert exc_info.value.status_code == 401


class TestRateLimit:
    """Tests para rate_limit_middleware y _RateLimiter."""

    def test_rate_limiter_dentro_del_limite(self):
        """Peticiones dentro del límite -> True."""
        from security import _rate_limiter
        # Limpiar estado previo
        _rate_limiter._requests.clear()

        ip = "127.0.0.1"
        for i in range(60):  # RATE_LIMIT_PER_MINUTE por defecto
            assert _rate_limiter.check(ip) is True

    def test_rate_limiter_fuera_del_limite(self):
        """Peticiones que superan el límite -> False (429)."""
        from security import _rate_limiter, RATE_LIMIT_PER_MINUTE
        # Limpiar y llenar
        _rate_limiter._requests.clear()
        ip = "10.0.0.1"

        for i in range(RATE_LIMIT_PER_MINUTE):
            assert _rate_limiter.check(ip) is True

        # La siguiente debería ser rechazada
        assert _rate_limiter.check(ip) is False

    def test_rate_limit_excluye_health(self):
        """La ruta /health no cuenta para rate limit."""
        from security import rate_limit_middleware
        request = MagicMock()
        request.url.path = "/health"
        request.client.host = "127.0.0.1"

        async def mock_call_next(req):
            return MagicMock(status_code=200)

        # No debe lanzar 429 incluso si está lleno
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            rate_limit_middleware(request, mock_call_next)
        )
        assert result.status_code == 200


class TestTimeout:
    """Tests para check_timeout."""

    def test_timeout_desactivado(self):
        """ASK_TIMEOUT_SECONDS <= 0 -> no lanza timeout."""
        with patch.dict(os.environ, {"ASK_TIMEOUT_SECONDS": "0"}, clear=False):
            from security import ASK_TIMEOUT_SECONDS, check_timeout
            assert ASK_TIMEOUT_SECONDS == 0
            # No debe lanzar
            result = check_timeout()
            assert result is None

    def test_timeout_activado_no_excedido(self):
        """Sin exceder el timeout -> no lanza."""
        with patch.dict(os.environ, {"ASK_TIMEOUT_SECONDS": "300"}, clear=False):
            from security import ASK_TIMEOUT_SECONDS, check_timeout
            # Setear _start lejos en el pasado para simular poco tiempo transcurrido
            check_timeout._start = 295.0  # segundos (simulado)
            result = check_timeout()
            assert result is None


class TestLogRequest:
    """Tests para log_request."""

    def test_log_request_retorna_dict(self):
        """log_request devuelve un dict con los campos esperados."""
        from security import log_request
        resultado = log_request("POST", "/ask", "thread-123", 450, 200)

        assert isinstance(resultado, dict)
        assert resultado["method"] == "POST"
        assert resultado["path"] == "/ask"
        assert resultado["thread_id"] == "thread-123"
        assert resultado["duration_ms"] == 450
        assert resultado["status_code"] == 200
        assert "timestamp" in resultado
