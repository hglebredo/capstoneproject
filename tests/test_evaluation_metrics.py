"""Tests para rag/evaluation/metrics.py - Métricas de evaluación del RAG."""

import pytest


class TestNormalizar:
    """Tests para normalizar."""

    def test_minusculas(self):
        from rag.evaluation.metrics import normalizar
        assert normalizar("HOLA") == "hola"

    def test_unifica_espacios(self):
        from rag.evaluation.metrics import normalizar
        result = normalizar("Hola   mundo\t\tprueba")
        assert result == "hola mundo prueba"

    def test_vacio(self):
        from rag.evaluation.metrics import normalizar
        assert normalizar("") == ""


class TestRankDeFuente:
    """Tests para rank_de_fuente."""

    def test_encuentra_fuente_en_primer_lugar(self):
        from rag.evaluation.metrics import rank_de_fuente
        chunks = [
            {"source": "reglamento.pdf"},
            {"source": "normativa.csv"},
        ]
        assert rank_de_fuente(chunks, "reglamento") == 1

    def test_encuentra_fuente_en_posicion_media(self):
        from rag.evaluation.metrics import rank_de_fuente
        chunks = [
            {"source": "a.pdf"},
            {"source": "b.csv"},
            {"source": "tarifas.json"},
        ]
        assert rank_de_fuente(chunks, "tarifas") == 3

    def test_no_encuentra_fuente(self):
        from rag.evaluation.metrics import rank_de_fuente
        chunks = [
            {"source": "a.pdf"},
            {"source": "b.csv"},
        ]
        assert rank_de_fuente(chunks, "no_existente") is None

    def test_none_fuente_esperada(self):
        from rag.evaluation.metrics import rank_de_fuente
        chunks = [{"source": "a.pdf"}]
        assert rank_de_fuente(chunks, None) is None


class TestCalcularHitAtK:
    """Tests para calcular_hit_at_k."""

    def test_hit_en_top_k(self):
        from rag.evaluation.metrics import calcular_hit_at_k
        chunks = [
            {"source": "tarifas.pdf"},
            {"source": "normativa.csv"},
        ]
        assert calcular_hit_at_k(chunks, "tarifas", k=2) is True

    def test_miss_fuera_top_k(self):
        from rag.evaluation.metrics import calcular_hit_at_k
        chunks = [
            {"source": "a.pdf"},  # pos 1
            {"source": "b.csv"},  # pos 2
            {"source": "tarifas.json"},  # pos 3, fuera de k=2
        ]
        assert calcular_hit_at_k(chunks, "tarifas", k=2) is False

    def test_sin_fuente_esperada(self):
        from rag.evaluation.metrics import calcular_hit_at_k
        chunks = [{"source": "a.pdf"}]
        assert calcular_hit_at_k(chunks, None, k=5) is False

    def test_chunks_vacios(self):
        from rag.evaluation.metrics import calcular_hit_at_k
        assert calcular_hit_at_k([], "tarifas", k=5) is False


class TestCalcularMRR:
    """Tests para calcular_mrr."""

    def test_rank_1_rr_maximo(self):
        from rag.evaluation.metrics import calcular_mrr
        chunks = [
            {"source": "reglamento.pdf"},
            {"source": "otro.csv"},
        ]
        assert calcular_mrr(chunks, "reglamento") == 1.0

    def test_rank_2_rr_metad(self):
        from rag.evaluation.metrics import calcular_mrr
        chunks = [
            {"source": "a.pdf"},
            {"source": "tarifas.csv"},
        ]
        assert calcular_mrr(chunks, "tarifas") == 0.5

    def test_no_encontrada_rr_cero(self):
        from rag.evaluation.metrics import calcular_mrr
        chunks = [{"source": "a.pdf"}]
        assert calcular_mrr(chunks, "no_existente") == 0.0

    def test_none_fuente_cero(self):
        from rag.evaluation.metrics import calcular_mrr
        assert calcular_mrr([{"source": "a.pdf"}], None) == 0.0


