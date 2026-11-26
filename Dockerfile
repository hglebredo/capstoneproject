# ===================================================================
# Dockerfile - PB3/MLOps (FastAPI + RAG)
# Multi-stage: build → run
# -------------------------------------------------------------------
# Uso local:
#   docker build -t rag-pb3 .
#   docker run --env-file .env -p 8000:8000 rag-pb3
#
# Render (selecciona este archivo en el panel):
#   Variables de entorno en panel + DATABASE_URL automático.
# ===================================================================

# --- Stage 1: base ---
FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Dependencias del sistema (OCR, PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# --- Stage 2: dependencias ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 3: código y assets ---
COPY . .

# Las variables de entorno se controlan desde .env (cargado por docker compose env_file
# o bien con --env-file en docker run). Se mantienen defaults solo como referencia.
# ENV DATABASE_URL=postgresql://postgres:postgres@localhost:5432/deportes
# ENV API_KEY=cambia-esto
# ENV GOOGLE_API_KEY=""
# ENV GEN_PROVIDER=google
# ENV EMBED_PROVIDER=google
# ENV TAG_PROVIDER=google
# ENV CORS_ORIGINS=*
# ENV ASK_TIMEOUT_SECONDS=300
# ENV RATE_LIMIT_PER_MINUTE=60

EXPOSE 8000

# Shell form: así ${PORT} (lo inyecta Render) se sustituye. --proxy-headers: IP real tras el proxy de Render.
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips="*"
