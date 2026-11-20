"""
Front Streamlit del PB3: cliente HTTP de la API del agente.

Solo habla HTTP con la API (requests): /health, /ask, /approve y
/threads/{id}/messages. No importa nada de agentes/ ni ejecuta tools.
La API_KEY y la URL de la API se leen de front/.env.
"""

import os
import uuid
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

# Carga solo front/.env (no el .env de la API, que está en la raíz)
load_dotenv(Path(__file__).parent / ".env")

# Misma clave que API_KEY del servidor; viaja en ?api_key=
api_key = (os.getenv("API_KEY") or "").strip()
# Dónde está la API (local o Render), sin barra final
base_url = (os.getenv("API_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(page_title="Deporte Municipal Madrid", page_icon="🏟️", layout="wide")


# --- Estado de la sesión ----------------------------------------------------
# Streamlit re-ejecuta el archivo en cada clic: lo que deba persistir va en session_state.
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"front-{uuid.uuid4().hex[:8]}"


# --- Llamadas a la API ------------------------------------------------------
def comprobar_health() -> dict | None:
    """GET /health (público, sin clave). None si la API no responde."""
    try:
        r = requests.get(f"{base_url}/health", timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


# --- Barra lateral ------------------------------------------------------------
with st.sidebar:
    st.header("Conexión")
    if api_key:
        st.success("API_KEY cargada desde front/.env")
    else:
        st.warning("Falta API_KEY en front/.env")
    st.caption(f"API: {base_url}")

    health = comprobar_health()
    if health is None:
        st.error("API no disponible. ¿Está arrancada?")
    elif health.get("db_ok"):
        st.success(f"Servicio: {health['status']} · Almacenamiento: {health['storage']}")
    else:
        st.warning("Servicio vivo, pero Postgres no responde")

    st.divider()
    st.subheader("Conversación")
    st.code(st.session_state.thread_id)
    if st.button("Nueva conversación", use_container_width=True):
        st.session_state.thread_id = f"front-{uuid.uuid4().hex[:8]}"
        st.rerun()
