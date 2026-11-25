# Contrato público de la API — Project Break 3 (MLOps)

> Acuerdo escrito **antes** de escribir código (Spec-Driven Development), para que los tres bloques (API, Postgres, Docker/Render) trabajen en paralelo sin pisarse.
>
> Primero lo que la API acepta y devuelve; después cómo se conecta por dentro con el agente del PB2 y con Postgres.
>
> **Versión 3.** Alineada con el código ya implementado (`app.py`, `schemas.py`, `front/`). Ver §12, "Historial de versiones".

---

## 1. Diagrama del sistema

```text
Front Streamlit (local)          ← solo habla HTTP, no importa el grafo
│  HTTPS   API_BASE_URL = URL de Render
▼
FastAPI (app.py)  ──►  AgentService del PB2  ──►  RAG + API externa
│                      (una sola instancia,       (tools reales)
│                       MemorySaver en memoria)
├── GET  /                              público → redirige a /docs
├── GET  /health                        público
├── GET  /docs                          público (Swagger)
├── POST /ask                           api_key → AskOut
├── POST /approve                       api_key → AskOut
└── GET  /threads/{thread_id}/messages  api_key → list[MessageOut]
│
│  DATABASE_URL
▼
PostgreSQL managed (Render) — historial de producto
```

---

## 2. Tabla de rutas

| Método | Ruta | `api_key` | Qué hace | Respuesta |
|--------|------|-----------|----------|-----------|
| GET  | `/` | No | Redirige a `/docs` | 307 |
| GET  | `/health` | No | Pulso. Indica que el almacenamiento es Postgres | `HealthOut` |
| GET  | `/docs` | No | Swagger con los schemas | HTML |
| POST | `/ask` | Sí | Un turno del agente | `AskOut` |
| POST | `/approve` | Sí | HITL: aprobar o rechazar el plan pendiente | `AskOut` |
| GET  | `/threads/{thread_id}/messages` | Sí | Historial del hilo, leído de Postgres | `list[MessageOut]` |

**Regla de acceso:** `/`, `/health` y `/docs` son públicos. El resto exige `api_key` como parámetro de **query** (`?api_key=...`), para poder probarlo desde Swagger.

---

## 3. Schemas Pydantic (`schemas.py`)

### 3.1 `AskIn` — entrada de `POST /ask`

```python
class AskIn(BaseModel):
    pregunta: str = Field(..., min_length=1, max_length=2000)    # vacía → 422
    thread_id: str = Field(..., min_length=1, max_length=100)    # lo genera el front
    auto_aprobar: bool = True                                    # cómodo en Swagger
```

### 3.2 `AskOut` — salida de `POST /ask` y de `POST /approve`

```python
class AskOut(BaseModel):
    respuesta: str                 # final_answer del agente
    thread_id: str
    done: bool = False             # True solo si el plan se aprobó y se cerró
    pendiente_hitl: bool = False   # True → el cliente debe llamar a /approve
    plan: list[str] = []           # viñetas del plan, para enseñarlas antes de aprobar
    error: Optional[str] = None    # ver §5
```

### 3.3 `ApproveIn` — entrada de `POST /approve`

```python
class ApproveIn(BaseModel):
    thread_id: str = Field(..., min_length=1, max_length=100)
    aprobado: bool                 # True aprueba, False rechaza
```

> El `AgentService` del PB2 exige un `plan_id` en `resolver_plan()`. **No se expone**: la API lo lee internamente con `consultar_estado(thread_id)["plan_id"]`.

### 3.4 `MessageOut` — unidad del historial

```python
class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: Optional[datetime] = None   # la lista ya viene en orden temporal
```

### 3.5 `HealthOut` — salida de `GET /health`

```python
class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]   # degraded si Postgres no responde
    storage: Literal["postgres"]
    db_ok: bool
```

---

## 4. Comportamiento por ruta

### `GET /health`
- **Siempre responde 200**, también sin `API_KEY` configurada (Render y el profesorado lo usan para ver si el servicio está vivo).
- Llama a `db_ok()` (un `SELECT 1` contra Postgres): `True` → `status="ok"`; `False` o excepción → `status="degraded"`, `db_ok=False`.

