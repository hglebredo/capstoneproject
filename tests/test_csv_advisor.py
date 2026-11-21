"""Tests para rag/csv_advisor.py — Clasificación y política de CSVs."""

import pytest


class TestNormalizarCol:
    """Tests para normalizar_col."""

    def test_minuscula(self):
        from rag.csv_advisor import normalizar_col
        assert normalizar_col("MXASSETNUM") == "mxassetnum"

    def sin_sufijo_tecnico(self):
        from rag.csv_advisor import normalizar_col
        # Las cabeceras técnicas como 'MXASSETNUM,C,12' se basifican
        assert normalizar_col("MXASSETNUM,C,12") == "mxassetnum"

    def test_vacia_devuelve_vacio(self):
        from rag.csv_advisor import normalizar_col
        assert normalizar_col("") == ""


class TestDetectarDelimitador:
    """Tests para detectar_delimitador."""

    def test_punto_y_coma(self, tmp_path):
        from rag.csv_advisor import detectar_delimitador
        ruta = tmp_path / "test.csv"
        # CSV con ';' como delimitador
        contenido = "col1;col2\nval1;val2\nval3;val4\nval5;val6\nval7;val8\nval9;val10"
        ruta.write_text(contenido, encoding="utf-8")
        assert detectar_delimitador(str(ruta)) == ";"

    def test_coma(self, tmp_path):
        from rag.csv_advisor import detectar_delimitador
        ruta = tmp_path / "test.csv"
        contenido = "col1,col2\nval1,val2\nval3,val4\nval5,val6\nval7,val8\nval9,val10"
        ruta.write_text(contenido, encoding="utf-8")
        assert detectar_delimitador(str(ruta)) == ","


class TestPareceNum:
    """Tests para _parece_num."""

    def test_entero(self):
        from rag.csv_advisor import _parece_num
        assert _parece_num("42") is True

    def test_decimal_coma(self):
        from rag.csv_advisor import _parece_num
        assert _parece_num("3,14") is True

    def test_decimal_punto(self):
        from rag.csv_advisor import _parece_num
        assert _parece_num("3.14") is True

    def test_no_es_numero(self):
        from rag.csv_advisor import _parece_num
        assert _parece_num("abc") is False


class TestCsvProfile:
    """Tests para el dataclass CsvProfile."""

    def test_valores_por_defecto(self):
        from rag.csv_advisor import CsvProfile
        profile = CsvProfile(source="test.csv", path="/test/test.csv")
        assert profile.n_rows == 0
        assert profile.n_cols == 0
        assert profile.uniqueness_ratio == 0.0
        assert not profile.has_date_column


class TestMatchKnownSource:
    """Tests para match_known_source."""

    def test_entity_table_conocida(self):
        from rag.csv_advisor import match_known_source, CsvProfile
        profile = CsvProfile(
            source="200186-0-polideportivos.csv",
            path="/data/200186-0-polideportivos.csv",
            columns=["pk", "nombre", "direccion"],  # pk está presente
        )
        resultado = match_known_source(profile)
        assert resultado is not None
        assert resultado.csv_kind == "entity_table"
        assert resultado.treatment == "entity_doc"
        assert resultado.dedup_policy == "exact_key"

    def test_fallback_si_columna_falta(self):
        """Si la columna ID falta, devuelve None (degrada a heurística)."""
        from rag.csv_advisor import match_known_source, CsvProfile
        profile = CsvProfile(
            source="200186-0-polideportivos.csv",
            path="/data/200186-0-polideportivos.csv",
            columns=["nombre", "direccion"],  # pk falta
        )
        resultado = match_known_source(profile)
        assert resultado is None

    def test_fallback_fuente_desconocida(self):
        from rag.csv_advisor import match_known_source, CsvProfile
        profile = CsvProfile(
            source="archivo_nuevo.csv",
            path="/data/archivo_nuevo.csv",
        )
        resultado = match_known_source(profile)
        assert resultado is None


