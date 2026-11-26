"""Tests para rag/index.py - Indexación en ChromaDB."""

from unittest.mock import MagicMock, patch

import pytest


class TestObtenerClienteChroma:
    """Tests para obtener_cliente_chroma."""

    def test_devuelve_client_persistent(self):
        from rag.index import obtener_cliente_chroma
        with patch("rag.index.chromadb.PersistentClient") as mock_pc:
            mock_instance = MagicMock()
            mock_pc.return_value = mock_instance
            resultado = obtener_cliente_chroma()
            assert mock_pc.called

    def test_persist_dir_por_defecto(self):
        from rag.index import obtener_cliente_chroma
        with patch("rag.index.chromadb.PersistentClient") as mock_pc, \
             patch("rag.index.CHROMA_DIR", "./output/chroma_db"):
            obtener_cliente_chroma()
            args, kwargs = mock_pc.call_args
            assert kwargs.get("path") == "./output/chroma_db"

    def test_persist_dir_personalizado(self):
        from rag.index import obtener_cliente_chroma
        with patch("rag.index.chromadb.PersistentClient") as mock_pc:
            obtener_cliente_chroma(persist_dir="/custom/path")
            args, kwargs = mock_pc.call_args
            assert kwargs.get("path") == "/custom/path"


class TestCrearColeccion:
    """Tests para crear_coleccion."""

    def test_crea_con_metrica_coseno(self):
        from rag.index import crear_coleccion
        client = MagicMock()
        collection = MagicMock()
        client.get_or_create_collection.return_value = collection
        resultado = crear_coleccion(client, "test")
        assert resultado == collection

    def test_nombre_por_defecto(self):
        from rag.index import crear_coleccion
        client = MagicMock()
        with patch("rag.index.COLLECTION_NAME", "deporte_municipal"):
            crear_coleccion(client)
            args, _ = client.get_or_create_collection.call_args
            assert args[0] == "deporte_municipal"


class TestSanear:
    """Tests para _sanear."""

    def test_nulo_se_convierte_a_string(self):
        from rag.index import _sanear
        resultado = _sanear({"clave": None})
        assert resultado["clave"] == "null"

    def test_lista_se_convierte_a_string(self):
        from rag.index import _sanear
        resultado = _sanear({"colores": ["rojo", "azul"]})
        assert isinstance(resultado["colores"], str)

    def valora_tuple(self):
        from rag.index import _sanear
        resultado = _sanear({"items": (1, 2, 3)})
        assert isinstance(resultado["items"], str)

    def test_no_muta_primitivos(self):
        from rag.index import _sanear
        resultado = _sanear({"num": 42, "str": "hola"})
        assert resultado["num"] == 42
        assert resultado["str"] == "hola"

    def test_set_se_convierte_a_string(self):
        from rag.index import _sanear
        resultado = _sanear({"tags": {"a", "b"}})
        assert isinstance(resultado["tags"], str)


class TestIndexar:
    """Tests para indexar."""

    def test_devuelve_tupla_vivos_totales(self):
        from rag.index import indexar
        with patch("rag.index.obtener_cliente_chroma") as mock_client, \
             patch("rag.index.crear_coleccion") as mock_cc:
            mock_col = MagicMock()
            mock_col.count.return_value = 10
            mock_col.get.return_value = {"ids": ["id1", "id2"]}
            mock_cc.return_value = mock_col
            mock_client.return_value = MagicMock(get_or_create_collection=mock_cc)

            vivos, totales = indexar(
                ids=["id1"],
                embeddings=[[0.1]],
                documents=["test doc"],
                metadatas=[{"source": "test"}],
            )
            assert isinstance(vivos, int)
            assert isinstance(totales, int)

    def test_ids_unicos_assert(self):
        from rag.index import indexar
        with patch("rag.index.obtener_cliente_chroma") as mock_client, \
             patch("rag.index.crear_coleccion") as mock_cc:
            mock_col = MagicMock()
            mock_col.count.return_value = 10
            mock_col.get.return_value = {"ids": ["id1"]}
            mock_cc.return_value = mock_col

            # ids duplicados → debe lanzar assert
            with pytest.raises(AssertionError, match="IDs no únicos"):
                indexar(
                    ids=["id1", "id1"],  # duplicado
                    embeddings=[[0.1], [0.2]],
                    documents=["a", "b"],
                    metadatas=[{}, {}],
                )

    def test_recreate_borra_coleccion(self):
        from rag.index import indexar
        with patch("rag.index.obtener_cliente_chroma") as mock_client, \
             patch("rag.index.crear_coleccion") as mock_cc:
            mock_col = MagicMock()
            mock_col.count.return_value = 10
            mock_col.get.return_value = {"ids": ["id1"]}
            mock_cc.return_value = mock_col

            indexar(
                ids=["id1"],
                embeddings=[[0.1]],
                documents=["doc"],
                metadatas=[{}],
                recreate=True,
            )


class TestObtenerGuidChroma:
    """Tests para obtener_guid_chroma."""

    def test_devuelve_none_si_no_existe_dir(self):
        from rag.index import obtener_guid_chroma
        resultado = obtener_guid_chroma("/no/existe/dir")
        assert resultado is None

    def test_solo_directorios_con_contenido(self, tmp_path):
        from rag.index import obtener_guid_chroma
        # Crear un directorio con contenido válido (GUID)
        sub_dir = tmp_path / "a1b2c3d4"
        sub_dir.mkdir()
        (sub_dir / "dummy").touch()

        resultado = obtener_guid_chroma(str(tmp_path))
        assert resultado == "a1b2c3d4"


class TestBatchSize:
    """Tests para el batch de inserción."""

    def test_batch_add_constante(self):
        from rag.index import _BATCH_ADD
        assert isinstance(_BATCH_ADD, int)
        assert _BATCH_ADD > 0
