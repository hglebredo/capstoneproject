"""Tests para rag/retrieval/pgvector_store.py - PostgreSQL + pgvector."""

import pytest

# El módulo rag.retrieval.pgvector_store no existe: la base vectorial en la nube
# queda fuera de alcance en el PB3 (el índice es Chroma, dentro de la imagen).
pytest.skip("pgvector fuera de alcance en el PB3", allow_module_level=True)


class TestPGVectorStore:
    """Tests para el backend PGVector."""

    def test_creacion(self):
        from rag.retrieval.pgvector_store import PGVectorStore

        store = PGVectorStore()
        assert hasattr(store, "collection") or hasattr(store, "_table_name")

    def test_add_y_query(self):
        from rag.retrieval.pgvector_store import PGVectorStore

        store = PGVectorStore()
        try:
            store.add("pg_test_1", "contenido de prueba", {"source": "test"})
            results = store.query("prueba", top_k=5)
            assert isinstance(results, list)
        finally:
            if hasattr(store, "close"):
                store.close()


class TestCreateVectorStore:
    """Tests para create_vector_store."""

    def test_fallback_a_json(self):
        from rag.retrieval.vector_store import create_vector_store
        from pathlib import Path

        # Con VECTOR_BACKEND no definido o json -> VectorStore
        with __import__("rag.config.settings", fromlist=["settings"]).config.settings:
            pass
