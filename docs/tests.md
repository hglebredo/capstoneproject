# Tests del Proyecto RAG / PB3/MLOps

## Resumen general

| Métrica | Valor |
|---------|-------|
| **Framework** | pytest (v9.1) con Python 3.14 |
| **Tests collectados** | ~491 tests en 28 archivos |
| **Estado actual** | Aproximadamente 80-85% de los tests pasan (`~370 passed`, `~65-70 failed`) |
| **Ubicación** | Carpeta `tests/` (raíz del proyecto) |

---

## Qué se prueba

Cada archivo de test cubre un módulo específico del RAG:

| Archivo | Módulo que prueba | Qué verifica |
|---------|------------------|---------------|
| `test_chunk.py` | `rag/chunk.py` | Troceado (`trocear()`), chunk_size, overlap, herencia metadata, bypass no_chunk |
| `test_clean.py` | Limpieza de texto | Normalizar page_content, limpiar PDF/CSV/CSV, normalización por formato |
| `test_config.py` | `rag/config.py` | Proveedores (ollama/huggingface/google), defaults de env vars, resolución de modelos |
| `test_csv_advisor.py` | Análisis CSV | Delimitador, tipo numérico, inferencia de fuente (`entity_table`, `fact_table`) |
| `test_csv_transform.py` | Transformación CSV a documentos | Limpieza de valores, filas a Document, tratamiento entity/group |
| `test_db_engine.py` | `rag/db/db_engine.py` | Conversaciones, mensajes, secuencia, persistencia SQLite/Postgres |
| `test_dedup.py` | Duplicados (exacto + semántico) | Deduplicación por contenido y similitud de embeddings, políticas exact_only/group_only |
| `test_embed.py` | Embeddings | Dispatch por proveedor, normalización de vectores, checkpoint, export JSON |
| `test_evaluation_metrics.py` | Métricas de evaluación | Hit@K, MRR, NDCG@K, BM25, RRF, latencia percentiles, abstenciones |
| `test_generate.py` | Generación (`rag/generate.py`) | Dispatch Google/Ollama/HF, retry, API key, temperatura |
| `test_index.py` | Indexación (ChromaDB) | Cliente Chroma, crear colección, sanear metadata, batch add |
| `test_informe.py` | Informes en Markdown | Tablas, fuentes, scoring TSD, integridad de datos |
| `test_load.py` | Carga de documentos | Formatos (PDF/CSV/TXT/MD), hash archivo, loaders map, manifiesto |
| `test_logging_utils.py` | Logging estructurado | Log con prefijo, medir tiempo, log consulta y métricas TSD |
| `test_logic.py` | Lógica principal (`rag/logic.py`) | Validar pregunta, hay evidencia, mejor distancia, responder/rag_ask integración |
| `test_models.py` | Modelos SQLAlchemy | Engine singleton, tablas (Conversation, Message), relaciones cascade |
| `test_pdf_tabular.py` | PDFs especiales y OCR | Extraer texto de tabla, parsear key-value, tesseract OCR |
| `test_pgvector.py` | PGVector (`rag/retrieval/pgvector_store.py`) | Creación del store, add + query, fallback a JSON |
| `test_pipeline.py` | Pipeline completo (`ejecutar_pipeline()`) | Fases (load→chunk→embed→index), params, métricas de salida |
| `test_prompts.py` | Construcción de prompts | Formatear contexto, construir prompt con sistema/usuario, múltiples chunks |
| `test_retrieve.py` | Recuperación (`rag/retrieval/`) | Tokenizar, RRF fusion, vector/BM25 retriever, recuperar hibrido |
| `test_schemas.py` | Schemas Pydantic (`schemas_mlops.py`) | AskIn, AskOut, ApproveIn, MessageOut, validación y serialización |
| `test_security.py` | Seguridad (`security.py`) | API key (header/query), rate limit 429, timeout 504, log_request |
| `test_tsd_dedup.py` | Deduplicación TSD | Clave exacta, dedup semántico, políticas, cobertura por categoría |
| `test_tsd_scoring.py` | Scoring TSD | Autoridad (reglamento/normativa), redundancia de vectores, puntuar chunks |
| `test_tsd_tag.py` | Tagging TSD | Taxonomía, chat providers, parse JSON, etiquetar con filtros |
| `test_vision.py` | Visión/OCR multimodal | MIME type, validar imagen, OCR imagen, descripción Gemini |

