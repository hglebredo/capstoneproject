"""RAG evaluation — métricas reutilizables para el RAG.

Este módulo extrae las funciones de cálculo de métricas del retrieval
de los scripts de herramientas (analyze_metrics.py, reporte_metricas.py)
para que puedan ser usadas tanto por los tests como por el pipeline online.

Funciones:
    - calcular_hit_at_k: Hit@K / Recall@K para un ranking dado.
    - calcular_mrr: Mean Reciprocal Rank.
    - calcular_ndcg_at_k: Normalized DCG@K.
    - calcular_distancia_media: Distancia coseno media de los chunks.
    - calcular_bm25_medio: BM25 score medio de los chunks.
    - calcular_rrf_medio: RRF score medio de los chunks.
    - calcular_latencia_percentiles: Percentiles p50/p95 de latencia.
    - calcular_abstenciones_correctas: % out-of-corpus con abstención correcta.
    - calcular_falsos_positivos: % out-of-corpus con respuesta no nula.
    - calcular_rank_de_fuente: Mejor posición (rank) de una fuente en el ranking.
"""

from __future__ import annotations

import math
from typing import Any


def normalizar(texto: str) -> str:
    """Normaliza un texto para comparación de fuentes: minúsculas y espacios."""
    return " ".join(str(texto).lower().split())


def rank_de_fuente(chunks: list[dict[str, Any]], fuente_esperada: str | None) -> int | None:
    """Devuelve el 1-based rank (posición en ranking) de la fuente esperada.

    Args:
        chunks: lista de chunks con 'source' en metadata o directamente como key.
        fuente_esperada: nombre de fuente a buscar; None devuelve None.

    Returns:
        Posición 1-based si se encuentra, None si no está.
    """
    if not fuente_esperada:
        return None
    esperada = normalizar(fuente_esperada)
    for i, chunk in enumerate(chunks, start=1):
        if esperada in normalizar(chunk.get("source", "")):
            return i
    return None


def calcular_hit_at_k(
    chunks: list[dict[str, Any]],
    fuente_esperada: str | None,
    k: int = 5,
) -> bool:
    """Comprueba si la fuente esperada está en los top-k resultados.

    Args:
        chunks: lista de chunks devueltos por el retrieval.
        fuente_esperada: nombre de fuente esperado.
        k: número máximo de posiciones a considerar (por defecto 5).

    Returns:
        True si la fuente aparece en los primeros k resultados.
    """
    if not fuente_esperada or not chunks:
        return False
    esperada = normalizar(fuente_esperada)
    for i, chunk in enumerate(chunks[:k], start=1):
        if esperada in normalizar(chunk.get("source", "")):
            return True
    return False


def calcular_mrr(
    chunks: list[dict[str, Any]],
    fuente_esperada: str | None,
) -> float:
    """Calcula el Reciprocal Rank de la fuente esperada.

    RR = 1 / rank si la fuente está en el ranking, 0 si no.

    Args:
        chunks: lista de chunks devueltos por el retrieval.
        fuente_esperada: nombre de fuente esperado.

    Returns:
        Reciprocal Rank (0.0 a 1.0).
    """
    rank = rank_de_fuente(chunks, fuente_esperada)
    if rank is None or rank == 0:
        return 0.0
    return 1.0 / rank


def calcular_ndcg_at_k(
    chunks: list[dict[str, Any]],
    fuente_esperada: str | None,
    k: int = 5,
) -> float:
    """Calcula nDCG@K para la fuente esperada.

    DCG = 1 / log2(rank + 1) si la fuente está en el ranking.
    IDCG = mejor caso posible (la fuente en posición 1).
    nDCG = DCG / IDCG.

    Args:
        chunks: lista de chunks devueltos por el retrieval.
        fuente_esperada: nombre de fuente esperado.
        k: límite superior para el cálculo.

    Returns:
        nDCG@K (0.0 a 1.0).
    """
    rank = rank_de_fuente(chunks, fuente_esperada)
    if rank is None or rank == 0:
        return 0.0

    # DCG: si la fuente está dentro de k posiciones
    dcg = 1.0 / math.log2(rank + 1) if rank <= k else 0.0

    # IDCG: mejor caso (fuente en posición 1)
    idcg = 1.0 / math.log2(2)  # siempre 1.0 cuando la fuente está en pos 1

    return dcg / idcg if idcg > 0 else 0.0