### `POST /ask`

Cómo se comporta el agente del PB2: si hay plan, el grafo **siempre se para antes de `aplicar`** (HITL). Por tanto:

| `auto_aprobar` | Qué hace la API | Respuesta típica |
|---|---|---|
| `true` | `procesar_turno()` y, si queda en HITL, `resolver_plan(aprobado=True)` en la misma petición | `done=true`, `pendiente_hitl=false` |
| `false` | Solo `procesar_turno()` | `done=false`, `pendiente_hitl=true`, `plan=[...]` |

Pasos:
1. Si `pregunta` o `thread_id` solo tienen espacios → **400**.
2. Ejecuta el turno con timeout (§6).
3. Si el agente acepta el pedido, guarda la pregunta **en memoria** (`app.py`) hasta que el turno se cierre.
4. Si el turno queda cerrado → guarda `user` + `assistant` en Postgres (`save_turn`).
5. Si queda en HITL → no guarda nada en Postgres todavía.

### `POST /approve`
1. Lee el estado del hilo con `consultar_estado(thread_id)`. Si no hay plan pendiente → **400** `HITL_NOT_PENDING`.
2. Llama a `resolver_plan(thread_id, aprobado, plan_id=...)`.
3. Guarda `user` (la pregunta en memoria) + `assistant` (respuesta final) en Postgres.
4. Devuelve `AskOut`:
   - aprobado → `done=true`, `respuesta` = respuesta + "Plan informativo aprobado…"
   - rechazado → `done=false`, `pendiente_hitl=false`, `respuesta="Propuesta rechazada. Puedes enviar un nuevo pedido."`

### Regla de guardado (importante para Postgres)
> **Se guarda cuando el turno ya no espera decisión humana y hay respuesta**: aprobado, rechazado o sin plan.
> En el PB2, `aplicar` devuelve `done=False` al rechazar. Si se guardara solo con `done=true`, los rechazos nunca llegarían al historial.
>
> El guardado ocurre **dentro del hilo del agente**: si la petición HTTP acaba en 504, el turno se guarda igualmente cuando el agente termina en segundo plano.

### `GET /threads/{thread_id}/messages`
- Devuelve los mensajes del hilo en orden temporal. Hilo inexistente → `[]` (200).
- Lee de Postgres, nunca de memoria. Dos `thread_id` distintos no se mezclan.

---

## 5. Códigos HTTP y errores

| Situación | Código | Quién |
|-----------|--------|-------|
| `pregunta` o `thread_id` solo con espacios | **400** | `app.py` |
| `/approve` sin plan pendiente (también tras reiniciar el servicio) | **400** `HITL_NOT_PENDING` | `app.py` |
| Sin `api_key` o clave incorrecta en ruta protegida | **401** | `security.py` |
| Conflicto de estado del HITL (ver tabla de abajo) | **409** | `app.py` |
| Body inválido (falta campo, pregunta vacía, demasiado larga…) | **422** | FastAPI/Pydantic |
| Por encima de `RATE_LIMIT_PER_MINUTE` | **429** | `security.py` |
| Fallo inesperado del agente o de la base | **500** (`detail` sin secretos) | `app.py` |
| Servicio sin `API_KEY` configurada (solo rutas protegidas) | **503** | `security.py` |
| El turno supera `ASK_TIMEOUT_SECONDS` | **504** | `app.py` |

Errores del `AgentService` que se devuelven como **409** (`detail` = código):

| Código del PB2 | Cuándo |
|---|---|
| `HITL_PENDING` | Se manda otra pregunta en un hilo con un plan sin resolver |
| `REQUEST_INCOMPLETE` | El hilo tiene una ejecución a medias → usar otro `thread_id` |
| `PLAN_NOT_CURRENT` | Decisión sobre un plan que ya no es el vigente |
| `PLAN_ALREADY_RESOLVED` | Decisión distinta sobre un plan ya resuelto |

**`AskOut.error`**: se rellena (`"ejecucion_incompleta"`) cuando el turno termina sin respuesta útil pero sin excepción. HTTP 200, `done=false`.

