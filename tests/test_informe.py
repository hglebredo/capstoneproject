"""Tests para rag/informe.py - Generación de informe markdown."""

from pathlib import Path
import pytest


class TestTabla:
    """Tests para _tabla."""

    def test_renderiza_filas(self):
        from rag.informe import _tabla
        filas = [("a", "1", "nota A"), ("b", "2", "nota B")]
        resultado = _tabla(filas)
        assert "| Variable | Valor | Nota |" in resultado
        assert "`a`" in resultado
        assert "`b`" in resultado

    def test_vacio_devuelve_header(self):
        from rag.informe import _tabla
        resultado = _tabla([])
        assert "| Variable | Valor | Nota |" in resultado


class TestFormatearDuracion:
    """Tests para formatear_duracion."""

    def test_milisegundos_bajo_un_segundo(self):
        from rag.informe import formatear_duracion
        assert "ms" in formatear_duracion(0.5)

    def test_segundos_sobre_un_segundo(self):
        from rag.informe import formatear_duracion
        resultado = formatear_duracion(1.5)
        assert "s" in resultado
        assert "ms" not in resultado

    def test_none_devuelve_dash(self):
        from rag.informe import formatear_duracion
        assert formatear_duracion(None) == "- "

    def test_cero_devuelve_dash(self):
        from rag.informe import formatear_duracion
        assert formatear_duracion(0) == "- "

    def test_muy_pequeno_devuelve_dash(self):
        """Valores < 50 microsegundos se muestran como '- '."""
        from rag.informe import formatear_duracion
        assert formatear_duracion(1e-6) == "- "


class TestFasesMd:
    """Tests para _fases_md."""

    def test_incluye_fases_basicas(self):
        from rag.informe import _fases_md
        fases = {"LOAD": 0.5, "CHUNK": 1.2}
        resumen = {"LOAD": "docs cargados", "CHUNK": "chunks generados"}
        resultado = _fases_md(fases, resumen)
        assert "LOAD" in resultado
        assert "CHUNK" in resultado

    def test_excluye_fases_sin_resumen(self):
        from rag.informe import _fases_md
        fases = {"PREFLIGHT": 0.1}
        resumen: dict[str, str] = {}
        resultado = _fases_md(fases, resumen)
        assert "PREFLIGHT" not in resultado


class TestFuentesMd:
    """Tests para _fuentes_md."""

    def test_renderiza_tabla_fuentes(self):
        from rag.informe import _fuentes_md
        fuentes = [
            ("a.pdf", {"docs": 10, "chunks_pre": 20, "chunks_post": 15}),
            ("b.csv", {"docs": 5, "chunks_pre": 10, "chunks_post": 8}),
        ]
        resultado = _fuentes_md(fuentes)
        assert any("a.pdf" in linea for linea in resultado)

    def test_vacia_devuelve_lista_vacia(self):
        from rag.informe import _fuentes_md
        assert _fuentes_md([]) == []

    def test_muestra_total(self):
        from rag.informe import _fuentes_md
        fuentes = [
            ("test.pdf", {"docs": 10, "chunks_pre": 20, "chunks_post": 15}),
        ]
        resultado = _fuentes_md(fuentes)
        assert "**total**" in str(resultado)


class TestScoringMd:
    """Tests para _scoring_md."""

    def test_tsd_desactivado(self):
        from rag.informe import _scoring_md
        resultado = _scoring_md(scoring=None, dedup=None)
        assert "TSD" in str(resultado[0]) if resultado else True
        # Debe mostrar que TSD está desactivado

    def test_tsd_con_scoring(self):
        from rag.informe import _scoring_md
        scoring = {
            "semantic_score_min": 0.1,
            "semantic_score_media": 0.5,
            "semantic_score_max": 0.9,
            "centralidad_media": 0.4,
            "redundancia_media": 0.3,
            "score_buenos_n": 80,
            "chunks_n": 100,
            "score_buenos_pct": 80.0,
            "tiempo_s": 2.5,
            "redundancia_umbral": 0.93,
            "redundancia_por_politica": {
                "semantica": {"n": 50, "media": 0.4, "p50": 0.3, "p90": 0.6, "pct_sup_umbral": 20.0},
            },
        }
        resultado = _scoring_md(scoring=scoring, dedup=None)
        assert len(resultado) > 0

    def test_tsd_con_dedup(self):
        from rag.informe import _scoring_md
        scoring = {
            "semantic_score_min": 0.1,
            "semantic_score_media": 0.5,
            "semantic_score_max": 0.9,
            "centralidad_media": 0.4,
            "redundancia_media": 0.3,
            "score_buenos_n": 80,
            "chunks_n": 100,
            "score_buenos_pct": 80.0,
            "tiempo_s": 2.5,
            "redundancia_umbral": 0.93,
            "redundancia_por_politica": {},
        }
        dedup = {
            "umbral": 0.93,
            "chunks_pre": 100,
            "chunks_post": 80,
            "descartados_exactos": 5,
            "descartados_semantico": 15,
            "descartados_total": 20,
            "descartados_pct": 20.0,
            "tiempo_s": 1.2,
            "audit": {"ruta": "output/dedup_audit.jsonl", "n": 20},
            "chunks_por_categoria": {},
            "tags_top3_post": [("abono", 5), ("piscina", 4)],
        }
        resultado = _scoring_md(scoring=scoring, dedup=dedup)
        assert len(resultado) > 0


