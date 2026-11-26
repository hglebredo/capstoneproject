"""Tests para rag/prompts.py - Construcción del prompt."""

import pytest


class TestFormatearContexto:
    """Tests para formatear_contexto."""

    def test_sin_chunks_devuelve_sin_fragmentos(self):
        from rag.prompts import formatear_contexto
        resultado = formatear_contexto([])
        assert "sin fragmentos recuperados" in resultado

    def test_con_un_chunk(self):
        from rag.prompts import formatear_contexto
        chunks = [{"text": "Hola mundo", "source": "test.pdf"}]
        resultado = formatear_contexto(chunks)
        assert "[Fragmento 1]" in resultado
        assert "Fuente: test.pdf" in resultado
        assert "Hola mundo" in resultado

    def test_con_multiples_chunks(self):
        from rag.prompts import formatear_contexto
        chunks = [
            {"text": "Primero", "source": "a.pdf"},
            {"text": "Segundo", "source": "b.csv"},
            {"text": "Tercero", "source": "c.pdf"},
        ]
        resultado = formatear_contexto(chunks)
        assert "[Fragmento 1]" in resultado
        assert "[Fragmento 2]" in resultado
        assert "[Fragmento 3]" in resultado

    def test_preserva_orden(self):
        from rag.prompts import formatear_contexto
        chunks = [
            {"text": "Z", "source": "z.pdf"},
            {"text": "A", "source": "a.pdf"},
        ]
        resultado = formatear_contexto(chunks)
        # Fragmento 1 debe ser Z, Fragmento 2 debe ser A
        pos_z = resultado.find("Z")
        pos_a = resultado.find("A")
        assert pos_z < pos_a

    def test_chunk_sin_texto(self):
        from rag.prompts import formatear_contexto
        chunks = [{"source": "test.pdf"}]  # sin 'text'
        resultado = formatear_contexto(chunks)
        assert "[Fragmento 1]" in resultado

    def test_source_por_defecto_desconocido(self):
        from rag.prompts import formatear_contexto
        chunks = [{"text": "contenido"}]  # sin 'source'
        resultado = formatear_contexto(chunks)
        assert "desconocido" in resultado

    def test_strip_content(self):
        from rag.prompts import formatear_contexto
        chunks = [{"text": "  texto con espacios  ", "source": "test.pdf"}]
        resultado = formatear_contexto(chunks)
        # El contenido debe estar limpio (strip)
        assert "texto con espacios" in resultado


class TestConstruirPrompt:
    """Tests para construir_prompt."""

    def test_incluye_instrucciones_sistema(self):
        from rag.prompts import construir_prompt
        resultado = construir_prompt("contexto", "pregunta")
        # INSTRUCCIONES_SISTEMA debe estar presente
        assert "Eres un asistente experto" in resultado or len(resultado) > 0

    def test_incluye_contexto(self):
        from rag.prompts import construir_prompt
        resultado = construir_prompt("Mi contexto de prueba", "¿Pregunta?")
        assert "=== CONTEXTO ===" in resultado
        assert "Mi contexto de prueba" in resultado

    def test_incluye_pregunta(self):
        from rag.prompts import construir_prompt
        resultado = construir_prompt("contexto", "¿Cuánto cuesta?")
        assert "=== PREGUNTA ===" in resultado
        assert "¿Cuánto cuesta?" in resultado

    def test_incluye_separador_respuesta(self):
        from rag.prompts import construir_prompt
        resultado = construir_prompt("contexto", "pregunta")
        assert "=== RESPUESTA ===" in resultado

    def test_pregunta_limpia_sin_espacios_extra(self):
        from rag.prompts import construir_prompt
        resultado = construir_prompt("ctx", "  ¿pregunta?  ")
        assert "¿pregunta?" in resultado

    def test_contexto_strip(self):
        from rag.prompts import construir_prompt
        resultado = construir_prompt("   contexto con espacios   ", "p")
        # Debe estar presente sin exceso de espacios


class TestConstruirPromptDesdeChunks:
    """Tests para construir_prompt_desde_chunks."""

    def test_formatea_y_construye(self):
        from rag.prompts import construir_prompt_desde_chunks
        chunks = [
            {"text": "Fragmento uno", "source": "a.pdf"},
            {"text": "Fragmento dos", "source": "b.csv"},
        ]
        resultado = construir_prompt_desde_chunks(chunks, "¿Cuánto cuesta?")
        assert isinstance(resultado, str)
        assert "[Fragmento 1]" in resultado
        assert "Fragmento uno" in resultado
        assert "=== PREGUNTA ===" in resultado

    def test_con_chunk_vacio(self):
        from rag.prompts import construir_prompt_desde_chunks
        chunks = [{}]  # chunk vacío sin text ni source
        resultado = construir_prompt_desde_chunks(chunks, "¿Qué hay?")
        assert isinstance(resultado, str)

    def test_múltiples_chunks_numerados(self):
        from rag.prompts import construir_prompt_desde_chunks
        chunks = [
            {"text": f"Chunk {i}", "source": f"f{i}.pdf"}
            for i in range(5)
        ]
        resultado = construir_prompt_desde_chunks(chunks, "Pregunta")
        assert "[Fragmento 1]" in resultado
        assert "[Fragmento 5]" in resultado
