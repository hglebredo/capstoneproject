"""
rag/informe.py
Genera el informe de indexaci\u00f3n en markdown (por defecto
``output/informe_index_<guid8_chroma>_aaaaMMdd_hhmm.md``)
al finalizar el pipeline: todos los par\u00e1metros aplicados y las m\u00e9tricas de la
ejecuci\u00f3n (tiempos por fase, chunking, scoring, dedup, \u00edndice final) listas
para la toma de decisiones.

El pipeline ensambla el dict de m\u00e9tricas (``datos``); este m\u00f3dulo solo renderiza:
Genera el informe de indexación en markdown (por defecto
``output/informe_index_<guid8_chroma>_aaaaMMdd_hhmm.md``)
al finalizar el pipeline: todos los parámetros aplicados y las métricas de la
ejecución (tiempos por fase, chunking, scoring, dedup, índice final) listas
para la toma de decisiones.

El pipeline ensambla el dict de métricas (``datos``); este módulo solo renderiza:
no lee config ni hace side effects de red, lo que permite testear la salida aislada.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Orden canonical de fases del pipeline (coincide con pipeline.py)
_FASES = ("PREFLIGHT", "LOAD", "CLEAN", "TAG", "CHUNK", "EMBED", "TSD", "INDEX", "FIN")


def _tabla(filas: list[tuple[str, str, str]]) -> str:
    """Renderiza filas (variable, valor, nota) como tabla markdown."""
    lineas = ["| Variable | Valor | Nota |", "|---|---|---|"]
    for var, valor, nota in filas:
        lineas.append(f"| `{var}` | {valor} | {nota} |")
    return "\n".join(lineas)


def formatear_duracion(segundos: float | None) -> str:
    """Duraci\u00f3n legible: milisegundos para < 1 s, segundos (2 decimales) para el resto.

    ``None``, o < 0.05 ms (el m\u00ednimo que distingue la precisi\u00f3n de ms) -> ``- ``.
    Usada en el informe para no mostrar falsos 0.0 s.
    """
    if not segundos or segundos < 5e-05:
        return "- "
def seccion_integridad_markdown(info: dict) -> str:
    integridad = info.get("integridad_archivos")

    if not integridad:
        return ""

    def escapar(valor: object) -> str:
        return (
            str(valor)
            .replace("|", "\\|")
            .replace("\r", " ")
            .replace("\n", " ")
        )

    lineas = [
        "## 8. Integridad de archivos",
        "",
        f"- Algoritmo: {integridad['algoritmo']}",
        f"- Verificación UTC: {integridad['verificado_en_utc']}",
        f"- Archivos comprobados: {integridad['total']}",
        f"- Sin cambios: {integridad['sin_cambios']}",
        f"- Modificados: {integridad['modificados']}",
        f"- Errores de lectura: {integridad['errores']}",
        "",
        "| Archivo | SHA-256 de carga | SHA-256 final | Estado |",
        "|---|---|---|---|",
    ]

    for archivo in integridad["archivos"]:
        if archivo["error"]:
            estado = f"ERROR: {archivo['error']}"
        elif archivo["sin_cambios"]:
            estado = "Sin cambios"
        else:
            estado = "MODIFICADO durante la ejecución"

        lineas.append(
            f"| {escapar(archivo['ruta'])} "
            f"| {archivo['sha256_carga']} "
            f"| {archivo['sha256_final'] or '—'} "
            f"| {escapar(estado)} |"
        )

    lineas.append("")
    return "\n".join(lineas)

def formatear_duracion(segundos: float | None) -> str:
    """Duración legible: milisegundos para < 1 s, segundos (2 decimales) para el resto.

    ``None``, o < 0.05 ms (el mínimo que distingue la precisión de ms) → ``—``.
    Usada en el informe para no mostrar falsos 0.0 s.
    """
    if not segundos or segundos < 5e-05:
        return "—"
    if segundos < 1:
        return f"{segundos * 1000:.1f} ms"
    return f"{segundos:.2f} s"


def _resumen_ejecutivo(datos: dict[str, Any]) -> list[str]:
    """Secci\u00f3n 0 \u2014 Resumen ejecutivo con m\u00e9tricas clave de toda la ejecuci\u00f3n.

    Presenta en una sola vista los indicadores que un responsable necesita para
    decidir si el pipeline ha ido bien y qu\u00e9 par\u00e1metros ajustar.
    """
    lineas: list[str] = [
        "## 0. Resumen ejecutivo",
        "",
        "| Indicador | Valor | Interpretaci\u00f3n |",
        "|---|---|---|",
    ]

    tiempo_total = datos.get("tiempo_total_s", 0)
    lineas.append(
        f"| Tiempo total de ejecuci\u00f3n | {formatear_duracion(tiempo_total)} | "
        "desde PREFLIGHT hasta INDEX + FIN |"
    )

    doc_cargados = datos.get("num_documentos_cargados", 0)
    doc_normalizados = datos.get("num_documentos_normalizados", 0)
    lineas.append(
        f"| Documentos cargados / normalizados | {doc_cargados} / {doc_normalizados} | "
        f"{doc_cargados - doc_normalizados} eliminados en CLEAN |"
    )

    chunks_pre = datos.get("num_chunks_pre_dedup", 0)
    chunks_post = datos.get("num_chunks_post_dedup", 0)
    descartados = datos.get("chunks_descartados", 0)
    descartado_pct = (descartados / chunks_pre * 100 if chunks_pre else 0)
    lineas.append(
        f"| Chunks pre \u2192 post dedup | {chunks_pre} \u2192 {chunks_post} ({descartados} descartados) | "
        f"ratio: {descartado_pct:.1f}% |"
    )

    dim = datos.get("dim_embedding", 0)
    indice = datos.get("indice", {})
    vectores = indice.get("vectores_insertados", chunks_post)
    space = indice.get("space", "- ")
    lineas.append(
        f"| Vectores en \u00edndice | {vectores} de dimensi\u00f3n {dim} | "
        f"espacio: `{space}` (coseno) |"
    )

    scoring = datos.get("scoring")
    if scoring is not None:
        lineas.append(
            f"| Semantic score | m\u00edn {scoring.get('semantic_score_min')} / media "
            f"{scoring.get('semantic_score_media')} / m\u00e1x {scoring.get('semantic_score_max')} | "
            f"{scoring.get('score_buenos_n', 0)} chunks \u2265 0.6 ({scoring.get('score_buenos_pct', 0):.1f}%) |"
        )

    dedup = datos.get("dedup")
    if dedup is not None:
        lineas.append(
            f"| Dedup umbral | {dedup.get('umbral')} | "
            f"{dedup.get('descartados_exactos', 0)} exactos, "
            f"{dedup.get('descartados_semantico', 0)} sem\u00e1nticos |"
        )

    integridad = datos.get("integridad", {})
    if integridad and integridad.get("n", 0) > 0:
        lineas.append(
            f"| Integridad de vectores | {integridad['n']} vectores, "
            f"NaN/Inf: {integridad['nan_inf']}, ceros: {integridad['cero']} | "
            f"L2 m\u00edn {integridad['norma_min']:.4f} / media {integridad['norma_media']:.4f} / "
            f"m\u00e1x {integridad['norma_max']:.4f} |"
        )

    lineas.append("")
    return lineas


def _load_metrics_md(datos: dict[str, Any]) -> list[str]:
    """Secci\u00f3n 2b \u2014 M\u00e9tricas de carga (LOAD): tipos de archivo y distribuci\u00f3n."""
    fuentes = datos.get("fuentes") or []
    if not fuentes:
        return []

    # Agrupar por tipo de extensi\u00f3n detectada en metadata.format
    formatos = datos.get("formatos_carga", {})
    lineas = [
        "### 2.1 Carga de corpus (LOAD)",
        "",
    ]

    if formatos:
        lineas += [
            "| Formato | Archivos | Documentos | Chunks pre-dedup |",
            "|---|---|---|---|",
        ]
        for fmt, info in sorted(formatos.items()):
            lineas.append(
                f"| {fmt} | {info.get('archivos', 0)} | "
                f"{info.get('documentos', 0)} | "
                f"{info.get('chunks_pre', 0)} |"
            )
        lineas.append("")

    # Distribuci\u00f3n por tipo de loader para PDFs especiales
    preflight = datos.get("preflight") or {}
    if preflight:
        pdf_tabulares = preflight.get("pdf_tabulares", [])
        pdf_ocr = preflight.get("pdf_ocr", [])
        notas_carga: list[str] = []
        if pdf_tabulares:
            notas_carga.append(
                f"- **PDFs tabulares (TAB):** {', '.join(pdf_tabulares)}"
            )
        if pdf_ocr:
            notas_carga.append(f"- **PDFs OCR:** {', '.join(pdf_ocr)}")
        if notas_carga:
            lineas += notas_carga + [""]

    # Resumen de fuentes con detalle de documentos/chunks
    tot_docs = sum(f["docs"] for _, f in fuentes)
    tot_pre = sum(f["chunks_pre"] for _, f in fuentes)
    tot_post = sum(f["chunks_post"] for _, f in fuentes)
    lineas += [
        "**Distribuci\u00f3n por fuente:**",
        "",
        "| Fuente | Docs | Chunks pre | Chunks post (dedup) | Densidad (chunks/doc) |",
        "|---|---|---|---|---|",
    ]
    for fuente, f in sorted(fuentes):
        dens = round(f["chunks_pre"] / f["docs"], 1) if f["docs"] else 0
        lineas.append(
            f"| {fuente} | {f['docs']} | {f['chunks_pre']} | "
            f"{f['chunks_post']} | {dens} |"
        )
    lineas.append(f"| **total** | {tot_docs} | {tot_pre} | {tot_post} | \u2014 |")
    lineas.append("")
    return lineas


def _clean_metrics_md(datos: dict[str, Any]) -> list[str]:
    """Secci\u00f3n 2c \u2014 M\u00e9tricas de limpieza (CLEAN): duplicados y eliminados."""
    clean = datos.get("clean_stats") or {}
    if not clean:
        return []

    lineas = [
        "### 2.2 Limpieza (CLEAN)",
        "",
        "| M\u00e9trica | Valor | Interpretaci\u00f3n |",
        "|---|---|---|",
        f"| Documentos de entrada | {clean.get('entrada', 0)} | tras LOAD |",
        f"| Documentos de salida | {clean.get('salida', 0)} | tras limpieza |",
        f"| Duplicados eliminados | {clean.get('duplicados', 0)} | por file_hash id\u00e9ntico |",
        f"| Vac\u00edos eliminados | {clean.get('vacios', 0)} | contenido en blanco o muy corto |",
    ]

    if clean.get("ratio_retencion"):
        lineas.append(
            f"| Ratio de retenci\u00f3n | {clean['ratio_retencion']:.1%} | "
            "documentos conservados sobre los cargados |"
        )

    lineas.append("")
    return lineas


def _chunking_metrics_md(datos: dict[str, Any]) -> list[str]:
    """Secci\u00f3n 4 mejorada \u2014 M\u00e9tricas detalladas de chunking."""
    stats = datos.get("chunk_stats") or {}
    if not stats and datos.get("num_chunks_pre_dedup", 0) == 0:
        return []

    lineas = [
        "### 4.1 Estrategia de chunking",
        "",
        "| Par\u00e1metro | Valor |",
        "|---|---|",
    ]

    # Extraer chunk_size y chunk_overlap de parametros si est\u00e1n
    params_map = {p[0]: p for p in datos.get("parametros") or []}
    if "CHUNK_SIZE" in params_map:
        lineas.append(
            f"| Chunk size | {params_map['CHUNK_SIZE'][1]} | longitud m\u00e1xima por chunk |"
        )
    else:
        lineas.append(
            f"| Chunk size | "
            f"{stats.get('chunk_size', datos.get('chunk_size_aplicado', 1000))} | "
            f"longitud m\u00e1xima por chunk |"
        )

    if "CHUNK_OVERLAP" in params_map:
        lineas.append(
            f"| Chunk overlap | {params_map['CHUNK_OVERLAP'][1]} | "
            f"sobrelapamiento entre chunks consecutivos |"
        )

    lineas += [
        "| Splitter usado | RecursiveCharacterTextSplitter | "
        "p\u00e1rrafo \u2192 frase \u2192 espacio \u2192 letra |",
        "",
    ]

    # M\u00e9tricas de distribuci\u00f3n de longitudes
    if stats:
        lineas += [
            "### 4.2 Distribuci\u00f3n de longitudes de chunk (caracteres)",
            "",
            "| M\u00e9trica | Valor | Nota |",
            "|---|---|---|",
            f"| min | {stats.get('min', 0)} | chunk m\u00e1s corto |",
            f"| p25 | {stats.get('p25', 0)} | "
            f"25 % de chunks \u2264 este valor |",
            f"| media | {stats.get('media', 0)} | longitud promedio |",
            f"| p50 (mediana) | {stats.get('p50', 0)} | valor central |",
            f"| p75 | {stats.get('p75', 0)} | "
            f"75 % de chunks \u2264 este valor |",
            f"| max | {stats.get('max', 0)} | "
            f"entidad \u00edntegra (no_chunk) si > chunk_size |",
            f"| rango | "
            f"{stats.get('rango', stats.get('max', 0) - stats.get('min', 0))} | max \u2212 min |",
            f"| chunks cortos (< 50 chars) | {stats.get('cortos', 0)} | ruido probable |",
            f"| \u00edntegras (no_chunk) | "
            f"{stats.get('sin_trocear', 0)} | entidades indexadas sin trocear |",
            "",
        ]

    return lineas


def _embed_metrics_md(datos: dict[str, Any]) -> list[str]:
    """Secci\u00f3n 4b \u2014 M\u00e9tricas de embedding (EMBED)."""
    embed = datos.get("embed_stats") or {}
    dim = datos.get("dim_embedding", 0)

    if not embed and dim == 0:
        return []

    lineas = [
        "### 4.3 Embeddings (EMBED)",
        "",
        "| M\u00e9trica | Valor | Interpretaci\u00f3n |",
        "|---|---|---|",
        f"| Modelo de embedding | {datos.get('embed_model', '- ')} | "
        f"proveedor: {datos.get('embed_provider', '- ')} |",
        f"| Vectores generados | "
        f"{embed.get('generados', datos.get('num_chunks_pre_dedup', 0))} | pre-dedup |",
        f"| Dimensi\u00f3n efectiva | {dim} | "
        f"(declarado: {datos.get('dim_declarado', '-')}, modelo: {datos.get('dim_modelo', '-')}) |",
    ]

    if embed.get("batch_size"):
        lineas.append(
            f"| Batch size | {embed['batch_size']} | "
            f"vectores por lote de inferencia |"
        )

    if embed.get("tiempo_s"):
        lineas.append(
            f"| Tiempo de embedding | "
            f"{formatear_duracion(embed['tiempo_s'])} | fase EMBED completa |"
        )

    # Mensaje de dimensi\u00f3n
    dim_msg = (datos.get("dim_msg") or "").strip()
    if dim_msg:
        lineas.append(f"| Dimensi\u00f3n | {dim_msg} |")

    lineas.append("")
    return lineas


def _fases_md(fases: dict[str, float], resumen: dict[str, str]) -> str:
    """Tabla de tiempos por fase con el resumen de cada una."""
    lineas = ["| Fase | Resultado | Tiempo |", "|---|---|---|"]
    for fase in _FASES:
        if fase in resumen:
            lineas.append(
                f"| {fase} | "
                f"{resumen[fase]} | "
                f"{formatear_duracion(fases.get(fase, 0))} |"
            )
            lineas.append(f"| {fase} | {resumen[fase]} | {formatear_duracion(fases.get(fase, 0))} |")
    return "\n".join(lineas)


_GLOSARIO_TSD = [
    "> Definiciones de m\u00e9tricas (los vectores est\u00e1n normalizados: norma L2 = 1, m\u00e9trica coseno):",
    "> - `semantic_score = 0.45\u00b7relevancia_LLM + 0.20\u00b7centralidad "
    "+ 0.20\u00b7(1 \u2212 redundancia) + 0.15\u00b7autoridad`, recortado a [0, 1]. "
    "> **Se\u00f1al** interna de priorizaci\u00f3n del corpus, **no** una medida de calidad del chunk ni "
    "de relevancia frente a consultas.",
    "> - `centralidad`: coseno del chunk contra el centroide de la colecci\u00f3n (media de todos los vectores). "
    "Coherencia con el centro del corpus.",
    "> - `redundancia`: coseno del chunk con su vecino m\u00e1s cercano (FAISS sobre los vectores normalizados; "
    "se excluye el propio). Alta redundancia media puede ser estructural "
    "(plantillas/CSVs de hechos) y no indicar corpus roto.",
    "> - **Pol\u00edtica exacta**: chunk cuya metadata `dedup_policy` es `exact_key`, "
    "`group_only` o `exact_only` (decidida por el asesor de CSVs); se deduplica "
    "**por clave** (nunca por coseno): la repetici\u00f3n literal se descarta, los sem\u00e1nticos cercanos no.",
    "> Definiciones de métricas (los vectores están normalizados: norma L2 = 1, métrica coseno):",
    "> - `semantic_score = 0.45·relevancia_LLM + 0.20·centralidad + 0.20·(1 − redundancia) + 0.15·autoridad`, recortado a [0, 1]. Señal interna de priorización del corpus, **no** una medida de calidad del chunk ni de relevancia frente a consultas.",
    "> - `centralidad`: coseno del chunk contra el centroide de la colección (media de todos los vectores). Coherencia con el centro del corpus.",
    "> - `redundancia`: coseno del chunk con su vecino más cercano (FAISS sobre los vectores normalizados; se excluye el propio). Alta redundancia media puede ser estructural (plantillas/CSVs de hechos) y no indicar corpus roto.",
    "> - **Política exacta**: chunk cuya metadata `dedup_policy` es `exact_key`, `group_only` o `exact_only` (decidida por el asesor de CSVs); se deduplica **por clave** (nunca por coseno): la repetición literal se descarta, los semánticos cercanos no.",
]


def _fuentes_md(fuentes: list[tuple[str, dict[str, int]]]) -> list[str]:
    """Tabla fuentes -> (docs, chunks pre, chunks post): los tres niveles del corpus.

    ``fuentes`` es ``sorted(fuentes.items())`` (orden alfab\u00e9tico determinista).
    Con corpus vac\u00edo (sin datos volcados) no se renderiza.
    """
    if not fuentes:
        return []
    lineas = [
        "| fuente | docs | chunks pre | chunks post (dedup) |",
        "|---|---|---|---|",
    ]
    tot_docs = tot_pre = tot_post = 0
    for fuente, f in fuentes:
        lineas.append(
            f"| {fuente} | {f['docs']} | "
            f"{f['chunks_pre']} | {f['chunks_post']} |"
        )



def _redundancia_politica_md(scoring: dict[str, Any]) -> list[str]:
    """Tabla de redundancia por política de dedup (6.1); opcional: si no hay
    datos volcados, no se muestra. El umbral se toma del volcado del scoring
    (``redundancia_umbral`` = DEDUP_UMBRAL), no hardcodeado."""
    if scoring.get("redundancia_umbral") is None:
        return []
    umbral = scoring["redundancia_umbral"]
    por_pol = scoring.get("redundancia_por_politica") or {}
    if not por_pol:
        return []
    lineas = [
        f"Redundancia (similitud con el vecino m\u00e1s cercano) "
        f"por pol\u00edtica de deduplicaci\u00f3n (umbral `{umbral}`):",
        "",
        "| pol\u00edtica | n | media | p50 | p90 | % \u2265 umbral |",
        f"Redundancia (similitud con el vecino más cercano) por política de deduplicación (umbral `{umbral}`):",
        "",
        "| política | n | media | p50 | p90 | % ≥ umbral |",
        "|---|---|---|---|---|---|",
    ]
    for pol in sorted(por_pol):
        r = por_pol[pol]
        lineas.append(
            f"| {pol} | {r['n']} | "
            f"{r['media']} | {r['p50']} | {r['p90']} | "
            f"{r['pct_sup_umbral']} % |"
        )
    lineas += [
        "",
        "> La alta media de `group_only`/`exact_key` es estructural "
        "(plantillas y entidades de CSV): esas pol\u00edticas se dedup por clave "
        "y nunca por coseno.",
        lineas.append(f"| {pol} | {r['n']} | {r['media']} | {r['p50']} | {r['p90']} | {r['pct_sup_umbral']} % |")
    lineas += [
        "",
        "> La alta media de `group_only`/`exact_key` es estructural (plantillas y entidades de CSV): esas políticas se dedup por clave y nunca por coseno.",
        "",
    ]
    return lineas


def _auditoria_md(dedup: dict[str, Any]) -> list[str]:
    """Auditor\u00eda de pares descartados en la 6.2: l\u00ednea del JSONL (o desactivada)
    y tabla por fuente. Opcional: si el dedup no volc\u00f3 datos de auditor\u00eda,
    """Auditoría de pares descartados en la 6.2: línea del JSONL (o desactivada)
    y tabla por fuente. Opcional: si el dedup no volcó datos de auditoría,
    solo se indica el estado."""
    lineas: list[str] = []
    audit = dedup.get("audit")
    if audit:
        lineas.append(
            f"- **Auditor\u00eda de pares:** `{audit['ruta']}` "
            f"({audit['n']} pares) "
            "-  muestrea la auditor\u00eda con `scripts/auditar_dedup.py`"
        )
    else:
        lineas.append("- **Auditor\u00eda de pares:** desactivada (DEDUP_AUDIT=false)")
    lineas.append("")
    por_fuente = dedup.get("descartes_por_fuente") or {}
    if por_fuente:
        lineas += [
            "**Descartes por fuente:**",
            "",
            "| fuente | descartes |",
            "|---|---|",
        ]
            f"- **Auditoría de pares:** `{audit['ruta']}` ({audit['n']} pares) "
            "— muestrea la auditoría con `scripts/auditar_dedup.py`"
        )
    else:
        lineas.append("- **Auditoría de pares:** desactivada (DEDUP_AUDIT=false)")
    lineas.append("")
    por_fuente = dedup.get("descartes_por_fuente") or {}
    if por_fuente:
        lineas += ["**Descartes por fuente:**", "",
                   "| fuente | descartes |", "|---|---|"]
        for fuente, n in sorted(por_fuente.items()):
            lineas.append(f"| {fuente} | {n} |")
        lineas.append("")
    return lineas


