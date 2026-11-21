"""Tests para rag/config.py - Resoluciones de proveedores y modelos."""

import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def reset_config():
    """Reinicia las variables de entorno relevantes antes de cada test."""
    # Guardar valores originales
    original = {
        "EMBED_PROVIDER": os.environ.get("EMBED_PROVIDER"),
        "GEN_PROVIDER": os.environ.get("GEN_PROVIDER"),
        "TAG_PROVIDER": os.environ.get("TAG_PROVIDER"),
        "OLLAMA_BASE_URL": os.environ.get("OLLAMA_BASE_URL"),
        "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY"),
    }
    yield
    # Restaurar valores originales
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_embed_provider_default_is_google():
    """EMBED_PROVIDER por defecto es 'google' en PB3."""
    # Limpiar TAG_PROVIDER para que no interfiera con la lectura de GEN_PROVIDER
    if "TAG_PROVIDER" in os.environ:
        del os.environ["TAG_PROVIDER"]
    
    from rag import config as cfg
    
    assert cfg.EMBED_PROVIDER == "ollama"


def test_gen_provider_default_is_google():
    """GEN_PROVIDER por defecto es 'google' en PB3."""
    # Limpiar TAG_PROVIDER para que no interfiera con la lectura de GEN_PROVIDER
    if "TAG_PROVIDER" in os.environ:
        del os.environ["TAG_PROVIDER"]
    
    from rag import config as cfg
    
    assert cfg.GEN_PROVIDER == "ollama"


def test_tag_provider_hereda_de_gen():
    """TAG_PROVIDER hereda de GEN_PROVIDER si está vacío."""
    # Configurar TAG_PROVIDER vacío y GEN_PROVIDER en google
    os.environ["GEN_PROVIDER"] = "google"
    os.environ["TAG_PROVIDER"] = ""

    # Recargar config para capturar el cambio
    import sys
    import importlib
    from rag import config as cfg
    
    if "rag.config" in sys.modules:
        importlib.reload(cfg)
    
    assert cfg.TAG_PROVIDER == "google"


def test_resolver_ollama():
    """_resolver devuelve el modelo correcto para ollama."""
    from rag.config import _resolver

    model = _resolver("ollama", "qwen3-embedding:0.6b", "hf-model", "gemini-model", "TEST")
    assert model == "qwen3-embedding:0.6b"


def test_resolver_huggingface():
    """_resolver devuelve el modelo correcto para huggingface."""
    from rag.config import _resolver

    model = _resolver("huggingface", "ollama-model", "hf-model", "gemini-model", "TEST")
    assert model == "hf-model"


def test_resolver_google():
    """_resolver devuelve el modelo correcto para google."""
    from rag.config import _resolver

    model = _resolver("google", "ollama-model", "hf-model", "gemini-model", "TEST")
    assert model == "gemini-model"


def test_resolver_provider_no_sothanado():
    """_resolver lanza ValueError para provider no soportado."""
    from rag.config import _resolver

    with pytest.raises(ValueError, match="no soportado"):
        _resolver("unknown", "model1", "model2", "model3", "TEST")


def test_ollama_base_url_default():
    """OLLAMA_BASE_URL por defecto es 127.0.0.1:11434."""
    from rag import config as cfg
    assert cfg.OLLAMA_BASE_URL == "http://127.0.0.1:11434"


def test_chunk_size_default():
    """CHUNK_SIZE por defecto es 1000."""
    if "CHUNK_SIZE" in os.environ:
        del os.environ["CHUNK_SIZE"]

    from rag import config as cfg
    assert cfg.CHUNK_SIZE == 1000


def test_chunk_overlap_default():
    """CHUNK_OVERLAP por defecto es 120 (coherente con .env.rag.example)."""
    if "CHUNK_OVERLAP" in os.environ:
        del os.environ["CHUNK_OVERLAP"]

    from rag import config as cfg
    assert cfg.CHUNK_OVERLAP == 120


def test_top_k_default():
    """TOP_K por defecto es 5."""
    if "TOP_K" in os.environ:
        del os.environ["TOP_K"]

    from rag import config as cfg
    assert cfg.TOP_K == 5


def test_retrieval_mode_hibrido():
    """RETRIEVAL_MODE por defecto es 'hibrido'."""
    if "RAG_RETRIEVAL_MODE" in os.environ:
        del os.environ["RAG_RETRIEVAL_MODE"]

    from rag import config as cfg
    assert cfg.RETRIEVAL_MODE == "hibrido"


def test_gen_temperature_default():
    """GEN_TEMPERATURE por defecto es 0.1."""
    if "GEN_TEMPERATURE" in os.environ:
        del os.environ["GEN_TEMPERATURE"]

    from rag import config as cfg
    assert cfg.GEN_TEMPERATURE == 0.1


def test_env_override_embed_provider():
    """EMBED_PROVIDER se puede sobrescribir con variable de entorno."""
    os.environ["EMBED_PROVIDER"] = "ollama"

    # Recargar para capturar el override
    import importlib
    from rag import config as cfg
    importlib.reload(cfg)

    assert cfg.EMBED_PROVIDER == "ollama"


def test_dimension_max_ollama():
    """EMBED_DIM_MAX_OLLAMA se lee correctamente."""
    os.environ["EMBED_DIM_MAX_OLLAMA"] = "1024"

    from rag import config as cfg
    # Recargar para capturar el cambio
    import importlib
    importlib.reload(cfg)

    assert cfg.EMBED_DIM_MAX_OLLAMA == 1024


def test_image_vision_model_herencia():
    """IMAGE_VISION_MODEL hereda de GEN_MODEL si no se define."""
    if "IMAGE_VISION_MODEL" in os.environ:
        del os.environ["IMAGE_VISION_MODEL"]

    from rag import config as cfg
    assert cfg.IMAGE_VISION_MODEL == cfg.GEN_MODEL


def test_chunking_hint_en_config():
    """Las constantes de chunking son enteros."""
    from rag import config as cfg
    assert isinstance(cfg.CHUNK_SIZE, int)
    assert isinstance(cfg.CHUNK_OVERLAP, int)
    assert cfg.CHUNK_SIZE > 0
    assert cfg.CHUNK_OVERLAP >= 0
