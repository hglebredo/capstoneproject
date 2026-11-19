"""
API FastAPI del PB3 — el agente del PB2 publicado como servicio.

Mismo patrón que los workouts de los Sprints 14 y 15:
FastAPI adapta; el agente decide. Esta capa traduce HTTP ↔ AgentService
y no reescribe el grafo.

  POST /ask     → AgentService.procesar_turno (+ resolver_plan si auto_aprobar)
  POST /approve → AgentService.resolver_plan (HITL)
  GET  /threads/{id}/messages → historial en Postgres (src/db.py)

Público: /, /docs, /health
Protegido (?api_key=): /ask, /approve, /threads/{id}/messages

Arranque:
  uvicorn app:app --reload --port 8000   →  http://127.0.0.1:8000/docs
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import asynccontextmanager
from typing import Any, Callable, TypeVar

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

import config
from agentes.runtime import crear_servicio
from schemas import ApproveIn, AskIn, AskOut, HealthOut, MessageOut
from security import require_api_key
from src import db

# Logs a consola. Nunca logueamos API_KEY, la clave de Gemini ni DATABASE_URL.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

T = TypeVar("T")

# Errores del AgentService (PB2) → código HTTP.
# 409 = conflicto de estado del HITL (como el 409 de negocio del Sprint 16).
# 400 = no hay plan que aprobar (como en el Sprint 14).
ERRORES_AGENTE = {
    "HITL_PENDING": 409,
    "REQUEST_INCOMPLETE": 409,
    "PLAN_NOT_CURRENT": 409,
    "PLAN_ALREADY_RESOLVED": 409,
    "HITL_NOT_PENDING": 400,
}

# Una sola instancia del agente para todo el proceso (se crea en lifespan).
# Si se creara por petición, /approve no encontraría el plan en MemorySaver.
_agente = None

# Última pregunta por hilo, para guardar el turno completo tras /approve
# (patrón _last_pregunta del Sprint 15). Vive en RAM: un reinicio pierde el
# HITL a medias igual que MemorySaver; el historial SQL no se pierde.
_pregunta_pendiente: dict[str, str] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _agente
    db.ensure_schema()
    _agente = crear_servicio(modo=config.AGENT_MODE)
    logger.info("Agente listo (modo=%s)", config.AGENT_MODE)
    yield


app = FastAPI(
    title="API Deporte Municipal Madrid — agente PB2",
    description=(
        "Agente multiagente LangGraph (PB2) publicado como API. "
        "Historial en PostgreSQL. En /docs: Try it out → parámetro api_key."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Helpers -----------------------------------------------------------------


def _con_timeout(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Ejecuta fn en un hilo y corta la espera a los ASK_TIMEOUT_SECONDS (Sprint 15).

    shutdown(wait=False): el 504 sale a tiempo. Python no puede matar el hilo:
    el agente termina en segundo plano (sigue gastando cuota).
    """
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=config.ASK_TIMEOUT_SECONDS)
    finally:
        pool.shutdown(wait=False)


def _ejecutar(ruta: str, thread_id: str, fn: Callable[..., dict], *args: Any, **kwargs: Any) -> dict:
    """Llama al agente con timeout y traduce sus errores a HTTP."""
    try:
        return _con_timeout(fn, *args, **kwargs)
    except FuturesTimeoutError:
        raise HTTPException(status_code=504, detail="El turno del agente superó el tiempo máximo") from None
    except ValueError as exc:
        codigo = str(exc).split(":", 1)[0].strip()
        if codigo in ERRORES_AGENTE:
            raise HTTPException(status_code=ERRORES_AGENTE[codigo], detail=codigo) from None
        logger.exception("%s error del agente thread_id=%s", ruta, thread_id)
        raise HTTPException(status_code=500, detail="Error interno del agente") from None
    except Exception:  # noqa: BLE001
        logger.exception("%s error inesperado thread_id=%s", ruta, thread_id)
        raise HTTPException(status_code=500, detail="Error interno del agente") from None


def _a_ask_out(estado: dict, thread_id: str) -> AskOut:
    """Traduce el estado del AgentService al contrato AskOut."""
    error = "ejecucion_incompleta" if estado.get("ejecucion_incompleta") else None
    return AskOut(
        respuesta=estado.get("final_answer") or "",
        thread_id=thread_id,
        done=bool(estado.get("done", False)),
        pendiente_hitl=bool(estado.get("pendiente_hitl", False)),
        plan=list(estado.get("plan") or []),
        error=error,
    )


