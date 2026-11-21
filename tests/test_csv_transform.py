"""Tests para rag/csv_transform.py - Transformación de CSV a Documentos."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document


class TestLimpiarValor:
    """Tests para limpiar_valor."""

    def test_compacta_espacios(self):
        from rag.csv_transform import limpiar_valor
        resultado = limpiar_valor("hola   mundo")
        assert resultado == "hola mundo"

    def test_nulo_devuelve_vacio(self):
        from rag.csv_transform import limpiar_valor
        resultado = limpiar_valor(None)
        assert resultado == ""

    def test_string_normal(self):
        from rag.csv_transform import limpiar_valor
        resultado = limpiar_valor("texto")
        assert resultado == "texto"


class TestBaseTexto:
    """Tests para _base_texto."""

    def test_convierte_fila_a_cadena(self):
        from rag.csv_transform import _base_texto
        row = {"nombre": "Juan", "edad": 30}
        columnas = ["nombre", "edad"]
        resultado = _base_texto(row, columnas)
        assert "nombre" in resultado
        assert "Juan" in resultado

    def test_ignora_valores_vacios(self):
        from rag.csv_transform import _base_texto
        row = {"nombre": "Juan", "edad": None}
        columnas = ["nombre", "edad"]
        resultado = _base_texto(row, columnas)
        assert "nombre" in resultado

    def test_separa_con_pipe(self):
        from rag.csv_transform import _base_texto
        row = {"a": "1", "b": "2"}
        columnas = ["a", "b"]
        resultado = _base_texto(row, columnas)
        assert "|" in resultado


class TestEntidadADocumento:
    """Tests para entidad_a_documento."""

    def test_devuelve_document(self):
        from rag.csv_transform import entidad_a_documento
        advice = MagicMock()
        advice.id_columns = ["id"]
        advice.dedup_policy = "exact_key"
        row = {"id": "123", "nombre": "Juan"}
        doc = entidad_a_documento("test.csv", row, 0, ["id", "nombre"], advice)

        assert isinstance(doc, Document)
        assert "entity_key" in doc.metadata

    def test_metadata_incluye_source(self):
        from rag.csv_transform import entidad_a_documento
        advice = MagicMock()
        advice.id_columns = ["id"]
        row = {"id": "123"}
        doc = entidad_a_documento("fuente.csv", row, 0, ["id"], advice)

        assert doc.metadata.get("source") == "fuente.csv"


class TestGrupoADocumento:
    """Tests para grupo_a_documento."""

    def test_devuelve_document(self):
        from rag.csv_transform import grupo_a_documento
        advice = MagicMock()
        advice.dedup_policy = "group_only"
        rows = [{"sexo": "M"}, {"sexo": "F"}]
        doc = grupo_a_documento(
            source="abonados.csv",
            keys=("grupo1",),
            rows=rows,
            columnas=["sexo"],
            advice=advice,
        )

        assert isinstance(doc, Document)
        assert "group_key" in doc.metadata


class TestFilaADocumentoEnriquecido:
    """Tests para fila_a_documento_enriquecido."""

    def test_devuelve_lista_documentos(self):
        from rag.csv_transform import fila_a_documento_enriquecido
        fila = {"nombre": "Juan", "edad": 30}
        resultado = fila_a_documento_enriquecido(fila, "test.csv")
        assert isinstance(resultado, list)

    def test_incluye_fuente(self):
        from rag.csv_transform import fila_a_documento_enriquecido
        fila = {"nombre": "Juan"}
        resultado = fila_a_documento_enriquecido(fila, "fuente.csv")
        assert len(resultado) > 0


class TestFilasADocumentos:
    """Tests para filas_a_documentos."""

    def test_devuelve_lista(self):
        from rag.csv_transform import filas_a_documentos
        advice = MagicMock()
        advice.dedup_policy = "row_as_doc"
        rows = [{"a": "1"}, {"a": "2"}]
        resultado = filas_a_documentos("test.csv", rows, ["a"], advice)

        assert isinstance(resultado, list)
        assert len(resultado) == 2


class TestTransformCsv:
    """Tests para transform_csv."""

    def test_devuelve_lista_documentos(self):
        from rag.csv_transform import transform_csv
        with patch("rag.csv_transform.advise_csv") as mock_advise, \
             patch("rag.csv_transform.leer_filas_csv") as mock_leer:
            advice = MagicMock()
            advice.treatment = "entity_doc"
            advice.source = "test.csv"
            mock_advise.return_value = (advice, {})

            rows = [{"id": "1", "nombre": "Juan"}]
            columnas = ["id", "nombre"]
            mock_leer.return_value = (columnas, rows)

            resultado = transform_csv("test.csv")
            assert isinstance(resultado, list)

    def test_treatment_entity_doc(self):
        from rag.csv_transform import transform_csv
        with patch("rag.csv_transform.advise_csv") as mock_advise, \
             patch("rag.csv_transform.leer_filas_csv") as mock_leer:
            advice = MagicMock()
            advice.treatment = "entity_doc"
            advice.source = "test.csv"
            mock_advise.return_value = (advice, {})

            rows = [{"id": "1"}]
            mock_leer.return_value = (["id"], rows)

            resultado = transform_csv("test.csv")
            assert len(resultado) > 0

    def test_treatment_grouped_doc(self):
        from rag.csv_transform import transform_csv
        with patch("rag.csv_transform.advise_csv") as mock_advise, \
             patch("rag.csv_transform.leer_filas_csv") as mock_leer:
            advice = MagicMock()
            advice.treatment = "grouped_doc"
            advice.grouping_keys = ["sexo"]
            advice.source = "test.csv"
            mock_advise.return_value = (advice, {})

            rows = [{"sexo": "M", "edad": 30}, {"sexo": "F", "edad": 25}]
            mock_leer.return_value = (["sexo", "edad"], rows)

            resultado = transform_csv("test.csv")
            assert isinstance(resultado, list)


class TestCsvTransformConstants:
    """Tests para constantes y aliases."""

    def test_district_alias(self):
        from rag.csv_transform import _DISTRICT
        assert "nombre_dis" in _DISTRICT or "distrito" in _DISTRICT

    def test_neighborhood_alias(self):
        from rag.csv_transform import _NEIGHBORHOOD
        assert "nombre_bar" in _NEIGHBORHOOD or "barrio" in _NEIGHBORHOOD
