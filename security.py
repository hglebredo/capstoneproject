
"""
security.py — Seguridad de la API PB3.

- require_api_key: valida la API Key.
    503: API_KEY no configurada en el servidor.
    401: API Key ausente o incorrecta.

- RateLimitMiddleware: limita las peticiones por cliente.
    429: límite de peticiones superado.
    Ventana deslizante de 60 segundos.

- Logging de seguridad para 401, 503 y 429.

La API Key se acepta en la cabecera X-API-Key (la que usa el front) o en el
parámetro ?api_key= (lo pide el enunciado para probar desde Swagger).
Nunca se almacenan ni registran las API Keys en texto plano: un filtro oculta
?api_key= en el access log de uvicorn.
"""

import hashlib
import logging
import re
import secrets
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader, APIKeyQuery
from starlette.middleware.base import BaseHTTPMiddleware

import config


logger = logging.getLogger("security")


# ---------------------------------------------------------------------------
# Dónde viaja la API Key
# ---------------------------------------------------------------------------

# auto_error=False: si falta, no responde 403 automáticamente; decidimos aquí (401/503).
# Swagger muestra ambas en el botón "Authorize".
_API_KEY_HEADER = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Clave de la API en cabecera (recomendado: no queda en los logs).",
)
_API_KEY_QUERY = APIKeyQuery(
    name="api_key",
    auto_error=False,
    description="Clave de la API en la URL (?api_key=), para probar desde Swagger.",
)


def _extraer_api_key(request: Request) -> str | None:
    """Lee la clave de la cabecera X-API-Key o, si no está, de ?api_key=."""
    return request.headers.get("X-API-Key") or request.query_params.get("api_key")


# ---------------------------------------------------------------------------
# Filtro del access log: oculta ?api_key= en las líneas de uvicorn
# ---------------------------------------------------------------------------

_PATRON_API_KEY = re.compile(r"(api_key=)[^&\s\"]+", re.IGNORECASE)


class OcultarApiKeyFilter(logging.Filter):
    """Cambia api_key=<valor> por api_key=*** antes de escribir la línea de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                _PATRON_API_KEY.sub(r"\1***", a) if isinstance(a, str) else a
                for a in record.args
            )
        if isinstance(record.msg, str):
            record.msg = _PATRON_API_KEY.sub(r"\1***", record.msg)
        return True


# Uvicorn configura sus loggers antes de importar la app, así que el filtro se
# añade al importar este módulo (app.py importa security).
logging.getLogger("uvicorn.access").addFilter(OcultarApiKeyFilter())


# ---------------------------------------------------------------------------
# Identificación segura del cliente
# ---------------------------------------------------------------------------

def _cliente(request: Request) -> str:
    """Identifica al cliente: por hash de api_key SOLO si es válida; si no, por IP."""
    api_key = _extraer_api_key(request)
    if (
        api_key
        and config.API_KEY
        and secrets.compare_digest(api_key, config.API_KEY)
    ):
        hash_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        return f"key:{hash_key}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def _cliente_para_log(request: Request) -> str:
    """Devuelve un identificador seguro para los logs."""
    if _extraer_api_key(request):
        return "api_key"

    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


# ---------------------------------------------------------------------------
# Validación API Key
# ---------------------------------------------------------------------------

def require_api_key(
    request: Request,
    api_key_header: str | None = Security(_API_KEY_HEADER),
    api_key_query: str | None = Security(_API_KEY_QUERY),
) -> None:
    """
    Dependencia FastAPI para proteger las rutas de la API.

    Acepta la clave en la cabecera X-API-Key o en ?api_key= (tiene prioridad la cabecera).
    503: el servidor no tiene API_KEY configurada.
    401: la petición no trae API Key o es incorrecta.
    """
    api_key = api_key_header or api_key_query

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

    if (
        not api_key
        or not secrets.compare_digest(api_key, config.API_KEY)
    ):
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
