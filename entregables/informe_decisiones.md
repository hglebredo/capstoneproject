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

### 3.1. Persistencia de conversaciones en PostgreSQL

El proyecto utiliza PostgreSQL como sistema de persistencia para almacenar el historial de conversaciones generado a través de la API.

La implementación se desarrolló principalmente en los archivos `src/db.py` y `src/models.py`, utilizando SQLModel y SQLAlchemy para definir los modelos y gestionar las operaciones con la base de datos.

El objetivo es separar el almacenamiento persistente del estado temporal que mantiene el agente durante la ejecución.

### 3.2. Estructura de los datos

La base de datos utiliza dos entidades principales:

**Conversation**

Representa una conversación o hilo del agente.

Sus campos principales son:

- `id`: identificador interno y clave primaria.
- `thread_id`: identificador del hilo, único e indexado.
- `created_at`: fecha de creación en UTC.
- `messages`: relación con los mensajes de la conversación.

**Message**

Representa cada mensaje perteneciente a una conversación.

Sus campos principales son:

- `id`: identificador interno y clave primaria.
- `conversation_id`: clave foránea que referencia a la conversación.
- `role`: rol del mensaje, por ejemplo `user` o `assistant`.
- `content`: contenido del mensaje.
- `created_at`: fecha de creación en UTC.

La relación entre ambas entidades es de uno a muchos: una conversación puede contener varios mensajes.

Esta estructura permite mantener el historial organizado, recuperar los mensajes de un hilo y separar conversaciones diferentes.

### 3.3. Operaciones de persistencia

La lógica de acceso a PostgreSQL se centraliza en `src/db.py`.

Se implementaron las siguientes operaciones:

**`ensure_schema()`**

Inicializa el esquema y crea las tablas necesarias mediante SQLModel. Se ejecuta durante el arranque de FastAPI.

**`save_turn()`**

Almacena un turno completo de conversación. Recibe el identificador del hilo, la pregunta del usuario y la respuesta del asistente.

Su funcionamiento es:

1. Busca la conversación correspondiente al `thread_id`.
2. Si no existe, crea una nueva.
3. Inserta el mensaje del usuario.
4. Inserta el mensaje del asistente.
5. Confirma ambas inserciones mediante una transacción.

Si se produce un error, se ejecuta rollback para evitar dejar una operación parcialmente confirmada.

**`list_messages()`**

Recupera los mensajes asociados a un `thread_id`, devolviendo su rol, contenido y fecha de creación.

Los mensajes se devuelven ordenados por identificador. Si el hilo no existe, devuelve una lista vacía.

**`db_ok()`**

Comprueba la disponibilidad de PostgreSQL mediante una consulta `SELECT 1`. Devuelve `True` si la comprobación se realiza correctamente y `False` si se produce un error.

### 3.4. Configuración y conexión

La conexión se configura mediante la variable de entorno `DATABASE_URL`.

La implementación contempla:

- Normalización de las URL de PostgreSQL para utilizar el controlador psycopg 3.
- Creación del engine bajo demanda.
- Protección frente a inicializaciones concurrentes mediante un bloqueo.
- Comprobación de conexiones del pool mediante `pool_pre_ping`.
- Tiempo máximo de conexión y espera del pool.
- Gestión de sesiones mediante un context manager con commit y rollback.

También se implementó `_set_engine_for_tests()` para permitir inyectar un engine alternativo durante las pruebas, facilitando la validación de las operaciones de persistencia.

### 3.5. Qué información permanece guardada al reiniciar

PostgreSQL almacena el historial de conversaciones y mensajes que la aplicación ha guardado mediante `save_turn()`.

Por tanto, después de reiniciar el proceso de FastAPI, se puede volver a consultar el historial mediante:

`GET /threads/{id}/messages`

Durante las pruebas se comprobó que los mensajes seguían disponibles después de detener y volver a iniciar Uvicorn.

Esto demuestra que el historial almacenado en PostgreSQL no depende exclusivamente de la memoria del proceso de la API.

### 3.6. Qué información se pierde al reiniciar

No todo el estado del agente se almacena en PostgreSQL.

El estado de una aprobación pendiente del flujo Human-in-the-Loop (HITL) se mantiene en memoria durante la ejecución de la aplicación.

En consecuencia, si se reinicia el proceso de FastAPI o se produce un redeploy, una aprobación que todavía estaba pendiente puede perderse.

La diferencia es la siguiente:

| Información | Dónde se mantiene | ¿Sobrevive al reinicio de la API? |
|---|---|---|
| Conversaciones guardadas | PostgreSQL | Sí |
| Mensajes del usuario | PostgreSQL | Sí |
| Respuestas del asistente guardadas | PostgreSQL | Sí |
| Estado de una aprobación HITL pendiente | Memoria del proceso | No |
| Historial recuperable mediante `thread_id` | PostgreSQL | Sí |

