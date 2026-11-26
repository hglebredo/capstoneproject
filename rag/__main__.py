"""Entry-point for `python -m rag run`."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rag",
        description="RAG pipeline — run the offline RAG workflow.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── "run" (default) ────────────────────────────────────────────────
    run_parser = subparsers.add_parser(
        "run", aliases=["r"], help="Run the full RAG pipeline"
    )
    run_parser.add_argument(
        "rutas", nargs="+", help="Archivos o carpetas del corpus (p. ej. data)"
    )
    run_parser.add_argument("--chunk-size", type=int, default=None)
    run_parser.add_argument("--chunk-overlap", type=int, default=None)
    run_parser.add_argument("--persist-dir", default=None)
    run_parser.add_argument("--collection", default=None)
    run_parser.add_argument(
        "--recreate-index", action="store_true", help="Borrar la colección antes de indexar"
    )

    args = parser.parse_args()

    from rag.pipeline import ejecutar_pipeline

    if not getattr(args, "command", None):
        # No sub-command given — treat positional as rutas for "run"
        result = ejecutar_pipeline(
            args.rutas if hasattr(args, "rutas") else ["data"],
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            persist_dir=args.persist_dir,
            collection_name=args.collection,
            recreate_index=getattr(args, "recreate_index", False),
        )
    elif args.command in ("run", "r"):
        result = ejecutar_pipeline(
            args.rutas,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            persist_dir=args.persist_dir,
            collection_name=args.collection,
            recreate_index=args.recreate_index,
        )
    else:
        parser.print_help()
        sys.exit(1)

    print(result)


if __name__ == "__main__":
    main()
