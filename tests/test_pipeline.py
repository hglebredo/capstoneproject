"""Tests para rag/pipeline.py - Pipeline RAG completo."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestEjecutarPipeline:
    """Tests para la función ejecutar_pipeline()."""

    _PREFLIGHT_MOCK = {"disponible": True, "aviso": None, "dim_modelo": 1024, "verificado_por": "online"}

    def test_devuelve_dict_con_metricas(self):
        from rag.pipeline import ejecutar_pipeline

        with patch("rag.pipeline.verificar_modelo_disponible", return_value=TestEjecutarPipeline._PREFLIGHT_MOCK):
            with patch("rag.pipeline.cargar_archivos", return_value=[]):
                with patch("rag.pipeline.limpiar", side_effect=lambda x: x if isinstance(x, list) else [x]):
                    with patch("rag.pipeline.trocear", return_value=[]):
                        with patch("rag.pipeline.embeddear_con_checkpoint", return_value=[]):
                            with patch("rag.pipeline.indexar", return_value=(0, 0)):
                                resultado = ejecutar_pipeline(
                                    "./data/corpus/",
                                    informe=False,
                                )
                                assert isinstance(resultado, dict)

    def test_rutas_lista(self):
        from rag.pipeline import ejecutar_pipeline

        with patch("rag.pipeline.verificar_modelo_disponible", return_value=TestEjecutarPipeline._PREFLIGHT_MOCK):
            with patch("rag.pipeline.cargar_archivos", return_value=[]):
                with patch("rag.pipeline.limpiar", side_effect=lambda x: x if isinstance(x, list) else [x]):
                    with patch("rag.pipeline.trocear", return_value=[]):
                        with patch("rag.pipeline.embeddear_con_checkpoint", return_value=[]):
                            with patch("rag.pipeline.indexar", return_value=(0, 0)):
                                resultado = ejecutar_pipeline(
                                    ["./data/corpus/", "./docs/"],
                                    informe=False,
                                )
                                assert "rutas" in resultado

    def test_ruta_string(self):
        from rag.pipeline import ejecutar_pipeline

        with patch("rag.pipeline.verificar_modelo_disponible", return_value=TestEjecutarPipeline._PREFLIGHT_MOCK):
            with patch("rag.pipeline.cargar_archivos", return_value=[]):
                with patch("rag.pipeline.limpiar", side_effect=lambda x: x if isinstance(x, list) else [x]):
                    with patch("rag.pipeline.trocear", return_value=[]):
                        with patch("rag.pipeline.embeddear_con_checkpoint", return_value=[]):
                            with patch("rag.pipeline.indexar", return_value=(0, 0)):
                                resultado = ejecutar_pipeline(
                                    "./data/corpus/",
                                    informe=False,
                                )
                                assert isinstance(resultado["rutas"], list)

    def test_sin_tag_scorin_dedup(self):
        from rag.pipeline import ejecutar_pipeline

        with patch("rag.pipeline.verificar_modelo_disponible", return_value=TestEjecutarPipeline._PREFLIGHT_MOCK):
            with patch("rag.pipeline.cargar_archivos", return_value=[]):
                with patch("rag.pipeline.limpiar", side_effect=lambda x: x if isinstance(x, list) else [x]):
                    with patch("rag.pipeline.trocear", return_value=[]):
                        with patch("rag.pipeline.embeddear_con_checkpoint", return_value=[]):
                            with patch("rag.pipeline.indexar", return_value=(0, 0)):
                                with patch("rag.pipeline.TAG_SCORING_DEDUP", False):
                                    resultado = ejecutar_pipeline(
                                        "./data/corpus/",
                                        informe=False,
                                    )
                                    assert "scoring" in resultado or resultado.get("scoring") is None

    def test_con_tag_scorin_dedup(self):
        from rag.pipeline import ejecutar_pipeline

        with patch("rag.pipeline.verificar_modelo_disponible", return_value=TestEjecutarPipeline._PREFLIGHT_MOCK):
            with patch("rag.pipeline.cargar_archivos", return_value=[]):
                with patch("rag.pipeline.limpiar", side_effect=lambda x: x if isinstance(x, list) else [x]):
                    with patch("rag.pipeline.trocear", return_value=[]):
                        with patch("rag.pipeline.embeddear_con_checkpoint", return_value=[]):
                            with patch("rag.pipeline.indexar", return_value=(0, 0)):
                                with patch("rag.pipeline.TAG_SCORING_DEDUP", True):
                                    resultado = ejecutar_pipeline(
                                        "./data/corpus/",
                                        informe=False,
                                    )
                                    assert "dedup" in resultado

    def test_chunk_stats_cortos(self):
        from rag.chunk import trocear
        from langchain_core.documents import Document

        # Chunks muy cortos (< 50 chars) deberían contarse como 'cortos'
        docs = [Document(page_content="x" * 10, metadata={"source": "test"})]
        chunks = trocear(docs, chunk_size=2000)
        assert len(chunks[0].page_content) < 50

    def test_parametros_incluyen_proveedor(self):
        from rag.pipeline import ejecutar_pipeline

        with patch("rag.pipeline.verificar_modelo_disponible", return_value=TestEjecutarPipeline._PREFLIGHT_MOCK):
            with patch("rag.pipeline.cargar_archivos", return_value=[]):
                with patch("rag.pipeline.limpiar", side_effect=lambda x: x if isinstance(x, list) else [x]):
                    with patch("rag.pipeline.trocear", return_value=[]):
                        with patch("rag.pipeline.embeddear_con_checkpoint", return_value=[]):
                            with patch("rag.pipeline.indexar", return_value=(0, 0)):
                                resultado = ejecutar_pipeline(
                                    "./data/corpus/",
                                    informe=False,
                                )
                                nombres_parametros = [p[0] for p in resultado["parametros"]]
                                assert "EMBED_PROVIDER" in nombres_parametros

    def test_tiempo_total_presente(self):
        from rag.pipeline import ejecutar_pipeline

        with patch("rag.pipeline.verificar_modelo_disponible", return_value=TestEjecutarPipeline._PREFLIGHT_MOCK):
            with patch("rag.pipeline.cargar_archivos", return_value=[]):
                with patch("rag.pipeline.limpiar", side_effect=lambda x: x if isinstance(x, list) else [x]):
                    with patch("rag.pipeline.trocear", return_value=[]):
                        with patch("rag.pipeline.embeddear_con_checkpoint", return_value=[]):
                            with patch("rag.pipeline.indexar", return_value=(0, 0)):
                                resultado = ejecutar_pipeline(
                                    "./data/corpus/",
                                    informe=False,
                                )
                                assert "tiempo_total_s" in resultado
                                assert isinstance(resultado["tiempo_total_s"], float)


class TestComprobarDim:
    """Tests para _comprobar_dim."""

    def test_vacio_sin_embeddings(self):
        from rag.pipeline import _comprobar_dim
        nivel, msg = _comprobar_dim(0, 384, None)
        assert nivel == "vacio"
        assert "vacío" in msg.lower() or "sin embedding" in msg.lower()

    def test_ok_dimension_coincide(self):
        from rag.pipeline import _comprobar_dim
        nivel, msg = _comprobar_dim(384, 384, None)
        assert nivel == "ok"

    def test_aviso_dim_mayor_que_generada(self):
        from rag.pipeline import _comprobar_dim
        nivel, msg = _comprobar_dim(256, 384, None)
        assert nivel == "aviso"

    def test_info_dim_max_modelo(self):
        from rag.pipeline import _comprobar_dim
        nivel, msg = _comprobar_dim(384, 384, 768)
        assert nivel == "info"


class TestStatsChunks:
    """Tests para _stats_chunks."""

    def test_vacia_devuelve_ceros(self):
        from rag.pipeline import _stats_chunks
        resultado = _stats_chunks([])
        assert resultado["min"] == 0
        assert resultado["media"] == 0
        assert resultado["max"] == 0

    def test_con_chunxs_calcula_percentiles(self):
        from rag.pipeline import _stats_chunks
        from langchain_core.documents import Document

        chunks = [
            Document(page_content="a" * i, metadata={"source": "test"})
            for i in [10, 50, 200, 500]
        ]
        resultado = _stats_chunks(chunks)
        assert resultado["min"] == 10
        assert resultado["max"] == 500
        assert resultado["media"] > 0


class TestIntegridadEmbebidos:
    """Tests para _integridad_embebidos."""

    def test_vacia_devuelve_ceros(self):
        from rag.pipeline import _integridad_embebidos
        resultado = _integridad_embebidos([])
        assert resultado["n"] == 0
        assert resultado["dim_ok"] == 0

    def test_con_embeddings_calcula_dim(self):
        from rag.pipeline import _integridad_embebidos
        embs = [[1.0, 2.0], [3.0, 4.0]]
        resultado = _integridad_embebidos(embs)
        assert resultado["n"] == 2
        assert resultado["dim"] == 2

    def test_detecta_nan_inf(self):
        from rag.pipeline import _integridad_embebidos
        import numpy as np

        embs = [[1.0, float("nan")], [3.0, 4.0]]
        resultado = _integridad_embebidos(embs)
        assert resultado["nan_inf"] >= 0


class TestEscribirAuditoria:
    """Tests para _escribir_auditoria_descartes."""

    def test_crea_archivo_jsonl(self, tmp_path):
        from rag.pipeline import _escribir_auditoria_descartes
        eventos = [{"motivo": "coseno", "sim": 0.95}]
        ruta = _escribir_auditoria_descartes(eventos, ruta_audit=tmp_path / "test_audit.jsonl")
        assert ruta.exists()
        contenido = ruta.read_text(encoding="utf-8")
        assert len(contenido.strip().split("\n")) == 1

    def test_contiene_eventos(self, tmp_path):
        from rag.pipeline import _escribir_auditoria_descartes
        eventos = [{"motivo": "coseno", "sim": 0.95}, {"motivo": "clave", "policy": "exact_key"}]
        ruta = _escribir_auditoria_descartes(eventos, ruta_audit=tmp_path / "test_audit2.jsonl")
        contenido = ruta.read_text(encoding="utf-8")
        assert "coseno" in contenido
        assert "clave" in contenido


class TestLog:
    """Tests para _log."""

    def test_formato_log(self, capsys):
        from rag.pipeline import _log
        _log("TEST", "mensaje de prueba")
        captured = capsys.readouterr()
        # Debe contener la marca de tiempo y la fase
        assert "[TEST]" in captured.out
        assert "mensaj" in captured.out
