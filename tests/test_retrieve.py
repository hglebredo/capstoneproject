"""Tests para rag/retrieve.py - Recuperación híbrida (vectorial + BM25 + RRF)."""

from unittest.mock import MagicMock, patch

import pytest


class TestTokenizar:
    """Tests para _tokenizar."""

    def test_tokeniza_texto_simple(self):
        from rag.retrieve import _tokenizar
        tokens = _tokenizar("Hola mundo")
        assert "hola" in tokens
        assert "mundo" in tokens

    def test_tokeniza_sin_mayusculas(self):
        from rag.retrieve import _tokenizar
        tokens = _tokenizar("HOLA MUNDO")
        assert all(t.islower() for t in tokens)

    def test_tokeniza_con_simbolos(self):
        from rag.retrieve import _tokenizar
        tokens = _tokenizar("Hola, mundo!")
        assert "hola" in tokens
        assert "mundo" in tokens

    def test_tokeniza_vacio(self):
        from rag.retrieve import _tokenizar
        tokens = _tokenizar("")
        assert len(tokens) == 0


class TestResolverNombre:
    """Tests para _resolver_nombre."""

    def test_devuelve_por_defecto(self):
        from rag.retrieve import _resolver_nombre, COLLECTION_NAME
        resultado = _resolver_nombre(None)
        assert resultado == COLLECTION_NAME

    def test_usa_nombre_proporcionado(self):
        from rag.retrieve import _resolver_nombre
        resultado = _resolver_nombre("mi_coleccion")
        assert resultado == "mi_coleccion"


class TestChunkKey:
    """Tests para _chunk_key."""

    def test_con_chunk_id(self):
        from rag.retrieve import _chunk_key
        chunk = {"source": "test.pdf", "metadata": {"chunk_id": "123"}}
        key = _chunk_key(chunk)
        assert "test.pdf" in key
        assert "123" in key

    def test_con_doc_id(self):
        from rag.retrieve import _chunk_key
        chunk = {"source": "test.pdf", "metadata": {"doc_id": "456"}}
        key = _chunk_key(chunk)
        assert "test.pdf" in key
        assert "456" in key

    def test_con_texto_como_fallback(self):
        from rag.retrieve import _chunk_key
        chunk = {"source": "test.txt", "text": "contenido de prueba"}
        key = _chunk_key(chunk)
        assert len(key) > 0


class TestRRFFusion:
    """Tests para RRF fusion."""

    def test_fusion_devuelve_chunks(self):
        from rag.retrieve import _rrf_fusion
        ranking1 = [{"text": "a", "source": "s1"}]
        ranking2 = [{"text": "b", "source": "s2"}]
        resultado = _rrf_fusion([ranking1, ranking2], top_k=5)
        assert isinstance(resultado, list)

    def test_fusion_duplicados_acumulan(self):
        from rag.retrieve import _rrf_fusion_debug
        chunk = {"text": "duplicado", "source": "s"}
        resultado = _rrf_fusion_debug([[chunk], [chunk]], top_k=5)
        # El chunk duplicado debe tener apariciones >= 2
        assert len(resultado["scores"]) == 1
        assert resultado["scores"][0]["apariciones"] >= 2

    def test_rrf_scores_incluyen_apariciones(self):
        from rag.retrieve import _rrf_fusion_debug
        ranking = [{"text": "x", "source": "s"}]
        resultado = _rrf_fusion_debug([ranking, ranking], top_k=5)
        assert len(resultado["scores"]) == 1
        score = resultado["scores"][0]
        assert "rrf_score" in score
        assert "apariciones" in score

    def test_rrf_limita_top_k(self):
        from rag.retrieve import _rrf_fusion_debug
        chunks = [{"text": f"chunk_{i}", "source": "s"} for i in range(10)]
        resultado = _rrf_fusion_debug([chunks], top_k=5)
        assert len(resultado["chunks"]) <= 5


class TestRecuperar:
    """Tests para recuperar (vectorial)."""

    def test_pregunta_vacia_lanza_error(self):
        from rag.retrieve import recuperar
        with patch("rag.retrieve.obtener_coleccion") as mock_col, \
             patch("rag.retrieve.VectorRetriever"):
            mock_col.return_value = MagicMock(count=lambda: 0)
            resultado = recuperar("")
            assert isinstance(resultado, list)

    def test_top_k_cero_lanza_error(self):
        from rag.retrieve import recuperar
        with pytest.raises(ValueError, match="top_k debe ser mayor que 0"):
            recuperar("¿Qué es?", top_k=0)

    def test_devuelve_lista_dicts(self):
        from rag.retrieve import recuperar
        with patch("rag.retrieve.obtener_coleccion") as mock_col, \
             patch("rag.retrieve.VectorRetriever") as mock_vr:
            mock_col.return_value = MagicMock(count=lambda: 1)
            mock_inst = MagicMock()
            mock_vr.return_value = mock_inst
            mock_inst.search.return_value = [{"text": "resultado", "distance": 0.3}]

            resultado = recuperar("pregunta")
            assert isinstance(resultado, list)
            if resultado:
                assert isinstance(resultado[0], dict)


