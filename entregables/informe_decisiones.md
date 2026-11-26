# Informe de decisiones — Project Break 3 (MLOps)

**Equipo:** Miguel López · David Cruz · Héctor González
**Dominio:** asistente de Deporte Municipal de Madrid (mismo que PB1 y PB2)
**URL del servicio:** _pendiente (Render)_

> Hilo del proyecto: **PB1** (RAG modular) → **PB2** (ese RAG como tool de un agente multiagente LangGraph) → **PB3** (ese agente publicado como servicio: API + PostgreSQL + Docker + Render).

---

## 1. Dibujo del sistema desplegado

```text
                    ┌──────────────────────────────┐
                    │  Front Streamlit (local)     │
                    │  front/streamlit_app.py      │
                    │  solo HTTP (requests)        │
                    └──────────────┬───────────────┘
                                   │ HTTPS  ·  API_BASE_URL = URL de Render
                                   │ ?api_key=...  (rutas protegidas)
                                   ▼
┌──────────────────────── Render · Web Service (1 contenedor Docker) ────────────────────────┐
│                                                                                              │
│  FastAPI (app.py)  ──►  AgentService del PB2  ──►  tools: RAG (Chroma, índice en la imagen)  │
│  /health /docs           grafo LangGraph              · API externa datos.madrid.es          │
│  /ask /approve           + MemorySaver (RAM)                                                 │
│  /threads/{id}/messages  límites en Python                                                   │
│                                                                                              │
└──────────────┬──────────────────────────────────────────────────┬────────────────────────────┘
               │ DATABASE_URL                                     │ GEMINI_API_KEY
               ▼                                                  ▼
┌──────────────────────────────┐                   ┌──────────────────────────────────┐
│ PostgreSQL managed (Render)  │                   │ Google Gemini                    │
│ Conversation · Message       │                   │ LLM del agente y embeddings      │
│ historial de producto        │                   │ de las consultas del RAG         │
└──────────────────────────────┘                   └──────────────────────────────────┘
```

**Qué hace cada pieza**

| Pieza | Dónde corre | Responsabilidad |
|---|---|---|
| Front Streamlit | Portátil del equipo | Interfaz: chat, plan con Aprobar/Rechazar, historial, estado del servicio. No importa el agente |
| FastAPI (`app.py`) | Web Service de Render | Traduce HTTP ↔ `AgentService`. Seguridad, timeout y logs. No reescribe el grafo |
| `AgentService` (PB2) | Mismo contenedor | Grafo multiagente con HITL. Una sola instancia por proceso |
| RAG + índice Chroma | Mismo contenedor (dentro de la imagen) | Tool documental del agente |
| PostgreSQL | Render (managed) | Historial de turnos cerrados. Sobrevive a reinicios y redeploys |
| Gemini | Servicio externo | LLM del agente y embeddings de las consultas |

**Flujo de un turno con HITL**

1. El front envía `POST /ask` con `auto_aprobar=false`.
2. La API llama a `procesar_turno()`; el grafo se para antes de `aplicar` y devuelve el plan (`pendiente_hitl=true`).
3. El usuario pulsa **Aprobar** o **Rechazar** → `POST /approve` → `resolver_plan()`.
4. La API guarda la pregunta y la respuesta en Postgres.
5. El front vuelve a pintar la conversación con `GET /threads/{id}/messages`.

---

## 2. Contrato: qué es público y qué lleva `api_key`

Contrato completo en [`docs/contrato_api.md`](../docs/contrato_api.md) (v3). Se escribió **antes** del código (SDD) y se actualizó cuando la implementación tomó decisiones nuevas; el historial de versiones está en su §12.

| Método | Ruta | Acceso | Por qué |
|---|---|---|---|
| GET | `/` | Público | Redirige a `/docs` |
| GET | `/health` | Público | Render y el profesorado comprueban si el servicio está vivo sin credenciales. Siempre 200 (`status` ok/degraded) |
| GET | `/docs` | Público | Swagger: documentación viva del contrato |
| POST | `/ask` | **`api_key`** | Gasta LLM: sin clave, cualquiera podría consumir la cuota de Gemini |
| POST | `/approve` | **`api_key`** | Cambia el estado de una conversación |
| GET | `/threads/{thread_id}/messages` | **`api_key`** | Expone el historial de los usuarios |

**Cómo se protege**

- La clave viaja en la **query** (`?api_key=...`), como pide el enunciado, para poder probarla en Swagger.
- Respuestas de la capa de seguridad: **401** (clave ausente o incorrecta), **503** (el servidor no tiene `API_KEY` configurada), **429** (rate limit).
- La clave del servicio y la de Gemini viven solo en el `.env` local y en el panel de Render; nunca en el repositorio ni en nuestros logs.

**Contrato de datos (resumen)**

| Schema | Campos |
|---|---|
| `AskIn` | `pregunta`, `thread_id`, `auto_aprobar` (por defecto `true`) |
| `AskOut` | `respuesta`, `thread_id`, `done`, `pendiente_hitl`, `plan`, `error` |
| `ApproveIn` | `thread_id`, `aprobado` |
| `MessageOut` | `role`, `content`, `created_at` |
| `HealthOut` | `status`, `storage`, `db_ok` |

---

## 3. Datos: qué hay en Postgres y qué se pierde al reiniciar

_Pendiente (Miguel)._

---

## 4. Prueba de vida