Por tanto, PostgreSQL proporciona persistencia para el historial, pero no supone que todo el estado interno del agente sea persistente.

Esta limitación es especialmente relevante en entornos como Render, donde un reinicio o redeploy puede provocar la pérdida del estado temporal que todavía no se haya guardado.

### 3.7. Validación de la persistencia

La implementación se validó mediante pruebas automatizadas y comprobaciones manuales.

**Pruebas automatizadas de base de datos**

Archivo: `tests/test_db.py`

Resultado:

`11 passed, 17 warnings`

Se comprobaron la creación de tablas, el guardado de mensajes, la reutilización de conversaciones, la recuperación del historial, el aislamiento entre hilos, las fechas explícitas, la comprobación de disponibilidad y la normalización de URL.

**Pruebas de integración con PostgreSQL real**

Archivo: `tests/test_persistencia.py`

Resultados obtenidos:

- `test_persistencia_real_guarda_y_recupera`: PASSED.
- `test_persistencia_real_sobrevive_a_nueva_sesion`: PASSED.
- `test_persistencia_real_db_ok`: PASSED.
- `test_persistencia_real_hilo_inexistente`: PASSED.

Resultado:

`4 passed, 17 warnings in 0.57s`

**Comprobaciones manuales**

También se realizaron las siguientes validaciones:

- Conexión directa con PostgreSQL mediante psycopg, obteniendo `CONEXION OK`.
- Arranque de FastAPI con inicialización del esquema.
- Comprobación de `/health`, obteniendo `db_ok: true`.
- Ejecución de `/ask` en modo demo.
- Recuperación de los mensajes mediante `/threads/{id}/messages`.
- Comprobación de que un hilo inexistente devuelve `[]`.
- Validación del flujo HITL y almacenamiento del turno después de su aprobación.
- Reinicio de Uvicorn y recuperación posterior del historial.
- Comprobación de que una aprobación pendiente antes del reinicio devuelve `HITL_NOT_PENDING` después de reiniciar.

Las pruebas de `/ask` se realizaron en modo demo, por lo que validan la integración de la API y la persistencia, no el funcionamiento de un flujo RAG real.

### 3.8. Conclusión del apartado

La solución implementada permite almacenar y recuperar de forma persistente las conversaciones del agente mediante PostgreSQL. La separación entre el historial persistente y el estado temporal del agente permite identificar claramente qué información sobrevive a un reinicio y qué información debe gestionarse de otra forma si se desea conservarla.

La principal limitación identificada es que el estado de una aprobación HITL pendiente se mantiene en memoria y no se recupera automáticamente después de reiniciar la aplicación.

## 4. Prueba de vida

_Pendiente (Héctor): turno en la URL pública → redeploy → `GET /threads/{id}/messages` sigue devolviéndolo. Pegar aquí la URL enviada al profesorado._

---

## 5. Conclusiones de arquitectura y coste

_Pendiente (Héctor)._

---

## 6. Conclusiones de CI/CD

### 6.1. Introducción

El proyecto utiliza un flujo de trabajo basado en Git y GitHub para organizar el desarrollo, integrar las contribuciones de los distintos miembros del equipo y preparar la aplicación para su despliegue.

El proceso CI/CD tiene como finalidad automatizar, en la medida de lo posible, la validación del código y facilitar la publicación de una versión funcional de la API.

En este proyecto se distinguen dos partes:

- **Continuous Integration (CI):** integración de cambios, instalación de dependencias y ejecución de pruebas para comprobar que las modificaciones no rompen el funcionamiento existente.
- **Continuous Delivery / Deployment (CD):** preparación y publicación de la aplicación en un entorno de ejecución, utilizando Docker y Render.

### 6.2. Integración continua (CI)

El desarrollo se organiza mediante ramas de Git y Pull Requests.

Cada integrante trabaja en su propia rama y posteriormente propone la incorporación de los cambios a la rama de desarrollo.

Este procedimiento permite:

- Separar las tareas de cada miembro.
- Revisar los cambios antes de integrarlos.
- Resolver conflictos entre implementaciones.
- Mantener un historial de modificaciones.
- Identificar qué contribuciones forman parte de la versión compartida.

En el caso de la contribución de PostgreSQL y seguridad, los cambios se integraron mediante la Pull Request #12, asociada al commit:

`7a21e68 – PostgreSQL, persistencia y seguridad de la API (Miguel)`

El proyecto dispone también de pruebas automatizadas para comprobar distintos componentes:

- Pruebas de seguridad mediante `tests/test_security.py`.
- Pruebas de persistencia mediante `tests/test_db.py`.
- Pruebas de integración con PostgreSQL real mediante `tests/test_persistencia.py`.

Estas pruebas permiten validar el comportamiento de la aplicación antes de incorporar cambios.

Durante el desarrollo se ejecutaron las tres suites y se obtuvieron 24 pruebas aprobadas en total.

