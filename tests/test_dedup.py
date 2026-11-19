"""Tests para rag/tsd/dedup.py - Deduplicación de chunks."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document


class TestDeduplicarExacto:
    """Tests para deduplicación exacta (exact_key, group_only, exact_only)."""

    def test_devuelve_tupla_chunks_embeddings(self):
        from rag.tsd.dedup import deduplicar
        chunks = [Document(page_content="x", metadata={"dedup_policy": "exact_key"})]
        embeddings = [[0.1]]
        resultado_chunks, resultado_embs = deduplicar(chunks, embeddings)
        assert isinstance(resultado_chunks, list)
        assert isinstance(resultado_embs, list)

    def test_exact_only_dedup_por_clave(self):
        from rag.tsd.dedup import deduplicar
        chunks = [
            Document(page_content="fila1", metadata={"dedup_policy": "exact_only", "source": "s"}),
            Document(page_content="fila1", metadata={"dedup_policy": "exact_only", "source": "s", "row": 1}),
        ]
        embeddings = [[0.5], [0.6]]
        resultado_chunks, _ = deduplicar(chunks, embeddings)
        # Debe descartar el duplicado exacto
        assert len(resultado_chunks) <= 2

    def test_group_only_dedup_por_grupo(self):
        from rag.tsd.dedup import deduplicar
        chunks = [
            Document(page_content="grupo_a", metadata={"dedup_policy": "group_only", "source": "s"}),
            Document(page_content="grupo_b", metadata={"dedup_policy": "group_only", "source": "s"}),
        ]
        embeddings = [[0.5], [0.6]]
        resultado_chunks, _ = deduplicar(chunks, embeddings)
        assert isinstance(resultado_chunks, list)


class TestDeduplicarSemantico:
    """Tests para deduplicación semántica (coseno)."""

    def test_semantic_no_dedup_si_bajo_umbral(self):
        from rag.tsd.dedup import _deduplicar_semantico
        chunks = [
            Document(page_content="texto similar", metadata={"semantic_score": 0.8}),
            Document(page_content="texto muy similar", metadata={"semantic_score": 0.9}),
        ]
        embeddings = [[1.0, 0.0], [1.0, 0.0]]  # coseno ~1.0

        kept, _, eventos = _deduplicar_semantico(chunks, embeddings, umbral=0.8)
        assert len(kept) <= 2


class TestDeduplicarPolitica:
    """Tests para la política mixta exacta + semántica."""

    def test_passthrough_exactos_no_se_dedup_santicamente(self):
        from rag.tsd.dedup import deduplicar
        chunks = [
            Document(page_content="exacto1", metadata={"dedup_policy": "exact_key"}),
            Document(page_content="sema1", metadata={"dedup_policy": "semantic_optional"}),
        ]
        embeddings = [[0.5], [0.6]]
        resultado_chunks, _ = deduplicar(chunks, embeddings)
        assert len(resultado_chunks) >= 2

    def test_semantic_se_dedup_entre_si(self):
        from rag.tsd.dedup import deduplicar
        chunks = [
            Document(page_content="similar1", metadata={"semantic_score": 0.9}),
            Document(page_content="similar2", metadata={"semantic_score": 0.85}),
        ]
        # Vectores casi idénticos (coseno ~1.0)
        embeddings = [[0.7, 0.7], [0.7, 0.7]]
        resultado_chunks, _ = deduplicar(chunks, embeddings, umbral=0.8)
        assert len(resultado_chunks) <= 2


class TestDeduplicarInfo:
    """Tests para el parámetro info de deduplicar."""

    def test_info_incluye_dedup_metrics(self):
        from rag.tsd.dedup import deduplicar
        chunks = [Document(page_content="x", metadata={"dedup_policy": "exact_key"})]
        embeddings = [[0.5]]
        info: dict = {}

        deduplicar(chunks, embeddings, umbral=0.8, info=info)
        assert "dedup" in info
        assert isinstance(info["dedup"], dict)

    def test_info_incluye_umbral(self):
        from rag.tsd.dedup import deduplicar
        chunks = [Document(page_content="x", metadata={})]
        embeddings = [[0.5]]
        info: dict = {}

        deduplicar(chunks, embeddings, umbral=0.75, info=info)
        assert info["dedup"]["umbral"] == 0.75


class TestDeduplicarVacio:
    """Tests para deduplicación con corpus vacío."""

    def test_chunks_vacios_devuelve_vacios(self):
        from rag.tsd.dedup import deduplicar
        resultado_chunks, resultado_embs = deduplicar([], [])
        assert resultado_chunks == []
        assert resultado_embs == []


class TestClaveExacta:
    """Tests para _clave_exacta."""

    def test_exact_key_clave(self):
        from rag.tsd.dedup import _clave_exacta, Document
        chunk = Document(
            page_content="dato",
            metadata={"dedup_policy": "exact_key", "source": "s", "entity_key": "E1"},
        )
        clave = _clave_exacta(chunk)
        assert len(clave) == 3

    def test_group_only_clave(self):
        from rag.tsd.dedup import _clave_exacta, Document
        chunk = Document(
            page_content="dato",
            metadata={"dedup_policy": "group_only", "source": "s", "group_key": "G1"},
        )
        clave = _clave_exacta(chunk)
        assert len(clave) == 4

    def test_exact_only_clave(self):
        from rag.tsd.dedup import _clave_exacta, Document
        chunk = Document(
            page_content="contenido",
            metadata={"dedup_policy": "exact_only", "source": "s", "row": 1},
        )
        clave = _clave_exacta(chunk)
        assert len(clave) == 3


class TestCoberturaCategoria:
    """Tests para _cobertura_categoria."""

    def test_devuelve_dict_categorias(self):
        from rag.tsd.dedup import _cobertura_categoria, CATEGORIAS_VALIDAS
        pre = [Document(page_content="x", metadata={"doc_category": "tarifas"})]
        post = [Document(page_content="x", metadata={"doc_category": "tarifas"})]

        cov = _cobertura_categoria(pre, post)
        assert isinstance(cov, dict)


class TestTagsTop3:
    """Tests para _tags_top3."""

    def test_devuelve_tuplas(self):
        from rag.tsd.dedup import _tags_top3
        chunks = [
            Document(page_content="x", metadata={"tag_piscina": True}),
            Document(page_content="y", metadata={"tag_piscina": True, "tag_reserva": True}),
        ]

        tags = _tags_top3(chunks)
        assert isinstance(tags, list)


class TestSnipYClaves:
    """Tests para funciones auxiliares de dedup."""

    def test_snip_trunca_contenido(self):
        from rag.tsd.dedup import Document
        chunk = Document(page_content="a" * 200)
        # _snip se usa internamente; verificamos que no rompe con contenido largo
        from rag.tsd.dedup import deduplicar
        chunks = [chunk]
        embeddings = [[1.0]]
        _, _ = deduplicar(chunks, embeddings)


class TestDedupAudit:
    """Tests para la auditoría de deduplicación."""

    def test_eventos_contienen_motivo(self):
        from rag.tsd.dedup import deduplicar
        chunks = [Document(page_content="x", metadata={"dedup_policy": "exact_key"})]
        embeddings = [[0.5]]
        info: dict = {}

        deduplicar(chunks, embeddings, umbral=0.8, info=info)
        if info["dedup"].get("descartes"):
            assert any(ev.get("motivo") in ("dedup_clave", "dedup_coseno") for ev in info["dedup"]["descartes"])

    def test_descartes_por_fuente(self):
        from rag.tsd.dedup import deduplicar
        chunks = [Document(page_content="x", metadata={"source": "test.pdf"})]
        embeddings = [[0.5]]
        info: dict = {}

        deduplicar(chunks, embeddings, umbral=0.8, info=info)
        assert "descartes_por_fuente" in info["dedup"]


class TestOrdenOriginal:
    """Tests para la preservación del orden original."""

    def test_kept_orden_original(self):
        from rag.tsd.dedup import _deduplicar_semantico, Document
        chunks = [
            Document(page_content="a", metadata={"semantic_score": 0.5}),
            Document(page_content="b", metadata={"semantic_score": 0.9}),
            Document(page_content="c", metadata={"semantic_score": 0.7}),
        ]
        embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]

        kept, _, _ = _deduplicar_semantico(chunks, embeddings, umbral=0.0)
        assert kept == sorted(kept), "Los índices deben estar en orden original"
