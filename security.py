
"""
security.py — Seguridad de la API PB3.

- require_api_key: valida la API Key.
    503: API_KEY no configurada en el servidor.
    401: API Key ausente o incorrecta.

- RateLimitMiddleware: limita las peticiones por cliente.
    429: límite de peticiones superado.
    Ventana deslizante de 60 segundos.

- Logging de seguridad para 401, 503 y 429.

Nunca se almacenan ni registran las API Keys en texto plano.
"""

import hashlib
import logging
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import config


logger = logging.getLogger("security")


# ---------------------------------------------------------------------------
# Identificación segura del cliente
# ---------------------------------------------------------------------------

def _cliente(request: Request) -> str:
    """Identifica al cliente: por hash de api_key SOLO si es válida; si no, por IP."""
    api_key = request.query_params.get("api_key")
    if api_key and api_key == config.API_KEY:
        hash_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        return f"key:{hash_key}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def _cliente_para_log(request: Request) -> str:
    """Devuelve un identificador seguro para los logs."""
    if request.query_params.get("api_key"):
        return "api_key"

    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


# ---------------------------------------------------------------------------
# Validación API Key
# ---------------------------------------------------------------------------

def require_api_key(
    request: Request,
    api_key: str | None = Query(default=None),
) -> None:
    """
    Dependencia FastAPI para proteger las rutas de la API.

    503: el servidor no tiene API_KEY configurada.
    401: la petición no trae API Key o es incorrecta.
    """

    if not config.API_KEY:
        logger.warning(
            "503 %s %s (servidor sin API_KEY)",
            request.method,
            request.url.path,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servidor sin API_KEY configurada",
        )

    if not api_key or api_key != config.API_KEY:
        logger.warning(
            "401 %s %s (api_key %s)",
            request.method,
            request.url.path,
            "ausente" if not api_key else "incorrecta",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key ausente o incorrecta",
        )


# ---------------------------------------------------------------------------
# Rate Limit
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware de rate limit mediante ventana deslizante de 60 segundos.

    Cada cliente tiene su propio historial de peticiones.

    - Cliente con API Key: identificador basado en SHA-256 de la clave.
    - Cliente sin API Key: dirección IP.

    Las rutas públicas quedan excluidas.
    """

    RUTAS_EXCLUIDAS = frozenset({
        "/",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    })

    VENTANA_SEGUNDOS = 60

    def __init__(self, app, limite: int):
        super().__init__(app)

        if limite < 1:
            raise ValueError("El límite de peticiones debe ser mayor que cero")

        self.limite = limite
        self._historial: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):

        # Las rutas públicas no consumen peticiones.
        if request.url.path in self.RUTAS_EXCLUIDAS:
            return await call_next(request)

        cliente = _cliente(request)
        ahora = time.monotonic()

        with self._lock:

            cola = self._historial[cliente]

            # Eliminar peticiones fuera de la ventana de 60 segundos.
            while cola and ahora - cola[0] >= self.VENTANA_SEGUNDOS:
                cola.popleft()

            # Comprobar si el cliente ha superado el límite.
            if len(cola) >= self.limite:

                logger.warning(
                    "429 %s %s (rate limit, cliente=%s)",
                    request.method,
                    request.url.path,
                    _cliente_para_log(request),
                )

                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit superado"
                    },
                    headers={
                        "Retry-After": str(self.VENTANA_SEGUNDOS)
                    },
                )

            # Registrar la petición permitida.
            cola.append(ahora)

        return await call_next(request)