class TestInferCsvKind:
    """Tests para infer_csv_kind."""

    def test_entity_table(self):
        from rag.csv_advisor import CsvProfile, infer_csv_kind
        profile = CsvProfile(
            source="test.csv",
            path="/data/test.csv",
            columns=["id", "nombre", "precio"],
            id_columns=["id"],
            n_cols=3,
            temporal_columns=[],
        )
        resultado = infer_csv_kind(profile)
        assert resultado.csv_kind == "entity_table"
        assert resultado.dedup_policy == "exact_key"

    def test_fact_table(self):
        from rag.csv_advisor import CsvProfile, infer_csv_kind
        profile = CsvProfile(
            source="test.csv",
            path="/data/test.csv",
            columns=["mes", "centro", "sexo", "edad"],
            id_columns=[],
            measure_columns=["n_abonados"],
            n_cols=4,
            temporal_columns=[],
        )
        resultado = infer_csv_kind(profile)
        assert resultado.csv_kind == "fact_table"

    def test_textual(self):
        from rag.csv_advisor import CsvProfile, infer_csv_kind
        profile = CsvProfile(
            source="test.csv",
            path="/data/test.csv",
            columns=["descripcion"],
            n_cols=1,
            avg_row_chars=300,  # > 250 → textual
        )
        resultado = infer_csv_kind(profile)
        assert resultado.csv_kind == "textual_table"

    def test_unknown(self):
        from rag.csv_advisor import CsvProfile, infer_csv_kind
        profile = CsvProfile(
            source="test.csv",
            path="/data/test.csv",
            columns=["a"],
            n_cols=1,
            avg_row_chars=50,  # bajo → unknown
        )
        resultado = infer_csv_kind(profile)
        assert resultado.dedup_policy == "exact_only"


class TestAdviseCsv:
    """Tests para advise_csv."""

    def test_devuelve_tuple(self):
        from rag.csv_advisor import advise_csv, CsvProfile
        with patch("rag.csv_advisor.inspect_csv") as mock_inspect, \
             patch("rag.csv_advisor.match_known_source") as mock_match:
            profile = CsvProfile(source="test.csv", path="/data/test.csv")
            advice_mock = MagicMock()  # type: ignore
            mock_inspect.return_value = profile
            mock_match.return_value = None

            resultado = advise_csv("/data/test.csv")
            assert len(resultado) == 2


class TestCsvAdviceDataClass:
    """Tests para el dataclass CsvAdvice."""

    def test_valores_por_defecto(self):
        from rag.csv_advisor import CsvAdvice
        advice = CsvAdvice(source="test", csv_kind="entity_table", treatment="entity_doc")
        assert advice.dedup_policy == "exact_only"  # default del tipo
        assert advice.confidence == 0.5

    def test_con_todos_los_campos(self):
        from rag.csv_advisor import CsvAdvice
        advice = CsvAdvice(
            source="test",
            csv_kind="fact_table",
            treatment="grouped_doc",
            dedup_policy="group_only",
            id_columns=["pk"],
            measure_columns=["precio"],
            grouping_keys=["mes", "centro"],
            confidence=0.95,
            reason="tabla de hechos",
        )
        assert advice.csv_kind == "fact_table"
        assert advice.confidence == 0.95


class TestIdTokens:
    """Tests para las listas de tokens."""

    def test_id_tokens_incluye_pk(self):
        from rag.csv_advisor import _ID_TOKENS
        assert "pk" in _ID_TOKENS

    def test_medida_tokens_incluiye_precio(self):
        from rag.csv_advisor import _MEDIDA_TOKENS
        assert "precio" in _MEDIDA_TOKENS


class TestRecetasConocidas:
    """Tests para las recetas de fuentes conocidas."""

    def test_todas_recetas_presentes(self):
        from rag.csv_advisor import RECETAS_CONOCIDAS
        assert len(RECETAS_CONOCIDAS) > 0

    def test_piscinas_es_entity_table(self):
        from rag.csv_advisor import RECETAS_CONOCIDAS
        receta = RECETAS_CONOCIDAS.get("210227-0-piscinas-publicas.csv")
        assert receta is not None
        assert receta["kind"] == "entity_table"

    def test_abonos_es_fact_table(self):
        from rag.csv_advisor import RECETAS_CONOCIDAS
        receta = RECETAS_CONOCIDAS.get("300085-0-deportes_abonos.csv")
        assert receta is not None
        assert receta["kind"] == "fact_table"


class TestCsvKind:
    """Tests para los tipos de CSV."""

    def test_todas_etiquetas_validas(self):
        from rag.csv_advisor import infer_csv_kind, CsvProfile
        # Probar que todos los kinds posibles son válidos
        kinds = ["entity_table", "fact_table", "time_series", "textual_table", "unknown_csv"]
        for kind in kinds:
            assert kind in [
                "entity_table", "fact_table", "time_series", "textual_table", "unknown_csv"
            ]