---

## 6. Seguridad y logs

- **CORS** abierto a lo que necesite el front (`CORS_ORIGINS`, lista separada por comas).
- **Un log por petición protegida** que llega a la ruta, con este formato:
  `POST /ask thread_id=demo-1 duration_ms=1234 status=200`
- **Nunca** en logs: `API_KEY`, la clave de Gemini ni `DATABASE_URL`.
- Los rechazos por clave (401/503) y por rate limit (429) se cortan antes de la ruta: los registra `security.py`.
- **429** se demuestra en local contra `GET …/messages` (no gasta LLM). En Render la variable queda puesta y documentada.
- **504** se demuestra en local bajando `ASK_TIMEOUT_SECONDS`; en Render se deja ~300 s.
  - El 504 corta la respuesta HTTP, pero el turno sigue ejecutándose en segundo plano hasta terminar, y entonces se guarda en Postgres (§4).
  - Mientras tanto, otra petición al mismo `thread_id` espera a que termine (limitación conocida → informe).

---

## 7. Interfaz interna API ↔ Postgres (para trabajar en paralelo)

`app.py` (David) llama a estas funciones; `src/db.py` + `src/models.py` (Miguel) las implementan. Cada función abre y cierra su propia sesión de SQLModel:

```python
def ensure_schema() -> None:
    """create_all al arrancar (lifespan)."""

def save_turn(thread_id: str, pregunta: str, respuesta: str) -> None:
    """Asegura la Conversation del thread_id, inserta user + assistant y hace commit."""

def list_messages(thread_id: str) -> list[dict]:
    """Mensajes del hilo en orden: dicts con role, content y created_at."""

def db_ok() -> bool:
    """SELECT 1 contra Postgres, para /health."""
```

Modelo de datos mínimo (SQLModel, `create_all` al arrancar):

| Tabla | Campos |
|---|---|
| `Conversation` | `id` = `thread_id` (PK), `created_at` |
| `Message` | `id` (PK), `thread_id` (FK), `role`, `content`, `created_at` |

`security.py` (Miguel) expone `require_api_key`, que `app.py` usa como `Depends(require_api_key)`. Lee `api_key` por **query** y aplica el rate limit.

---

## 8. Ciclo de vida y estado en memoria

- `AgentService` se crea **una sola vez** al arrancar FastAPI (`lifespan`) con `crear_servicio(modo=AGENT_MODE)` y se reutiliza en todas las peticiones. Si se creara por petición, `/approve` no encontraría el plan.
- En modo `real`, **si falta la clave de Gemini la API no arranca** y muestra un error claro (se ve en los logs del deploy).
- En memoria viven el `MemorySaver` (checkpoints del grafo) y la pregunta pendiente de cada hilo. **Un reinicio o un redeploy pierde un HITL a medias** → `/approve` devuelve 400 `HITL_NOT_PENDING`. El historial ya guardado en Postgres no se pierde.
- El free tier de Render se duerme tras un rato sin uso: también pierde los HITL a medias.

---

## 9. Variables de entorno de la API (`config.py` / panel de Render)

| Variable | Uso | Ejemplo local |
|---|---|---|
| `DATABASE_URL` | Postgres. `postgres://` se normaliza a `postgresql://` | `postgresql://postgres:postgres@localhost:5432/deportes` |
| `API_KEY` | Clave de la API (la de demo se envía al profesorado aparte) | `cambia-esto` |
| `GEMINI_API_KEY` | Clave de Gemini. `config.py` la copia a `GOOGLE_API_KEY`, que es el nombre que lee el código del PB2 | — |
| `GEN_PROVIDER`, `EMBED_PROVIDER`, `TAG_PROVIDER` | Deben ser `google` (por defecto el código del RAG usa `ollama`) | `google` |
| `AGENT_MODE` | `real` (Gemini + RAG) o `demo` (agente simulado, sin LLM, para probar la API) | `real` |
| `CORS_ORIGINS` | Orígenes permitidos | `http://localhost:8501` |
| `ASK_TIMEOUT_SECONDS` | Timeout de un turno | `300` |
| `RATE_LIMIT_PER_MINUTE` | Tope de peticiones por clave y minuto | `30` |

