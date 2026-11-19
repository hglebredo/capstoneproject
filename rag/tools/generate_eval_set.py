#!/usr/bin/env python3
"""
Genera queries/eval_set.jsonl a partir de los chunks ya indexados en ChromaDB.

Modo rápido (por defecto): extrae preguntas directamente de los chunkes sin
llamar al retriever (evita problemas de dimensión).
Modo LLM: usa Gemini/Ollama para generar preguntas más naturales.

Uso:
    python -m rag.tools.generate_eval_set          # modo rápido, 50 preguntas
    python -m rag.tools.generate_eval_set --llm     # genera con LLM (más lento)
    python -m rag.tools.generate_eval_set --n 100   # 100 preguntas
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_chroma_chunks(top_n=None):
    """Obtiene los chunks de ChromaDB directamente."""
    from rag.index import obtener_cliente_chroma

    client = obtener_cliente_chroma()
    collection = client.get_collection(name="deporte_municipal")

    results = collection.get(
        limit=top_n or 1000,
        include=["documents", "metadatas"],
    )

    chunks = []
    for i in range(len(results["ids"])):
        meta = (results["metadatas"][i] or {})
        doc = results["documents"][i] or ""
        match_nombre = re.search(r"nombre:\s*([^|]+)", doc)
        nombre = match_nombre.group(1).strip() if match_nombre else None

        chunks.append({
            "id": results["ids"][i],
            "content": doc,
            "source": meta.get("source", ""),
            "chunk_index": int(meta.get("chunk_index", 0)),
            "nombre": nombre,
        })
    return chunks


def _pregunta_tipo(src: str, doc: str, nombre: str) -> tuple[str, bool]:
    """Devuelve (texto_pregunta, es_nombre_especifico)."""
    if "polideportivos" in src.lower():
        return f"Información sobre los polideportivos del municipio", False
    elif "piscinas" in src.lower():
        return f"Características y horarios de las piscinas públicas", False
    elif "abonos" in src.lower() or "precios" in src.lower():
        return f"Precios y abonos para instalaciones deportivas", False
    elif "descuentos" in src.lower():
        return f"Descuentos disponibles en deportes municipales", False
    elif any(x in src.lower() for x in ["instalaciones", "areas"]):
        return f"Instalaciones y áreas deportivas del municipio", False
    elif any(x in src.lower() for x in ["agenda", "actividades"]):
        return f"Actividades y eventos deportivos programados", False
    elif "juegos" in src.lower():
        return f"Juegos y competiciones deportivas", False
    elif any(x in doc for x in ["horario", "hora", "abierto"]):
        if nombre:
            return f"Horario de {nombre}", True
        else:
            return "Horarios de las instalaciones deportivas", False
    elif any(x in doc for x in ["precio", "coste", "pvp", "euros"]):
        if nombre:
            return f"Precio de {nombre}", True
        else:
            return "Precios y tarifas de servicios deportivos", False
    elif any(x in src.lower() for x in ["normativa", "reglamento", "bases"]):
        return f"NORMATIVA y reglamentos deportivos municipales", False
    elif any(x in doc.lower() for x in ["reserva", "booking"]):
        return f"Información sobre reservas de instalaciones", False
    else:
        if nombre and len(nombre) > 3:
            return f"Información general sobre {nombre}", True
        else:
            return "Contenido general del documento deportivo", False


def extract_questions_from_chunks(chunks: list, n: int = 50) -> list[dict]:
    """Extrae preguntas del eval set directamente de los chunkes indexados.

    Estrategia:
      1. Recorre TODOS los chunkes y clasifica cada uno por tipo.
      2. Para tipos genéricos (polideportivos, piscinas...), toma la PRIMERA
         ocurrencia como pregunta representativa de esa fuente.
      3. Para nombres específicos, crea una pregunta individual.
      4. Completa con out-of-corpus hasta llegar a n.
    """
    questions = []

    # Paso 1: clasificar todos los chunkes por tipo
    generic_types = {}   # tipo -> primera ocurrencia (pregunta, fuente)
    specific_names = set()  # (nombre, fuente) ya añadidos
    all_sources = {}      # source -> primer chunk de esa fuente

    for c in chunks:
        src = c["source"] or "desconocido"
        doc = (c["content"] or "").strip()
        nombre = c.get("nombre") or ""

        if src not in all_sources:
            all_sources[src] = c

        q_texto, es_nombre = _pregunta_tipo(src, doc, nombre)

        if es_nombre and nombre:
            # Nombre específico: siempre único por (nombre, fuente)
            key = f"{nombre}|{src}"
            if key not in specific_names:
                specific_names.add(key)
                questions.append({
                    "pregunta": q_texto,
                    "fuente_esperada": src,
                    "out_of_corpus": False,
                })
        else:
            # Tipo genérico: solo la primera ocurrencia por tipo de pregunta
            if q_texto not in generic_types:
                generic_types[q_texto] = src
                questions.append({
                    "pregunta": q_texto,
                    "fuente_esperada": src,
                    "out_of_corpus": False,
                })

    # Paso 2: si aún no llegamos a n, añadir nombres específicos restantes
    if len(questions) < n:
        for c in chunks:
            if len(questions) >= n:
                break
            src = c["source"] or "desconocido"
            nombre = c.get("nombre") or ""

            if nombre and len(nombre) > 3:
                q_texto = f"Información general sobre {nombre}"
                key = f"{nombre}|{src}"
                if key not in specific_names:
                    specific_names.add(key)
                    questions.append({
                        "pregunta": q_texto,
                        "fuente_esperada": src,
                        "out_of_corpus": False,
                    })

    # Paso 3: agregar preguntas out-of-corpus
    remaining = n - len(questions)
    if remaining > 0:
        ooc_questions = [
            {"pregunta": "¿Cuál es el presupuesto municipal para deportes en 2027?",
             "fuente_esperada": None, "out_of_corpus": True},
            {"pregunta": "¿Se puede reservar una pista de pádel online?",
             "fuente_esperada": None, "out_of_corpus": True},
            {"pregunta": "¿Hay servicio de guardería en los centros deportivos?",
             "fuente_esperada": None, "out_of_corpus": True},
        ]
        for ooc in ooc_questions[:remaining]:
            questions.append(ooc)

    return questions[:n]


def generate_with_llm(chunks: list, n: int = 50):
    """Genera preguntas usando el LLM (Gemini/Ollama)."""
    from rag.generate import generar

    sample_docs = []
    for c in chunks[:20]:
        doc = (c["content"] or "")[:300]
        sample_docs.append(f"[{c['source']}] {doc}")

    context = "\n\n".join(sample_docs)

    prompt = (
        f"Genera exactamente {n} preguntas para evaluar un sistema RAG sobre deporte municipal.\n"
        f"Cada pregunta debe ser específica y responderse con el corpus.\n\n"
        f"Incluye 2-3 preguntas que NO tienen respuesta en los documentos (out-of-corpus).\n\n"
        f"Formato: una pregunta por línea, sin viñetas ni números.\n"
    )

    try:
        respuesta = generar(prompt)
        lines = [l.strip().lstrip("•- ") for l in respuesta.splitlines()]
        questions = []
        seen = set()
        for line in lines:
            if not line or len(line) < 10:
                continue
            key = line.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            questions.append({
                "pregunta": line,
                "fuente_esperada": None,
                "out_of_corpus": False,
            })

        return questions[:n]
    except Exception as e:
        print(f"  [WARN] Error con LLM ({e}), usando modo rápido.")
        return extract_questions_from_chunks(chunks, n)


def main(n=50, use_llm=False, out_path=None):
    """Genera el eval set y lo guarda."""

    if not out_path:
        out_path = os.getenv("EVAL_SET_RUTA", "queries/eval_set.jsonl")

    print(f"=== Generando eval_set.jsonl ({n} preguntas) ===\n")

    # 1. Cargar chunks de ChromaDB (cargamos todos para tener cobertura)
    print("1. Cargando chunkes de ChromaDB...")
    all_chunks = get_chroma_chunks(top_n=500)
    print(f"   {len(all_chunks)} chunkes encontrados\n")

    if not all_chunks:
        print("   [WARN] No hay chunkes indexados.")
        print("   Ejecuta 'python -m rag run' primero para indexar el corpus.\n")
        return

    # 2. Generar preguntas
    if use_llm:
        print("2. Generando preguntas con LLM...")
        questions = generate_with_llm(all_chunks, n)
        print(f"   {len(questions)} preguntas generadas\n")
    else:
        print("2. Extrayendo preguntas de los chunkes (modo rápido)...")
        questions = extract_questions_from_chunks(all_chunks, n)
        print(f"   {len(questions)} preguntas extraídas\n")

    # 3. Contar in/out corpus y fuentes únicas
    in_corpus = sum(1 for q in questions if not q.get("out_of_corpus"))
    out_corpus = sum(1 for q in questions if q.get("out_of_corpus"))
    fuentes_unicas = set(q.get("fuente_esperada", "") for q in questions if q.get("fuente_esperada"))

    print(f"   {in_corpus} in-corpus | {out_corpus} out-of-corpus")
    print(f"   Fuentes únicas: {len(fuentes_unicas)}\n")

    # 4. Guardar JSONL
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for item in questions:
            f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")

    print(f"4. Guardado en {path}\n")

    # 5. Mostrar muestra (primera de cada tipo)
    print("=== Muestra de preguntas ===")
    shown_types = set()
    for i, q in enumerate(questions[:15], 1):
        ooc = " [out]" if q.get("out_of_corpus") else ""
        src = f" -> {q.get('fuente_esperada', '')}" if q.get("fuente_esperada") else ""
        tipo = q["pregunta"][:35]
        new_type = tipo not in shown_types
        if new_type:
            shown_types.add(tipo)
        marker = " *" if new_type and i > 1 else ""
        print(f"  {i:2}. {q['pregunta']}{src}{ooc} ({tipo}){marker}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Genera queries/eval_set.jsonl a partir de los chunkes indexados."
    )
    parser.add_argument("--n", type=int, default=50, help="Número de preguntas (default: 50)")
    parser.add_argument("--llm", action="store_true", help="Usar LLM para generar preguntas")
    parser.add_argument("--out", type=str, default=None, help="Ruta de salida")

    args = parser.parse_args()
    main(n=args.n, use_llm=args.llm, out_path=args.out)