def calcular_distancia_media(chunks: list[dict[str, Any]]) -> float:
    """Calcula la distancia coseno media de los chunks devueltos.

    Args:
        chunks: lista de chunks con 'distance' en cada uno.

    Returns:
        Distancia coseno promedio (0.0 = idéntico, 2.0 = máximo).
    """
    if not chunks:
        return 1.0
    distances = [c.get("distance", 1.0) for c in chunks]
    return sum(distances) / len(distances)


def calcular_bm25_medio(chunks: list[dict[str, Any]]) -> float:
    """Calcula el BM25 score medio de los chunks que lo tienen.

    Args:
        chunks: lista de chunks con opcional 'bm25_score'.

    Returns:
        Score BM25 promedio (0.0 si no hay scores).
    """
    bm25_scores = [c.get("bm25_score") for c in chunks if "bm25_score" in c]
    if not bm25_scores:
        return 0.0
    return sum(bm25_scores) / len(bm25_scores)


def calcular_rrf_medio(chunks: list[dict[str, Any]]) -> float:
    """Calcula el RRF score medio de los chunks que lo tienen.

    Args:
        chunks: lista de chunks con opcional 'rrf_score' o 'score'.

    Returns:
        Score RRF promedio (0.0 si no hay scores).
    """
    rrf_scores = [c.get("rrf_score") or c.get("score", 0.0) for c in chunks]
    if not rrf_scores:
        return 0.0
    return sum(rrf_scores) / len(rrf_scores)


def calcular_latencia_percentiles(
    latencias_s: list[float],
) -> dict[str, float]:
    """Calcula percentiles p50 y p95 de latencia en milisegundos.

    Args:
        latencias_s: lista de latencias en segundos.

    Returns:
        Dict con 'p50' y 'p95' en milisegundos.
    """
    if not latencias_s:
        return {"p50": 0.0, "p95": 0.0}

    sorted_lats = sorted(latencias_s)
    n = len(sorted_lats)

    p50_idx = n // 2
    p95_idx = min(int(n * 0.95) - 1, n - 1)

    return {
        "p50": round(sorted_lats[p50_idx] * 1000, 3),
        "p95": round(sorted_lats[max(0, p95_idx)] * 1000, 3),
    }


def calcular_abstenciones_correctas(
    resultados: list[dict[str, Any]],
) -> float:
    """Calcula el % de preguntas out-of-corpus con abstención correcta.

    Una abstención es correcta si no hay chunks relevantes (rank_nulo para
    todas las fuentes).

    Args:
        resultados: lista de dicts con 'out_of_corpus' y ranks por método.

    Returns:
        Porcentaje de abstenciones correctas (0-100).
    """
    out_of = [r for r in resultados if r.get("out_of_corpus")]
    if not out_of:
        return 0.0

    correctas = sum(
        1
        for r in out_of
        if r.get("rank_coseno") is None
        and r.get("rank_bm25") is None
        and r.get("rank_rrf") is None
    )
    return round(correctas / len(out_of) * 100, 1)


def calcular_falsos_positivos(
    resultados: list[dict[str, Any]],
) -> float:
    """Calcula el % de preguntas out-of-corpus con respuesta no nula.

    Un falso positivo ocurre cuando una pregunta fuera del corpus devuelve
    chunks relevantes (al menos un rank no nulo).

    Args:
        resultados: lista de dicts con 'out_of_corpus' y ranks por método.

    Returns:
        Porcentaje de falsos positivos (0-100).
    """
    out_of = [r for r in resultados if r.get("out_of_corpus")]
    if not out_of:
        return 0.0

    falsos = sum(
        1
        for r in out_of
        if r.get("rank_coseno") is not None
        or r.get("rank_bm25") is not None
        or r.get("rank_rrf") is not None
    )
    return round(falsos / len(out_of) * 100, 1)


def calcular_rank_de_fuente(
    chunks: list[dict[str, Any]],
    fuente_esperada: str | None,
) -> int | None:
    """Alias de rank_de_fuente para compatibilidad con la API exportada.

    Args:
        chunks: lista de chunks devueltos por el retrieval.
        fuente_esperada: nombre de fuente esperado.

    Returns:
        Posición 1-based o None.
    """
    return rank_de_fuente(chunks, fuente_esperada)