---

## Cómo ejecutar los tests

### 1. Ejecutar TODOS los tests (masivo)

```powershell
cd F:\SERIOUSLY\capstoneproject
python -m pytest tests/ --tb=short
```

Esto ejecuta los **~491 tests** de todos los archivos y muestra:
- Un punto `.` por cada test que pasa.
- Una `F` por cada test que falla.
- Al final, el resumen con total passed/failed.

#### Opciones útiles del comando masivo

| Comando | Qué hace |
|---------|----------|
| `python -m pytest tests/ --tb=short` | Todos los tests, tracebacks cortos (recomendado para revisión rápida) |
| `python -m pytest tests/ --tb=line` | Muestra solo la línea del error (más compacto) |
| `python -m pytest tests/ -v` | Verbose: muestra nombre de cada test + PASSED/FAILED en tiempo real |
| `python -m pytest tests/ -q` | Quiet: salida resumida con barra de progreso |
| `python -m pytest tests/ --tb=short -k "pipeline"` | Solo los tests que contienen "pipeline" en el nombre |

#### Entorno requerido para un resultado limpio

Antes de correr, asegurate de tener las variables de entorno configuradas:

```powershell
# Opción A: copiar .env a la raíz del proyecto (recomendado)
copy .env.rag.example .env
```

Algunas variables en `.env` pueden venir vacías (`MAX_TURNS=`, `HTTP_TIMEOUT=`). El código las lee con `os.getenv("X", "default")` pero si el `.env` las define como **cadena vacía** (`""`) en lugar de omitirlas, `int("")` falla. Si ves errores así:

```
ValueError: invalid literal for int() with base 10: ''
```

puedes corregirlo con:

```powershell
# Opción B: setear las vars críticas antes de ejecutar
$env:MAX_TURNS = "20"
$env:HTTP_TIMEOUT = "30"
python -m pytest tests/ --tb=short
```

---

### 2. Ejecutar un SOLO test (individual)

#### Por archivo completo

```powershell
# Solo los tests de chunking
python -m pytest tests/test_chunk.py -v

# Solo seguridad y API key
python -m pytest tests/test_security.py -v
```

#### Por nombre exacto del test (`-k`)

```powershell
# Un test específico por su nombre completo
python -m pytest tests/test_config.py::test_embed_provider_default_is_google -v

# Todos los que contengan "default" en el nombre
python -m pytest tests/ -k "default" -v

# Todos los que contengan "ollama" en cualquier archivo
python -m pytest tests/ -k "ollama" -v
```

#### Por clase de test

```powershell
# Todos los tests de la clase TestTrocear dentro de test_chunk.py
python -m pytest tests/test_chunk.py::TestTrocear -v

# Los tests de PydanticValidation en schemas
python -m pytest tests/test_schemas.py::TestPydanticValidation -v
```

#### Por ruta completa (path)

```powershell
# Un solo test con path completo y línea del fallo
python -m pytest tests/test_embed.py::TestNormalizarVectores::test_vacia_devuelve_vacia --tb=short -v
```

---

## Resultados esperados

### Escenario ideal (todo verde)

Al ejecutar `python -m pytest tests/ --tb=short` con el `.env` correcto, se espera:

- **~491 tests collectados** de 28 archivos.
- **370+ PASSED**, **65-70 FAILED**.
- Sin errores de configuración (sin `ValueError: invalid literal for int()`).
- El error de symlink en Windows (`PermissionError: [WinError 5]`) es post-run y no afecta el resultado.

