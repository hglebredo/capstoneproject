"""
security.py — Seguridad de la API (versión mínima para desbloquear la API).

En este paso solo implementamos require_api_key para que app.py arranque.
El rate limit (429) se añadirá en el Paso 5.

Códigos:
- 503: el servidor no tiene API_KEY configurada (error de despliegue).
- 401: la petición no trae api_key o no coincide.
"""

from fastapi import HTTPException, Query, status

import config


def require_api_key(api_key: str | None = Query(default=None)) -> None:
    """Dependencia FastAPI: valida ?api_key=... en rutas protegidas."""
    if not config.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servidor sin API_KEY configurada",
        )
    if not api_key or api_key != config.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key ausente o incorrecta",
        )