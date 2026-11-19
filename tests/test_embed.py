"""Tests para rag/embed.py - Embeddings con múltiples proveedores."""

from unittest.mock import MagicMock, patch

import pytest


class TestEmbeddear:
    """Tests para la función embeddear()."""

    def test_dispatch_por_proveedor(self):
        from rag.embed import embeddear
        with patch("rag.embed.EMBED_PROVIDER", "ollama"), \
             patch("rag.embed._PROVIDERS") as mock_providers, \
             patch("rag.embed._corte_dim", side_effect=lambda v, c: v) as mock_corte:
            mock_fn = MagicMock(return_value=[[0.1] * 384])
            mock_providers.get.return_value = mock_fn

            resultado = embeddear(["texto"])
            assert len(resultado) == 1
            assert len(resultado[0]) == 384

    def test_dim_cap_restriccion(self):
        from rag.embed import embeddear
        with patch("rag.embed.EMBED_PROVIDER", "ollama"), \
             patch("rag.embed._PROVIDERS") as mock_providers, \
             patch("rag.embed._corte_dim") as mock_corte:
            mock_fn = MagicMock(return_value=[[0.1] * 512])

            resultado = embeddear(["texto"], dim=384)
            # _corte_dim debe llamarse con el cap
            assert mock_corte.called

    def test_provider_no_soportado_lanza(self):
        from rag.embed import embeddear
        with patch("rag.embed.EMBED_PROVIDER", "desconocido"), \
             patch("rag.embed._PROVIDERS", {}), \
             patch("rag.embed.EMBED_DIM", 384):
            with pytest.raises(ValueError, match="no soportado"):
                embeddear(["texto"])

    def test_devuelve_lista_de_listas(self):
        from rag.embed import embeddear
        with patch("rag.embed.EMBED_PROVIDER", "ollama"), \
             patch("rag.embed._PROVIDERS") as mock_providers, \
             patch("rag.embed._corte_dim"):
            mock_fn = MagicMock(return_value=[[0.1] * 384 for _ in range(5)])
            mock_providers.get.return_value = mock_fn

            resultado = embeddear(["t"] * 5)
            assert isinstance(resultado, list)
            assert all(isinstance(v, list) for v in resultado)


class TestEmbedConsulta:
    """Tests para embeddear_consulta."""

    def test_devuelve_vector_uno(self):
        from rag.embed import embeddear_consulta
        with patch("rag.embed.embeddear", return_value=[[0.1] * 384]) as mock_emb:
            resultado = embeddear_consulta("pregunta")
            assert isinstance(resultado, list)
            # Debe devolver el primer (y único) vector
            assert len(resultado) == 384


class TestNormalizarVectores:
    """Tests para _normalizar."""

    def test_normaliza_a_norma_1(self):
        from rag.embed import _normalizar
        vectores = [[3.0, 4.0], [1.0, 0.0]]  # norma=5 y norma=1
        resultado = _normalizar(vectores)
        for v in resultado:
            norma = (x * x for x in v)
            suma_norma = sum(norma) ** 0.5
            assert abs(suma_norma - 1.0) < 0.01

    def test_vacia_devuelve_vacia(self):
        from rag.embed import _normalizar
        assert _normalizar([]) == []

    def test_vector_cero_se_normaliza(self):
        """Un vector cero no debe generar división por cero."""
        from rag.embed import _normalizar
        resultado = _normalizar([[0.0, 0.0, 0.0]])
        assert len(resultado[0]) == 3


class TestCorteDim:
    """Tests para _corte_dim."""

    def test_corta_a_dim_cap(self):
        from rag.embed import _corte_dim
        vectores = [[1.0] * 512 for _ in range(3)]
        resultado = _corte_dim(vectores, dim_cap=384)
        assert all(len(v) == 384 for v in resultado)

    def test_no_op_si_dim_suficiente(self):
        from rag.embed import _corte_dim
        vectores = [[1.0] * 256 for _ in range(3)]
        resultado = _corte_dim(vectores, dim_cap=512)
        assert all(len(v) == 256 for v in resultado)

    def test_none_no_corta(self):
        from rag.embed import _corte_dim
        vectores = [[1.0] * 384]
        resultado = _corte_dim(vectores, dim_cap=None)
        assert len(resultado[0]) == 384


