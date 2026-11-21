# Contrato público de la API — Project Break 3 (MLOps)

> Acuerdo escrito **antes** de escribir código (Spec-Driven Development), para que los tres bloques (API, Postgres, Docker/Render) trabajen en paralelo sin pisarse.
>
> Primero lo que la API acepta y devuelve; después cómo se conecta por dentro con el agente del PB2 y con Postgres.
>
> **Versión 2.** Base de Héctor + ajustes de David tras leer el `AgentService` del PB2 (ver §11, "Cambios respecto a la v1").

---

## 1. Diagrama del sistema

```text
Front Streamlit (local)          ← solo habla HTTP, no importa el grafo
│  HTTPS   API_BASE_URL = URL de Render
▼
FastAPI (app.py)  ──►  AgentService del PB2  ──►  RAG + API externa
│                      (una sola instancia,       (tools reales)
│                       MemorySaver en memoria)
├── GET  /health                        público
├── GET  /docs                          público (Swagger)
├── POST /ask                           api_key -> AskOut
├── POST /approve                       api_key -> AskOut
└── GET  /threads/{thread_id}/messages  api_key -> list[MessageOut]
│
│  DATABASE_URL
▼
PostgreSQL managed (Render) — historial de producto
```

---

## 2. Tabla de rutas

| Método | Ruta | `api_key` | Qué hace | Respuesta |
|--------|------|-----------|----------|-----------|
| GET  | `/health` | No | Pulso. Indica que el almacenamiento es Postgres | `HealthOut` |
| GET  | `/docs` | No | Swagger con los schemas | HTML |
| POST | `/ask` | Sí | Un turno del agente | `AskOut` |
| POST | `/approve` | Sí | HITL: aprobar o rechazar el plan pendiente | `AskOut` |
| GET  | `/threads/{thread_id}/messages` | Sí | Historial del hilo, leído de Postgres | `list[MessageOut]` |

**Regla de acceso:** `/health` y `/docs` son públicos. El resto exige `api_key` como parámetro de **query** (`?api_key=...`), para poder probarlo desde Swagger.

---

## 3. Schemas Pydantic (`schemas.py`)

### 3.1 `AskIn` — entrada de `POST /ask`

```python
class AskIn(BaseModel):
    pregunta: str = Field(..., min_length=1)    # vacía -> 422
    thread_id: str = Field(..., min_length=1)   # lo genera el front (uuid)
    auto_aprobar: bool = True                   # cómodo en Swagger
```

### 3.2 `AskOut` — salida de `POST /ask` y de `POST /approve`

```python
class AskOut(BaseModel):
    respuesta: str                 # final_answer del agente
    thread_id: str
    done: bool                     # True solo si el plan se aprobó y se cerró
    pendiente_hitl: bool           # True -> el front debe llamar a /approve
    plan: list[str] = []           # viñetas del plan, para enseñarlas antes de aprobar
    error: Optional[str] = None    # ver §5
```

> `plan` no está en el enunciado, pero el front lo necesita para mostrar qué se aprueba. Añadir un campo no rompe el contrato.

### 3.3 `ApproveIn` — entrada de `POST /approve`

```python
class ApproveIn(BaseModel):
    thread_id: str = Field(..., min_length=1)
    aprobado: bool                 # True aprueba, False rechaza
```

> El `AgentService` del PB2 exige un `plan_id` en `resolver_plan()`. **No se expone**: la API lo lee internamente con `consultar_estado(thread_id)["plan_id"]`.

### 3.4 `MessageOut` — unidad del historial

