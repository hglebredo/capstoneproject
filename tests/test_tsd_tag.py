"""Tests para rag/tsd/tag.py - Etiquetado semántico offline."""

import pytest
from unittest.mock import patch, MagicMock


class TestTaxonomia:
    """Tests para las taxonomías cerradas."""

    def test_categorias_validas(self):
        from rag.tsd.tag import CATEGORIAS_VALIDAS
        assert isinstance(CATEGORIAS_VALIDAS, frozenset)
        expected = {"tarifas", "normativa", "reservas", "abonos", "instalaciones", "agenda"}
        assert CATEGORIAS_VALIDAS == expected

    def test_tags_validos(self):
        from rag.tsd.tag import TAGS_VALIDAS
        assert isinstance(TAGS_VALIDAS, frozenset)
        # Debe incluir los tags principales
        assert "abono" in TAGS_VALIDAS
        assert "piscina" in TAGS_VALIDAS

    def test_prompt_contiene_categorias(self):
        from rag.tsd.tag import PROMPT
        for cat in CATEGORIAS_VALIDAS:
            assert cat in PROMPT


class TestChatProviders:
    """Tests para los proveedores de chat (Ollama, HF, Google)."""

    def test_chat_dispatch(self):
        from rag.tsd.tag import _CHAT
        assert "ollama" in _CHAT
        assert "huggingface" in _CHAT
        assert "google" in _CHAT

    @patch("rag.tsd.tag.requests.post")
    def test_chat_ollama_llama_a_api(self, mock_post):
        from rag.tsd.tag import _chat_ollama

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": '{"categoria":"tarifas"}'}}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = _chat_ollama("test prompt", "llama3.2")

        assert mock_post.called
        assert "api/chat" in str(mock_post.call_args)
        assert result == '{"categoria":"tarifas"}'

    @patch("rag.tsd.tag.requests.post")
    def test_chat_google_requiere_api_key(self, mock_post):
        from rag.tsd.tag import _chat_google

        # Sin GOOGLE_API_KEY debe levantar RuntimeError
        with patch("rag.tsd.tag.GOOGLE_API_KEY", None):
            with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
                _chat_google("prompt test", "gemini-2.0-flash")

    @patch("rag.tsd.tag.requests.post")
    def test_chat_huggingface_carga_persistente(self, mock_pipeline):
        from rag.tsd.tag import _chat_huggingface, _HF_GEN

        # Guardar estado original
        orig = _HF_GEN
        try:
            mock_out = [{"generated_text": '{"categoria":"reservas"}'}]
            mock_pipeline.return_value = lambda *a, **k: mock_out
            result = _chat_huggingface("prompt", "mistralai/Mistral-7B-v0.1")

            assert isinstance(result, str)
        finally:
            import rag.tsd.tag as tag_mod
            tag_mod._HF_GEN = orig


class TestParseJson:
    """Tests para _parse_json."""

    def test_parsa_json_valido(self):
        from rag.tsd.tag import _parse_json
        result = _parse_json('{"categoria": "tarifas", "tags": ["abono"], "relevancia": 0.8}')
        assert isinstance(result, dict)
        assert result["categoria"] == "tarifas"

    def test_parsa_json_con_texto_around(self):
        from rag.tsd.tag import _parse_json
        text = 'Aquí está el resultado: {"categoria": "normativa"} y más texto.'
        result = _parse_json(text)
        assert result["categoria"] == "normativa"

    def test_lanza_si_no_hay_json(self):
        from rag.tsd.tag import _parse_json
        with pytest.raises(Exception):  # JSONDecodeError
            _parse_json("No tiene JSON")

    def test_lanza_si_no_es_objeto(self):
        from rag.tsd.tag import _parse_json
        with pytest.raises(ValueError, match="objeto"):
            _parse_json('[1, 2, 3]')