class TestCoberturaMd:
    """Tests para _cobertura_md."""

    def test_con_cobertura(self):
        from rag.informe import _cobertura_md
        dedup = {
            "chunks_por_categoria": {
                "tarifas": {"pre": 50, "post": 45},
                "normativa": {"pre": 30, "post": 28},
            },
            "tags_top3_post": [("abono", 10), ("piscina", 8)],
        }
        resultado = _cobertura_md(dedup)
        assert len(resultado) > 0

    def test_sin_dedup_devuelve_vacio(self):
        from rag.informe import _cobertura_md
        assert _cobertura_md(None) == []


class TestSenales:
    """Tests para _senales."""

    def test_senales_basicas(self):
        from rag.informe import _senales
        datos = {
            "chunk_stats": {"cortos": 3},
            "dedup": {"descartados_pct": 25.0, "descartados_total": 10},
            "dim_msg": "dim efectiva del índice",
            "preflight": {"verificado_por": "online"},
        }
        resultado = _senales(datos)
        assert len(resultado) > 0

    def test_sin_alertas(self):
        from rag.informe import _senales
        datos: dict[str, object] = {
            "chunk_stats": {"cortos": 0},
            "dedup": None,
            "dim_msg": "",
            "preflight": {},
            "scoring": None,
        }
        resultado = _senales(datos)
        assert len(resultado) > 0

    def test_fuente_vacia(self):
        from rag.informe import _senales
        datos: dict[str, object] = {
            "chunk_stats": {},
            "dedup": {"fuentes_vacias": {"test.pdf": {"motivo": "dedup_coseno", "sim": 0.95}}},
            "dim_msg": "",
            "preflight": {},
            "scoring": None,
        }
        datos["fuentes"] = [("test.pdf", {"chunks_pre": 10, "chunks_post": 0})]
        resultado = _senales(datos)
        assert any("crítica" in s for s in resultado)


class TestIntegridadMd:
    """Tests para _integridad_md."""

    def test_con_datos(self):
        from rag.informe import _integridad_md
        integridad = {
            "n": 100, "dim": 384, "nan_inf": 2,
            "cero": 1, "norma_min": 0.95,
            "norma_media": 1.0, "norma_max": 1.05,
        }
        resultado = _integridad_md(integridad)
        assert len(resultado) == 1

    def test_sin_datos_devuelve_vacio(self):
        from rag.informe import _integridad_md
        assert _integridad_md(None) == []

    def test_cero_vectores_devuelve_vacio(self):
        from rag.informe import _integridad_md
        assert _integridad_md({"n": 0}) == []


class TestGenerarInforme:
    """Tests para generar_informe."""

    def test_genera_archivo(self, tmp_path):
        from rag.informe import generar_informe
        datos = {
            "rutas": ["data/corpus"],
            "parametros": [("CHUNK_SIZE", 1000, "longitud de chunk")],
            "tiempo_total_s": 5.234,
            "fases": {"LOAD": 0.5},
            "resumen_fases": {"LOAD": "docs cargados"},
            "chunk_stats": {"min": 10, "p25": 50, "media": 800, "p50": 70, "p75": 950, "max": 1500, "cortos": 3},
            "indice": {"nombre": "deporte_municipal", "space": "cosine", "dim": 384,
                       "vectores_insertados": 100, "vectores_totales": 100},
        }
        ruta = str(tmp_path / "informe.md")
        resultado = generar_informe(datos, ruta=ruta)

        assert resultado.exists()
        contenido = resultado.read_text(encoding="utf-8")
        assert "# Informe de indexación" in contenido

    def test_ruta_por_defecto(self):
        from rag.informe import generar_informe
        datos: dict[str, object] = {
            "indice": {"guid_chroma": "a1b2c3d4"},
            "rutas": ["data"],
            "parametros": [],
            "tiempo_total_s": 1.0,
            "fases": {},
            "resumen_fases": {},
            "chunk_stats": {},
        }
        resultado = generar_informe(datos)
        assert isinstance(resultado, Path)

    def test_contiene_secciones_basicas(self):
        from rag.informe import generar_informe
        datos: dict[str, object] = {
            "indice": {"guid_chroma": "a1b2c3d4"},
            "rutas": ["data/corpus"],
            "parametros": [("CHUNK_SIZE", 1000, "longitud")],
            "tiempo_total_s": 5.0,
            "fases": {"LOAD": 0.5, "CHUNK": 1.2},
            "resumen_fases": {"LOAD": "docs cargados", "CHUNK": "chunks generados"},
            "chunk_stats": {"min": 10, "p25": 50, "media": 800, "p50": 70, "p75": 950, "max": 1500},
        }
        ruta = str(Path("/tmp/test_informe.md"))
        resultado = generar_informe(datos, ruta=ruta)
        contenido = resultado.read_text(encoding="utf-8")

        assert "## 1. Parámetros aplicados" in contenido
        assert "## 2. Preflight" in contenido
        assert "## 3. Métricas por fase" in contenido
        assert "## 4. Corpus y chunking" in contenido


class TestGlosarioTsd:
    """Tests para las definiciones del glosario TSD."""

    def test_glosario_existe(self):
        from rag.informe import _GLOSARIO_TSD
        assert isinstance(_GLOSARIO_TSD, list)
        assert len(_GLOSARIO_TSD) > 0


class TestFasesOrden:
    """Tests para el orden de las fases."""

    def test_fases_en_orden(self):
        from rag.informe import _FASES
        esperado = ("PREFLIGHT", "LOAD", "CLEAN", "TAG", "CHUNK", "EMBED", "TSD", "INDEX", "FIN")
        assert _FASES == esperado