def _cobertura_md(dedup: dict[str, Any] | None) -> list[str]:
    """Secci\u00f3n 6.3 - cobertura por categor\u00eda (pre/post dedup) y top-3 de tags.

    Solo se renderiza si TSD est\u00e1 activo y se volc\u00f3 la cobertura; si no, no se
    """Sección 6.3 — cobertura por categoría (pre/post dedup) y top-3 de tags.

    Solo se renderiza si TSD está activo y se volcó la cobertura; si no, no se
    muestra (la multi-facialidad no existe sin etiquetado).
    """
    if dedup is None or "chunks_por_categoria" not in dedup:
        return []
    cov = dedup["chunks_por_categoria"]
    if not cov:
        return []
    lineas = [
        "### 6.3 Cobertura por categor\u00eda",
        "",
        "| categor\u00eda | pre | post (dedup) |",
        "|---|---|---|",
    ]
    # La taxonom\u00eda cerrada ordena las 6 categor\u00edas fijas: si no est\u00e1n en el
    # corpus, aparecen expl\u00edcitamente como 0 (no se ocultan).
    for cat in sorted(cov):
        lineas.append(
            f"| {cat} | {cov[cat]['pre']} | "
            f"{cov[cat]['post']} |"
        )
    top3 = dedup.get("tags_top3_post") or []
    if top3:
        lineas.append(
            "> **top 3 tags (post):** "
            + " \u00b7 ".join(f"{t} ({n})" for t, n in top3)
        )
    else:
        lineas.append("> **top 3 tags (post):** - ")
    lineas.append(
        "> La categor\u00eda es \u00fanica por fuente "
        "(la intenci\u00f3n dominante seg\u00fan TAG); los tags son multi-faces "
        "(un chunk puede llevar varios). Limitaci\u00f3n de TAG: solo ve el primer "
        "documento de cada fuente (\u2264 6000 caracteres), que decide categor\u00eda, "
        "tags y relevancia."
        "### 6.3 Cobertura por categoría",
        "",
        "| categoría | pre | post (dedup) |",
        "|---|---|---|",
    ]
    # La taxonomía cerrada ordena las 6 categorías fijas: si no están en el
    # corpus, aparecen explícitamente como 0 (no se ocultan).
    for cat in sorted(cov):
        lineas.append(f"| {cat} | {cov[cat]['pre']} | {cov[cat]['post']} |")
    top3 = dedup.get("tags_top3_post") or []
    lineas.append(
        f"> **top 3 tags (post):** "
        f"{' · '.join(f'{t} ({n})' for t, n in top3) if top3 else '—'}"
    )
    lineas.append(
        "> La categoría es única por fuente (la intención dominante según TAG); los tags son multi-faces (un chunk puede llevar varios). Limitación de TAG: solo ve el primer documento de cada fuente (≤ 6000 caracteres), que decide categoría, tags y relevancia."
    )
    lineas.append("")
    return lineas


def _senales(datos: dict[str, Any]) -> list[str]:
    """Heur\u00edsticas autom\u00e1ticas sobre las m\u00e9tricas de la ejecuci\u00f3n."""
    """Heurísticas automáticas sobre las métricas de la ejecución."""
    s: list[str] = []
    stats = datos.get("chunk_stats") or {}
    dedup = datos.get("dedup")
    dim_msg = (datos.get("dim_msg") or "").strip()
    preflight = datos.get("preflight") or {}
    scoring = datos.get("scoring")

    if stats.get("cortos"):
        plural = "chunks" if stats["cortos"] != 1 else "chunk"
        s.append(
            f"**Chunking:** hay {stats['cortos']} {plural} < 50 caracteres (ruido "
            "probable). Revisa los loaders o sube `CHUNK_SIZE`."
        )
    # Alerta cr\u00edtica (fuente a 0 post-dedup): si un archivo entero desaparece
    # del \u00edndice, su contenido deja de ser recuperable. No la ocultan las
    # heur\u00edsticas habituales: va expl\u00edcita para que no se pase por alto.
    # Alerta crítica (fuente a 0 post-dedup): si un archivo entero desaparece
    # del índice, su contenido deja de ser recuperable. No la ocultan las
    # heurísticas habituales: va explícita para que no se pase por alto.
    vacias = (dedup or {}).get("fuentes_vacias") or {}
    for fuente, f in (datos.get("fuentes") or []):
        pre, post = f.get("chunks_pre", 0), f.get("chunks_post", 0)
        if pre > 0 and post == 0:
            vaciada = vacias.get(fuente)
            causa = ""
            if vaciada and vaciada.get("motivo") == "dedup_coseno":
                par = vaciada["pareja"]
                causa = (
                    f" vaciada por dedup sem\u00e1ntica frente a `{par['fuente']}` "
                    f"(sim {vaciada['sim']})"
                )
            s.append(
                f"**Fuente vac\u00eda (cr\u00edtica):** `{fuente}` qued\u00f3 con 0 chunks "
                f"post-dedup ({pre} pre): su contenido ya no se recupera, "
                f"{causa} - revisa `DEDUP_UMBRAL` o regenera el \u00edndice; con una "
                "\u00fanica fuente de 1 chunk el descarte suele ser azar de la dedup "
                "sem\u00e1ntica (el LLM de TAG var\u00eda entre ejecuciones)."
            )
    if dedup is not None and dedup.get("descartados_pct", 0) > 50:
        s.append(
            f"**Dedup:** se descart\u00f3 el {dedup['descartados_pct']} % de los chunks (>50 %). "
            "Si es excesivo, baja `DEDUP_UMBRAL`; para m\u00e1s dedup, s\u00fabelo."
        )
    if dedup is not None and dedup.get("descartados_total", 0) == 0:
        s.append(
            "**Dedup:** no se descart\u00f3 ning\u00fan chunk: `DEDUP_UMBRAL` puede estar "
                causa = (f" vaciada por dedup semántica frente a `{par['fuente']}` "
                         f"(sim {vaciada['sim']})")
            s.append(
                f"**Fuente vacía (crítica):** `{fuente}` quedó con 0 chunks "
                f"post-dedup ({pre} pre): su contenido ya no se recupera, "
                f"{causa} — revisa `DEDUP_UMBRAL` o regenera el índice; con una "
                "única fuente de 1 chunk el descarte suele ser azar de la dedup "
                "semántica (el LLM de TAG varía entre ejecuciones)."
            )
    if dedup is not None and dedup.get("descartados_pct", 0) > 50:
        s.append(
            f"**Dedup:** se descartó el {dedup['descartados_pct']} % de los chunks (>50 %). "
            "Si es excesivo, baja `DEDUP_UMBRAL`; para más dedup, súbelo."
        )
    if dedup is not None and dedup.get("descartados_total", 0) == 0:
        s.append(
            "**Dedup:** no se descartó ningún chunk: `DEDUP_UMBRAL` puede estar "
            "demasiado alto o el corpus muy diverso."
        )
    if dim_msg:
        s.append(f"**Dimensiones:** {dim_msg}.")
    if preflight.get("verificado_por") == "cache_env":
        s.append(
            "**Preflight:** la disponibilidad se verific\u00f3 por cach\u00e9 `.env` (sin comprobaci\u00f3n "
            "online, p. ej. red cortada). La dim usada es fiable solo si "
            "`EMBED_DIM_MAX_*` est\u00e1 declarada."
            "**Preflight:** la disponibilidad se verificó por caché `.env` (sin comprobación "
            "online, p. ej. red cortada). La dim usada es fiable solo si "
            "`EMBED_DIM_MAX_*` está declarada."
        )
    cov = (dedup or {}).get("chunks_por_categoria") or {}
    for cat in sorted(cov):
        pre, post = cov[cat]["pre"], cov[cat]["post"]
        if post == 0:
            causa = (
                f"ning\u00fan chunk en {cat} (0 pre): el corpus no cubre esa intenci\u00f3n"
                if pre == 0
                else f"{pre} chunks entraron y todos fueron descartados"
            )
            s.append(
                f"**Cobertura:** la categor\u00eda {cat} queda vac\u00eda post-dedup ({causa}): "
                "las preguntas de esa intenci\u00f3n no podr\u00e1n responderse con este \u00edndice. "
                "A\u00f1ade corpus o revisa `DEDUP_UMBRAL`."            )
    if scoring is not None and scoring.get("score_buenos_pct", 100) < 50:
        s.append(
            f"Scoring: la distribuci\u00f3n de `semantic_score` se concentra por debajo de 0.6 "
            f"({scoring.get('score_buenos_pct', 0)} % de chunks superan el umbral). Es una se\u00f1al "
            "interna de priorizaci\u00f3n del corpus, no una m\u00e9trica de precisi\u00f3n del retrieval; "
                f"ningún chunk en {cat} (0 pre): el corpus no cubre esa intención"
                if pre == 0 else f"{pre} chunks entraron y todos fueron descartados"
            )
            s.append(
                f"**Cobertura:** la categoría {cat} queda vacía post-dedup ({causa}): "
                "las preguntas de esa intención no podrán responderse con este índice. "
                "Añade corpus o revisa `DEDUP_UMBRAL`."
            )
    if scoring is not None and scoring.get("score_buenos_pct", 100) < 50:
        s.append(
            f"Scoring: la distribución de `semantic_score` se concentra por debajo de 0.6 "
            f"({scoring.get('score_buenos_pct', 0)} % de chunks superan el umbral). Es una señal "
            "interna de priorización del corpus, no una métrica de precisión del retrieval; "
            "debe validarse con consultas reales. Si el corpus se nota pobre, revisa el "
            "modelo de TAG (solo ve los primeros 6000 caracteres de cada fuente)."
        )
    if not s:
        s.append(
            "Sin se\u00f1ales de alerta: las m\u00e9tricas est\u00e1n dentro de rangos habituales."
        )
    return [f"- {x}" for x in s]


def _criterios_decision_md(datos: dict[str, Any]) -> list[str]:
    """Tabla resumen de criterios de decisi\u00f3n basada en las m\u00e9tricas actuales.

    Genera una vista compacta que un responsable puede usar para decidir r\u00e1pidamente
    si el pipeline fue exitoso y qu\u00e9 par\u00e1metros ajustar.
    """
    dedup = datos.get("dedup") or {}
    scoring = datos.get("scoring") or {}
    stats = datos.get("chunk_stats") or {}
    integridad = datos.get("integridad", {})

    criterios: list[tuple[str, str, str]] = []

    # 1. Calidad del corpus (cobertura)
    cobertura_ok = True
    cov = dedup.get("chunks_por_categoria", {})
    for cat, vals in cov.items():
        if vals["post"] == 0 and vals["pre"] > 0:
            criterios.append((
                f"Cobertura {cat}",
                "\u26a0\ufe0f Vac\u00eda post-dedup",
                "Revisar DEDUP_UMBRAL o a\u00f1adir corpus",
            ))
            cobertura_ok = False
    if cobertura_ok and cov:
        total_cubiertos = sum(v["post"] for v in cov.values())
        criterios.append((
            "Cobertura general",
            f"{total_cubiertos} chunks cubiertos",
            "Todas las categor\u00edas tienen contenido",
        ))

    # 2. Dedup ratio
    pct = dedup.get("descartados_pct", 0)
    if pct > 50:
        criterios.append((
            "Dedup ratio",
            f"{pct}% descartado",
            "Posiblemente excesivo; bajar DEDUP_UMBRAL",
        ))
    elif pct < 10 and dedup.get("descartados_total", 0) > 0:
        criterios.append((
            "Dedup ratio",
            f"{pct}% descartado",
            "Bajo; corpus muy diverso o umbral alto",
        ))
    else:
        criterios.append((
            "Dedup ratio",
            f"{pct}% descartado",
            "Dentro de rango normal",
        ))

    # 3. Integridad de vectores
    if integridad.get("n", 0) > 0:
        n_vec = integridad["n"]
        nan_pct = round(integridad["nan_inf"] / n_vec * 100, 2)
        criterios.append((
            "Integridad de vectores",
            f"{integridad['nan_inf']} NaN/Inf ({nan_pct}%), "
            f"{integridad['cero']} ceros",
            (
                "Vectores limpios para inferencia" if nan_pct < 1
                else "Revisar embeddings"
            ),
        ))

    # 4. Calidad de scoring
    if scoring.get("score_buenos_n"):
        score_pct = scoring["score_buenos_pct"]
        if score_pct >= 70:
            criterios.append((
                "Calidad del scoring",
                f"{score_pct}% chunks \u2265 0.6",
                "Corpus bien puntuado por el LLM",
            ))
        elif score_pct >= 50:
            criterios.append((
                "Calidad del scoring",
                f"{score_pct}% chunks \u2265 0.6",
                "Puntuaci\u00f3n aceptable; validar con consultas reales",
            ))
        else:
            criterios.append((
                "Calidad del scoring",
                f"{score_pct}% chunks \u2265 0.6",
                "Corpus puede ser pobre; revisar TAG o corpus de entrada",
            ))

    # 5. Chunks cortos
    if stats.get("cortos", 0) > 0:
        criterios.append((
            f"Chunks cortos ({stats['cortos']})",
            "< 50 caracteres",
            "Ruido probable; revisar loaders o subir CHUNK_SIZE",
        ))

    # 6. Tiempo total
    t_total = datos.get("tiempo_total_s", 0)
    if t_total > 1:
        criterios.append((
            "Tiempo de ejecuci\u00f3n",
            f"{formatear_duracion(t_total)}",
            (
                "Dentro de lo esperado"
                if t_total < 30
                else "Ejecuci\u00f3n larga; considerar batching"
            ),
        ))

    # Construir tabla
    lineas: list[str] = [
        "### 7.1 Criterios de decisi\u00f3n (resumen)",
        "",
        "| Criterio | Valor | Acci\u00f3n recomendada |",
        "|---|---|---|",
    ]
    for crit, valor, accion in criterios:
        lineas.append(f"| {crit} | {valor} | {accion} |")
    lineas.append("")

    return lineas


def _scoring_md(
    scoring: dict[str, Any] | None, dedup: dict[str, Any] | None
) -> list[str]:
    """Secci\u00f3n 6 (TSD) completa: 6.1 Scoring -> 6.2 Dedup -> 6.3 Cobertura."""
    if scoring is None and dedup is None:
        return [
            "## 6. TSD (scoring + dedup)",
            "",
            "Bloque TSD desactivado (TAG_SCORING_DEDUP=false).",
            "",
        ]
    lineas = ["## 6. TSD (scoring + dedup)", ""]

        s.append("Sin señales de alerta: las métricas están dentro de rangos habituales.")
    return [f"- {x}" for x in s]


def _scoring_md(scoring: dict[str, Any] | None, dedup: dict[str, Any] | None) -> list[str]:
    """Sección 6 (TSD) completa: 6.1 Scoring → 6.2 Dedup → 6.3 Cobertura (una sola pasada)."""
    if scoring is None and dedup is None:
        return ["## 6. TSD (scoring + dedup)", "", "Bloque TSD desactivado (TAG_SCORING_DEDUP=false).", ""]
    lineas = ["## 6. TSD (scoring + dedup)", ""]
    if scoring is not None:
        lineas += [
            "### 6.1 Scoring (`semantic_score`)",
            "",
            "| M\u00e9trica | Valor | Interpretaci\u00f3n |",
            "|---|---|---|",
            (
                f"| min | {scoring.get('semantic_score_min', 0)} "
                f"| score m\u00e1s bajo del corpus |"
            ),
            (
                f"| media | {scoring.get('semantic_score_media', 0)} | |"
            ),
            (
                f"| m\u00e1x | {scoring.get('semantic_score_max', 0)} "
                f"| score m\u00e1s alto del corpus |"
            ),
            (
                f"| centralidad media | "
                f"{scoring.get('centralidad_media', 0)} "
                f"| coherencia con el centroide |"
            ),
            (
                f"| redundancia media | "
                f"{scoring.get('redundancia_media', 0)} "
                f"| similitud con el vecino m\u00e1s cercano |"
            ),
            (
                f"| chunks con score \u2265 0.6 | "
                f"{scoring.get('score_buenos_n', 0)} de "
                f"{scoring.get('chunks_n', 0)} "
                f"({scoring.get('score_buenos_pct', 0.0)} %) "
                f"| umbral interno de esta fase: "
                f"NO es precisi\u00f3n ni relevancia frente a consultas |"
            ),
            (
                f"| tiempo | {formatear_duracion(scoring.get('tiempo_s'))} "
                f"| fase SCORING |"
            ),
            "| Métrica | Valor | Interpretación |",
            "|---|---|---|",
            f"| min | {scoring.get('semantic_score_min', 0)} | score más bajo del corpus |",
            f"| media | {scoring.get('semantic_score_media', 0)} | |",
            f"| máx | {scoring.get('semantic_score_max', 0)} | score más alto del corpus |",
            f"| centralidad media | {scoring.get('centralidad_media', 0)} | coherencia con el centroide |",
            f"| redundancia media | {scoring.get('redundancia_media', 0)} | similitud con el vecino más cercano |",
            (
                f"| chunks con score ≥ 0.6 | {scoring.get('score_buenos_n', 0)} de {scoring.get('chunks_n', 0)} "
                f"({scoring.get('score_buenos_pct', 0.0)} %) | umbral interno de esta fase: "
                "NO es precisión ni relevancia frente a consultas |"
            ),
            f"| tiempo | {formatear_duracion(scoring.get('tiempo_s'))} | fase SCORING |",
            "",
        ]
        lineas += _GLOSARIO_TSD
        lineas += [""] + _redundancia_politica_md(scoring)

    if dedup is not None:
        lineas += [
            "### 6.2 Dedup",
            "",
            "| M\u00e9trica | Valor |",
            "|---|---|",
            (
                f"| umbral coseno (`DEDUP_UMBRAL`) | {dedup.get('umbral')} |"
            ),
            f"| chunks pre | {dedup.get('chunks_pre', 0)} |",
            f"| chunks post | {dedup.get('chunks_post', 0)} |",
            (
                f"| descartados exactos | "
                f"{dedup.get('descartados_exactos', 0)} |"
            ),
            (
                f"| descartados sem\u00e1nticos | "
                f"{dedup.get('descartados_semantico', 0)} |"
            ),
            (
                f"| descartados total | "
                f"{dedup.get('descartados_total', 0)} "
                f"({dedup.get('descartados_pct', 0)} %) |"
            ),
            (
                f"| tiempo | {formatear_duracion(dedup.get('tiempo_s'))} "
                f"| fase DEDUP |"
            ),
            "",
        ]
        lineas += _auditoria_md(dedup)

            "| Métrica | Valor |",
            "|---|---|",
            f"| umbral coseno (`DEDUP_UMBRAL`) | {dedup.get('umbral')} |",
            f"| chunks pre | {dedup.get('chunks_pre', 0)} |",
            f"| chunks post | {dedup.get('chunks_post', 0)} |",
            f"| descartados exactos | {dedup.get('descartados_exactos', 0)} |",
            f"| descartados semánticos | {dedup.get('descartados_semantico', 0)} |",
            f"| descartados total | {dedup.get('descartados_total', 0)} ({dedup.get('descartados_pct', 0)} %) |",
            f"| tiempo | {formatear_duracion(dedup.get('tiempo_s'))} | fase DEDUP |",
            "",
        ]
        lineas += _auditoria_md(dedup)
    lineas += _cobertura_md(dedup)
    return lineas


def _integridad_md(integridad: dict[str, Any] | None) -> list[str]:
    """Secci\u00f3n 5 - l\u00ednea de integridad de los vectores finales (solo si hay datos)."""
    """Sección 5 — línea de integridad de los vectores finales (solo si hay datos)."""
    if not integridad or integridad.get("n", 0) == 0:
        return []
    return [
        (
            f"- **Integridad:** {integridad['n']} vectores \u00b7 dim "
            f"{integridad['dim']} \u00b7 NaN/Inf {integridad['nan_inf']} "
            f"\u00b7 ceros {integridad['cero']} \u00b7 "
            f"norma L2 m\u00edn {integridad['norma_min']:.4f} / "
            f"media {integridad['norma_media']:.4f} / "
            f"m\u00e1x {integridad['norma_max']:.4f}"
            f"- **Integridad:** {integridad['n']} vectores · dim {integridad['dim']} · "
            f"NaN/Inf {integridad['nan_inf']} · ceros {integridad['cero']} · "
            f"norma L2 mín {integridad['norma_min']:.4f} / media {integridad['norma_media']:.4f} / máx {integridad['norma_max']:.4f}"
        ),
    ]


def generar_informe(
    datos: dict[str, Any], ruta: str | Path | None = None
) -> Path:
    """Escribe el informe markdown de indexaci\u00f3n y devuelve su ruta.

    Args:
        datos: m\u00e9tricas y par\u00e1metros ensamblados por el pipeline:
