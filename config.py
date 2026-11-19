"""
config.py — Configuración compartida del proyecto de agentes.

Requisitos de agentes/tools/vision.py:
- ROOT: raíz del proyecto para resolver rutas relativas.
- IMAGEN_DEFAULT_PATH: imagen demo usada por la tool de visión.
- VISION_MODEL: modelo multimodal imagen -> texto.
"""

from pathlib import Path
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Raíz real del repositorio.
ROOT = Path(__file__).resolve().parent

# Recursos compartidos.
ASSETS_DIR = ROOT / "assets"

# Imagen obligatoria para la demo multimodal.
IMAGEN_DEFAULT_PATH = ASSETS_DIR / "imagen_demo.jpg"

# Modelo de visión usado por agentes/tools/vision.py.
VISION_MODEL = os.getenv("VISION_MODEL", "gemini-3.8-flash")

# --- API PB3 (app.py) --------------------------------------------------------
# Patrón de config.py del Sprint 15: valores del entorno, con defaults seguros.

# El código del PB2 lee GOOGLE_API_KEY; el equipo usa GEMINI_API_KEY.
# Si solo existe GEMINI_API_KEY, se copia para que el agente la encuentre.
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# "real" (Gemini + RAG) o "demo" (agente simulado, sin LLM: para probar la API)
AGENT_MODE: str = os.getenv("AGENT_MODE", "real")

API_KEY: str | None = os.getenv("API_KEY") or None
RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8501,http://localhost:8501",
)
CORS_ORIGINS: list[str] = [o.strip() for o in _cors_raw.split(",") if o.strip()]

# Tope de tiempo por turno (POST /ask y /approve) → 504
ASK_TIMEOUT_SECONDS: int = int(os.getenv("ASK_TIMEOUT_SECONDS", "300"))
