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

# Misma clave que API_KEY del servidor.
api_key = (os.getenv("API_KEY") or "").strip()
# Dónde está la API (local o Render), sin barra final
base_url = (os.getenv("API_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(page_title="Deporte Municipal Madrid", page_icon="🏟️", layout="wide")

# --- Estado de la sesión ---
# Streamlit re-ejecuta el archivo en cada clic: lo que deba persistir va en session_state.
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"front-{uuid.uuid4().hex[:8]}"


# --- Llamadas a la API ---
def comprobar_health() -> dict | None:
    """GET /health (público, sin clave). None si la API no responde."""
    try:
        r = requests.get(f"{base_url}/health", timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None
    
def llamar_api(metodo: str, ruta: str, body: dict | None = None, timeout: int = 300):
    """Llama a una ruta protegida. Devuelve (status, datos) o (None, mensaje de error)."""
    try:
        r = requests.request(
            metodo,
            f"{base_url}{ruta}",
            params={"api_key": api_key},
            json=body,
            timeout=timeout,
        )
    except requests.Timeout:
        return None, f"El front dejó de esperar a los {timeout} s."
    except requests.RequestException:
        return None, "No se pudo conectar con la API."
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def decidir(thread_id: str, aprobado: bool) -> None:
    """POST /approve: aprueba o rechaza el plan pendiente del hilo."""
    with st.spinner("Aplicando tu decisión…"):
        status, datos = llamar_api(
            "POST", "/approve", {"thread_id": thread_id, "aprobado": aprobado}
        )
    st.session_state.ultima_respuesta = (status, datos)
    st.rerun()

# --- Barra lateral ---
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
        st.session_state.pop("ultima_respuesta", None)
        st.rerun()


# --- Zona principal -----------------------------------------------------------
st.title("🏟️ Asistente Deporte Municipal Madrid")

thread_id = st.session_state.thread_id

# 1)Historial leído de la API (GET /threads/{id}/messages)
status, mensajes = llamar_api("GET", f"/threads/{thread_id}/messages", timeout=30)
if status == 200:
    for m in mensajes:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
else:
    st.error(f"No se pudo leer el historial ({status}): {mensajes}")

# 2) Estado del último turno (guardado antes del st.rerun())
status, datos = st.session_state.get("ultima_respuesta", (None, None))
pendiente = status == 200 and bool(datos.get("pendiente_hitl"))

# 3) Plan pendiente → pregunta + respuesta + botones (aún no están en Postgres)
if pendiente:
    with st.chat_message("user"):
        st.markdown(st.session_state.get("ultima_pregunta", ""))
    with st.chat_message("assistant"):
        st.markdown(datos["respuesta"])
        st.markdown("**Plan propuesto:**")
        for paso in datos["plan"]:
            st.markdown(f"- {paso}")
        col1, col2 = st.columns(2)
        if col1.button("✅ Aprobar", use_container_width=True):
            decidir(thread_id, True)
        if col2.button("❌ Rechazar", use_container_width=True):
            decidir(thread_id, False)
elif status is not None and status != 200:
    st.error(f"Error {status}: {datos}")

# 4) Nueva pregunta → POST /ask (desactivada si hay un plan sin decidir)
pregunta = st.chat_input(
    "Aprueba o rechaza el plan antes de seguir" if pendiente
    else "Pregunta sobre instalaciones, piscinas, precios…",
    disabled=pendiente,
)
if pregunta:
    with st.chat_message("user"):
        st.markdown(pregunta)
    with st.spinner("El agente está pensando…"):
        status, datos = llamar_api(
            "POST", "/ask",
            {"pregunta": pregunta, "thread_id": thread_id, "auto_aprobar": False},
        )
    st.session_state.ultima_pregunta = pregunta
    st.session_state.ultima_respuesta = (status, datos)
    st.rerun()
