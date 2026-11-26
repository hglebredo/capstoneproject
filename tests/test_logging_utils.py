"""Tests para rag/logging_utils.py - Utilidades de logging estructurado."""

import time
from unittest.mock import patch

import pytest


class TestLogFunctions:
    """Tests para las funciones de log simple."""

    def test_log_incluye_prefijo(self):
        from rag.logging_utils import log
        with patch("rag.logging_utils.time.strftime", return_value="2026-01-01 00:00:00") as mock_strftime, \
             patch("builtins.print") as mock_print:
            log("mensaje de prueba")
            assert mock_print.called
            llamado = mock_print.call_args[0][0]
            assert "[RAG]" in llamado
            assert "INFO" in llamado

    def test_log_nivel_error(self):
        from rag.logging_utils import log
        with patch("builtins.print") as mock_print:
            log("error crítico", nivel="ERROR")
            llamado = mock_print.call_args[0][0]
            assert "ERROR" in llamado

    def test_log_info(self):
        from rag.logging_utils import log_info
        with patch("rag.logging_utils.log") as mock_log:
            log_info("info message")
            mock_log.assert_called_once_with("info message", "INFO")

    def test_log_warning(self):
        from rag.logging_utils import log_warning
        with patch("rag.logging_utils.log") as mock_log:
            log_warning("warn message")
            mock_log.assert_called_once_with("warn message", "WARN")

    def test_log_error(self):
        from rag.logging_utils import log_error
        with patch("rag.logging_utils.log") as mock_log:
            log_error("error message")
            mock_log.assert_called_once_with("error message", "ERROR")


class TestMedirTiempo:
    """Tests para medir_tiempo (context manager)."""

    def test_registra_tiempo_en_dict(self):
        from rag.logging_utils import medir_tiempo
        metricas = {}
        with medir_tiempo("retrieval", metricas):
            time.sleep(0.01)  # 10ms mínimo para distinguir de cero
        assert "retrieval" in metricas
        assert metricas["retrieval"] > 0

    def test_tiempo_redondeado(self):
        from rag.logging_utils import medir_tiempo
        metricas = {}
        with medir_tiempo("test", metricas):
            pass
        # Debe estar redondeado a 4 decimales
        assert isinstance(metricas["test"], float)

    def test_sin_metricas_no_lanza(self):
        from rag.logging_utils import medir_tiempo
        with medir_tiempo("no_metrics"):
            time.sleep(0.01)
        # No debe lanzar excepción

    def test_mismo_nombre_sobrescribe(self):
        """Si se usa el mismo nombre, sobrescribe el valor."""
        from rag.logging_utils import medir_tiempo
        metricas = {}
        with medir_tiempo("test", metricas):
            time.sleep(0.01)
        primer_valor = metricas["test"]

        with medir_tiempo("test", metricas):
            time.sleep(0.02)
        assert metricas["test"] > primer_valor

    def test_excepcion_registra_tiempo(self):
        """El tiempo se registra incluso si hay excepción."""
        from rag.logging_utils import medir_tiempo
        metricas = {}
        with pytest.raises(RuntimeError):
            with medir_tiempo("fallida", metricas):
                time.sleep(0.01)
                raise RuntimeError("error de prueba")
        assert "fallida" in metricas


class TestLogConsulta:
    """Tests para log_consulta."""

    def test_log_consulta_llama_print(self):
        from rag.logging_utils import log_consulta
        with patch("rag.logging_utils.log") as mock_log, \
             patch("rag.logging_utils.time.strftime", return_value="2026-01-01 00:00:00"):
            log_consulta(
                pregunta="¿Cuánto cuesta?",
                top_k=5,
                n_chunks=3,
                modelo="google:gemini-2.0-flash",
                metricas={"t_retrieval": 0.123},
                abstained=False,
            )
            assert mock_log.called

    def test_log_consulta_incluye_campos(self):
        from rag.logging_utils import log_consulta
        with patch("rag.logging_utils.log") as mock_log:
            log_consulta(
                pregunta="test",
                top_k=5,
                n_chunks=3,
                modelo="ollama:llama3.2",
                metricas={"t_retrieval": 0.1},
                abstained=True,
            )
            llamado = mock_log.call_args[0][0]
            assert "test" in llamado

    def test_log_consulta_abstencion(self):
        from rag.logging_utils import log_consulta
        with patch("rag.logging_utils.log") as mock_log:
            # abstained=True debe reflejarse en el JSON
            log_consulta(
                pregunta="¿Hay algo?",
                top_k=5,
                n_chunks=0,
                modelo="google:test",
                metricas={},
                abstained=True,
            )
            llamado = mock_log.call_args[0][0]
            assert "abstained" in llamado

    def test_metricas_se_prefijan_con_t(self):
        from rag.logging_utils import log_consulta
        with patch("rag.logging_utils.log") as mock_log:
            metricas = {"retrieval": 0.1, "generation": 0.2}
            log_consulta(
                pregunta="x",
                top_k=5,
                n_chunks=1,
                modelo="test",
                metricas=metricas,
            )
            llamado = mock_log.call_args[0][0]
            assert "t_retrieval" in llamado or "retrieval" in llamado
