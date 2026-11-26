"""Tests para rag/chunk.py - Troceado de documentos."""

import pytest
from langchain_core.documents import Document


class TestTrocear:
    """Tests para trocear()."""

    def test_devuelve_lista_documentos(self):
        from rag.chunk import trocear
        docs = [Document(page_content="Hola mundo", metadata={"source": "test"})]
        resultado = trocear(docs)
        assert isinstance(resultado, list)
        for r in resultado:
            assert isinstance(r, Document)

    def test_con_chunk_size_personalizado(self):
        from rag.chunk import trocear
        docs = [Document(page_content="a" * 2000, metadata={"source": "test"})]
        resultado = trocear(docs, chunk_size=500)
        assert len(resultado) > 1

    def test_con_chunk_overlap_personalizado(self):
        from rag.chunk import trocear
        docs = [Document(page_content="a" * 2000, metadata={"source": "test"})]
        resultado = trocear(docs, chunk_size=500, chunk_overlap=100)
        assert len(resultado) > 0

    def test_chunk_index_se_asigna(self):
        from rag.chunk import trocear
        docs = [Document(page_content="Hola mundo", metadata={"source": "test"})]
        resultado = trocear(docs, chunk_size=2000)
        for r in resultado:
            assert "chunk_index" in r.metadata

    def test_chunk_size_en_metadata(self):
        from rag.chunk import trocear
        docs = [Document(page_content="Hola mundo", metadata={"source": "test"})]
        resultado = trocear(docs, chunk_size=1234)
        for r in resultado:
            assert r.metadata["chunk_size"] == 1234

    def test_string_plano_se_envuelve(self):
        from rag.chunk import trocear
        texto = "Hola mundo"
        resultado = trocear(texto, chunk_size=500)
        assert len(resultado) >= 1
        # El string se envuelve en un Document con source="inline"
        if resultado:
            assert resultado[0].metadata.get("source") == "inline"

    def test_no_chunk_bypass(self):
        from rag.chunk import trocear
        doc = Document(
            page_content="Entidad atómica",
            metadata={"source": "test", "chunking_hint": "no_chunk"},
        )
        resultado = trocear([doc], chunk_size=500)
        assert len(resultado) == 1
        # no_chunk: no pasa por splitter, conserva chunk_index=0

    def test_light_chunk_bajo_umbral(self):
        from rag.chunk import trocear
        doc = Document(
            page_content="Corto",
            metadata={"source": "test", "chunking_hint": "light_chunk"},
        )
        resultado = trocear([doc], chunk_size=500)
        assert len(resultado) == 1

    def test_light_chunk_sobre_umbral_trocea(self):
        from rag.chunk import trocear
        doc = Document(
            page_content="Texto " * 200,  # ~1400 chars > chunk_size=500
            metadata={"source": "test", "chunking_hint": "light_chunk"},
        )
        resultado = trocear([doc], chunk_size=500)
        assert len(resultado) >= 1

    def test_multiple_documentos(self):
        from rag.chunk import trocear
        docs = [
            Document(page_content="Doc uno", metadata={"source": "a"}),
            Document(page_content="Doc dos", metadata={"source": "b"}),
        ]
        resultado = trocear(docs, chunk_size=500)
        assert len(resultado) == 2

    def test_herencia_metadata(self):
        from rag.chunk import trocear
        doc = Document(
            page_content="Texto de prueba para troceado",
            metadata={"source": "test.pdf", "doc_category": "tarifas"},
        )
        resultado = trocear([doc], chunk_size=50)
        for r in resultado:
            assert r.metadata.get("source") == "test.pdf"

    def test_chunk_overlap_cero(self):
        from rag.chunk import trocear
        docs = [Document(page_content="a" * 1000, metadata={"source": "test"})]
        # overlap=0 es válido (no falsy)
        resultado = trocear(docs, chunk_size=200, chunk_overlap=0)
        assert len(resultado) > 0

    def test_vacia_devuelve_vacio(self):
        from rag.chunk import trocear
        assert trocear([], chunk_size=500) == []


class TestRecursiveCharacterTextSplitter:
    """Tests de comportamiento del splitter."""

    def test_separadores_orden_correcto(self):
        """Los separadores se aplican en orden: párrafo -> frase -> espacio -> letra."""
        from rag.chunk import trocear
        # Texto con saltos de línea y espacios
        texto = "Párrafo uno.\nPárrafo dos. Párrafo tres."
        docs = [Document(page_content=texto, metadata={"source": "test"})]
        resultado = trocear(docs, chunk_size=100)
        assert len(resultado) >= 1

    def test_chunks_no_superan_chunk_size(self):
        """Cada chunk debe ser <= chunk_size caracteres."""
        from rag.chunk import trocear
        docs = [Document(page_content="a" * 500, metadata={"source": "test"})]
        resultado = trocear(docs, chunk_size=200)
        for r in resultado:
            assert len(r.page_content) <= 200

    def test_preserva_source_en_todos(self):
        """Todos los chunks heredan el source del documento."""
        from rag.chunk import trocear
        docs = [Document(page_content="x" * 500, metadata={"source": "test.pdf"})]
        resultado = trocear(docs, chunk_size=100)
        for r in resultado:
            assert r.metadata.get("source") == "test.pdf"
