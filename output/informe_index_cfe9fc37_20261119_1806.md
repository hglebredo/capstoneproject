# Informe de indexación

- **Fecha:** 2026-11-19 18:06:49
- **Corpus (rutas):** .\data\corpus
- **Tiempo total:** 78.92 s

## 0. Resumen ejecutivo

| Indicador | Valor | Interpretación |
|---|---|---|
| Tiempo total de ejecución | 78.92 s | desde PREFLIGHT hasta INDEX + FIN |
| Documentos cargados / normalizados | 931 / 931 | 0 eliminados en CLEAN |
| Chunks pre → post dedup | 1130 → 1118 (12 descartados) | ratio: 1.1% |
| Vectores en índice | 1118 de dimensión 1024 | espacio: `cosine` (coseno) |
| Semantic score | mín 0.3211 / media 0.6506 / máx 0.7909 | 952 chunks ≥ 0.6 (84.2%) |
| Dedup umbral | 0.93 | 0 exactos, 12 semánticos |
| Integridad de vectores | 1118 vectores, NaN/Inf: 0, ceros: 0 | L2 mín 1.0000 / media 1.0000 / máx 1.0000 |

## 1. Parámetros aplicados

| Variable | Valor | Nota |
|---|---|---|
| `EMBED_PROVIDER` | ollama | proveedor de embeddings |
| `EMBED_MODEL` | qwen3-embedding:0.6b | modelo de embeddings |
| `EMBED_DIM_DECLARADO` | 1024 | tope declarado en .env |
| `EMBED_DIM_MODELO` | 1024 | dimensión máxima declarada (EMBED_DIM_MAX_*) |
| `EMBED_DIM` | 1024 | dimensión efectiva del índice (la de los vectores generados) |
| `EMBED_BATCH_SIZE` | 50 | tamaño de lote de embeddings |
| `TAG_PROVIDER` | ollama | proveedor del etiquetado LLM |
| `TAG_MODEL` | gemma4:12b | modelo del etiquetado LLM |
| `GEN_PROVIDER` | ollama | proveedor de generación |
| `GEN_MODEL` | gemma4:12b | modelo de generación |
| `OLLAMA_BASE_URL` | http://127.0.0.1:11434 | endpoint de Ollama |
| `CHUNK_SIZE` | 900 | longitud de chunk |
| `CHUNK_OVERLAP` | 120 | sobrelap de chunks |
| `TAG_SCORING_DEDUP` | True | bloque TSD activo |
| `DEDUP_UMBRAL` | 0.93 | umbral coseno de dedup |
| `CHROMA_DIR` | ./output/chromadb | directorio de ChromaDB |
| `COLLECTION_NAME` | deporte_municipal | colección de vectores |
| `COSINE_SPACE` | cosine | métrica de similitud |
| `recreate_index` | False | la colección se borró antes de indexar |
| `EXPORT_EMBEDDINGS` | True | exportación a output/embeddings.json |

## 2. Pipeline de datos (LOAD → CLEAN → CHUNK)

- **Dim máxima del modelo (`EMBED_DIM_MAX_*`):** 1024
- **Verificado por:** `online`
- **Aviso:** sin avisos

### 2.1 Carga de corpus (LOAD)

**Distribución por fuente:**

| Fuente | Docs | Chunks pre | Chunks post (dedup) | Densidad (chunks/doc) |
|---|---|---|---|---|
| 200186-0-polideportivos.csv | 82 | 82 | 82 | 1.0 |
| 200215-0-instalaciones-deportivas.csv | 607 | 607 | 607 | 1.0 |
| 210227-0-piscinas-publicas.csv | 56 | 56 | 56 | 1.0 |
| 300390-0-areas-deportivas.csv | 84 | 84 | 84 | 1.0 |
| BasesDeportesEquipo47jdm_1Sp.pdf | 30 | 75 | 75 | 2.5 |
| DecretoAnulacionReservasConCoste.pdf | 3 | 8 | 8 | 2.7 |
| PreciosPublicos2026.pdf | 3 | 3 | 3 | 1.0 |
| normativaGeneral46jdm.pdf | 41 | 130 | 118 | 3.2 |
| reglamento_instalaciones.pdf | 25 | 85 | 85 | 3.4 |
| **total** | 931 | 1130 | 1118 | — |

