# RAG — Project Break 3 (MLOps)

Pipeline RAG completo para el corpus de Deporte Municipal del Ayuntamiento de Madrid.  
Portado desde PB2, reutilizado en PB3 sin reescribir el grafo.

---

## Arquitectura por capas

```
app.py (FastAPI)
    │
    ├── POST /ask      --->  responder(pregunta)   -> rag.logic.responder()
    ├── POST /approve  --->  resuelve plan HITL
    └── GET  /threads/ --->  get_messages()        -> rag.db.get_messages()

rag_utils.py (punto de entrada portable)
    │
    ├── responder()     -> rag.logic.responder()   (online: pregunta -> respuesta)
    ├── ejecutar_pipeline() -> rag.pipeline.ejecutar_pipeline() (offline: indexación)
    └── init_rag_db()   -> rag.db.models.init_db()  (crear tablas PG/SQLite)

┌──────────────────────────── RAG PIPELINE ──────────────────────────┐
│                                                                      │
│  PREFLIGHT  ->  LOAD  ->  CLEAN  ->  TAG  ->  CHUNK  ->  EMBED          │
│     │           │         │        │         │         │             │
│   Verificar    PDF/CSV   Normal- Etiqueta- Trocear   Embeddings:   │
│   modelo       TXT/MD    iza      semántico Recursive   Ollama/HF/  │
│   disponible   -> Docs   por      (categoria+         Google        │
│                limpio  formato  tags)     char split  ──────────    │
│                                                                      │
│  SCORING  ->  DEDUP  ->  INDEX                                       │
│     │           │         │                                         │
│   Puntuar       Eliminar   ChromaDB                                  │
│   (0.45·rel+    duplicados  Vector store local                       │
│    0.20·cent+   por        con búsqueda coseno/BM25/RRF             │
│    0.20·red+     política)                                       │
│    0.15·aut)                                                             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Proveedores (interruptibles por variable de entorno)

| Fase | Proveedor | Variable | Default PB3 | Opciones |
|------|-----------|----------|-------------|----------|
| Embeddings | Google Gemini | `EMBED_PROVIDER` | `google` | `ollama`, `huggingface` |
| Generación | Google Gemini | `GEN_PROVIDER` | `google` | `ollama`, `huggingface` |
| Tagging | Google Gemini | `TAG_PROVIDER` | hereda de GEN | `ollama`, `huggingface` |

### Claves necesarias

- **Google**: `GOOGLE_API_KEY`
- **HuggingFace**: `HF_TOKEN` (solo para modelos gated)
- **Ollama local**: sin clave, solo `OLLAMA_BASE_URL` (por defecto `http://127.0.0.1:11434`)

---

## Flujo online (pregunta -> respuesta)

```python
from rag_utils import responder

resultado = responder("¿Cuánto cuesta el abono de piscina?")
# {
#     "respuesta": str,           # Texto generado por Gemini
#     "chunks": [...],            # Chunks recuperados
#     "fuentes": ["file1.pdf"],   # Fuentes únicas en orden
#     "contexto": str,            # Bloque de contexto del prompt
#     "metrics": {...},           # Tiempos y parámetros
#     "abstained": bool,          # True si no hay evidencia suficiente
#     "error": str | None,        # Mensaje de error o None
# }
```

---

## Flujo offline (indexación completa)

```python
from rag_utils import ejecutar_pipeline, init_rag_db

init_rag_db()  # Crea tablas Conversation + Message en PG/SQLite
info = ejecutar_pipeline("./data/corpus/")
# {
#     "num_documentos_cargados": int,
#     "num_chunks_pre_dedup": int,
#     "num_chunks_post_dedup": int,
#     "tiempo_total_s": float,
# }
```

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---------|----------------|
| `config.py` | Todas las constantes y variables de entorno (proveedores, modelos, rutas) |
| `logic.py` | Orquestador online: `responder()` + `rag_ask()` |
| `pipeline.py` | Pipeline offline completo: PREFLIGHT -> LOAD -> CLEAN -> TAG -> CHUNK -> EMBED -> SCORING -> DEDUP -> INDEX |
| `load.py` | Carga de documentos: PDF, CSV, TXT, MD (con soporte TAB/OCR) |
| `clean.py` | Limpieza y normalización por formato (PDF/CSV/JSON genérico) |
| `chunk.py` | Troceado en fragmentos con RecursiveCharacterTextSplitter |
| `embed.py` | Embeddings: Ollama / HuggingFace / Google GenAI + checkpointing |
| `generate.py` | Generación de texto: Gemini / Ollama / HF (con retry) |
| `retrieve.py` | Recuperación híbrida: vectorial + BM25 fusionadas por RRF |
| `prompts.py` | Construcción del prompt para el LLM |
| `index.py` | Indexación en ChromaDB con verificación de ids |
| `vision.py` | Carga de imágenes (OCR Tesseract + Gemini Vision) |
| `pdf_tabular.py` | Procesamiento especial de PDFs marcados TAB/OCR |
| `csv_advisor.py` | Clasificación heurística de CSVs (policy-aware: exact_key, group_only, etc.) |
| `csv_transform.py` | Transformación de filas a Documents según política del advisor |
| `informe.py` | Genera informe markdown tras la indexación |
| `logging_utils.py` | Logging estructurado con métricas por fase |

### Subpaquetes

| Paquete | Contenido |
|---------|-----------|
| `tsd/` | Tagging, Scoring y Deduplicación (offline) |
| `db/` | Capa relacional: Conversation + Message (Postgres/SQLite) |
| `tools/` | Utilidades de debugging y análisis de métricas |

---

## Variables clave (resumen)

Ver [`docs/environment.md`](../docs/environment.md) para la referencia completa.

| Variable | Valor PB3 default | Descripción |
|----------|-------------------|-------------|
| `GOOGLE_API_KEY` | `""` | Clave de Gemini (requerida en producción) |
| `HF_TOKEN` | `""` | Token HuggingFace (opcional, para modelos gated) |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Endpoint Ollama local |
| `GEN_MODEL` | `gemini-3.6-flash` | Modelo de generación efectivo |
| `EMBED_MODEL` | `gemini-embedding-2` | Modelo de embeddings efectivo |
| `DATABASE_URL` | `postgresql://.../deportes` | Postgres para historial (SQLite si vacío) |

---

## Notas técnicas

- **Dimensión consistente**: `embeddear()` garantiza que los vectores nunca superan `EMBED_DIM`. Esto se hereda al índice y a la consulta.
- **Checkpoint de embeddings**: Los embeddings calculados se persisten en JSONL (`output/embeddings_checkpoint.jsonl`). Si Gemini cae, el pipeline reanuda donde se quedó.
- **RRF (Reciprocal Rank Fusion)**: La recuperación híbrida fusiona ranking vectorial y BM25 con K=60. Un chunk presente en ambos rankings acumula score.
- **Dedup por política**: Los chunks de CSVs con `exact_key` nunca se deduplican por coseno. Los `group_only` se agrupan por dimensiones. El resto pasa por dedup semántico.
- **FAISS para scoring y dedup**: Memoria O(n·d) en vez de O(n²). ~1,3 GB vs ~68 GB a escala real.