```python
class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime           # orden temporal; la lista ya viene ordenada
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
- Hace un `SELECT 1` contra Postgres: `db_ok=True` -> `status="ok"`; si falla -> `status="degraded"`, `db_ok=False`.

### `POST /ask`

Cómo se comporta el agente del PB2: si hay plan, el grafo **siempre se para antes de `aplicar`** (HITL). Por tanto:

| `auto_aprobar` | Qué hace la API | Respuesta típica |
|---|---|---|
| `true` | `procesar_turno()` y, si queda en HITL, `resolver_plan(aprobado=True)` en la misma petición | `done=true`, `pendiente_hitl=false` |
| `false` | Solo `procesar_turno()` | `done=false`, `pendiente_hitl=true`, `plan=[...]` |

Pasos:
1. Asegura la `Conversation` de ese `thread_id`.
2. Ejecuta el turno.
3. Si el turno **queda resuelto** -> guarda `user` + `assistant` y hace commit.
4. Si queda en HITL (`auto_aprobar=false`) -> guarda la pregunta en `Conversation.pregunta_pendiente`. **No guarda mensajes todavía.**

### `POST /approve`
1. Lee el `plan_id` vigente con `consultar_estado(thread_id)`.
2. Llama a `resolver_plan(thread_id, aprobado, plan_id=...)`.
3. Guarda `user` (desde `pregunta_pendiente`) + `assistant` (respuesta final), limpia `pregunta_pendiente` y hace commit.
4. Devuelve `AskOut`:
   - aprobado -> `done=true`, `respuesta` = respuesta + "Plan informativo aprobado…"
   - rechazado -> `done=false`, `pendiente_hitl=false`, `respuesta="Propuesta rechazada. Puedes enviar un nuevo pedido."`

### Regla de guardado (importante para Postgres)
> **Se guarda cuando el turno se resuelve (aprobado o rechazado), no cuando `done=true`.**
> En el PB2, `aplicar` devuelve `done=False` al rechazar. Si se guardara solo con `done`, los rechazos nunca llegarían al historial.

### `GET /threads/{thread_id}/messages`
- Devuelve los mensajes del hilo en orden temporal. Hilo inexistente -> `[]` (200).
- Lee de Postgres, nunca de memoria. Dos `thread_id` distintos no se mezclan.

---

## 5. Códigos HTTP y errores

| Situación | Código | Quién |
|-----------|--------|-------|
| Sin `api_key` o clave incorrecta en ruta protegida | **401** | `security.py` |
| Servicio sin `API_KEY` configurada (solo rutas protegidas) | **503** | `security.py` |
| Body inválido (falta campo, pregunta vacía…) | **422** | FastAPI/Pydantic |
| Conflicto de estado del HITL (ver tabla de abajo) | **409** | `app.py` |
| Por encima de `RATE_LIMIT_PER_MINUTE` | **429** | `security.py` |
| El turno supera `ASK_TIMEOUT_SECONDS` | **504** | `security.py` / `app.py` |
| Fallo inesperado del agente o de la base | **500** (mensaje sin secretos) | `app.py` |

Errores del `AgentService` que se devuelven como **409** (`detail` = código):

| Código del PB2 | Cuándo |
|---|---|
| `HITL_PENDING` | Se manda otra pregunta en un hilo con un plan sin resolver |
| `REQUEST_INCOMPLETE` | El hilo tiene una ejecución a medias -> usar otro `thread_id` |
| `HITL_NOT_PENDING` | `/approve` sin plan pendiente (también tras reiniciar el servicio) |
| `PLAN_NOT_CURRENT` / `PLAN_ALREADY_RESOLVED` | Decisión sobre un plan antiguo o ya resuelto |

**`AskOut.error`**: se rellena cuando el turno termina sin respuesta útil pero sin excepción (p. ej. `ejecucion_incompleta`). HTTP 200, `done=false`.

---

## 6. Seguridad y logs

- **CORS** abierto a lo que necesite el front (`CORS_ORIGINS`, lista separada por comas).
- **Un log por petición protegida**: método, ruta, `thread_id`, `duration_ms`, status.
- **Nunca** en logs: `API_KEY`, la clave del LLM ni `DATABASE_URL`.
- **429** se demuestra en local contra `GET …/messages` (no gasta LLM). En Render la variable queda puesta y documentada.
- **504** se demuestra en local bajando `ASK_TIMEOUT_SECONDS`; en Render se deja ~300 s.
  - Nota: el 504 corta la respuesta HTTP, pero el turno sigue ejecutándose en segundo plano hasta terminar (limitación conocida -> informe).

---

## 7. Interfaz interna API ↔ Postgres (para trabajar en paralelo)

`app.py` (David) llama a estas funciones; `src/db.py` + `src/models.py` (Miguel) las implementan. Firmas acordadas:

```python
def asegurar_conversacion(session, thread_id: str) -> None: ...
def guardar_pregunta_pendiente(session, thread_id: str, pregunta: str) -> None: ...
def leer_pregunta_pendiente(session, thread_id: str) -> str | None: ...
def guardar_turno(session, thread_id: str, pregunta: str, respuesta: str) -> None:
    """Inserta user + assistant, limpia pregunta_pendiente y hace commit."""
