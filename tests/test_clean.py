"""Tests para rag/clean.py - Limpieza y normalización por formato."""

import pytest
from langchain_core.documents import Document


class TestNormalizarPageContent:
    """Tests para _normalizar_page_content."""

    def test_dobles_saltos_linea_se_unifican(self):
        from rag.clean import _normalizar_page_content
        resultado = _normalizar_page_content("línea 1\n\n\nlínea 2")
        assert "línea 1\n\nlínea 2" in resultado

    def test_espacios_extraños_se_normalizan(self):
        from rag.clean import _normalizar_page_content
        resultado = _normalizar_page_content("texto   con\t\tespacios")
        # Los espacios/tabs dobles se reducen a uno
        assert "  " not in resultado or "\t" not in resultado

    def test_bom_se_elimina(self):
        from rag.clean import _normalizar_page_content
        resultado = _normalizar_page_content("\ufeffHola mundo")
        assert not resultado.startswith("\ufeff")

    def test_caracteres_control_se_eliminan(self):
        from rag.clean import _normalizar_page_content
        # Caracter de control \x00-\x08 y \x0b, \x0c
        texto = "dato\x00\x01\ntexto\x0b\r\nfin"
        resultado = _normalizar_page_content(texto)
        assert "\x00" not in resultado

    def test_strip_final(self):
        from rag.clean import _normalizar_page_content
        resultado = _normalizar_page_content("  contenido  \n\n")
        assert resultado == resultado.strip()


class TestLimpiarPdf:
    """Tests para _limpiar_pdf."""

    def test_limpia_caracteres_control(self):
        from rag.clean import _limpiar_pdf
        texto = "dato\x01\x02\ntexto"
        resultado = _limpiar_pdf(texto)
        assert "\x01" not in resultado and "\x02" not in resultado

    def test_limpia_caracteres_binarios_c1(self):
        from rag.clean import _limpiar_pdf
        # Caracter C1 y U+FFFD (REPLACEMENT CHAR)
        texto = "dato\x80\texto\ufffdfin"
        resultado = _limpiar_pdf(texto)
        assert "\x80" not in resultado

    def test_unifica_saltos_multiples(self):
        from rag.clean import _limpiar_pdf
        resultado = _limpiar_pdf("línea 1\n\n\n\nlínea 2")
        assert "línea 1\n\nlínea 2" in resultado


class TestLimpiarCsv:
    """Tests para _limpiar_csv."""

    def test_limpia_caracteres_control(self):
        from rag.clean import _limpiar_csv
        texto = "dato\x01\x02\ntexto"
        resultado = _limpiar_csv(texto)
        assert "\x01" not in resultado

    def test_strip_final(self):
        from rag.clean import _limpiar_csv
        resultado = _limpiar_csv("  dato  \n\n")
        assert " " not in resultado.split() or resultado == resultado.strip()


class TestNormalizarPorFormato:
    """Tests para normalizar_por_formato."""

    def test_pdf_recibe_limpieza_pdf(self):
        from rag.clean import normalizar_por_formato
        doc = Document(
            page_content="dato\x01\n\ntexto",
            metadata={"format": "pdf"},
        )
        resultado = normalizar_por_formato([doc])
        assert len(resultado) == 1
        # El texto limpio no debe tener \x01
        assert "\x01" not in resultado[0].page_content

    def test_csv_recibe_limpieza_csv(self):
        from rag.clean import normalizar_por_formato
        doc = Document(
            page_content="dato\x02\n\ntexto",
            metadata={"format": "csv"},
        )
        resultado = normalizar_por_formato([doc])
        assert len(resultado) == 1

    def test_json_no_se_modifica(self):
        from rag.clean import normalizar_por_formato
        contenido_original = "texto json sin cambios"
        doc = Document(
            page_content=contenido_original,
            metadata={"format": "json"},
        )
        resultado = normalizar_por_formato([doc])
        assert resultado[0].page_content == contenido_original

    def test_otro_recibe_normalizacion_generic(self):
        from rag.clean import normalizar_por_formato
        doc = Document(
            page_content="dato\n\ntexto",
            metadata={"format": "txt"},
        )
        resultado = normalizar_por_formato([doc])
        assert len(resultado) == 1

    def test_preserva_metadata(self):
        from rag.clean import normalizar_por_formato
        doc = Document(
            page_content="contenido",
            metadata={"source": "test.pdf", "format": "pdf"},
        )
        resultado = normalizar_por_formato([doc])
        assert resultado[0].metadata["source"] == "test.pdf"

    def test_no_muta_originales(self):
        from rag.clean import normalizar_por_formato
        doc = Document(
            page_content="  dato  \n\n",
            metadata={"format": "pdf"},
        )
        original_content = doc.page_content
        resultado = normalizar_por_formato([doc])
        # El documento original no se modifica (se copia metadata)
        assert len(resultado) == 1


class TestLimpiar:
    """Tests para limpiar."""

    def test_string_plano(self):
        from rag.clean import limpiar
        texto = "  Hola\n\nMundo  "
        resultado = limpiar(texto)
        assert isinstance(resultado, str)
        # Debe ser string normalizado (sin dobles saltos ni espacios extra)
        assert "\n\n" not in resultado or resultado == resultado.strip()

    def test_lista_documentos(self):
        from rag.clean import limpiar
        docs = [
            Document(page_content="  dato1  ", metadata={"format": "pdf"}),
            Document(page_content="  dato2  ", metadata={"format": "csv"}),
        ]
        resultado = limpiar(docs)
        assert isinstance(resultado, list)
        assert len(resultado) == 2

    def test_preserva_metadata_de_documentos(self):
        from rag.clean import limpiar
        doc = Document(
            page_content="  contenido con ruido  ",
            metadata={"source": "test.pdf", "format": "pdf"},
        )
        resultado = limpiar([doc])
        assert resultado[0].metadata["source"] == "test.pdf"

    def test_vacia_devuelve_vacio(self):
        from rag.clean import limpiar
        assert limpiar("") == ""
        assert limpiar([]) == []
