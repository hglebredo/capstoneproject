"""
agentes/tools/vision.py

Tool de visión: imagen -> texto.

Contrato:
    imagen_preguntar(image_id, pregunta) -> dict
        {
            "ok": bool,
            "resultado": str,
            "fuentes": list[str],
            "abstained": bool,
            "error": str | None,
        }

Reglas:
- Nunca lanza excepciones: los errores viajan en "error".
- Acepta JPG/JPEG y PNG (los mismos formatos que valida agentes/image_input.py).
- Si el modelo de visión no es de Gemini (p. ej. GEN_PROVIDER=ollama sin
  IMAGE_VISION_MODEL), se abstiene con un aviso claro en vez de devolver un 404.
- Si no hay GOOGLE_API_KEY, informa de visión no disponible y se abstiene.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

import requests
from langchain_core.tools import tool

from rag.config import IMAGE_VISION_MODEL

FORMATOS_PERMITIDOS = {".jpg", ".jpeg", ".png"}
MIME_POR_EXTENSION = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
IMAGEN_DEMO = RAIZ_PROYECTO / "assets" / "imagen_demo.jpg"
_API_KEY_AL_IMPORTAR = os.getenv("GOOGLE_API_KEY")
GOOGLE_API_KEY = _API_KEY_AL_IMPORTAR

def _api_key() -> str:
    """Resuelve la clave: el parche del módulo tiene prioridad; si no, el entorno."""
    if GOOGLE_API_KEY != _API_KEY_AL_IMPORTAR:
        return GOOGLE_API_KEY or ""

    return os.getenv("GOOGLE_API_KEY") or ""

def _abstencion(error: str) -> dict:
    return {
        "ok": False,
        "resultado": "",
        "fuentes": [],
        "abstained": True,
        "error": error,
    }


def _error(error: str) -> dict:
    return {
        "ok": False,
        "resultado": "",
        "fuentes": [],
        "abstained": False,
        "error": error,
    }


@tool
def imagen_preguntar(image_id: str, pregunta: str = "Describe objetivamente la imagen.") -> dict:
    """Responde una pregunta sobre una imagen usando visión multimodal.

    Args:
        image_id: Ruta o identificador de la imagen.
        pregunta: Pregunta que debe responderse usando solo información visible.
    """
    # Primero se valida la imagen y después la clave: así el error es útil
    # aunque no haya GOOGLE_API_KEY.
    ruta = IMAGEN_DEMO if image_id == "imagen_demo" else Path(image_id)

    if not ruta.exists():
        return _error(f"No hay imagen en la ruta indicada: {image_id}")

    if ruta.suffix.lower() not in FORMATOS_PERMITIDOS:
        return _error(
            f"Formato no soportado: {ruta.suffix}. "
            f"Formatos permitidos: {', '.join(sorted(FORMATOS_PERMITIDOS))}."
        )
    api_key = _api_key()
    if not api_key:
        return _abstencion(
            "Visión no disponible: GOOGLE_API_KEY no está definida."
        )

    # IMAGE_VISION_MODEL hereda GEN_MODEL (rag/config.py). Si GEN_PROVIDER no es
    # google (p. ej. ollama → llama3.2), Gemini respondería 404: mejor avisar.
    if not str(IMAGE_VISION_MODEL).startswith("gemini"):
        return _abstencion(
            f"Visión no disponible: el modelo de visión '{IMAGE_VISION_MODEL}' no es de Gemini. "
            "Define IMAGE_VISION_MODEL o usa GEN_PROVIDER=google."
        )

    try:
        imagen_base64 = base64.b64encode(ruta.read_bytes()).decode("utf-8")
    except OSError as exc:
        return _error(f"No se pudo leer la imagen: {exc}")
    
    mime_type = MIME_POR_EXTENSION[ruta.suffix.lower()]
  
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{IMAGE_VISION_MODEL}:generateContent"
    )

    try:
        respuesta = requests.post(
            url,
            headers={"x-goog-api-key": api_key},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": pregunta},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": imagen_base64,
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 512,
                },
            },
            timeout=120,
        )
        respuesta.raise_for_status()

        partes = respuesta.json()["candidates"][0]["content"]["parts"]
        texto = "".join(parte.get("text", "") for parte in partes).strip()

    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        return _abstencion(f"Error al consultar el modelo de visión: {exc}")

    if not texto:
        return _abstencion(
            "El modelo de visión no devolvió información verificable."
        )

    return {
        "ok": True,
        "resultado": texto,
        "fuentes": [str(ruta)],
        "abstained": False,
        "error": None,
    }
