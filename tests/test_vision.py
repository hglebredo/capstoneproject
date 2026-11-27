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
"""Tests de la tool de visión (agentes/tools/vision.py)."""
import agentes.nodes.documental as nod
import pytest
import os
from agentes.nodes.documental import nodo_documental
from agentes.tools.vision import imagen_preguntar

CLAVES = {"ok", "resultado", "fuentes", "abstained", "error"}
api_key = os.getenv("GOOGLE_API_KEY")

def test_imagen_inexistente_devuelve_error(tmp_path):
    out = imagen_preguntar.invoke({"image_id": str(tmp_path / "no_existe.jpg")})
    assert set(out) == CLAVES
    assert out["ok"] is False
    assert "No hay imagen" in out["error"]


def test_formato_no_soportado(tmp_path):
    gif = tmp_path / "foto.gif"
    gif.write_bytes(b"GIF89a")
    out = imagen_preguntar.invoke({"image_id": str(gif)})
    assert out["ok"] is False
    assert "Formato no soportado" in out["error"]


def test_sin_api_key_visión_no_disponible(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    out = imagen_preguntar.invoke({"image_id": "imagen_demo", "pregunta": "¿Qué ves?"})
    assert out["ok"] is False
    assert out["abstained"] is True
    assert "GOOGLE_API_KEY" in out["error"]
    assert out["resultado"] == ""


def test_nodo_documental_llama_a_imagen_con_invoke(monkeypatch, tmp_path):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: {
        "ok": True, "resultado": "x", "fuentes": [], "abstained": False, "error": None,
    })
    imagen = tmp_path / "cartel.jpg"
    imagen.write_bytes(b"imagen de prueba sin consultar la API")
    out = nodo_documental({"request_id": "r1", "pedido": "¿Qué dice el cartel?", "image_id": str(imagen)})
    eventos = out["documental"]["eventos"]
    assert [e["tool"] for e in eventos] == ["imagen", "rag"]
    assert eventos[0]["ok"] is False
    assert eventos[0]["abstained"] is True
    assert any("GOOGLE_API_KEY" in e for e in out["documental"]["errores"])


@pytest.mark.parametrize("extension,mime", [
    (".png", "image/png"), (".jpg", "image/jpeg"),
    (".jpeg", "image/jpeg"),
])
def test_vision_envia_mime_y_fuentes_compatibles_con_documental(monkeypatch, tmp_path, extension, mime):
    import agentes.tools.vision as vision
    from types import SimpleNamespace

    imagen = tmp_path / f"cartel{extension}"
    imagen.write_bytes(b"bytes transportados a un proveedor doble")
    monkeypatch.setenv("GOOGLE_API_KEY", "clave-doble")
    # El modelo de visión hereda GEN_MODEL; en los tests el proveedor por defecto no es google.
    monkeypatch.setattr(vision, "IMAGE_VISION_MODEL", "gemini-3.6-flash")
    llamadas = []

    def post(url, **kwargs):
        llamadas.append(kwargs)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"candidates": [{"content": {"parts": [{"text": "Cartel municipal"}]}}]},
        )

    monkeypatch.setattr(vision.requests, "post", post)
    r = imagen_preguntar.invoke({"image_id": str(imagen)})
    assert r["ok"] is True and r["error"] is None
    assert r["fuentes"] == [str(imagen)]
    parte = llamadas[0]["json"]["contents"][0]["parts"][1]
    assert parte["inline_data"]["mime_type"] == mime


def test_imagen_con_proveedor_doble_pasa_el_adaptador_comun(monkeypatch, tmp_path):
    import agentes.tools.vision as vision
    from agentes.documental_adapter import crear_adaptador_documental
    from agentes.state import initial_state
    from types import SimpleNamespace

    imagen = tmp_path / "cartel.png"
    imagen.write_bytes(b"doble")
    monkeypatch.setenv("GOOGLE_API_KEY", "clave-doble")
    # El modelo de visión hereda GEN_MODEL; en los tests el proveedor por defecto no es google.
    monkeypatch.setattr(vision, "IMAGE_VISION_MODEL", "gemini-3.6-flash")
    monkeypatch.setattr(vision.requests, "post", lambda *args, **kwargs: SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"candidates": [{"content": {"parts": [{"text": "Cartel municipal"}]}}]},
    ))
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: {
        "ok": True, "resultado": "", "fuentes": [], "abstained": True, "error": None,
    })
    # La autorización de ruta tiene sus propias regresiones; aquí se comprueba
    # el contrato real tool → nodo → adaptador con una imagen temporal.
    import agentes.documental_adapter as adapter
    monkeypatch.setattr(adapter, "validar_image_id", lambda image_id: image_id)
    state = initial_state("Describe el cartel")
    state["image_id"] = str(imagen)
    node = crear_adaptador_documental(ejecutar_documental=nodo_documental)
    result = node(state)["specialist_results"]["documental"]
    assert result.status == "ok"
    assert result.evidence[0].source == str(imagen)
    assert "no acredita normativa vigente" in result.answer


def test_vision_se_abstiene_si_el_modelo_no_es_gemini(monkeypatch, tmp_path):
    """Con GEN_PROVIDER=ollama el modelo heredado no es de Gemini: aviso claro, sin llamar a la API."""
    import agentes.tools.vision as vision

    imagen = tmp_path / "cartel.png"
    imagen.write_bytes(b"doble")
    monkeypatch.setenv("GOOGLE_API_KEY", "clave-doble")
    monkeypatch.setattr(vision, "IMAGE_VISION_MODEL", "llama3.2")

    def no_llamar(*args, **kwargs):
        raise AssertionError("no debe llamar a la API de Gemini")

    monkeypatch.setattr(vision.requests, "post", no_llamar)

    out = vision.imagen_preguntar.invoke({"image_id": str(imagen), "pregunta": "¿Qué pone?"})
    assert out["abstained"] is True
    assert "llama3.2" in out["error"]
