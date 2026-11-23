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
- **Un 504 no detiene al agente.** Python no puede matar el hilo: el turno termina en segundo plano (sigue gastando cuota) y se guarda al acabar; mientras tanto, otra petición al mismo hilo espera.