## 3. Tiempos por fase

| Fase | Resultado | Tiempo |
|---|---|---|
| PREFLIGHT | ok (modelo disponible) | 28.3 ms |
| LOAD | 931 documentos cargados | 1.57 s |
| CLEAN | 931 documentos normalizados | 40.3 ms |
| TAG | 9 fuentes etiquetadas (LLM) | 71.99 s |
| CHUNK | 1130 chunks generados (min 27, media 892.6) | 4.9 ms |
| EMBED | 1130 vectores de 1024 dims (pre-dedup 1130) | 4.31 s |
| TSD | scoring + dedup: 12 chunks descartados | 43.4 ms |
| INDEX | 1118 vectores insertados de 1146 totales | 931.9 ms |
| FIN | pipeline completado en 78.92 s | 78.92 s |

## 4. Corpus y chunking (longitudes en caracteres)

> **fuente** = archivo original · **documento** = salida de LOAD (página/fila/grupo) · **chunk** = salida de CHUNK (íntegro si entidad `no_chunk`).

| fuente | docs | chunks pre | chunks post (dedup) |
|---|---|---|---|
| 200186-0-polideportivos.csv | 82 | 82 | 82 |
| 200215-0-instalaciones-deportivas.csv | 607 | 607 | 607 |
| 210227-0-piscinas-publicas.csv | 56 | 56 | 56 |
| 300390-0-areas-deportivas.csv | 84 | 84 | 84 |
| BasesDeportesEquipo47jdm_1Sp.pdf | 30 | 75 | 75 |
| DecretoAnulacionReservasConCoste.pdf | 3 | 8 | 8 |
| PreciosPublicos2026.pdf | 3 | 3 | 3 |
| normativaGeneral46jdm.pdf | 41 | 130 | 118 |
| reglamento_instalaciones.pdf | 25 | 85 | 85 |
| **total** | 931 | 1130 | 1118 |

### 4.1 Estrategia de chunking

| Parámetro | Valor |
|---|---|
| Chunk size | 900 | longitud máxima por chunk |
| Chunk overlap | 120 | sobrelapamiento entre chunks consecutivos |
| Splitter usado | RecursiveCharacterTextSplitter | párrafo → frase → espacio → letra |

### 4.2 Distribución de longitudes de chunk (caracteres)

| Métrica | Valor | Nota |
|---|---|---|
| min | 27 | chunk más corto |
| p25 | 748.0 | 25 % de chunks ≤ este valor |
| media | 892.6 | longitud promedio |
| p50 (mediana) | 792.0 | valor central |
| p75 | 848.0 | 75 % de chunks ≤ este valor |
| max | 3397 | entidad íntegra (no_chunk) si > chunk_size |
| rango | 3370 | max − min |
| chunks cortos (< 50 chars) | 2 | ruido probable |
| íntegras (no_chunk) | 829 | entidades indexadas sin trocear |

### 4.3 Embeddings (EMBED)

| Métrica | Valor | Interpretación |
|---|---|---|
| Modelo de embedding | -  | proveedor: -  |
| Vectores generados | 1130 | pre-dedup |
| Dimensión efectiva | 1024 | (declarado: 1024, modelo: 1024) |

## 5. Índice final (ChromaDB)

- **Colección:** `deporte_municipal`
- **Vector space:** `cosine` (coseno)
- **Dim de embedding:** 1024
- **Vectores insertados:** 1118
- **Vectores totales en la colección:** 1146
- **Recreado (`--recreate-index`):** False
- **Integridad:** 1118 vectores · dim 1024 · NaN/Inf 0 · ceros 0 · norma L2 mín 1.0000 / media 1.0000 / máx 1.0000

## 6. TSD (scoring + dedup)

### 6.1 Scoring (`semantic_score`)

| Métrica | Valor | Interpretación |
|---|---|---|
| min | 0.3211 | score más bajo del corpus |
| media | 0.6506 | |
| máx | 0.7909 | score más alto del corpus |
| centralidad media | 0.6797 | coherencia con el centroide |
| redundancia media | 0.7793 | similitud con el vecino más cercano |
| chunks con score ≥ 0.6 | 952 de 1130 (84.25 %) | umbral interno de esta fase: NO es precisión ni relevancia frente a consultas |
| tiempo | 31.0 ms | fase SCORING |