class TestExportarJson:
    """Tests para exportar_json."""

    def test_crea_archivo(self, tmp_path):
        from rag.embed import exportar_json
        chunks = [MagicMock(page_content="texto", metadata={"source": "test"})]
        ruta = str(tmp_path / "embeddings.json")
        exportar_json(chunks, ruta=ruta)
        assert (tmp_path / "embeddings.json").exists()

    def test_incluye_embedding_si_proveido(self, tmp_path):
        from rag.embed import exportar_json
        chunks = [MagicMock(page_content="texto", metadata={"source": "test"})]
        embeddings = [[0.1, 0.2, 0.3]]
        ruta = str(tmp_path / "embeddings.json")
        exportar_json(chunks, embeddings=embeddings, ruta=ruta)

        import json
        datos = json.loads((tmp_path / "embeddings.json").read_text())
        assert len(datos) == 1
        assert "embedding" in datos[0]


class TestCheckpoint:
    """Tests para el sistema de checkpoint."""

    def test_clave_checkpoint_determinista(self):
        from rag.embed import _clave_checkpoint
        k1 = _clave_checkpoint("texto", "ollama", None, 384)
        k2 = _clave_checkpoint("texto", "ollama", None, 384)
        assert k1 == k2

    def test_clave_depende_de_texto(self):
        from rag.embed import _clave_checkpoint
        k1 = _clave_checkpoint("texto A", "ollama", None, 384)
        k2 = _clave_checkpoint("texto B", "ollama", None, 384)
        assert k1 != k2

    def test_clave_depende_de_proveedor(self):
        from rag.embed import _clave_checkpoint
        k1 = _clave_checkpoint("texto", "ollama", None, 384)
        k2 = _clave_checkpoint("texto", "huggingface", None, 384)
        assert k1 != k2

    def test_clave_depende_de_dim(self):
        from rag.embed import _clave_checkpoint
        k1 = _clave_checkpoint("texto", "ollama", None, 384)
        k2 = _clave_checkpoint("texto", "ollama", None, 512)
        assert k1 != k2

    def test_cargar_checkpoint_vacia_ruta_inexistente(self):
        from rag.embed import _cargar_checkpoint
        resultado = _cargar_checkpoint("/no/existe/checkpoint.jsonl")
        assert isinstance(resultado, dict)
        assert len(resultado) == 0


class TestEmbedProvidersMap:
    """Tests para el mapa de proveedores."""

    def test_todos_proveedores_presentes(self):
        from rag.embed import _PROVIDERS
        assert "ollama" in _PROVIDERS
        assert "huggingface" in _PROVIDERS
        assert "google" in _PROVIDERS


class TestEmbedLogging:
    """Tests para utilidades de logging de embeddings."""

    def test_embed_log_every_defecto(self):
        from rag.embed import _EMBED_LOG_EVERY
        assert isinstance(_EMBED_LOG_EVERY, int)
        assert _EMBED_LOG_EVERY > 0


class TestPreflight:
    """Tests para la función verificar_modelo_disponible."""

    def test_devuelve_dict_con_claves(self):
        from rag.embed import verificar_modelo_disponible
        with patch("rag.embed.EMBED_PROVIDER", "ollama"), \
             patch("rag.embed.EMBED_MODEL", "test-model"):
            resultado = verificar_modelo_disponible()
            assert isinstance(resultado, dict)
            assert "disponible" in resultado
            assert "dim_modelo" in resultado
            assert "verificado_por" in resultado

    def test_disponible_true(self):
        from rag.embed import verificar_modelo_disponible
        with patch("rag.embed.EMBED_PROVIDER", "ollama"), \
             patch("rag.embed.EMBED_MODEL", "test-model"):
            resultado = verificar_modelo_disponible()
            assert resultado["disponible"] is True

    def test_aviso_cach_env(self):
        """Cuando no se puede verificar online, devuelve aviso."""
        from rag.embed import verificar_modelo_disponible
        # Forzar None en _pre_online para simular red cortada
        with patch("rag.embed._pre_online", return_value=None), \
             patch("rag.embed.EMBED_PROVIDER", "ollama"), \
             patch("rag.embed.EMBED_MODEL", "test-model"):
            resultado = verificar_modelo_disponible()
            assert resultado["verificado_por"] == "cache_env"