_Pendiente (Héctor): turno en la URL pública → redeploy → `GET /threads/{id}/messages` sigue devolviéndolo. Pegar aquí la URL enviada al profesorado._

---

## 5. Conclusiones de arquitectura y coste

_Pendiente (Héctor)._

---

## 6. Conclusiones de CI/CD

_Pendiente (Miguel)._

---

## 7. Tres fallos conocidos y qué haríamos después

_Pendiente de consolidar (Héctor). Candidatos detectados durante el desarrollo:_

- **La `api_key` aparece en el access log de uvicorn.** El enunciado pide la clave por query; uvicorn escribe la URL completa en su log. Propuesta: filtrar la clave en el log y aceptarla también en la cabecera `X-API-Key` (el front la enviaría así).
- **Un reinicio o redeploy pierde el HITL a medias.** El checkpoint del grafo vive en `MemorySaver` (RAM); `/approve` responde 400 `HITL_NOT_PENDING`. El historial en Postgres sí se conserva.
- **Un 504 puede perder el turno del historial.** Python no puede matar el hilo: el agente sigue trabajando en segundo plano (y gastando cuota), pero el guardado en PostgreSQL se hace en la ruta, después de responder, así que ese turno **no queda garantizado en el historial**. Mientras tanto, otra petición al mismo hilo espera. Mejora: guardar el turno dentro del propio hilo del agente.

---

## 8. Decisiones técnicas

_Base redactada por Héctor; actualizada al código final de `development`._

### D1. FastAPI como framework de la API
- **Decisión:** FastAPI + uvicorn para exponer el agente del PB2.
- **Por qué:** genera Swagger (`/docs`) solo a partir del contrato, valida con Pydantic (422 automático) y es el framework visto en los workouts.
- **Alternativas descartadas:** Flask (sin validación ni Swagger automáticos) y Django (demasiado pesado para una API pequeña).

### D2. PostgreSQL con SQLModel para el historial
- **Decisión:** historial en PostgreSQL con SQLModel (`src/models.py`, `src/db.py`). **Sin respaldo en SQLite:** sin `DATABASE_URL` la API no arranca.
- **Tablas:** `Conversation` (`id`, `thread_id` único) y `Message` (`conversation_id` → FK, `role`, `content`, `created_at`).
- **Por qué:** el historial tiene que sobrevivir a reinicios y redeploys; el disco de Render no es persistente.
- El RAG sigue usando Chroma (dentro de la imagen) para los embeddings: Postgres es solo para el historial.

### D3. Seguridad: API key, rate limit y timeout
| Capa | Dónde | Código |
|---|---|---|
| API key por query (`?api_key=`) | `security.py` → `require_api_key` | 401 (ausente o incorrecta), 503 (servidor sin `API_KEY`) |
| Rate limit, ventana de 60 s; cliente = hash de la clave válida o, si no, IP (aceptado por el equipo) | `security.py` → `RateLimitMiddleware` | 429 con `Retry-After` |
| Timeout por turno | `app.py` (hilo con `ASK_TIMEOUT_SECONDS`) | 504 |

- CORS configurable con `CORS_ORIGINS`. Logs con método, ruta, `thread_id`, `duration_ms` y status, sin secretos.

### D4. Proveedor único: Google Gemini
- **Decisión:** solo Gemini, para generación, etiquetado y embeddings (`gemini-3.6-flash` y `gemini-embedding-2`).
- **Por qué:** Ollama no cabe en el free tier de Render y la demo va contra la URL pública.
- **Clave:** `GEMINI_API_KEY` en el panel; `config.py` la copia a `GOOGLE_API_KEY`, que es el nombre que lee el código del PB2.

### D5. HITL con `auto_aprobar` como interruptor
- `true` → la API aprueba sola el plan (cómodo en Swagger). `false` → devuelve `pendiente_hitl=true` y el `plan`; el front decide con `/approve`.
- **Regla de guardado:** el turno se guarda cuando ya no espera decisión humana y hay respuesta (aprobado, rechazado o sin plan). Limitación: si la petición acaba en 504, no está garantizado que el turno se guarde (ver §7).

### D6. La API adapta; el agente decide
- `app.py` no reescribe el grafo: llama al `AgentService` del PB2 (`procesar_turno`, `resolver_plan`, `consultar_estado`). El RAG y la API del Ayuntamiento siguen siendo **tools** del agente.
- Una sola instancia del agente por proceso (`lifespan`): si se creara por petición, `/approve` no encontraría el plan.

### D7. Docker y Render
- **Imagen única** (`python:3.12-slim`) con la API, el agente, el corpus y el **índice del RAG construido en el `docker build`**.
- La clave de Gemini llega al build como **build secret** (Secret File `gemini_api_key` en Render): no queda en la imagen, ni en su historial, ni en los logs.
- `CMD` con `${PORT:-8000}` (Render inyecta `PORT`). **Pendiente** (PR #13): `--proxy-headers --forwarded-allow-ips="*"` para obtener la IP real del usuario tras el proxy de Render.
- El índice se construye en una capa propia, antes de copiar el resto del código: cambiar `app.py` no obliga a re-indexar.

### D8. Contrato HTTP con Pydantic (`schemas.py`)
- `AskIn`, `AskOut`, `ApproveIn`, `MessageOut` y `HealthOut`, definidos **antes** del código en `docs/contrato_api.md` (SDD) y actualizados con la implementación (v3.1).

