"""Tests para rag/pdf_tabular.py - Procesamiento de PDFs tabulares y OCR."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestExtraerTextoTabla:
    """Tests para _extraer_texto_tabla_a_textos."""

    def test_devuelve_lista_strings(self):
        from rag.pdf_tabular import _extraer_texto_tabla_a_textos
        with patch("rag.pdf_tabular.pdfplumber") as mock_pdfplumber:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_tables.return_value = [
                [["Col1", "Col2"], ["Val1", "Val2"]],
            ]
            mock_page.extract_text.return_value = "Texto normal"
            mock_doc.pages = [mock_page]
            mock_pdfplumber.open.return_value.__enter__.return_value = mock_doc

            resultado = _extraer_texto_tabla_a_textos(Path("test.pdf"))
            assert isinstance(resultado, list)

    def test_paginas_sin_tablas_extraen_texto(self):
        from rag.pdf_tabular import _extraer_texto_tabla_a_textos
        with patch("rag.pdf_tabular.pdfplumber") as mock_pdfplumber:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_tables.return_value = []
            mock_page.extract_text.return_value = "Texto sin tablas"
            mock_doc.pages = [mock_page]
            mock_pdfplumber.open.return_value.__enter__.return_value = mock_doc

            resultado = _extraer_texto_tabla_a_textos(Path("test.pdf"))
            assert len(resultado) >= 1


class TestParsearKeyValue:
    """Tests para _parsear_a_key_value_simple."""

    def test_parsa_clave_valor(self):
        from rag.pdf_tabular import _parsear_a_key_value_simple
        texto = "Nombre: Juan\nEdad: 30"
        resultado = _parsear_a_key_value_simple(texto)
        assert "Nombre" in resultado
        assert "Edad" in resultado

    def test_parsa_flecha(self):
        from rag.pdf_tabular import _parsear_a_key_value_simple
        texto = "Dirección -> Calle 1\nCiudad -> Madrid"
        resultado = _parsear_a_key_value_simple(texto)
        assert "Dirección" in resultado

    def test_ignora_lineas_vacias(self):
        from rag.pdf_tabular import _parsear_a_key_value_simple
        texto = "\n\nNombre: Juan\n\nEdad: 30\n"
        resultado = _parsear_a_key_value_simple(texto)
        assert len(resultado) >= 2

    def test_vacio_devuelve_dict_vacio(self):
        from rag.pdf_tabular import _parsear_a_key_value_simple
        resultado = _parsear_a_key_value_simple("")
        assert isinstance(resultado, dict)


class TestCargarPdfsEspeciales:
    """Tests para cargar_pdfs_especiales."""

    def test_lanza_si_no_existe_manifiesto(self):
        from rag.pdf_tabular import cargar_pdfs_especiales
        with patch("rag.pdf_tabular.Path") as mock_path:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = False
            mock_path.return_value = mock_dir

            with pytest.raises(FileNotFoundError, match="manifiesto"):
                cargar_pdfs_especiales(mock_dir)

    def test_devuelve_dict_con_tabular_y_ocr(self):
        from rag.pdf_tabular import cargar_pdfs_especiales
        with patch("rag.pdf_tabular.Path") as mock_path_cls:
            mock_dir = MagicMock()
            mock_manifiesto = MagicMock()
            mock_manifiesto.exists.return_value = True

            def read_text_mock(*args, **kwargs):
                return "test1.pdf:TAB\ntest2.pdf:OCR\n"

            mock_manifiesto.read_text.return_value = "test1.pdf:TAB\ntest2.pdf:OCR\n"

            mock_pdf_tab = MagicMock()
            mock_pdf_tab.exists.return_value = True
            mock_pdf_ocr = MagicMock()
            mock_pdf_ocr.exists.return_value = True

            paths = {
                "especiales.txt": mock_manifiesto,
                "test1.pdf": mock_pdf_tab,
                "test2.pdf": mock_pdf_ocr,
            }

            def get_path(name):
                return paths.get(name, MagicMock(exists=lambda: False))

            mock_path_cls.side_effect = lambda x: get_path(x) if isinstance(x, str) else mock_dir

            resultado = cargar_pdfs_especiales(mock_dir)
            assert "tabular" in resultado
            assert "ocr" in resultado


class TestConstants:
    """Tests para constantes de pdf_tabular."""

    def test_manifiesto(self):
        from rag.pdf_tabular import MANIFIESTO
        assert MANIFIESTO == "especiales.txt"

    def test_etiqueta_tabular(self):
        from rag.pdf_tabular import ETIQUETA_TABULAR
        assert ETIQUETA_TABULAR == "TAB"

    def test_etiqueta_ocr(self):
        from rag.pdf_tabular import ETIQUETA_OCR
        assert ETIQUETA_OCR == "OCR"


class TestOcrPdf:
    """Tests para _ocr_pdf."""

    def test_llama_pytesseract(self):
        from rag.pdf_tabular import _ocr_pdf
        with patch("rag.pdf_tabular.pytesseract") as mock_tess, \
             patch("rag.pdf_tabular.convert_from_path") as mock_convert:
            mock_convert.return_value = [MagicMock()]
            mock_tess.image_to_string.return_value = "Texto OCR"

            resultado = _ocr_pdf(Path("test.pdf"))
            assert isinstance(resultado, str)


class TestMain:
    """Tests para main()."""

    def test_muestra_resumen(self, capsys):
        from rag.pdf_tabular import main
        with patch("rag.pdf_tabular.sys.argv", ["pdf_tabular", "./data"]), \
             patch("rag.pdf_tabular.cargar_pdfs_especiales") as mock_cargar:
            mock_cargar.return_value = {
                "tabular": [{"texto": "tabla1", "fuente": "a.pdf"}],
                "ocr": [{"texto": "ocr1", "fuente": "b.pdf"}],
            }

            main()
            captured = capsys.readouterr()
            assert "Resumen" in captured.out or "tabular" in captured.out.lower()