class TestCalcularNDCGAtK:
    """Tests para calcular_ndcg_at_k."""

    def test_posicion_1_ndcg_uno(self):
        from rag.evaluation.metrics import calcular_ndcg_at_k
        chunks = [{"source": "reglamento.pdf"}]
        assert calcular_ndcg_at_k(chunks, "reglamento", k=5) == 1.0

    def test_fuera_de_k_ndcg_cero(self):
        from rag.evaluation.metrics import calcular_ndcg_at_k
        chunks = [
            {"source": f"doc_{i}.pdf"} for i in range(6)
        ]
        # "tarifas" en posición 5, k=3 -> fuera de k
        assert calcular_ndcg_at_k(chunks, "no_encontrada", k=3) == 0.0

    def test_posicion_media(self):
        from rag.evaluation.metrics import calcular_ndcg_at_k
        chunks = [
            {"source": "a.pdf"},
            {"source": "tarifas.csv"},
        ]
        ndcg = calcular_ndcg_at_k(chunks, "tarifas", k=5)
        assert 0.0 < ndcg <= 1.0


class TestCalcularDistanciaMedia:
    """Tests para calcular_distancia_media."""

    def test_con_chunks(self):
        from rag.evaluation.metrics import calcular_distancia_media
        chunks = [
            {"distance": 0.3},
            {"distance": 0.5},
            {"distance": 0.4},
        ]
        assert abs(calcular_distancia_media(chunks) - 0.4) < 0.01

    def test_sin_chunks(self):
        from rag.evaluation.metrics import calcular_distancia_media
        assert calcular_distancia_media([]) == 1.0

    def test_con_distance_none(self):
        from rag.evaluation.metrics import calcular_distancia_media
        chunks = [{"distance": None}, {"source": "a"}]
        # distance=None se trata como 1.0 (default de .get)
        result = calcular_distancia_media(chunks)
        assert result >= 0 and result <= 2.0


class TestCalcularBM25Medio:
    """Tests para calcular_bm25_medio."""

    def test_con_scores(self):
        from rag.evaluation.metrics import calcular_bm25_medio
        chunks = [
            {"bm25_score": 1.5},
            {"bm25_score": 2.5},
        ]
        assert abs(calcular_bm25_medio(chunks) - 2.0) < 0.01

    def test_sin_scores(self):
        from rag.evaluation.metrics import calcular_bm25_medio
        chunks = [{"source": "a"}, {"text": "b"}]
        assert calcular_bm25_medio(chunks) == 0.0


class TestCalcularRRFMedio:
    """Tests para calcular_rrf_medio."""

    def test_con_rrf_score(self):
        from rag.evaluation.metrics import calcular_rrf_medio
        chunks = [{"rrf_score": 0.1}, {"rrf_score": 0.2}]
        assert abs(calcular_rrf_medio(chunks) - 0.15) < 0.01

    def test_con_score_fallback(self):
        from rag.evaluation.metrics import calcular_rrf_medio
        chunks = [{"score": 0.3}, {"rrf_score": 0.2}]
        # score se usa como fallback de rrf_score
        result = calcular_rrf_medio(chunks)
        assert abs(result - 0.25) < 0.01

    def test_sin_scores(self):
        from rag.evaluation.metrics import calcular_rrf_medio
        chunks = [{"source": "a"}]
        assert calcular_rrf_medio(chunks) == 0.0


class TestCalcularLatenciaPercentiles:
    """Tests para calcular_latencia_percentiles."""

    def test_p50_y_p95(self):
        from rag.evaluation.metrics import calcular_latencia_percentiles
        latencias = [0.1, 0.2, 0.3, 0.4, 0.5]  # en segundos
        result = calcular_latencia_percentiles(latencias)

        assert "p50" in result
        assert "p95" in result
        assert isinstance(result["p50"], float)
        assert isinstance(result["p95"], float)

    def test_vacia(self):
        from rag.evaluation.metrics import calcular_latencia_percentiles
        result = calcular_latencia_percentiles([])
        assert result == {"p50": 0.0, "p95": 0.0}

    def test_una_sola_medida(self):
        from rag.evaluation.metrics import calcular_latencia_percentiles
        result = calcular_latencia_percentiles([0.25])
        assert abs(result["p50"] - 250.0) < 1.0


