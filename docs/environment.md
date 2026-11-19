# Variables de Entorno - PB3/MLOps

Archivo de referencia para todas las variables que lee el sistema.  
Copiar de `.env.rag.example` y ajustar según el entorno (local, Render, CI).

---

## 🔑 Credenciales

| Variable | Uso | Valor por defecto | Notas |
|----------|-----|-------------------|-------|
| `GOOGLE_API_KEY` | SDK Gemini para generación, embeddings y tagging. | `""` (vacío) | **Requerida** si `GEN_PROVIDER=google`. Lee el mismo nombre que el PB2. |
| `HF_TOKEN` | Token de HuggingFace para modelos gated. | `""` (vacío) | Necesaria solo si se usan modelos gated con HF (`meta-llama/*`, etc.). Opcional con modelos públicos. |
| `OLLAMA_TOKEN` | Autenticación opcional para Ollama remoto. | `""` (vacío) | No necesaria para Ollama local (`http://127.0.0.1:11434`). Se usa si se configura un Ollama en servidor con auth. |
| `API_KEY` | Clave de la API REST protegida. | `""` (vacío) | Si está vacía, salta validación (modo dev). Si tiene valor, exige `X-API-Key` o query param `?api_key=`. 401 si incorrecta. La demo se envía al profesorado aparte. |

---

## 🤖 Proveedores RAG

### Interruptores de proveedor

| Variable | Valores válidos | Por defecto PB3 | Descripción |
|----------|-----------------|-----------------|-------------|
| `EMBED_PROVIDER` | `ollama`, `huggingface`, `google` | `google` | Proveedor para embeddings (offline + consulta). |
| `GEN_PROVIDER` | `ollama`, `huggingface`, `google` | `google` | Proveedor para generación de texto. |
| `TAG_PROVIDER` | `ollama`, `huggingface`, `google`, `` (hereda) | hereda de GEN | Proveedor para tagging/etiquetado. Si vacío, usa `GEN_PROVIDER`. |

### Modelos por proveedor

| Variable | ollama | huggingface | google |
|----------|--------|-------------|--------|
| **Embedding** | `OLLAMA_EMBED_MODEL` = `qwen3-embedding:0.6b` | `HF_EMBED_MODEL` = `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `GOOGLE_EMBED_MODEL` = `gemini-embedding-2` |
| **Generación** | `OLLAMA_GEN_MODEL` = `smtek/Qwen3.8-27B:Q2_K_XL-16gb` | `HF_GEN_MODEL` = `meta-llama/Llama-3.2-3B-Instruct` | `GOOGLE_GEN_MODEL` = `gemini-3.6-flash` |
| **Tagging** | `OLLAMA_TAG_MODEL` = `smtek/Qwen3.8-27B:Q2_K_XL-16gb` | `HF_TAG_MODEL` = `meta-llama/Llama-3.2-3B-Instruct` | `GOOGLE_TAG_MODEL` = `gemini-3.6-flash` |

### URLs y configuración

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Endpoint del servidor Ollama local o remoto. |
| `HF_DEVICE` | `cpu` | Dispositivo para modelos HuggingFace (`cpu`, `cuda`). |

---

## 🗄️ Base de datos y API REST (PB3)

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/deportes` | URL de PostgreSQL. Si está vacía, usa SQLite local (`rag_mlops.db`). El prefijo `postgres://` se normaliza a `postgresql://`. |
| `CORS_ORIGINS` | `*` | Orígenes permitidos para CORS (lista separada por comas). `*` = todos. Ej: `http://localhost:8501,https://mi-front.com`. |
| `ASK_TIMEOUT_SECONDS` | `300` | Timeout máximo de un turno en `/ask`. Si se supera -> 504 Gateway Timeout. En Render ~300s. |
| `RATE_LIMIT_PER_MINUTE` | `60` | Peticiones máximas por IP en ventana de 60 segundos. Si se supera -> 429 Too Many Requests. |

---

## 📦 RAG - Configuración general

### Supervisor y grafo

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `MAX_ITER` | `8` | Máximo número de iteraciones del supervisor/grafos. |
| `MAX_STEPS` | `5` | Pasos máximos en el grafo de supervisión. |
| `MAX_TURNS` | `20` | Turnos máximos por conversación (0 = ilimitado). |
| `SUPERVISOR_MODE` | `reglas` | Modo del supervisor: `reglas`, `llm`. |
| `HTTP_TIMEOUT` | `` | Timeout HTTP en segundos para llamadas externas. |

### Retrieval y chunking

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `RAG_RETRIEVAL_MODE` | `hibrido` | Modo de recuperación: `vectorial`, `hibrido`. |
| `TOP_K` | `5` | Número de chunks a recuperar. |
| `MAX_CHUNKS` | `5` | Máximo número de chunkes pasados al prompt. |
| `CHUNK_SIZE` | `1000` | Tamaño máximo de cada chunk en caracteres. |
| `CHUNK_OVERLAP` | `120` | Solapamiento entre chunks consecutivos. |

### Generación

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `GEN_TEMPERATURE` | `0.1` | Temperatura de generación (0 = determinista, 1 = creativa). |
| `GEN_MAX_TOKENS` | `1024` | Máximo número de tokens en la respuesta generada. |
| `GEN_TIMEOUT` | `140` | Timeout en segundos para llamadas de generación al LLM. |