def listar_mensajes(session, thread_id: str) -> list[Message]: ...
def db_ok(session) -> bool: ...   # SELECT 1 para /health
```

Modelo de datos mínimo propuesto (SQLModel, `create_all` al arrancar):

| Tabla | Campos |
|---|---|
| `Conversation` | `thread_id` (PK), `created_at`, `pregunta_pendiente` (nullable) |
| `Message` | `id` (PK), `thread_id` (FK), `role`, `content`, `created_at` |

---

## 8. Ciclo de vida y estado en memoria

- `AgentService` se crea **una sola vez** al arrancar FastAPI (`lifespan`) con `crear_servicio(modo="real")` y se reutiliza en todas las peticiones. Si se creara por petición, `/approve` no encontraría el plan.
- `MemorySaver` (checkpoints del grafo) sigue en memoria. **Un reinicio o un redeploy pierde un HITL a medias** -> `/approve` devuelve 409 `HITL_NOT_PENDING`. El historial SQL no se pierde.
- El free tier de Render se duerme tras un rato sin uso: también pierde los HITL a medias.

---

## 9. Variables de entorno (`config.py` / panel de Render)

| Variable | Uso | Ejemplo local |
|---|---|---|
| `DATABASE_URL` | Postgres. `postgres://` se normaliza a `postgresql://` | `postgresql://postgres:postgres@localhost:5432/deportes` |
| `API_KEY` | Clave de la API (la de demo se envía al profesorado aparte) | `cambia-esto` |
| `GOOGLE_API_KEY` | Gemini. **Es el nombre que ya lee el código del PB2** (`rag/config.py`) | — |
| `GEN_PROVIDER`, `EMBED_PROVIDER`, `TAG_PROVIDER` | Deben ser `google` (por defecto el código usa `ollama`) | `google` |
| `CORS_ORIGINS` | Orígenes permitidos | `http://localhost:8501` |
| `ASK_TIMEOUT_SECONDS` | Timeout de un turno | `300` |
| `RATE_LIMIT_PER_MINUTE` | Tope de peticiones | `30` |

**Proveedor único: Gemini.** Sin Ollama ni HuggingFace (Ollama no cabe en el free tier de Render y la demo va contra la URL pública).

---

## 10. Criterios de aceptación compartidos

- [ ] `/docs` lista las rutas y los schemas.
- [ ] `/health` responde 200 e indica `storage="postgres"`.
- [ ] Un `/ask` con clave devuelve `AskOut` y se nota una tool real (RAG o API externa).
- [ ] `auto_aprobar=false` deja `pendiente_hitl=true`; `/approve` aprueba o rechaza, y ambos casos quedan en el historial.
- [ ] Tras reiniciar el proceso, `GET …/messages` sigue devolviendo el turno.
- [ ] Dos `thread_id` distintos no mezclan mensajes.
- [ ] Se ven en local: 401, 422, 409, 429 y 504.
- [ ] El front, apuntando a la API local, aprueba o rechaza un plan.

---

## 11. Notas para el equipo

- El grafo y las tools del PB2 **no se reescriben**.
- El front **no importa** `agentes/` ni ejecuta tools: solo HTTP.
- **`api_key` en query, no en el body**: así Swagger puede enviarla.
- **`auto_aprobar` como interruptor**: un modo cómodo para Swagger y otro que obliga a pasar por el HITL del front.

### Cambios respecto a la v1
1. `/health` ya no devuelve 503: siempre 200. El 503 aplica a rutas protegidas sin `API_KEY`.
2. Solo Gemini: fuera `LLM_PROVIDER`, Ollama y HuggingFace. Variable real: `GOOGLE_API_KEY`.
3. Añadidos `HealthOut`, la salida de `/approve` (`AskOut`) y el campo `plan` en `AskOut`.
4. Regla de guardado: al resolver el turno (aprobado o rechazado), no solo con `done=true`.
5. Pregunta pendiente del HITL guardada en `Conversation.pregunta_pendiente`.
6. Errores del `AgentService` -> 409.
7. Interfaz interna API ↔ Postgres (§7) para que API y base avancen en paralelo.