def generar_informe(datos: dict[str, Any], ruta: str | Path | None = None) -> Path:
    """Escribe el informe markdown de indexación y devuelve su ruta.

    Args:
        datos: métricas y parámetros ensamblados por el pipeline:
            rutas, parametros (lista de (variable, valor, nota)), tiempo_total_s,
            fases (tiempos por fase), resumen_fases (texto por fase), num_documentos,
            num_chunks_pre_dedup/post_dedup, chunk_stats, dim_embedding, dim_msg,
            preflight, indice (nombre/vectores/space), scoring, dedup,
            fuentes ([(fuente, {docs, chunks_pre, chunks_post}), ...]), integridad.

            Nuevas claves opcionales para m\u00e9tricas mejoradas:
                - clean_stats: dict con entrada, salida, duplicados, vacios,
                  ratio_retencion.
                - embed_stats: dict con generados, batch_size, tiempo_s.
                - formatos_carga: dict {formato: {archivos, documentos, chunks_pre}}.
                - chunk_size_aplicado: int (override de CHUNK_SIZE si se pas\u00f3 por CLI).
        ruta: ruta del informe (por defecto
            ``output/informe_index_<guid8_chroma>_aaaaMMdd_hhmm.md``, con la fecha y
            hora locales de la ejecuci\u00f3n.
        ruta: ruta del informe (por defecto
            ``output/informe_index_<guid8_chroma>_aaaaMMdd_hhmm.md``, con la fecha y
            hora locales de la ejecución).

    Returns:
        Ruta absoluta del informe escrito.
    """
    if ruta is None:
        guid_chroma = (datos.get("indice") or {}).get("guid_chroma")
        sufijo = f"_{guid_chroma[:8]}" if guid_chroma else ""
        ruta = (
            f"output/informe_index{sufijo}_"
            f"{datetime.now(timezone.utc).astimezone():%Y%m%d_%H%M}.md"
        )
    ruta = Path(ruta)

        ruta = f"output/informe_index{sufijo}_{datetime.now(timezone.utc).astimezone():%Y%m%d_%H%M}.md"
    ruta = Path(ruta)
    fases: dict[str, float] = datos.get("fases") or {}
    resumen_fases: dict[str, str] = datos.get("resumen_fases") or {}
    stats: dict[str, Any] = datos.get("chunk_stats") or {}
    indice: dict[str, Any] = datos.get("indice") or {}
    scoring = datos.get("scoring")
    dedup = datos.get("dedup")
    preflight = datos.get("preflight") or {}

    lineas: list[str] = [
        "# Informe de indexaci\u00f3n",
        "",
        (
            f"- **Fecha:** "
            f"{datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        (
            f"- **Corpus (rutas):** "
            f"{', '.join(datos.get('rutas') or [])}"
        ),
        (
            f"- **Tiempo total:** "
            f"{formatear_duracion(datos.get('tiempo_total_s', 0))}"
        ),
        "",
    ]

    # Secci\u00f3n 0: Resumen ejecutivo
    lineas += _resumen_ejecutivo(datos)

    # Secci\u00f3n 1: Par\u00e1metros aplicados
    lineas += [
        "## 1. Par\u00e1metros aplicados",
        "",
        _tabla(datos.get("parametros") or []),
        "",
    ]

    # Secci\u00f3n 2: Preflight + m\u00e9tricas de carga, limpieza y chunking
    lineas += ["## 2. Pipeline de datos (LOAD \u2192 CLEAN \u2192 CHUNK)", ""]

    if preflight and preflight.get("dim_modelo"):
        lineas.append(
            f"- **Dim m\u00e1xima del modelo (`EMBED_DIM_MAX_*`):** "
            f"{preflight['dim_modelo']}"
        )
    elif not preflight:
        pass  # no mostrar si no hay datos de preflight
    else:
        lineas.append(
            "- **Dim m\u00e1xima del modelo (`EMBED_DIM_MAX_*`):** no declarada "
            "(el preflight solo verifica la disponibilidad, "
            "no la dimensi\u00f3n)"
        )

    lineas += [
        (
            f"- **Verificado por:** "
            f"`{preflight.get('verificado_por', 'online')}`"
            if preflight
            else "- **Verificado por:** - "
        ),
        (
            f"- **Aviso:** {preflight.get('aviso') or 'sin avisos'}"
        ),
        "",
    ]

    # M\u00e9tricas de carga
    lineas += _load_metrics_md(datos)

    # M\u00e9tricas de limpieza (si existen datos de clean_stats)
    if datos.get("clean_stats"):
        lineas += _clean_metrics_md(datos)

    # Secci\u00f3n 3: M\u00e9tricas por fase (tiempos resumidos)
    lineas += [
        "## 3. Tiempos por fase",
        "",
        _fases_md(fases, resumen_fases),
        "",
    ]

    # Secci\u00f3n 4: Chunking y Embeddings detallados
    lineas += [
        "## 4. Corpus y chunking (longitudes en caracteres)",
        "",
        (
            "> **fuente** = archivo original \u00b7 "
            "**documento** = salida de LOAD (p\u00e1gina/fila/grupo) \u00b7 "
            "**chunk** = salida de CHUNK (\u00edntegro si entidad `no_chunk`)."
        ),
        "",
    ]

    # Distribuci\u00f3n por fuente compacta
    lineas += _fuentes_md(datos.get("fuentes") or [])
    if datos.get("fuentes"):
        lineas.append("")

    # M\u00e9tricas de chunking detalladas
    lineas += _chunking_metrics_md(datos)

    # M\u00e9tricas de embedding
    lineas += _embed_metrics_md(datos)

    # Secci\u00f3n 5: \u00cdndice final (ChromaDB)
    lineas += [
        "## 5. \u00cdndice final (ChromaDB)",
        "",
        f"- **Colecci\u00f3n:** `{indice.get('nombre', '- ')}`",
        f"- **Vector space:** `{indice.get('space', '- ')}` (coseno)",
        (
            f"- **Dim de embedding:** "
            f"{indice.get('dim', datos.get('dim_embedding', 0))}"
        ),
        (
            f"- **Vectores insertados:** "
            f"{indice.get('vectores_insertados', datos.get('num_chunks_post_dedup', 0))}"
        ),
        (
            f"- **Vectores totales en la colecci\u00f3n:** "
            f"{indice.get('vectores_totales', '- ')}"
        ),
        f"- **Recreado (`--recreate-index`):** {indice.get('recreado', False)}",
    ]

    integridad = datos.get("integridad")
    if integridad and integridad.get("n", 0) > 0:
        lineas.append(
            f"- **Integridad:** {integridad['n']} vectores \u00b7 dim "
            f"{integridad['dim']} \u00b7 NaN/Inf {integridad['nan_inf']} "
            f"\u00b7 ceros {integridad['cero']} \u00b7 "
            f"norma L2 m\u00edn {integridad['norma_min']:.4f} / "
            f"media {integridad['norma_media']:.4f} / "
            f"m\u00e1x {integridad['norma_max']:.4f}"
        )

    lineas.append("")

    # Secci\u00f3n 6: TSD (scoring + dedup)
    lineas += _scoring_md(scoring, dedup)

    # Secci\u00f3n 7: M\u00e9tricas y criterios de decisi\u00f3n
    lineas += [
        "## 7. M\u00e9tricas y criterios de decisi\u00f3n",
        "",
    ]
    lineas += [*_criterios_decision_md(datos)]
    lineas.append("")

    # Se\u00f1ales heur\u00edsticas (al final para referencia)
    lineas += [* _senales(datos)]

    # Debug: find any non-str items
    for i, x in enumerate(lineas):
        if not isinstance(x, str):
            import sys
            print(f"DEBUG: item {i} is {type(x).__name__}: {x!r}", file=sys.stderr)

        "# Informe de indexación",
        "",
        f"- **Fecha:** {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Corpus (rutas):** {', '.join(datos.get('rutas') or [])}",
        f"- **Tiempo total:** {formatear_duracion(datos.get('tiempo_total_s', 0))}",
        "",
        "",
        "## 1. Parámetros aplicados",
        "",
        _tabla(datos.get("parametros") or []),
        "",
        "## 2. Preflight",
        "",
        (f"- **Verificado por:** `{preflight.get('verificado_por', 'online')}`" if preflight else "- **Verificado por:** —"),
    ]
    if preflight and preflight.get("dim_modelo"):
        lineas.append(f"- **Dim máxima del modelo (`EMBED_DIM_MAX_*`):** {preflight['dim_modelo']}")
    if not preflight.get("dim_modelo"):
        lineas.append(
            "- **Dim máxima del modelo (`EMBED_DIM_MAX_*`):** no declarada "
            "(el preflight solo verifica la disponibilidad, no la dimensión)"
        )
    lineas += [
        f"- **Aviso:** {preflight.get('aviso') or 'sin avisos'}",
        "",
        "## 3. Métricas por fase",
        "",
        _fases_md(fases, resumen_fases),
        "",
        "## 4. Corpus y chunking (longitudes en caracteres)",
        "",
        "> **fuente** = archivo original · **documento** = salida de LOAD (página/fila/grupo) · **chunk** = salida de CHUNK (íntegro si entidad `no_chunk`).",
        "",
        *_fuentes_md(datos.get("fuentes") or []),
        *([""] if (datos.get("fuentes") or []) else []),
        "| Métrica (caracteres) | Valor |",
        "|---|---|",
        f"| min | {stats.get('min', 0)} |",
        f"| p25 | {stats.get('p25', 0)} |",
        f"| media | {stats.get('media', 0)} |",
        f"| p50 | {stats.get('p50', 0)} |",
        f"| p75 | {stats.get('p75', 0)} |",
        f"| max | {stats.get('max', 0)} |",
        f"| chunks cortos (< 50) | {stats.get('cortos', 0)} |",
        f"| íntegras (`no_chunk`) | {stats.get('sin_trocear', 0)} |",
        "",
        "> Un `max` mayor que `CHUNK_SIZE` no es un error: son las entidades indexadas íntegras (una fila = un chunk).",
        "",
        "## 5. Índice final (ChromaDB)",
        "",
        f"- **Colección:** `{indice.get('nombre', '—')}`",
        f"- **Vector space:** `{indice.get('space', '—')}` (coseno)",
        f"- **Dim de embedding:** {indice.get('dim', datos.get('dim_embedding', 0))}",
        f"- **Vectores insertados:** {indice.get('vectores_insertados', datos.get('num_chunks_post_dedup', 0))}",
        f"- **Vectores totales en la colección:** {indice.get('vectores_totales', '—')}",
        f"- **Recreado (`--recreate-index`):** {indice.get('recreado', False)}",
        *_integridad_md(datos.get("integridad")),
        "",
        *_scoring_md(scoring, dedup),
        "## 7. Señales y criterios de decisión",
        "",
        * _senales(datos),
        "",
        "\n" + seccion_integridad_markdown(datos),
    ]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta
