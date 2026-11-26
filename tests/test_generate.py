"""Tests para rag/generate.py -Generación de texto con LLM."""

from unittest.mock import MagicMock, patch

import pytest


class TestGenerar:
    """Tests para la función generar()."""

    def test_dispatch_google(self):
        from rag.generate import generar
        with patch("rag.generate.GEN_PROVIDER", "google"), \
             patch("rag.generate._generar_google") as mock_gg:
            mock_gg.return_value = "Respuesta de Gemini"
            resultado = generar("prompt prueba")
            assert resultado == "Respuesta de Gemini"

    def test_dispatch_ollama(self):
        from rag.generate import generar
        with patch("rag.generate.GEN_PROVIDER", "ollama"), \
             patch("rag.generate._generar_ollama") as mock_go:
            mock_go.return_value = "Respuesta de Ollama"
            resultado = generar("prompt prueba")
            assert resultado == "Respuesta de Ollama"

    def test_dispatch_huggingface(self):
        from rag.generate import generar
        with patch("rag.generate.GEN_PROVIDER", "huggingface"), \
             patch("rag.generate._generar_huggingface") as mock_hf:
            mock_hf.return_value = "Respuesta de HF"
            resultado = generar("prompt prueba")
            assert resultado == "Respuesta de HF"

    def test_provider_override(self):
        from rag.generate import generar
        with patch("rag.generate._generar_ollama") as mock_go, \
             patch("rag.generate.GEN_PROVIDER", "google"):
            mock_go.return_value = "Override"
            resultado = generar("prompt", provider="ollama")
            assert resultado == "Override"

    def test_prompt_vacio_lanza_valorerror(self):
        from rag.generate import generar
        with patch("rag.generate.GEN_PROVIDER", "google"), \
             patch("rag.generate._generar_google"):
            with pytest.raises(ValueError, match="vacío"):
                generar("")

    def test_prompt_no_string_lanza(self):
        from rag.generate import generar
        with patch("rag.generate.GEN_PROVIDER", "google"), \
             patch("rag.generate._generar_google"):
            with pytest.raises(ValueError):
                generar(123)  # type: ignore

    def test_provider_desconocido_lanza(self):
        from rag.generate import generar
        with patch("rag.generate.GEN_PROVIDER", "desconocido"), \
             patch("rag.generate._PROVEEDORES", {}):
            with pytest.raises(ValueError, match="no soportado"):
                generar("prompt")

    def test_prompt_strip_antes_de_enviar(self):
        from rag.generate import generar
        with patch("rag.generate.GEN_PROVIDER", "google"), \
             patch("rag.generate._generar_google") as mock_gg:
            mock_gg.return_value = "x"
            generar("  prompt con espacios  ")
            # El provider recibe el strip
            args, _ = mock_gg.call_args
            assert args[0] == "prompt con espacios"


class TestGenerarGoogle:
    """Tests para _generar_google."""

    def test_llama_a_gemini(self):
        from rag.generate import _generar_google
        with patch("rag.generate.genai") as mock_genai, \
             patch("rag.generate.GOOGLE_API_KEY", "test-key"):
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = "Respuesta Gemini"
            mock_client.models.generate_content.return_value = mock_response

            resultado = _generar_google("prompt")
            assert resultado == "Respuesta Gemini"

    def test_respuesta_vacia_lanza(self):
        from rag.generate import _generar_google
        with patch("rag.generate.genai") as mock_genai, \
             patch("rag.generate.GOOGLE_API_KEY", "test-key"):
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = ""
            mock_client.models.generate_content.return_value = mock_response

            with pytest.raises(RuntimeError, match="respuesta vacía"):
                _generar_google("prompt")

    def test_sin_api_key_lanza(self):
        from rag.generate import _generar_google
        with patch.dict("rag.generate.os.environ", {"GOOGLE_API_KEY": ""}):
            # Forzar que GOOGLE_API_KEY sea None/vacío en el módulo
            with patch("rag.generate.GOOGLE_API_KEY", ""):
                with pytest.raises(RuntimeError, match="no está definida"):
                    _generar_google("prompt")

    def test_retry_en_transitorio(self):
        from rag.generate import _generar_google
        call_count = 0

        def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("503 Service Unavailable")
            resp = MagicMock()
            resp.text = "OK"
            return resp

        with patch("rag.generate.genai") as mock_genai, \
             patch("rag.generate.GOOGLE_API_KEY", "test-key"), \
             patch("time.sleep"):  # evitar sleeps en test
            client = MagicMock()
            mock_genai.Client.return_value = client
            client.models.generate_content.side_effect = mock_generate

            resultado = _generar_google("prompt")
            assert resultado == "OK"
            assert call_count == 3


class TestGenerarOllama:
    """Tests para _generar_ollama."""

    def test_post_a_api_chat(self):
        from rag.generate import _generar_ollama
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "Respuesta Ollama"}
        }
        mock_response.raise_for_status = MagicMock()

        with patch("rag.generate.requests.post", return_value=mock_response), \
             patch("rag.generate.OLLAMA_BASE_URL", "http://localhost:11434"):
            resultado = _generar_ollama("prompt")
            assert resultado == "Respuesta Ollama"

    def test_respuesta_vacia_lanza(self):
        from rag.generate import _generar_ollama
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": ""}}
        mock_response.raise_for_status = MagicMock()

        with patch("rag.generate.requests.post", return_value=mock_response), \
             patch("rag.generate.OLLAMA_BASE_URL", "http://localhost:11434"):
            with pytest.raises(RuntimeError, match="respuesta vacía"):
                _generar_ollama("prompt")

    def test_connection_error_retry(self):
        from rag.generate import _generar_ollama
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise requests.ConnectionError("connection failed")
            resp = MagicMock()
            resp.json.return_value = {"message": {"content": "OK"}}
            resp.raise_for_status = MagicMock()
            return resp

        import requests
        with patch("rag.generate.requests.post", side_effect=mock_post), \
             patch("rag.generate.OLLAMA_BASE_URL", "http://localhost:11434"), \
             patch("rag.generate.GEN_TIMEOUT", 5), \
             patch("time.sleep"):
            resultado = _generar_ollama("prompt")
            assert resultado == "OK"

    def test_error_no_transitorio_lanza(self):
        """NameError no es transitorio -> se levanta directamente."""
        from rag.generate import _generar_ollama

        def mock_post(*args, **kwargs):
            raise ValueError("error persistente")

        with patch("rag.generate.requests.post", side_effect=mock_post), \
             patch("rag.generate.OLLAMA_BASE_URL", "http://localhost:11434"), \
             patch("rag.generate.GEN_TIMEOUT", 5):
            with pytest.raises(ValueError, match="error persistente"):
                _generar_ollama("prompt")


class TestProveedoresMap:
    """Tests para el dispatch de proveedores."""

    def test_todos_proveedores_en_mapa(self):
        from rag.generate import _PROVEEDORES
        assert "ollama" in _PROVEEDORES
        assert "huggingface" in _PROVEEDORES
        assert "google" in _PROVEEDORES


class TestHfCache:
    """Tests para el caché de HuggingFace."""

    def test_hf_cache_existe(self):
        from rag.generate import _HF_GEN_CACHE
        assert isinstance(_HF_GEN_CACHE, dict)