> Definiciones de métricas (los vectores están normalizados: norma L2 = 1, métrica coseno):
> - `semantic_score = 0.45·relevancia_LLM + 0.20·centralidad + 0.20·(1 − redundancia) + 0.15·autoridad`, recortado a [0, 1]. > **Señal** interna de priorización del corpus, **no** una medida de calidad del chunk ni de relevancia frente a consultas.
> - `centralidad`: coseno del chunk contra el centroide de la colección (media de todos los vectores). Coherencia con el centro del corpus.
> - `redundancia`: coseno del chunk con su vecino más cercano (FAISS sobre los vectores normalizados; se excluye el propio). Alta redundancia media puede ser estructural (plantillas/CSVs de hechos) y no indicar corpus roto.
> - **Política exacta**: chunk cuya metadata `dedup_policy` es `exact_key`, `group_only` o `exact_only` (decidida por el asesor de CSVs); se deduplica **por clave** (nunca por coseno): la repetición literal se descarta, los semánticos cercanos no.

Redundancia (similitud con el vecino más cercano) por política de deduplicación (umbral `0.93`):

| política | n | media | p50 | p90 | % ≥ umbral |
|---|---|---|---|---|---|
| exact_key | 829 | 0.7943 | 0.7711 | 1.0 | 13.3 % |
| semantica | 301 | 0.7382 | 0.732 | 0.8436 | 4.7 % |

> La alta media de `group_only`/`exact_key` es estructural (plantillas y entidades de CSV): esas políticas se dedup por clave y nunca por coseno.

### 6.2 Dedup

| Métrica | Valor |
|---|---|
| umbral coseno (`DEDUP_UMBRAL`) | 0.93 |
| chunks pre | 1130 |
| chunks post | 1118 |
| descartados exactos | 0 |
| descartados semánticos | 12 |
| descartados total | 12 (1.1 %) |
| tiempo | 9.0 ms | fase DEDUP |

- **Auditoría de pares:** `output\dedup_audit.jsonl` (12 pares) -  muestrea la auditoría con `scripts/auditar_dedup.py`

**Descartes por fuente:**

| fuente | descartes |
|---|---|
| normativaGeneral46jdm.pdf | 12 |

### 6.3 Cobertura por categoría

| categoría | pre | post (dedup) |
|---|---|---|
| abonos | 0 | 0 |
| agenda | 205 | 193 |
| instalaciones | 829 | 829 |
| normativa | 85 | 85 |
| reservas | 8 | 8 |
| tarifas | 3 | 3 |
> **top 3 tags (post):** instalación (917) · accesibilidad (745) · temporada (196)
> La categoría es única por fuente (la intención dominante según TAG); los tags son multi-faces (un chunk puede llevar varios). Limitación de TAG: solo ve el primer documento de cada fuente (≤ 6000 caracteres), que decide categoría, tags y relevancia.

## 7. Métricas y criterios de decisión

### 7.1 Criterios de decisión (resumen)

| Criterio | Valor | Acción recomendada |
|---|---|---|
| Cobertura general | 1118 chunks cubiertos | Todas las categorías tienen contenido |
| Dedup ratio | 1.1% descartado | Bajo; corpus muy diverso o umbral alto |
| Integridad de vectores | 0 NaN/Inf (0.0%), 0 ceros | Vectores limpios para inferencia |
| Calidad del scoring | 84.25% chunks ≥ 0.6 | Corpus bien puntuado por el LLM |
| Chunks cortos (2) | < 50 caracteres | Ruido probable; revisar loaders o subir CHUNK_SIZE |
| Tiempo de ejecución | 78.92 s | Ejecución larga; considerar batching |


- **Chunking:** hay 2 chunks < 50 caracteres (ruido probable). Revisa los loaders o sube `CHUNK_SIZE`.
- **Cobertura:** la categoría abonos queda vacía post-dedup (ningún chunk en abonos (0 pre): el corpus no cubre esa intención): las preguntas de esa intención no podrán responderse con este índice. Añade corpus o revisa `DEDUP_UMBRAL`.