### Archivos que deberían pasar todos (~31 tests)

Estos archivos son estables y se espera **0 fallos**:

| Archivo | Tests | Estado ideal |
|---------|-------|-------------|
| `test_clean.py` | 20/20 | Todo verde |
| `test_config.py` | 17/17 | Todo verde |
| `test_logging_utils.py` | 14/14 | Todo verde |
| `test_models.py` | 10/10 | Todo verde |
| `test_prompts.py` | 16/16 | Todo verde |
| `test_tsd_dedup.py` | 17/17 | Todo verde |
| `test_tsd_scoring.py` | 16/16 | Todo verde |

### Archivos con fallos conocidos (~30 tests)

Estos archivos tienen falgos recurrentes (generalmente por dependencias externas):

| Archivo | Fallos típicos | Causa principal |
|---------|---------------|-----------------|
| `test_generate.py` | 6-8 fallos | Variables de entorno vacías (`MAX_TURNS`, etc.) al importar módulos |
| `test_pgvector.py` | 3/3 fallos | Depende del mismo issue de env vars + conexión PGVector |
| `test_pipeline.py` | 7 fallos | Fases del pipeline, params y timing; requiere `.env` cargado |
| `test_vision.py` | 4 fallos | OCR imagen y descripción Gemini requieren tesseract/Gemini disponibles |
| `test_logic.py` | 3 fallos | Integración con responder/rag_ask (depende de providers) |
| `test_load.py` | 4 fallos | Normalizar source, hash file; sensible a rutas relativas |
| `test_embed.py` | 5 fallos | Embed results y normalización de vectores |
| `test_tsd_tag.py` | 8 fallos | Etiquetar con providers JSON, parse |

### Errores comunes y solución

| Error | Causa | Solución |
|-------|-------|----------|
| `ValueError: invalid literal for int() with base 10: ''` | `.env` tiene vars vacías (`MAX_TURNS=`, `HTTP_TIMEOUT=`) | Setear `$env:MAX_TURNS = "20"` o corregir el `.env` con valores por defecto |
| `PermissionError: [WinError 5] Acceso denegado` (symlink) | Cleanup de pytest en Windows no puede borrar symlink temporal | **No afecta** — es post-run, los tests ya pasaron |
| `Connection refused` / timeout | Ollama o Gemini no están disponibles | Los tests que fallan por esto suelen usar mocks; verificar si el fallo es real o solo del provider online |

---

## Flujo de trabajo recomendado

```powershell
# 1. Asegurar entorno limpio
cd F:\SERIOUSLY\capstoneproject
$env:MAX_TURNS = "20"
$env:HTTP_TIMEOUT = "30"

# 2. Ejecutar todos los tests (revisión rápida)
python -m pytest tests/ --tb=short

# 3. Si hay fallos, identificar cuáles
python -m pytest tests/ --tb=line | Select-String "FAILED"

# 4. Re-ejecutar solo los que fallaron
python -m pytest tests/ --tb=short -v --lf   # --lf = last failed first

# 5. Si necesitas debuggear un test específico
python -m pytest tests/test_chunk.py::TestTrocear::test_devuelve_lista_documentos -vv --tb=long
```

---

## Notas técnicas

- **pytest** se ejecuta desde la raíz del proyecto (`F:\SERIOUSLY\capstoneproject`). No necesita `conftest.py` a nivel de raíz, pero cada archivo puede tener sus propios fixtures.
- Los tests usan `unittest.mock.patch` y `patch.dict(os.environ)` para aislar el estado de las variables de entorno entre ejecuciones.
- La estructura sigue un patrón **clasico por grupos**: los tests se organizan en clases (`TestNombre`) que agrupan pruebas relacionadas, con métodos individuales (`test_descripcion`).
- Los mocks son preferidos sobre llamadas reales a APIs para mantener la velocidad (~10 segundos de ejecución total).
