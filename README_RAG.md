# RAG — Project Break 3 (MLOps)

Este directorio contiene el sistema RAG completo, portable desde `agentes_deportesmad/` al proyecto `capstoneproject/`, alineado con las instrucciones del PB3/MLOps.

## Estructura

```
capstoneproject/
├── rag/                          # ← Paquete RAG (portable)
│   ├── __init__.py               # API pública: responder(), rag_ask(), ejecutar_pipeline()
│   ├── config.py                 # Configuración (env variables, rutas relativas)
│   ├── logic.py                  # Orquestador online: responder(pregunta) → dict
│   ├── pipeline.py               # Pipeline offline: LOAD→CLEAN→TAG→CHUNK→EMBED→INDEX
│   ├── retrieve.py               # Recuperación vectorial + híbrida (ChromaDB / PGVector)
│   ├── embed.py                  # Embeddings (Google Gemini, Ollama, HuggingFace)
│   ├── generate.py               # Generación con LLM
│   ├── load.py                   # Carga de documentos (PDF, Excel, Word, Markdown)
│   ├── chunk.py                  # Chunking inteligente
│   ├── clean.py                  # Limpieza y normalización de texto
│   ├── prompts.py                # Templates de prompt para generación
│   ├── index.py                  # Indexación en ChromaDB / PGVector
│   ├── informe.py                # Generación de informes markdown
│   ├── vision.py                 # OCR + visión multimodal
│   ├── tools/                    # Utilidades (debug, métricas)
│   │   └── ...
│   ├── tsd/                      # Tagging → Scoring → Deduplication
│   │   ├── __init__.py
│   │   ├── tag.py                # Etiquetado LLM por fuente
│   │   ├── scoring.py            # Puntuación de chunks
│   │   └── dedup.py              # Deduplicación por similitud coseno
│   └── db/                      # Capa relacional (PB3/MLOps)
│       ├── __init__.py           # Package marker
│       ├── models.py             # Conversation + Message (SQLAlchemy)
│       ├── init_db.py            # Inicialización SQLite (legacy)
│       ├── db_init.py            # Package marker
│       └── db_engine.py          # CRUD para historial del agente
├── rag_utils.py                  # Punto de entrada portable (import desde cualquier sitio)
├── .env                          # Variables locales (no commitear)
├── .env.rag.example              # Plantilla de variables
└── requirements-rag.txt          # Dependencias específicas del RAG
```

## Uso rápido

### 1. Configurar el entorno

```bash
# Copiar la plantilla y ajustar valores
cp .env.rag.example .env
# Editar .env: GOOGLE_API_KEY, DATABASE_URL, API_KEY, etc.
```

### 2. Inicializar la base de datos relacional (PB3/MLOps)

```python
from rag_utils import init_rag_db

init_rag_db()
# Crea tablas Conversation + Message en PostgreSQL o SQLite
```

### 3. Consultar el RAG (online — pregunta → respuesta)

```python
from rag_utils import responder

resultado = responder("¿Qué servicios ofrece el ayuntamiento?")
print(resultado["respuesta"])
# { "respuesta": "...", "chunks": [...], "fuentes": [...], ... }
```

### 4. Indexar documentos (offline — ingestión del corpus)

```python
from rag_utils import ejecutar_pipeline

info = ejecutar_pipeline("./data/corpus/")
# { "num_documentos_cargados": N, "num_chunks_post_dedup": M, ... }
```

## Integración con PB3/MLOps

El RAG se integra como **tool** del agente del PB2:

- `rag.logic.responder()` → tool real que devuelve contexto + respuesta
- `rag.db.models.Conversation` y `Message` → historial en PostgreSQL
- Compatible con ChromaDB (local) y PGVector (PostgreSQL)
- Proveedor único de generación: **Gemini** (`GEN_PROVIDER=google`)

### Variables clave para PB3/MLOps

| Variable | Valor recomendado | Uso |
|----------|-------------------|-----|
| `GEN_PROVIDER` | `google` | Gemini como único proveedor de generación |
| `EMBED_PROVIDER` | `google` | Gemini embeddings (o `ollama` si se prefiere offline) |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL para historial del agente |
| `API_KEY` | string | Clave de la API REST protegida |
| `CORS_ORIGINS` | `*` o lista | Orígenes permitidos para el front Streamlit |

## Cómo funciona desde la API FastAPI

```
POST /ask          → rag.logic.responder() + guarda en Postgres
POST /approve      → decisión humana (HITL) + guarda en Postgres
GET  /health       → estado del servicio + storage (PostgreSQL/ChromaDB)
GET  /docs         → Swagger con schemas Pydantic
```

## Requisitos técnicos

- Python 3.10+
- `GOOGLE_API_KEY` configurada para Gemini (único proveedor en producción PB3/MLOps)
- PostgreSQL con pgvector (o ChromaDB local como fallback)
- `DATABASE_URL` apuntando al Postgres correcto (`postgresql://`, no `postgres://`)
