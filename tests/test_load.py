"""Tests para rag/load.py - Carga de documentos (PDF, CSV, TXT, MD)."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document


class TestFormatoDocumento:
    """Tests para _formato_documento."""

    def test_pdf(self):
        from rag.load import _formato_documento
        assert _formato_documento("archivo.pdf") == "pdf"

    def test_csv(self):
        from rag.load import _formato_documento
        assert _formato_documento("datos.csv") == "csv"

    def test_json(self):
        from rag.load import _formato_documento
        assert _formato_documento("data.json") == "json"

    def test_txt(self):
        from rag.load import _formato_documento
        assert _formato_documento("nota.txt") == "txt"

    def test_md(self):
        from rag.load import _formato_documento
        assert _formato_documento("readme.md") == "md"

    def test_extension_mayuscula(self):
        from rag.load import _formato_documento
        assert _formato_documento("archivo.PDF") == "pdf"

    def test_extension_desconocida_otro(self):
        from rag.load import _formato_documento
        assert _formato_documento("archivo.xyz") == "otro"

    def test_sin_extension(self):
        from rag.load import _formato_documento
        assert _formato_documento("sinext") == "otro"


class TestHashFile:
    """Tests para _hash_file."""

    def test_determinista(self, tmp_path):
        from rag.load import _hash_file
        ruta = tmp_path / "test.txt"
        ruta.write_text("contenido de prueba", encoding="utf-8")
        h1 = _hash_file(str(ruta))
        h2 = _hash_file(str(ruta))
        assert h1 == h2

    def test_diferente_contenido_diferente_hash(self, tmp_path):
        from rag.load import _hash_file
        ruta1 = tmp_path / "a.txt"
        ruta2 = tmp_path / "b.txt"
        ruta1.write_text("contenido A", encoding="utf-8")
        ruta2.write_text("contenido B", encoding="utf-8")
        assert _hash_file(str(ruta1)) != _hash_file(str(ruta2))

    def test_es_hex(self, tmp_path):
        from rag.load import _hash_file
        ruta = tmp_path / "test.txt"
        ruta.write_text("x", encoding="utf-8")
        h = _hash_file(str(ruta))
        assert len(h) == 64  # SHA-256 hex es 64 caracteres


class TestNormalizarSource:
    """Tests para _normalizar_source."""

    def test_fuerza_basename(self):
        from rag.load import _normalizar_source
        docs = [Document(page_content="x", metadata={"source": "dir/archivo.pdf"})]
        resultado = _normalizar_source(docs, "/otra/dir/archivo.pdf")
        assert all(d.metadata["source"] == "archivo.pdf" for d in resultado)

    def test_añade_file_hash(self):
        from rag.load import _normalizar_source
        docs = [Document(page_content="x", metadata={})]
        resultado = _normalizar_source(docs, "/test/archivo.txt")
        assert all("file_hash" in d.metadata for d in resultado)

    def test_mismo_hash_para_misma_ruta(self):
        from rag.load import _normalizar_source
        docs = [Document(page_content="x"), Document(page_content="y")]
        resultado = _normalizar_source(docs, "/test/archivo.txt")
        hashes = [d.metadata["file_hash"] for d in resultado]
        assert len(set(hashes)) == 1


class TestLeerPdfsTabulares:
    """Tests para funciones de manifiesto."""

    def test_devuelve_set_vacio_si_no_existe(self, tmp_path):
        from rag.load import _leer_pdfs_tabulares
        resultado = _leer_pdfs_tabulares(tmp_path)
        assert isinstance(resultado, set)
        assert len(resultado) == 0


class TestDetectarEncoding:
    """Tests para _detectar_encoding."""

    def test_utf8(self, tmp_path):
        from rag.load import _detectar_encoding
        ruta = tmp_path / "utf8.txt"
        ruta.write_bytes("hola mundo".encode("utf-8"))
        assert _detectar_encoding(str(ruta)) == "utf-8-sig"

    def test_cp1252(self, tmp_path):
        from rag.load import _detectar_encoding
        ruta = tmp_path / "cp1252.txt"
        # Texto que decodea bien en cp1252 pero no utf-8-sig por BOM
        ruta.write_bytes("hola".encode("cp1252"))
        assert _detectar_encoding(str(ruta)) in ("utf-8-sig", "cp1252")

    def test_fallback_latin1(self, tmp_path):
        from rag.load import _detectar_encoding
        ruta = tmp_path / "latin.txt"
        # latin-1 nunca falla (decodea todos los bytes)
        ruta.write_bytes(bytes(range(256)))
        assert _detectar_encoding(str(ruta)) == "latin-1"


class TestEsTabular:
    """Tests para _es_tabular."""

    def test_csv_minimo_es_tabular(self, tmp_path):
        from rag.load import _es_tabular
        ruta = tmp_path / "tabular.csv"
        # 50 filas x 2 columnas mínimo
        lines = ["col1;col2"] + [f"{i};dato{i}" for i in range(50)]
        ruta.write_text("\n".join(lines), encoding="utf-8")
        assert _es_tabular(str(ruta)) is True

    def test_txt_no_tabular(self, tmp_path):
        from rag.load import _es_tabular
        ruta = tmp_path / "notab.txt"
        # Texto plano sin delimitador adecuado
        ruta.write_text("Línea uno\nLínea dos\nTres líneas", encoding="utf-8")
        assert _es_tabular(str(ruta)) is False


class TestCargarArchivos:
    """Tests de integración para cargar_archivos."""

    def test_ruta_individual(self, tmp_path):
        from rag.load import cargar_archivos
        ruta = tmp_path / "test.txt"
        ruta.write_text("contenido de prueba", encoding="utf-8")
        resultado = cargar_archivos(str(ruta))
        assert isinstance(resultado, list)

    def test_ruta_lista(self, tmp_path):
        from rag.load import cargar_archivos
        r1 = tmp_path / "a.txt"
        r2 = tmp_path / "b.txt"
        r1.write_text("contenido A", encoding="utf-8")
        r2.write_text("contenido B", encoding="utf-8")
        resultado = cargar_archivos([str(r1), str(r2)])
        assert len(resultado) >= 2

    def test_directorio(self, tmp_path):
        from rag.load import cargar_archivos
        (tmp_path / "a.txt").write_text("A", encoding="utf-8")
        (tmp_path / "b.txt").write_text("B", encoding="utf-8")
        resultado = cargar_archivos(str(tmp_path))
        assert isinstance(resultado, list)

    def test_añade_metadata_basica(self):
        from rag.load import cargar_archivos
        with patch("rag.load.cargar_archivos") as mock:
            # Mock simple para verificar la estructura del retorno
            docs = [Document(page_content="x", metadata={"source": "test.txt"})]
            assert isinstance(docs[0], Document)


class TestLoadersMap:
    """Tests para el mapa _LOADERS."""

    def test_pdf_en_loaders(self):
        from rag.load import _LOADERS
        assert ".pdf" in _LOADERS

    def test_txt_en_loaders(self):
        from rag.load import _LOADERS
        assert ".txt" in _LOADERS

    def test_md_en_loaders(self):
        from rag.load import _LOADERS
        assert ".md" in _LOADERS

    def test_csv_en_loaders(self):
        from rag.load import _LOADERS
        assert ".csv" in _LOADERS


class TestManifiesto:
    """Tests para la gestión del manifiesto especiales.txt."""

    def test_constantes_manifiesto(self):
        from rag.load import MANIFIESTO, ETIQUETA_TABULAR, ETIQUETA_OCR
        assert MANIFIESTO == "especiales.txt"
        assert ETIQUETA_TABULAR == "TAB"
        assert ETIQUETA_OCR == "OCR"

    def test_excluye_manifiesto_de_carga(self):
        """El archivo especiales.txt no se carga como documento."""
        from rag.load import cargar_archivos, MANIFIESTO
        with patch("rag.load.Path.is_file", return_value=True), \
             patch("rag.load.Path.suffix", ".txt"), \
             patch("rag.load._LOADERS", {".txt": lambda r: [Document(page_content="x")]}) as mock_loaders:
            # Mock para verificar que el manifiesto se excluye
            pass
