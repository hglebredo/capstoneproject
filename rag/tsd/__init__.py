"""tsd - Tagging, Scoring y Deduplicación del RAG.

Este paquete se ejecuta en la fase offline (indexación) sobre los chunks
generados después de CHUNK/EMBED:

    TAG     · Clasificación semántica con LLM (categoria + tags + relevancia)
              Proveedor interruptible: ollama | huggingface | google
    SCORING · Puntuación ponderada: 0.45·relevancia_LLM + 0.20·centralidad
              + 0.20·(1−redundancia) + 0.15·autoridad (FAISS, O(n·d))
    DEDUP   · Deduplicación por política: exact_key / group_only / semantic
              Los chunks con dedup_policy=exacta se dedup por clave; el resto
              pasa por coseno con umbral configurable (DEDUP_UMBRAL).

Dependencias del pipeline: TSD -> INDEX. El scoring y dedup requieren que
los embeddings ya estén calculados y normalizados.
"""