**Estado de la automatización CI:** se dispone de pruebas automatizadas y de un flujo de integración mediante Git y Pull Requests. Sin embargo, con las evidencias disponibles no se puede afirmar que exista un workflow de GitHub Actions que ejecute automáticamente todas las pruebas en cada Pull Request.

Para completar la integración continua automatizada sería recomendable incorporar un workflow que:

1. Se ejecute al abrir o actualizar una Pull Request.
2. Configure la versión de Python utilizada por el proyecto.
3. Instale las dependencias de `requirements.txt`.
4. Configure las variables de entorno necesarias para los tests.
5. Prepare PostgreSQL como servicio cuando se ejecuten las pruebas de integración.
6. Ejecute las pruebas mediante `pytest`.
7. Informe del resultado y bloquee la integración si las comprobaciones obligatorias fallan.

### 6.3. Despliegue continuo (CD)

Para preparar el despliegue de la aplicación se utiliza Docker, lo que permite definir el entorno de ejecución y empaquetar las dependencias necesarias.

El proyecto dispone de un Dockerfile con los ajustes necesarios para ejecutar la API en el entorno de despliegue.

Entre los aspectos contemplados se encuentran:

- Instalación de dependencias.
- Configuración del puerto de ejecución mediante la variable `PORT`.
- Inclusión de los elementos necesarios para el funcionamiento del proyecto.
- Preparación del arranque de la aplicación mediante Uvicorn.
- Configuración del entorno para su ejecución en Render.

También se han realizado cambios relacionados con la preparación del índice RAG y los modelos de Gemini durante la construcción de la imagen Docker.

**Infraestructura de despliegue**

La decisión acordada por el equipo es desplegar en Render únicamente:

- La API desarrollada con FastAPI.
- La base de datos PostgreSQL.

Streamlit queda fuera del despliegue, de acuerdo con el alcance establecido para el proyecto.

La aplicación utiliza variables de entorno para configurar aspectos como la conexión con PostgreSQL, las credenciales de acceso y el modo de funcionamiento del agente.

La configuración debe realizarse en el entorno de despliegue sin incorporar credenciales reales al repositorio.

**Estado del despliegue automático:** el proyecto cuenta con preparación mediante Docker y con una arquitectura prevista para Render. No obstante, las evidencias disponibles no permiten asegurar que exista un despliegue automático configurado para cada merge en la rama de desarrollo.

### 6.4. Relación entre CI/CD y la arquitectura del proyecto

La arquitectura facilita la integración y el despliegue al mantener separadas las distintas responsabilidades:

- FastAPI expone los endpoints.
- El servicio del agente conserva la lógica de ejecución.
- PostgreSQL almacena el historial de conversaciones.
- Docker define el entorno de ejecución.
- Render proporciona el entorno de despliegue de la API y la base de datos.

La configuración mediante variables de entorno permite adaptar la aplicación a distintos entornos sin modificar el código fuente.

Además, las pruebas automatizadas proporcionan una base para verificar que las operaciones de persistencia y seguridad siguen funcionando después de realizar cambios.

### 6.5. Aspectos que deben contemplarse para completar CI/CD

Para disponer de un flujo CI/CD más completo, se consideran recomendables las siguientes mejoras:

**En integración continua:**

- Crear un workflow de GitHub Actions.
- Ejecutar automáticamente las pruebas unitarias en cada Pull Request.
- Ejecutar las pruebas de integración con una instancia PostgreSQL de pruebas.
- Verificar que las dependencias se instalan correctamente.
- Evitar la integración de cambios cuando las pruebas obligatorias fallen.

**En despliegue continuo:**

- Automatizar la construcción de la imagen Docker.
- Comprobar que la imagen se construye correctamente.
- Configurar el despliegue de la API en Render tras integrar cambios en la rama correspondiente.
- Mantener PostgreSQL como servicio de persistencia.
- Gestionar las credenciales mediante variables de entorno.
- Verificar el estado de la aplicación después del despliegue mediante `/health`.

Estas mejoras constituyen los objetivos recomendables para completar el proceso; no deben confundirse con funcionalidades cuya implementación no se haya comprobado.

### 6.6. Conclusión del apartado

El proyecto dispone de una estructura de trabajo basada en Git, ramas y Pull Requests, pruebas automatizadas, preparación de la aplicación mediante Docker y una arquitectura de despliegue prevista en Render.

La existencia de las suites de pruebas permite validar los componentes principales, mientras que Docker facilita reproducir el entorno de ejecución y preparar la publicación de la API.

La siguiente mejora natural consiste en completar la automatización del proceso mediante workflows de GitHub Actions que ejecuten las pruebas en cada Pull Request y una configuración de despliegue automático vinculada a la integración del código.

De esta manera, el proyecto podrá avanzar desde un flujo de integración y despliegue apoyado en herramientas y validaciones existentes hacia un proceso CI/CD completamente automatizado.

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