**Proveedor único: Gemini.** Sin Ollama ni HuggingFace en el servicio (Ollama no cabe en el free tier de Render y la demo va contra la URL pública).

---

## 10. Front Streamlit (`front/`)

Cliente HTTP de la API. **No importa `agentes/` ni ejecuta tools**: solo usa `requests`.

| Qué muestra | Ruta que llama |
|---|---|
| Estado del servicio y de Postgres | `GET /health` |
| Historial de la conversación | `GET /threads/{thread_id}/messages` |
| Chat (siempre con `auto_aprobar=false`) | `POST /ask` |
| Plan con botones Aprobar / Rechazar | `POST /approve` |
| `thread_id` visible y «Nueva conversación» (genera otro) | — |

Errores: se muestran como `Error XXX al <acción> — descripción`.

Variables (`front/.env`, plantilla en `front/.env.example`):

| Variable | Uso |
|---|---|
| `API_KEY` | La misma que la del servidor; viaja en `?api_key=` |
| `API_BASE_URL` | Local: `http://127.0.0.1:8000` · Demo: URL de Render |

---

## 11. Criterios de aceptación compartidos

- [ ] `/docs` lista las rutas y los schemas.
- [ ] `/health` responde 200 e indica `storage="postgres"`.
- [ ] Un `/ask` con clave devuelve `AskOut` y se nota una tool real (RAG o API externa).
- [ ] `auto_aprobar=false` deja `pendiente_hitl=true`; `/approve` aprueba o rechaza, y ambos casos quedan en el historial.
- [ ] Tras reiniciar el proceso, `GET …/messages` sigue devolviendo el turno.
- [ ] Dos `thread_id` distintos no mezclan mensajes.
- [ ] Se ven en local: 400, 401, 409, 422, 429 y 504.
- [ ] El front, apuntando a la API local, aprueba o rechaza un plan.

### Notas para el equipo

- El grafo y las tools del PB2 **no se reescriben**.
- El front **no importa** `agentes/` ni ejecuta tools: solo HTTP.
- **`api_key` en query, no en el body**: así Swagger puede enviarla.
- **`auto_aprobar` como interruptor**: un modo cómodo para Swagger y otro que obliga a pasar por el HITL del front.

---

## 12. Historial de versiones

### v3 — alineada con el código implementado
1. La pregunta pendiente del HITL vive **en memoria** (`app.py`), no en Postgres: desaparece `Conversation.pregunta_pendiente`.
2. Interfaz con Postgres simplificada: `ensure_schema()`, `save_turn()`, `list_messages()` y `db_ok()`, sin parámetro `session`.
3. `HITL_NOT_PENDING` pasa de 409 a **400**. Nuevo 400 para pregunta o `thread_id` solo con espacios.
4. Regla de guardado: cuando el turno ya no espera HITL y hay respuesta; se guarda dentro del hilo del agente, así que **un 504 ya no pierde el turno**.
5. En modo real, la API no arranca sin clave de Gemini.
6. Nuevas variables `GEMINI_API_KEY` (copiada a `GOOGLE_API_KEY`) y `AGENT_MODE` (`real`/`demo`).
7. Formato del log concretado. `GET /` redirige a `/docs`.
8. Nueva sección §10 sobre el front.

### v2 — ajustes tras leer el `AgentService` del PB2
1. `/health` ya no devuelve 503: siempre 200. El 503 aplica a rutas protegidas sin `API_KEY`.
2. Solo Gemini: fuera `LLM_PROVIDER`, Ollama y HuggingFace.
3. Añadidos `HealthOut`, la salida de `/approve` (`AskOut`) y el campo `plan` en `AskOut`.
4. Regla de guardado: al resolver el turno (aprobado o rechazado), no solo con `done=true`.
5. Pregunta pendiente del HITL guardada en `Conversation.pregunta_pendiente` (sustituido en v3).
6. Errores del `AgentService` → 409.
7. Interfaz interna API ↔ Postgres para que API y base avancen en paralelo.

### v1 — versión inicial de Héctor