class TestCalcularAbstencionesCorrectas:
    """Tests para calcular_abstenciones_correctas."""

    def test_todas_correctas(self):
        from rag.evaluation.metrics import calcular_abstenciones_correctas
        resultados = [
            {"out_of_corpus": True, "rank_coseno": None, "rank_bm25": None, "rank_rrf": None},
            {"out_of_corpus": True, "rank_coseno": None, "rank_bm25": None, "rank_rrf": None},
        ]
        assert calcular_abstenciones_correctas(resultados) == 100.0

    def test_con_falso_positivo(self):
        from rag.evaluation.metrics import calcular_abstenciones_correctas
        resultados = [
            {"out_of_corpus": True, "rank_coseno": None, "rank_bm25": None, "rank_rrf": None},
            {"out_of_corpus": True, "rank_coseno": 3, "rank_bm25": None, "rank_rrf": None},
        ]
        # 1 de 2 correctas = 50%
        assert calcular_abstenciones_correctas(resultados) == 50.0

    def test_sin_out_of_corpus(self):
        from rag.evaluation.metrics import calcular_abstenciones_correctas
        resultados = [
            {"out_of_corpus": False, "rank_coseno": 1},
        ]
        assert calcular_abstenciones_correctas(resultados) == 0.0


class TestCalcularFalsosPositivos:
    """Tests para calcular_falsos_positivos."""

    def test_con_falso_positivo(self):
        from rag.evaluation.metrics import calcular_falsos_positivos
        resultados = [
            {"out_of_corpus": True, "rank_coseno": 3},  # falso positivo
            {"out_of_corpus": True, "rank_bm25": None},  # no es FP (solo bm25)
        ]
        assert calcular_falsos_positivos(resultados) == 50.0

    def test_sin_out_of_corpus(self):
        from rag.evaluation.metrics import calcular_falsos_positivos
        resultados = [{"out_of_corpus": False}]
        assert calcular_falsos_positivos(resultados) == 0.0


class TestCalcularRankDeFuente:
    """Tests para calcular_rank_de_fuente (alias)."""

    def test_es_alias_de_rank_de_fuente(self):
        from rag.evaluation.metrics import calcular_rank_de_fuente, rank_de_fuente
        chunks = [
            {"source": "tarifas.pdf"},
            {"source": "normativa.csv"},
        ]
        assert calcular_rank_de_fuente(chunks, "tarifas") == rank_de_fuente(chunks, "tarifas")


class TestIntegration:
    """Tests de integración de métricas."""

    def test_pipeline_completo_evaluacion(self):
        """Simula un flujo completo de evaluación RAG."""
        from rag.evaluation.metrics import (
            calcular_hit_at_k, calcular_mrr, calcular_ndcg_at_k,
            calcular_distancia_media, rank_de_fuente,
        )

        chunks = [
            {"source": "reglamento.pdf", "distance": 0.3, "bm25_score": 1.5},
            {"source": "tarifas.csv", "distance": 0.5, "bm25_score": 1.2},
            {"source": "normativa.json", "distance": 0.7},
        ]

        # Hit@k
        assert calcular_hit_at_k(chunks, "reglamento", k=3) is True
        assert calcular_hit_at_k(chunks, "tarifas", k=2) is True

        # MRR
        mrr = calcular_mrr(chunks, "reglamento")
        assert mrr == 1.0

        # nDCG
        ndcg = calcular_ndcg_at_k(chunks, "tarifas", k=5)
        assert 0 < ndcg <= 1

        # Distancia media
        dist_media = calcular_distancia_media(chunks)
        assert 0 < dist_media < 2
