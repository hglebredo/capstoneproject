"""Rag evaluation — métricas reutilizables para el RAG.

Este módulo extrae las funciones de cálculo de métricas del retrieval
de los scripts de herramientas (analyze_metrics.py, reporte_metricas.py)
para que puedan ser usadas tanto por los tests como por el pipeline online.
"""

from .metrics import (
    calcular_hit_at_k,
    calcular_mrr,
    calcular_ndcg_at_k,
    calcular_distancia_media,
    calcular_bm25_medio,
    calcular_rrf_medio,
    calcular_latencia_percentiles,
    calcular_abstenciones_correctas,
    calcular_falsos_positivos,
    calcular_rank_de_fuente,
)

__all__ = [
    "calcular_hit_at_k",
    "calcular_mrr",
    "calcular_ndcg_at_k",
    "calcular_distancia_media",
    "calcular_bm25_medio",
    "calcular_rrf_medio",
    "calcular_latencia_percentiles",
    "calcular_abstenciones_correctas",
    "calcular_falsos_positivos",
    "calcular_rank_de_fuente",
]
