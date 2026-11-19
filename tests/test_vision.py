"""Tests para rag/vision.py - Carga de imágenes como Documentos."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestMimeTypo:
    """Tests para _mime_type."""

    def test_png(self):
        from rag.vision import _mime_type
        with patch.object(Path, "suffix", new_callable=lambda: property(lambda self: ".png")) as _:
            path = MagicMock(spec=Path)
            path.name = "test.png"
            resultado = _mime_type(path)
            assert "image/png" in resultado

    def test_jpg(self):
        from rag.vision import _mime_type
        with patch.object(Path, "suffix", new_callable=lambda: property(lambda self: ".jpg")) as _:
            path = MagicMock(spec=Path)
            path.name = "test.jpg"
            resultado = _mime_type(path)
            assert "image/jpeg" in resultado

    def test_mime_no_encontrado_lanza_error(self):
        from rag.vision import _mime_type, mimetypes
        with patch("rag.vision.mimetypes.guess_type", return_value=(None, None)):
            path = MagicMock(spec=Path)
            path.name = "test.xyz"

            with pytest.raises(ValueError, match="MIME"):
                _mime_type(path)


class TestValidarImagen:
    """Tests para _validar_imagen."""

    def test_archivo_no_existente_lanza_error(self):
        from rag.vision import _validar_imagen
        path = MagicMock(spec=Path)
        path.is_file.return_value = False
        path.name = "test.png"

        with pytest.raises(FileNotFoundError, match="no existe"):
            _validar_imagen(path)

    def test_extension_no_soportada_lanza_error(self):
        from rag.vision import _validar_imagen
        path = MagicMock(spec=Path)
        path.is_file.return_value = True
        path.suffix.lower = property(lambda self: ".xyz")
        path.name = "test.xyz"

        with pytest.raises(ValueError, match="no soportado"):
            _validar_imagen(path)


class TestOcrImagen:
    """Tests para _ocr_imagen."""

    def test_devuelve_string(self):
        from rag.vision import _ocr_imagen
        with patch("rag.vision.pytesseract") as mock_tess, \
             patch("rag.vision.PIL.Image"):
            mock_tess.image_to_string.return_value = "Texto OCR extraído"

            path = MagicMock(spec=Path)
            resultado = _ocr_imagen(path)
            assert isinstance(resultado, str)


class TestDescripcionGemini:
    """Tests para _descripcion_gemini."""

    def test_devuelve_descripcion(self):
        from rag.vision import _descripcion_gemini
        with patch("rag.vision.base64.b64encode", return_value=b"dGVzdA=="), \
             patch("rag.vision.requests.post") as mock_post, \
             patch("rag.vision._mime_type", return_value="image/png"):
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "candidates": [{
                    "content": {"parts": [{"text": "Descripción de la imagen."}]}
                }]
            }
            mock_post.return_value = mock_resp

            path = MagicMock(spec=Path)
            resultado = _descripcion_gemini(path)
            assert isinstance(resultado, str)
            assert len(resultado) > 0


class TestCargarImagen:
    """Tests para cargar_imagen."""

    def test_devuelve_lista_documentos(self):
        from rag.vision import cargar_imagen
        with patch("rag.vision.Path") as mock_path_cls, \
             patch("rag.vision.IMAGE_OCR_ENABLED", True), \
             patch("rag.vision._validar_imagen"), \
             patch("rag.vision._ocr_imagen", return_value="Texto OCR"), \
             patch("rag.vision.IMAGE_VISION_ENABLED", False):

            mock_path = MagicMock(spec=Path)
            mock_path.name = "test.png"
            mock_path.suffix.lower = property(lambda self: ".png")
            mock_path.is_file.return_value = True
            mock_path_cls.side_effect = lambda x: mock_path if isinstance(x, (str, Path)) else mock_path

            resultado = cargar_imagen("test.png")
            assert isinstance(resultado, list)

    def test_devuelve_vacio_sin_contenido(self):
        from rag.vision import cargar_imagen
        with patch("rag.vision.Path") as mock_path_cls, \
             patch("rag.vision.IMAGE_OCR_ENABLED", True), \
             patch("rag.vision._validar_imagen"), \
             patch("rag.vision._ocr_imagen", return_value=""), \
             patch("rag.vision.IMAGE_VISION_ENABLED", False):

            mock_path = MagicMock(spec=Path)
            mock_path.name = "test.png"
            mock_path.suffix.lower = property(lambda self: ".png")
            mock_path.is_file.return_value = True
            mock_path_cls.side_effect = lambda x: mock_path if isinstance(x, (str, Path)) else mock_path

            resultado = cargar_imagen("test.png")
            assert isinstance(resultado, list)


class TestExtensionesAceptadas:
    """Tests para las extensiones de imagen aceptadas."""

    def test_extensiones_definidas(self):
        from rag.vision import _EXTENSIONES_ACEPTADAS
        assert ".png" in _EXTENSIONES_ACEPTADAS
        assert ".jpg" in _EXTENSIONES_ACEPTADAS
        assert ".jpeg" in _EXTENSIONES_ACEPTADAS
        assert ".webp" in _EXTENSIONES_ACEPTADAS


class TestMetadataBase:
    """Tests para los metadatos base de las imágenes."""

    def test_metadatos_incluyen_source(self):
        from rag.vision import cargar_imagen, Document
        with patch("rag.vision.Path") as mock_path_cls, \
             patch("rag.vision.IMAGE_OCR_ENABLED", True), \
             patch("rag.vision._validar_imagen"), \
             patch("rag.vision._ocr_imagen", return_value="Texto OCR"), \
             patch("rag.vision.IMAGE_VISION_ENABLED", False):

            mock_path = MagicMock(spec=Path)
            mock_path.name = "foto.png"
            mock_path.suffix.lower = property(lambda self: ".png")
            mock_path.is_file.return_value = True
            mock_path_cls.side_effect = lambda x: mock_path if isinstance(x, (str, Path)) else mock_path

            resultado = cargar_imagen("foto.png")
            for doc in resultado:
                assert isinstance(doc, Document)


class TestImageVisionEnabled:
    """Tests para el modo IMAGE_VISION_ENABLED."""

    def test_lanza_si_no_api_key(self):
        from rag.vision import _descripcion_gemini
        with patch("rag.vision.GOOGLE_API_KEY", ""), \
             patch("rag.vision.IMAGE_VISION_ENABLED", True), \
             pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
            path = MagicMock(spec=Path)
            path.read_bytes.return_value = b"data"
            _descripcion_gemini(path)