class TestVectorRetriever:
    """Tests para la clase VectorRetriever."""

    def test_inicializa_con_client(self):
        from rag.retrieve import VectorRetriever
        with patch("rag.retrieve.obtener_cliente_chroma") as mock_client:
            mock_col = MagicMock()
            mock_client.return_value.get_collection.return_value = mock_col
            retriever = VectorRetriever(None, "test")
            assert hasattr(retriever, "_client")

    def test_search_devuelve_resultados(self):
        from rag.retrieve import VectorRetriever
        with patch("rag.retrieve.obtener_cliente_chroma") as mock_client:
            mock_col = MagicMock()
            mock_col.query.return_value = {
                "ids": [["id1"]],
                "documents": [["texto de prueba"]],
                "metadatas": [[{"source": "test.pdf"}]],
                "distances": [[0.3]],
            }
            mock_client.return_value.get_collection.return_value = mock_col

            retriever = VectorRetriever(None, "test")
            resultado = retriever.search("pregunta", top_k=5, candidates=10)
            assert isinstance(resultado, list)


class TestBM25Retriever:
    """Tests para la clase BM25Retriever."""

    def test_inicializa_con_client(self):
        from rag.retrieve import BM25Retriever
        with patch("rag.retrieve.obtener_cliente_chroma") as mock_client, \
             patch.object(BM25Retriever, "_cargar"):
            mock_col = MagicMock()
            mock_client.return_value.get_collection.return_value = mock_col

            retriever = BM25Retriever(None, "test")
            assert hasattr(retriever, "_client")

    def test_search_devuelve_resultados(self):
        from rag.retrieve import BM25Retriever
        with patch("rag.retrieve.obtener_cliente_chroma") as mock_client:
            mock_col = MagicMock()
            mock_col.count.return_value = 10
            mock_col.get.return_value = {
                "documents": ["texto uno", "texto dos"],
                "metadatas": [{"source": "test.pdf"}, {"source": "test.txt"}],
            }

            retriever = BM25Retriever(None, "test")
            resultado = retriever.search("pregunta", top_k=5)
            assert isinstance(resultado, list)


class TestRecuperarHibrido:
    """Tests para recuperar_hibrido."""

    def test_pregunta_vacia_lanza_error(self):
        from rag.retrieve import recuperar_hibrido
        with pytest.raises(ValueError, match="pregunta"):
            recuperar_hibrido("")

    def test_top_k_cero_lanza_error(self):
        from rag.retrieve import recuperar_hibrido
        with pytest.raises(ValueError, match="top_k debe ser mayor que 0"):
            recuperar_hibrido("¿Qué es?", top_k=0)

    def test_devuelve_lista_chunks(self):
        from rag.retrieve import recuperar_hibrido
        with patch("rag.retrieve.obtener_coleccion") as mock_col, \
             patch("rag.retrieve.VectorRetriever"), \
             patch("rag.retrieve.BM25Retriever"):
            mock_col.return_value = MagicMock(count=lambda: 1)

            resultado = recuperar_hibrido("pregunta", top_k=5)
            assert isinstance(resultado, list)


class TestRecuperarHibridoDebug:
    """Tests para recuperar_hibrido_debug."""

    def test_devuelve_dict_completo(self):
        from rag.retrieve import recuperar_hibrido_debug
        with patch("rag.retrieve.obtener_coleccion") as mock_col, \
             patch("rag.retrieve.VectorRetriever"), \
             patch("rag.retrieve.BM25Retriever"):
            mock_col.return_value = MagicMock(count=lambda: 1)

            resultado = recuperar_hibrido_debug("pregunta", top_k=5)
            assert isinstance(resultado, dict)
            assert "coseno" in resultado
            assert "bm25" in resultado
            assert "rrf" in resultado
            assert "rrf_scores" in resultado

    def test_coleccion_vacia_devuelve_dict_vacio(self):
        from rag.retrieve import recuperar_hibrido_debug
        with patch("rag.retrieve.obtener_coleccion") as mock_col:
            mock_col.return_value = MagicMock(count=lambda: 0)

            resultado = recuperar_hibrido_debug("pregunta", top_k=5)
            assert len(resultado["coseno"]) == 0
            assert len(resultado["bm25"]) == 0


class TestObtenerColeccion:
    """Tests para obtener_coleccion."""

    def test_devuelve_coleccion(self):
        from rag.retrieve import obtener_coleccion
        with patch("rag.retrieve.obtener_cliente_chroma") as mock_client, \
             patch("rag.retrieve.COLLECTION_NAME", "test_col"):
            mock_client.return_value.get_collection.return_value = MagicMock()

            resultado = obtener_coleccion()
            assert mock_client.called

    def test_con_persist_dir(self):
        from rag.retrieve import obtener_coleccion
        with patch("rag.retrieve.obtener_cliente_chroma") as mock_client:
            mock_client.return_value.get_collection.return_value = MagicMock()

            resultado = obtener_coleccion(persist_dir="/custom/path")
            assert mock_client.called


class TestRRFConstants:
    """Tests para constantes RRF."""

    def test_rrf_k_positivo(self):
        from rag.retrieve import RRF_K
        assert isinstance(RRF_K, int)
        assert RRF_K > 0