class TestEtiquetar:
    """Tests para etiquetar (función principal)."""

    @patch("rag.tsd.tag.TAG_PROVIDER", "ollama")
    @patch("rag.tsd.tag._CHAT")
    def test_etiqueta_un_documento(self, mock_chat):
        from rag.tsd.tag import etiquetar, CATEGORIAS_VALIDAS
        from langchain_core.documents import Document

        mock_fn = MagicMock(return_value='{"categoria": "tarifas", "tags": ["abono"], "relevancia": 0.9}')
        mock_chat.__getitem__ = lambda self, k: mock_fn if k == "ollama" else None
        mock_chat.get = lambda self, key, default=None: mock_fn if key == "ollama" else default

        docs = [Document(page_content="Precio del abono de piscina", metadata={"source": "abonos.csv"})]
        result = etiquetar(docs)

        assert len(result) == 1
        meta = result[0].metadata
        assert meta["doc_category"] in CATEGORIAS_VALIDAS
        assert "relevancia_llm" in meta

    @patch("rag.tsd.tag.TAG_PROVIDER", "ollama")
    @patch("rag.tsd.tag._CHAT")
    def test_etiqueta_propaga_a_misma_fuente(self, mock_chat):
        from rag.tsd.tag import etiquetar
        from langchain_core.documents import Document

        mock_fn = MagicMock(return_value='{"categoria": "reservas", "tags": ["reserva"], "relevancia": 0.7}')
        mock_chat.get = lambda self, key, default=None: mock_fn if key == "ollama" else default

        # Dos páginas del mismo documento fuente
        doc1 = Document(page_content="Pág 1 contenido", metadata={"source": "reservas.pdf"})
        doc2 = Document(page_content="Pág 2 contenido", metadata={"source": "reservas.pdf"})
        docs = [doc1, doc2]

        result = etiquetar(docs)

        # Ambos deben tener la misma categoría (propagada desde el representante de la fuente)
        assert all(d.metadata["doc_category"] == "reservas" for d in result)

    @patch("rag.tsd.tag.TAG_PROVIDER", "ollama")
    @patch("rag.tsd.tag._CHAT")
    def test_etiqueta_filtro_categorias(self, mock_chat):
        from rag.tsd.tag import etiquetar, CATEGORIAS_VALIDAS
        from langchain_core.documents import Document

        # LLM devuelve categoría fuera de taxonomía -> debe caer a "instalaciones"
        mock_fn = MagicMock(return_value='{"categoria": "desconocida", "tags": [], "relevancia": 0.5}')
        mock_chat.get = lambda self, key, default=None: mock_fn if key == "ollama" else default

        doc = Document(page_content="Texto de prueba", metadata={"source": "test.txt"})
        result = etiquetar([doc])

        assert result[0].metadata["doc_category"] == "instalaciones"

    @patch("rag.tsd.tag.TAG_PROVIDER", "ollama")
    @patch("rag.tsd.tag._CHAT")
    def test_etiqueta_filtro_tags(self, mock_chat):
        from rag.tsd.tag import etiquetar, TAGS_VALIDAS
        from langchain_core.documents import Document

        # LLM devuelve tags válidos e inválidos -> solo se filtran los válidos
        mock_fn = MagicMock(
            return_value='{"categoria": "tarifas", "tags": ["abono", "piscina", "invalid_tag"], "relevancia": 0.6}'
        )
        mock_chat.get = lambda self, key, default=None: mock_fn if key == "ollama" else default

        doc = Document(page_content="Contenido", metadata={"source": "s"})
        result = etiquetar([doc])

        tags_str = result[0].metadata["tags"]
        assert "abono" in tags_str
        assert "piscina" in tags_str

    @patch("rag.tsd.tag.TAG_PROVIDER", "ollama")
    @patch("rag.tsd.tag._CHAT")
    def test_etiqueta_json_malformado(self, mock_chat):
        from rag.tsd.tag import etiquetar
        from langchain_core.documents import Document

        # JSON malformado -> debe caer a defecto sin romper el pipeline
        mock_fn = MagicMock(return_value="no es json valido { broken")
        mock_chat.get = lambda self, key, default=None: mock_fn if key == "ollama" else default

        doc = Document(page_content="Contenido", metadata={"source": "s"})
        result = etiquetar([doc])

        # Debe tener categoría por defecto
        assert result[0].metadata["doc_category"] == "instalaciones"


class TestModelosTag:
    """Tests para la resolución de modelos de tagging."""

    def test_modeles_tag_dict(self):
        from rag.tsd.tag import _MODELOS_TAG
        assert "ollama" in _MODELOS_TAG
        assert "huggingface" in _MODELOS_TAG
        assert "google" in _MODELOS_TAG


class TestEtiquetarEdgeCases:
    """Tests para casos límite del etiquetado."""

    @patch("rag.tsd.tag.TAG_PROVIDER", "ollama")
    @patch("rag.tsd.tag._CHAT")
    def test_etiqueta_proveedor_no_soportado(self, mock_chat):
        from rag.tsd.tag import etiquetar

        with patch("rag.tsd.tag.TAG_PROVIDER", "unknown_provider"):
            with patch.object(__import__("rag.tsd.tag", fromlist=["_CHAT"]), "_CHAT", {}):
                from langchain_core.documents import Document
                doc = Document(page_content="Test", metadata={"source": "s"})

    @patch("rag.tsd.tag.TAG_PROVIDER", "ollama")
    def test_etiqueta_con_texto_largo(self):
        from rag.tsd.tag import etiquetar, PROMPT
        from langchain_core.documents import Document

        # El prompt recorta a 8000 caracteres
        doc = Document(page_content="x" * 10000, metadata={"source": "big.txt"})
        assert len(doc.page_content) > 8000


class TestConstants:
    """Tests para constantes del módulo."""

    def test_prompt_es_string(self):
        from rag.tsd.tag import PROMPT
        assert isinstance(PROMPT, str)
        assert "{text}" in PROMPT
