# syntax=docker/dockerfile:1
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

# --- Stage 3: índice del RAG, construido en el docker build ---
# Configuración del RAG fija en la imagen: la misma al indexar (build) y al consultar
# (runtime). Si el índice y las consultas usan otro modelo o dimensión, el RAG falla.
# Se puede sobrescribir desde el panel de Render.
ENV EMBED_PROVIDER=google \
    TAG_PROVIDER=google \
    GEN_PROVIDER=google \
    GOOGLE_EMBED_MODEL=gemini-embedding-2 \
    GOOGLE_GEN_MODEL=gemini-3.6-flash \
    GOOGLE_TAG_MODEL=gemini-3.6-flash \
    EMBED_DIM=1024 \
    EXPORT_EMBEDDINGS=false

# Solo el RAG y el corpus: así un cambio en app.py o en el agente NO invalida la caché
# de esta capa y no se re-indexa (ni se gasta Gemini) en cada deploy.
COPY rag/ rag/
COPY data/ data/

# La clave de Gemini solo hace falta para indexar y llega como *build secret*:
# se monta en /run/secrets/ solo durante este RUN y no queda en la imagen, ni en su
# historial, ni en los logs del build (con ARG sí aparecía en claro).
#   Render: Secret File llamado "gemini_api_key" (Render lo expone como build secret).
#   Local:  docker build --secret id=gemini_api_key,env=GOOGLE_API_KEY -t pb3-api .
RUN --mount=type=secret,id=gemini_api_key,required=true \
    GOOGLE_API_KEY="$(cat /run/secrets/gemini_api_key)" \
    python -m rag.pipeline data/corpus --recreate-index

# --- Stage 4: resto del código (API, agente, assets) ---
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

# sh -c para que ${PORT} (lo inyecta Render) se sustituya; exec para que uvicorn reciba
# las señales de parada. --proxy-headers: IP real del usuario tras el proxy de Render.
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
