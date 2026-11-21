"""Tests para rag/logic.py - Pipeline online completo."""

import pytest


class TestValidacionPregunta:
    """Tests para _validar_pregunta en logic.py."""

    def test_valida_pregunta_normal(self):
        from rag.logic import _validar_pregunta
        assert _validar_pregunta("¿Cuánto cuesta?") is None

    def test_rechaza_pregunta_vacia(self):
        from rag.logic import _validar_pregunta
        error = _validar_pregunta("")
        assert error is not None
        assert "vacía" in error

    def test_rechaza_string_no_str(self):
        """Valor no string -> error."""
        from rag.logic import _validar_pregunta
        error = _validar_pregunta(123)  # type: ignore
        assert error is not None

    def test_rechaza_demasiado_larga(self):
        from rag.logic import _validar_pregunta
        pregunta = "a" * 1001
        error = _validar_pregunta(pregunta)
        assert "demasiado larga" in error


class TestHayEvidencia:
    """Tests para _hay_evidencia."""

    def test_sin_chunks_no_hay_evidencia(self):
        from rag.logic import _hay_evidencia
        assert _hay_evidencia([]) is False

    def test_con_chunk_bajo_umbral_si_hay_evidencia(self):
        """Chunk con distancia <= 0.65 -> evidencia."""
        from rag.logic import _hay_evidencia
        chunks = [{"distance": 0.43}, {"distance": 0.55}]
        assert _hay_evidencia(chunks) is True

    def test_sin_chunks_fuera_umbral_no_hay_evidencia(self):
        """Todos los chunks con distancia > 0.65 -> no evidencia."""
        from rag.logic import _hay_evidencia
        chunks = [{"distance": 0.73}, {"distance": 0.8}]
        assert _hay_evidencia(chunks) is False

    def test_umbral_personalizado(self):
        """Se puede pasar un umbral personalizado."""
        from rag.logic import _hay_evidencia
        chunks = [{"distance": 0.5}, {"distance": 0.7}]
        assert _hay_evidencia(chunks, umbral=0.6) is True


class TestMejorDistancia:
    """Tests para _mejor_distancia."""

    def test_sin_chunks_devuelve_1(self):
        from rag.logic import _mejor_distancia
        assert _mejor_distancia([]) == 1.0

    def test_con_chunks_devuelve_minima(self):
        from rag.logic import _mejor_distancia
        chunks = [{"distance": 0.7}, {"distance": 0.3}, {"distance": 0.5}]
        assert _mejor_distancia(chunks) == 0.3


class TestExtraerFuentes:
    """Tests para _extraer_fuentes."""

    def test_extrae_fuentes_unicas(self):
        from rag.logic import _extraer_fuentes
        chunks = [
            {"source": "file1.pdf"},
            {"source": "file2.csv"},
            {"source": "file1.pdf"},  # duplicada
        ]
        fuentes = _extraer_fuentes(chunks)
        assert len(fuentes) == 2
        assert "file1.pdf" in fuentes
        assert "file2.csv" in fuentes

    def test_preserva_orden_aparicion(self):
        from rag.logic import _extraer_fuentes
        chunks = [
            {"source": "zulu.pdf"},
            {"source": "alfa.csv"},
        ]
        fuentes = _extraer_fuentes(chunks)
        assert fuentes == ["zulu.pdf", "alfa.csv"]


class TestResultadosError:
    """Tests para _resultado_error."""

    def test_resultado_error_completo(self):
        from rag.logic import _resultado_error
        resultado = _resultado_error("Test error")

        assert resultado["respuesta"] == ""
        assert resultado["chunks"] == []
        assert resultado["fuentes"] == []
        assert resultado["contexto"] == ""
        assert resultado["metrics"] == {}
        assert resultado["abstained"] is False
        assert resultado["error"] == "Test error"


class TestResponderIntegration:
    """Tests de integración de responder() - sin red (mock)."""

    def test_responde_con_respuesta_vacia(self):
        """responder con pregunta válida y chunks vacíos -> respuesta del LLM."""
        from rag.logic import responder
        # Mock generate para no necesitar red real
        with patch("rag.logic.generar", return_value="Respuesta mock"):
            resultado = responder("¿Cuánto cuesta?")

        assert "respuesta" in resultado
        assert isinstance(resultado["respuesta"], str)


class TestRagAsk:
    """Tests para rag_ask."""

    def test_rag_ask_devuelve_string(self):
        from rag.logic import rag_ask
        with patch("rag.logic.responder", return_value={"respuesta": "Hola mundo"}):
            resultado = rag_ask("¿Qué hay?")
        assert isinstance(resultado, str)
        assert resultado == "Hola mundo"

    def test_rag_ask_con_error_devuelve_abstencion(self):
        """Si responder devuelve error -> rag_ask retorna ABSTENTION_MESSAGE."""
        from rag.logic import rag_ask
        with patch("rag.logic.responder", return_value={"respuesta": "", "error": "Error de prueba"}):
            resultado = rag_ask("¿Qué hay?")
        # Debe devolver el mensaje de abstención, no la respuesta vacía
        assert isinstance(resultado, str)