def _guardar_si_cerrado(thread_id: str, pregunta: str, estado: dict) -> None:
    """Puente API → Postgres. Guarda si el turno ya no espera HITL y hay respuesta
    (aprobado, rechazado o sin plan), como en el Sprint 15."""
    respuesta = (estado.get("final_answer") or "").strip()
    if estado.get("pendiente_hitl") or not respuesta:
        return
    db.save_turn(thread_id, pregunta, respuesta)


def _log(metodo: str, ruta: str, thread_id: str, t0: float, status: int) -> None:
    duration_ms = int((time.perf_counter() - t0) * 1000)
    logger.info("%s %s thread_id=%s duration_ms=%s status=%s", metodo, ruta, thread_id, duration_ms, status)


# --- Rutas públicas ----------------------------------------------------------


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    """Público: pulso del servicio y estado de Postgres. Siempre 200."""
    try:
        ok = db.db_ok()
    except Exception:  # noqa: BLE001
        ok = False
    return HealthOut(status="ok" if ok else "degraded", storage="postgres", db_ok=ok)


# --- Rutas protegidas --------------------------------------------------------


@app.post("/ask", response_model=AskOut, dependencies=[Depends(require_api_key)])
def ask(body: AskIn) -> AskOut:
    """Un turno del agente.

    auto_aprobar=True (por defecto): si el grafo queda en HITL, la API aprueba
    el plan en la misma petición. auto_aprobar=False: devuelve pendiente_hitl=True
    y el plan; el cliente decide con POST /approve.
    """
    t0 = time.perf_counter()
    thread_id = body.thread_id.strip()
    pregunta = body.pregunta.strip()
    if not pregunta or not thread_id:
        _log("POST", "/ask", thread_id, t0, 400)
        raise HTTPException(status_code=400, detail="pregunta y thread_id no pueden estar vacíos")

    def _turno() -> dict:
        estado = _agente.procesar_turno(pregunta, thread_id)
        if body.auto_aprobar and estado.get("pendiente_hitl"):
            estado = _agente.resolver_plan(thread_id, True, plan_id=estado["plan_id"])
        return estado

    try:
        estado = _ejecutar("POST /ask", thread_id, _turno)
    except HTTPException as exc:
        _log("POST", "/ask", thread_id, t0, exc.status_code)
        raise

    if estado.get("pendiente_hitl"):
        _pregunta_pendiente[thread_id] = pregunta
    else:
        _guardar_si_cerrado(thread_id, pregunta, estado)

    _log("POST", "/ask", thread_id, t0, 200)
    return _a_ask_out(estado, thread_id)


@app.post("/approve", response_model=AskOut, dependencies=[Depends(require_api_key)])
def approve(body: ApproveIn) -> AskOut:
    """HITL: aprueba o rechaza el plan pendiente del hilo y guarda el turno."""
    t0 = time.perf_counter()
    thread_id = body.thread_id.strip()

    def _decidir() -> dict:
        # El plan_id del PB2 no se expone: se lee del estado del hilo.
        actual = _agente.consultar_estado(thread_id)
        if not actual.get("pendiente_hitl") or not actual.get("plan_id"):
            raise ValueError("HITL_NOT_PENDING: no hay un plan pendiente de decisión")
        return _agente.resolver_plan(thread_id, body.aprobado, plan_id=actual["plan_id"])

    try:
        estado = _ejecutar("POST /approve", thread_id, _decidir)
    except HTTPException as exc:
        _log("POST", "/approve", thread_id, t0, exc.status_code)
        raise

    pregunta = _pregunta_pendiente.pop(thread_id, "")
    if pregunta:
        _guardar_si_cerrado(thread_id, pregunta, estado)

    _log("POST", "/approve", thread_id, t0, 200)
    return _a_ask_out(estado, thread_id)


@app.get(
    "/threads/{thread_id}/messages",
    response_model=list[MessageOut],
    dependencies=[Depends(require_api_key)],
)
def get_messages(thread_id: str) -> list[MessageOut]:
    """Historial del hilo leído de Postgres (no de la RAM del agente)."""
    t0 = time.perf_counter()
    filas = db.list_messages(thread_id)
    _log("GET", "/threads/{id}/messages", thread_id, t0, 200)
    return [MessageOut(**fila) for fila in filas]
