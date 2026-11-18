# Contrato público de la API — Project Break 3 (MLOps)

> Acuerdo escrito **antes** de escribir código, para que los tres bloques (API, Postgres, Docker/Render) trabajen sin reescribirse ni pisarse.
>
> Primero lo que la API acepta y devuelve, luego el motor del agente por dentro.

---

## 1. Diagrama del flujo de contrato

```text
Front Streamlit (local)
│ HTTPS API_BASE_URL = URL de Render
▼
FastAPI ← agente PB2 ← RAG
│
├── GET /health (público)
├── GET /docs (público, Swagger)
├── POST /ask (api_key) → AskOut
├── POST /approve (api_key) → HITL
└── GET /threads/{id}/messages (api_key) → historial de Postgres
▼
PostgreSQL managed (Render)
```  

---

## 2. Tabla de rutas (el contrato HTTP)

| Método | Ruta | ¿`api_key`? | Qué hace |
|--------|------|------------|----------|
| GET    | `/health`  | No | Pulso. Indica que el almacenamiento es Postgres |
| GET    | `/docs`    | No | Swagger con los schemas |
| POST   | `/ask`     | Sí | Un turno del agente |
| POST   | `/approve` | Sí | HITL: aprobar o rechazar el plan |
| GET    | `/threads/{thread_id}/messages` | Sí | Historial leído de Postgres |

**Regla de acceso:** `/health` y `/docs` son públicos. El resto exige `api_key` como parámetro de **query** (así Swagger puede autocompletarlo).
* Sin clave → **401**.
* Body inválido → **422** (FastAPI lo hace por defecto).

---

## 3. Contratos Pydantic (lo que entra y sale)

### 3.1 `AskIn` - entrada de `POST /ask`

```python
class AskIn(BaseModel):
    pregunta: str                  # obligatoria
    thread_id: str                 # obligatoria (clave del hilo)
    auto_aprobar: bool = True      # por defecto True → cómodo en Swagger
```  

* Con auto_aprobar=true: si el grafo queda en HITL, la API cierra el turno sola.
* Con auto_aprobar=false: la respuesta vuelve con pendiente_hitl=true y el front llama a /approve.

### 3.2 `AskOut` - salida de `POST /ask`

```python  
class AskOut(BaseModel):
    respuesta: str
    thread_id: str
    done: bool                 # el turno quedó cerrado?
    pendiente_hitl: bool       # espera decisión humana?
    error: Optional[str] = None
``` 

### 3.3 `ApproveIn` - entrada de `POST /approve` 

```python  
class ApproveIn(BaseModel):
    thread_id: str
    aprobado: bool             # True = aprueba el plan, False = rechaza
``` 

### 3.4 `MessageOut` - unidad de historial (para `GET /threads/{id}/messages`)

```python  
class MessageOut(BaseModel):
    role: str                  # "user" | "assistant"
    content: str
    order: int                 # orden temporal dentro del hilo
``` 

## 4. Comportamiento por ruta

`GET /health`
* Público. Devuelve estado vivo y confirma que el almacenamiento es Postgres.
* Si el servicio está sin `API_KEY` configurada → 503.

`POST /ask` 
1. Asegura la conversación de ese `thread_id`.
2. Ejecuta el turno del agente PB2.
3. Si el turno queda cerrado (`done`): guarda **user + assistant** y hace commit.
4. Si el turno queda en HITL y `auto_aprobar=false`: `pendiente_hitl=true`.

`POST /approve`
* Llama a la decisión humana del PB2. Aprobado o rechazado.

`GET /threads/{thread_id}/messages`
* Devuelve los mensajes de ese hilo en orden (order).
* Lee de Postgres, no de una lista solo en memoria del front.

## 5. Códigos de error y seguridad

| Situación | Código |
|-----------|--------|
| Sin `api_key` o clave incorrecta en ruta protegida | **401** |
| Servicio sin `API_KEY` configurada | **503** |
| Por encima de `RATE_LIMIT_PER_MINUTE` | **429** |
| El turno supera `ASK_TIMEOUT_SECONDS` | **504** |

* **CORS** abierto a lo que necesite el front (`CORS_ORIGINS`).
* Log por petición protegida: método, ruta, `thread_id`, `duration_ms`, status.
* Sin `API_KEY`, sin la clave del LLM y sin la connection string.
* El **429** se demuestra en local contra una ruta que no gasta LLM (`GET …/messages` vale). En Render la variable queda puesta y documentada.
* El **504** se demuestra en local bajando el timeout; en Render se deja un valor con margen para un turno real del multiagente.


## 6. Criterios de aceptación compartidos

- [ ] `/docs` lista las rutas y los schemas.
- [ ] Un `/ask` con clave devuelve `AskOut` y se nota una tool real (RAG/API).
- [ ] `auto_aprobar=false` deja `pendiente_hitl=true`; `/approve` cierra o rechaza.
- [ ] Tras reiniciar el proceso, `GET .../messages` sigue devolviendo el turno.
- [ ] Dos `thread_id` distintos no mezclan mensajes.
- [ ] Se ven en local: 401, 429 y 504.
- [ ] El fron, apuntando a la API local, aprueba o rechaza un plan.

## 7. Notas para el equipo

* El grafo del PB02 y las tools no se reescriben en este bloque.
* El front no import `graph.py` ni ejecuta tools: solo habla HTTP.
* `MemorySaver` sigue el memoria; el historial de producto pasa a PostGres. Un reinicio pierde HITL a medias, pero el historial SQL no.

## 8. Variables de entorno (para `config.py` / Render)

* `DATABASE_URL` 
* `API_KEY` 
* `LLM_PROVIDER`          # "google"
* clave del LLM según el proveedor:
    - actualmente `GEMINI_API_KEY` para provedor "google"
* `CORS_ORIGINS`  
* `ASK_TIMEOUT_SECONDS`  
* `RATE_LIMIT_PER_MINUTE` 


## 9. Un par de cuestiones didácticas

> - **`api_key` en query, no en el body.** Se hace así a propósito para que **Swagger** pueda autocompletar la clave al hacer la petición. Si se pusiera en el body, el editor de documentación no la vería y nadie podría probarlo. Es una decisión de diseño, no casual.
> - **`auto_aprobar` como interruptor.** Permite dos modos con el mismo endpoint: uno cómodo para probar (cerrar solo) y otro que obliga a pasar por el front para la aprobación humana (HITL).
> - **Un solo proveedor activo por vez.** La variable `LLM_PROVIDER` elige cuál se usa en cada arranque; no se ejecutan dos a la vez.
> - **Ollama no necesita clave.** Al ser local, la única diferencia con HuggingFace es el endpoint y (opcionalmente) una clave, no el flujo de la API.