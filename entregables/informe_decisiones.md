# Informe de Decisiones — Project Break 3 (MLOps)

> Fecha: Nov 2026  
> Equipo: Miguel, David, Héctor  

---

## D1. FastAPI como framework API (elegido vs Flask/Django)

**Decisión:** Se usa **FastAPI + uvicorn** para exponer el agente del PB2.

- **Por qué:** native async, auto-generación de Swagger/OpenAPI, validación con Pydantic v2, tipado estricto.
- **Alternativa descartada:** Flask (sin validación automática) y Django (demasiado pesado para una API ligera).
- **Impacto:** `app.py` es el entry point principal; `uvicorn` corre como servidor ASGI.

---

## D2. PostgreSQL con SQLAlchemy Core (elegido vs SQLite puro / PGVector alone)

**Decisión:** Persistencia en **PostgreSQL** vía SQLAlchemy Core (`rag/db/models.py`, `db_engine.py`).  
Fallback a SQLite local si no hay `DATABASE_URL`.

- **Por qué:** El spec PB3 exige historial de producto persistente, multi-thread-safe y desplegable en Render.
- **Tablas:** `Conversation` (hilo) + `Message` (mensajes), unidas por `thread_id`.
- **Impacto:** `/ask`, `/approve` y `/threads/{id}/messages` operan sobre Postgres; el RAG sigue usando ChromaDB local para embeddings.

---

## D3. Modelo de seguridad: API key + rate limit + timeout

**Decisión:** Tres capas en `security.py`:

| Capa | Código | Condición |
|------|--------|-----------|
| API Key | 401 | Falta o incorrecta (`X-API-Key` header o query param) |
| Rate Limit | 429 | > `RATE_LIMIT_PER_MINUTE` peticiones/IP en 60s |
| Timeout | 504 | Turno supera `ASK_TIMEOUT_SECONDS` (300s por defecto) |

- **Por qué:** Cumple el spec PB3 y es demostrable localmente.
- **CORS** abierto vía variable `CORS_ORIGINS`.

---

## D4. Proveedor único: Google Gemini

**Decisión:** Solo **Gemini** para generación, embeddings y tagging (`google-genai`).

- **Por qué:** Ollama no cabe en el free tier de Render; HuggingFace es opcional pero no necesario para la demo.
- **Variables:** `GEN_PROVIDER=google`, `EMBED_PROVIDER=google`, `TAG_PROVIDER=google`.
- **Clave:** `GOOGLE_API_KEY` (el mismo nombre que lee el PB2).

---

## D5. HITL con auto_aprobar como interruptor

**Decisión:** El endpoint `/ask` acepta `auto_aprobar: bool`:

- `true` -> cierra solo si queda en HITL (modo cómodo para Swagger/demo).
- `false` -> deja plan pendiente, el front debe llamar a `/approve`.

**Regla de guardado:** se persiste al **resolver** el turno (aprobado o rechazado), no solo con `done=true`.

---

## D6. Arquitectura por capas: app.py llama, rag/ se mantiene

**Decisión:** No reescribir el grafo del PB2; `app.py` llama a `rag.logic.responder()`:

```
FastAPI (app.py)  ──►  AgentService del PB2  ──►  RAG + Gemini
    │
    ├── POST /ask          -> rag.logic.responder()
    ├── POST /approve      -> resuelve plan HITL
    └── GET /threads/...   -> rag.db.get_messages()
```

- **Ventaja:** el grafo, las tools y el pipeline de indexación se reutilizan sin cambios.
- **Impacto:** `rag_utils.py` es el punto de entrada portable (`responder`, `ejecutar_pipeline`).

---

## D7. Docker + Render para despliegue

**Decisión:** Contenerizar con Dockerfile multi-stage; desplegar en Render con Postgres managed.

- **Dockerfile:** Python 3.12 slim, copia de código y `.env`, `uvicorn` como CMD.
- **.dockerignore:** excluye `.venv/`, `__pycache__/`, archivos locales pesados.
- **Render:** variables de entorno en panel; DATABASE_URL automático con add-on Postgres.

---

## D8. Schemas Pydantic propios (schemas_mlops.py)

**Decisión:** Nuevo archivo de contratos para PB3/MLOps: `AskIn`, `AskOut`, `ApproveIn`, `ApproveOut`, `MessageOut`, `MessagesOut`.

- **No rompen el spec v1:** añaden campos opcionales (`plan`, `pendiente_hitl`).
- **Validación automática** de cuerpos en FastAPI (422 si inválido).

---

## Resumen de archivos del PR#2

| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `app.py` | NUEVO | Routes FastAPI: /health, /ask, /approve, /threads/{id}/messages |
| `schemas_mlops.py` | NUEVO | Contratos Pydantic del contrato PB3 |
| `security.py` | NUEVO | API key (401), rate limit (429), timeout (504), CORS, logs |
| `rag/db/models.py` | ACTUALIZADO | Conversation + Message alineados con spec PB3 |
| `rag/db/db_engine.py` | ACTUALIZADO | ensure_conversation, add_message, get_messages |
| `rag/config.py` | ACTUALIZADO | Vars de entorno adaptadas a PB3 (Gemini-only) |
| `.env` | ACTUALIZADO | Config local con DATABASE_URL y API_KEY |
| `.env.rag.example` | ACTUALIZADO | Ejemplo completo para copiar |
| `requirements-rag.txt` | ACTUALIZADO | Incluye fastapi, uvicorn, pydantic>=2, psycopg, pgvector |
| `rag_utils.py` | ACTUALIZADO | Punto de entrada portable (responder, ejecutar_pipeline) |
| `Dockerfile` | NUEVO | Multi-stage para producción |
| `.dockerignore` | NUEVO | Excluye .venv y archivos locales |
| `docs/contrato_api.md` | ACTUALIZADO | Spec API actualizado a v2 |
| `README.md` | ACTUALIZADO | Estructura actualizada al nuevo layout |
