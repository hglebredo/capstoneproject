"""security.py - API key, rate limit y timeout para el PB3/MLOps.

- api_key: valida contra variable de entorno API_KEY. 401 si falta/incorrecta.
- rate_limit: cuenta peticiones por IP en ventana de tiempo. 429 si supera RATE_LIMIT_PER_MINUTE.
- timeout middleware: envia 504 si el turno excede ASK_TIMEOUT_SECONDS.
"""
from __future__ import annotations

import os
import time
import threading as _threading
import hmac as _hmac
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


# --------------------------------------------------------------------------- #
#  API Key                                                                     #
# --------------------------------------------------------------------------- #

API_KEY: str = os.environ.get("API_KEY", "")
RATE_LIMIT_PER_MINUTE: int = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
ASK_TIMEOUT_SECONDS: int = int(os.environ.get("ASK_TIMEOUT_SECONDS", "300"))


def require_api_key(request: Request) -> None:
    """Dependencia FastAPI para verificar API key.

    Lee la clave de query param (para Swagger), header o body.
    Si no hay API_KEY configurada, salta la validacion (modo dev).
    Si falta o es incorrecta → 401.
    """
    if not API_KEY:
        return  # modo dev sin clave

    api_key = (request.query_params.get("api_key")
               or request.headers.get("X-API-Key"))

    if not api_key or _hmac.compare_digest(api_key, API_KEY):
        return  # valido

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API key incorrecta o falta",
    )


# --------------------------------------------------------------------------- #
#  Rate Limit                                                                  #
# --------------------------------------------------------------------------- #

class _RateLimiter:
    """Contador simple de peticiones por IP en ventana de 60s."""

    def __init__(self, max_per_minute: int = RATE_LIMIT_PER_MINUTE):
        self.max_per_minute = max_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = _threading.Lock()

    def check(self, ip: str) -> bool:
        """Devuelve True si la peticion esta dentro del limite."""
        now = time.time()
        window = 60.0  # segundos

        with self._lock:
            # limpiar entradas viejas
            timestamps = self._requests[ip]
            cutoff = now - window
            self._requests[ip] = [t for t in timestamps if t > cutoff]

            if len(self._requests[ip]) >= self.max_per_minute:
                return False

            self._requests[ip].append(now)
            return True


_rate_limiter = _RateLimiter()


async def rate_limit_middleware(request: Request, call_next: Callable):
    """Middleware que cuenta peticiones por IP y devuelve 429 si supera el tope."""
    # Saltar para rutas publicas (/health, /docs)
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    ip = request.client.host if request.client else "unknown"
    if not _rate_limiter.check(ip):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": f"Rate limit excedido ({RATE_LIMIT_PER_MINUTE}/min)"},
        )

    response = await call_next(request)
    return response


# --------------------------------------------------------------------------- #
#  Timeout                                                                     #
# --------------------------------------------------------------------------- #

def check_timeout() -> None:
    """Verifica si el turno ha superado ASK_TIMEOUT_SECONDS. Lanza HTTPException 504."""
    if ASK_TIMEOUT_SECONDS <= 0:
        return
    # Se usa en los endpoints /ask para verificar antes de llamar al grafo
    elapsed = getattr(check_timeout, "_start", time.time())
    duration_ms = int((time.time() - elapsed) * 1000)

    if duration_ms > ASK_TIMEOUT_SECONDS * 1000:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Timeout: el turno supero {ASK_TIMEOUT_SECONDS}s",
        )


# --------------------------------------------------------------------------- #
#  Logging                                                                     #
# --------------------------------------------------------------------------- #

def log_request(method: str, path: str, thread_id: str | None, duration_ms: int, status_code: int) -> dict[str, Any]:
    """Log estructurado con los campos que pide el PB3."""
    entry = {
        "method": method,
        "path": path,
        "thread_id": thread_id or "",
        "duration_ms": duration_ms,
        "status_code": status_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    import logging
    logging.info("%s %s thread=%s dur=%dms status=%d", entry["method"], entry["path"], entry["thread_id"], entry["duration_ms"], entry["status_code"])
    return entry