### Embeddings

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `EMBED_DIM` | `384` | Dimensión del vector de embedding (puede variar según proveedor). |
| `EMBED_BATCH_SIZE` | `30` | Tamaño de lote para embeddings. |
| `EMBED_TIMEOUT` | `600` | Timeout en segundos para operaciones de embedding. |
| `EMBED_MAX_ATTEMPTS` | `8` | Reintentos máximos ante fallo de embedding. |
| `EMBED_RETRY_BASE_DELAY` | `5` | Delay base en segundos para backoff exponencial entre reintentos. |
| `EXPORT_EMBEDDINGS` | `true` | Exportar embeddings al terminar el pipeline. |
| `EMBED_CHECKPOINT_ENABLED` | `true` | Activar checkpoint de embeddings (persiste progreso). |
| `EMBED_DIM_MAX_OLLAMA` | `` / `1024` | Dimensión máxima para Ollama (dejar vacío = auto). |
| `EMBED_DIM_MAX_HF` | `` / `""` | Dimensión máxima para HuggingFace. |
| `EMBED_DIM_MAX_GOOGLE` | `` / `""` | Dimensión máxima para Google/Gemini. |

### TSD (Tagging + Scoring + Dedup)

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `TAG_SCORING_DEDUP` | `true` | Ejecutar scoring y deduplicación tras el tagging. |
| `TAG_MAX_TOKENS` | `1024` | Máximo de tokens en la salida del tagger. |
| `DEDUP_UMBRAL` | `0.93` | Umbral de similitud cosine para considerar dos chunks como duplicados. |
| `DEDUP_AUDIT` | `true` | Habilitar log de deduplicación. |
| `DEDUP_AUDIT_RUTA` | `output/dedup_audit.jsonl` | Ruta del archivo de audit de deduplicación. |

### ChromaDB (fallback local)

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `CHROMA_DIR` | `./output/chromadb` | Directorio del vector store local ChromaDB. |
| `COLLECTION_NAME` | `deporte_municipal` | Nombre de la colección en ChromaDB. |

### Question set y eval

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `QUESTION_SET` | `` / `true` | Conjunto de preguntas predefinidas para testing. |
| `MAX_QUESTIONS` | `1` | Máximo número de preguntas a evaluar. |
| `QUESTION_SET_RUTA` | `output/question_set.json` | Ruta del archivo de question set. |
| `EVAL_SET` | `true` | Activar conjunto de evaluación. |
| `EVAL_SET_N` | `50` | Número de muestras en el eval set. |
| `EVAL_SET_RUTA` | `queries/eval_set.jsonl` | Ruta del eval set. |

---

## 📄 Carga de documentos y OCR

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `IMAGE_OCR_ENABLED` | `true` | Habilitar OCR para imágenes en el pipeline. |
| `IMAGE_VISION_ENABLED` | `false` | Habilitar visión (Gemini) para análisis de imágenes. Requiere `GOOGLE_API_KEY`. |
| `IMAGE_VISION_MODEL` | hereda de `GEN_MODEL` | Modelo de visión independiente. Si vacío, usa el mismo que generación. |
| `IMAGE_OCR_LANG` | `spa+eng` | Idiomas del OCR (formato Tesseract: `spa`, `eng`, `spa+eng`). |
| `IMAGE_MAX_DESCRIPTION_CHARS` | `1200` | Máximo de caracteres en la descripción generada para imágenes. |
| `TESSERACT_CMD` | `` | Ruta al binario de Tesseract (si no está en PATH). |
| `POPPLER_PATH` | `` | Ruta a Poppler (para PDFs con texto embebido). |
| `OCR_LANG` | `spa` | Idioma del OCR para PDFs. |
| `OCR_DPI` | `200` | DPI de escaneo/OCR para imágenes y PDFs. |
| `OCR_PSM` | `6` | Page Segmentation Mode de Tesseract (`3`=full auto, `6`=uniform block). |

---

## 📁 Rutas y directorios

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `RAG_INDEX_DIR` | `{project}/data/index` | Directorio de índice del RAG. |
| `ASSETS_DIR` | `{project}/assets` | Directorio de assets (imágenes, documentos, etc.). |
| `EMBED_CHECKPOINT_FILE` | `{project}/output/embeddings_checkpoint.jsonl` | Archivo de checkpoint para embeddings. |

---

## 🔧 Log y depuración

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `LOG_LEVEL` | `INFO` | Nivel de log: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

---

## 🐍 Portable / Entorno

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `PYTHONUNBUFFERED` | `1` | Desactiva buffering de stdout/stderr (útil en Docker/Render). |
| `PYTHONDONTWRITEBYTECODE` | `1` | Evita crear archivos `.pyc` en disco. |

---

## 📌 Notas importantes

### Proveedor único PB3/MLOps (producción)
```
GEN_PROVIDER=google
EMBED_PROVIDER=google  
TAG_PROVIDER=google
GOOGLE_API_KEY=<tu-clave>
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/deportes
```

### Modo local offline (Ollama sin internet)
```
GEN_PROVIDER=ollama
EMBED_PROVIDER=ollama
TAG_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
DATABASE_URL=""  # usa SQLite local
```

### Variables que NUNCA se muestran en logs
- `API_KEY` - clave de la API REST.
- `GOOGLE_API_KEY` - clave de Gemini.
- `HF_TOKEN` - token de HuggingFace.
- `DATABASE_URL` - cadena de conexión (puede contener contraseña).
