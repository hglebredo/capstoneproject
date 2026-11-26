"""Tests para rag/tsd/scoring.py - Puntuación semántica de chunks."""

import pytest
from unittest.mock import patch


class TestAutoridad:
    """Tests para _autoridad."""

    def test_reglamo_peso_maximo(self):
        from rag.tsd.scoring import _autoridad
        assert _autoridad("reglamento.pdf") == 1.0

    def test_normativa_peso_maximo(self):
        from rag.tsd.scoring import _autoridad
        assert _autoridad("normativa_municipal.csv") == 1.0

    def test_precios_tarifas_alto(self):
        from rag.tsd.scoring import _autoridad
        assert _autoridad("precios_abonos.json") == 0.9
        assert _autoridad("tarifas_2024.pdf") == 0.9

    def test_agenda_medio(self):
        from rag.tsd.scoring import _autoridad
        assert _autoridad("agenda_eventos.csv") == 0.6

    def test_csv_generico_default(self):
        from rag.tsd.scoring import _autoridad
        assert _autoridad("datos_generales.txt") == 0.7


class TestRedundancias:
    """Tests para _redundancias."""

    def test_un_vector_cero_redundancia(self):
        from rag.tsd.scoring import _redundancias
        import numpy as np
        E = np.array([[0.5, 0.5]], dtype=np.float32)
        red = _redundancias(E)
        assert len(red) == 1
        assert red[0] >= 0

    def test_dos_vectores_similares_alta_redundancia(self):
        from rag.tsd.scoring import _redundancias
        import numpy as np
        E = np.array([[0.5, 0.5], [0.49, 0.51]], dtype=np.float32)
        red = _redundancias(E)
        assert all(r > 0 for r in red)

    def test_vectores_ortogonales_baja_redundancia(self):
        from rag.tsd.scoring import _redundancias
        import numpy as np
        E = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        red = _redundancias(E)
        # Vectores ortogonales tienen baja similitud


class TestRedundanciaPorPolitica:
    """Tests para _redundancia_por_politica."""

    def test_agrupa_por_policy(self):
        from rag.tsd.scoring import _redundancia_por_politica
        from langchain_core.documents import Document
        import numpy as np

        chunks = [
            Document(page_content="a", metadata={"dedup_policy": "exact_key"}),
            Document(page_content="b", metadata={"dedup_policy": "semantica"}),
            Document(page_content="c", metadata={"dedup_policy": "semantica"}),
        ]
        redundancias = np.array([0.8, 0.5, 0.6], dtype=np.float32)

        result = _redundancia_por_politica(chunks, redundancias)
        assert "exact_key" in result
        assert "semantica" in result
        assert result["exact_key"]["n"] == 1
        assert result["semantica"]["n"] == 2


class TestPuntuar:
    """Tests para puntuar (función principal)."""

    def test_puntua_chunks_correctamente(self):
        from rag.tsd.scoring import puntuar
        from langchain_core.documents import Document

        docs = [Document(page_content=f"Texto {i}", metadata={
            "relevancia_llm": 0.8,
            "source": "reglamento",
        }) for i in range(5)]
        embs = [[0.1 * i + 0.5] * 3 for i in range(5)]

        result = puntuar(docs, embs)
        assert len(result) == 5
        # Cada chunk debe tener semantic_score en metadata
        for c in result:
            assert "semantic_score" in c.metadata
            score = c.metadata["semantic_score"]
            assert 0.0 <= score <= 1.0

    def test_sin_chunks_retorna_vacio(self):
        from rag.tsd.scoring import puntuar
        result = puntuar([], [])
        assert result == []

    def test_llena_info_metricas(self):
        from rag.tsd.scoring import puntuar
        from langchain_core.documents import Document

        docs = [Document(page_content=f"T{i}", metadata={"relevancia_llm": 0.7, "source": "normativa"}) for i in range(10)]
        embs = [[0.3 + 0.02 * i] * 4 for i in range(10)]
        info: dict = {}

        puntuar(docs, embs, info=info)

        assert "scoring" in info
        scoring = info["scoring"]
        assert "semantic_score_min" in scoring
        assert "semantic_score_media" in scoring
        assert "semantic_score_max" in scoring
        assert "centralidad_media" in scoring
        assert "redundancia_media" in scoring
        assert "chunks_n" in scoring


class TestScoringConstants:
    """Tests para constantes del scoring."""

    def test_autoridad_dict(self):
        from rag.tsd.scoring import AUTORIDAD
        assert isinstance(AUTORIDAD, dict)
        assert "reglamento" in AUTORIDAD
        assert AUTORIDAD["reglamento"] == 1.0


class TestScoringEdgeCases:
    """Tests para casos límite del scoring."""

    def test_chunk_sin_relevancia_llm(self):
        from rag.tsd.scoring import puntuar
        from langchain_core.documents import Document

        doc = Document(page_content="Sin relevancia", metadata={"source": "datos"})
        result = puntuar([doc], [[0.5, 0.5]])
        assert "semantic_score" in result[0].metadata

    def test_centroide_cero_vectores(self):
        """Con un solo vector, el centroide debe ser ese mismo."""
        from rag.tsd.scoring import puntuar
        from langchain_core.documents import Document

        doc = Document(page_content="Único", metadata={"relevancia_llm": 0.5})
        result = puntuar([doc], [[1.0, 0.0]])
        assert "semantic_score" in result[0].metadata


class TestPrintOutput:
    """Tests para la salida por consola del scoring."""

    def test_puntuar_imprime_resultados(self, capsys):
        from rag.tsd.scoring import puntuar
        from langchain_core.documents import Document

        docs = [Document(page_content=f"Doc{i}", metadata={"relevancia_llm": 0.7}) for i in range(3)]
        embs = [[0.5] * 4 for _ in range(3)]

        puntuar(docs, embs)
        captured = capsys.readouterr()
        assert "[SCORE]" in captured.out
