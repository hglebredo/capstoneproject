# capstoneproject
Capstone Project se erige como final de trayecto colaborativo en el marco del bootcamp AI Engineering de The Bridge, con microcredenciales de UAM para los tres integrantes del equipo: Miguel, David y Héctor. En él se hace entrega de todo lo aprendido durante el itinerario formativo, así como algunas pinceladas de profesionalidad aplicada.

Las tres líneas de desarrollo del Project Break 3 son:
* API y agente en producción: exponer el agente del PB2 mediante FastAPI, con /ask, /approve, Swagger y contrato Pydantic.
* Persistencia y robustez: guardar el historial de conversaciones en PostgreSQL con SQLModel, y añadir API key, rate limit, timeout, CORS y logs.
* Despliegue y producto: empaquetar API, agente y RAG en Docker, desplegar en Render con Postgres, y conectar un front Streamlit a la URL pública.

Posible estructura de carpetas:

```text
projectcapstone/
├── docs/
│   └── contrato_api.md
├── README.md
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .env                    # Variables de entorno (no commitear)
├── .env.example            # Plantilla completa
├── .gitignore
├── config.py
├── app.py
├── schemas.py
├── security.py
├── docker-compose.yml      # App + PostgreSQL (pgvector)
├── src/
│   ├── db.py
│   ├── models.py
│   ├── agent.py
│   ├── graph.py
│   └── tools/
├── rag/
├── data/
├── front/
│   └── streamlit_app.py
└── entregables/
    └── informe_decisiones.md
```

## Despliegue rápido con Docker Compose

```bash
# 1. Crea tu .env a partir de la plantilla (nunca se sube al repo)
#    y rellena al menos GEMINI_API_KEY (o GOOGLE_API_KEY) y API_KEY:
cp .env.example .env

# 2. Levanta todo en un comando (Postgres + App):
docker compose up --build -d

# 3. Verifica que la app arrancó correctamente:
curl http://localhost:8000/health

# 4. Abre Swagger UI interactiva:
#    http://localhost:8000/docs
```

> **Nota:** el proveedor es `google` (Gemini) y el historial se guarda en el PostgreSQL del contenedor `pg`. **Sin `DATABASE_URL` la API no arranca**: no hay respaldo en SQLite ni en ficheros locales.

---

## Contrato de la API

Contrato completo (schemas, códigos de error, interfaz con Postgres): [`docs/contrato_api.md`](docs/contrato_api.md).

### Rutas

| Método | Ruta | ¿`api_key`? | Qué hace |
|--------|------|-------------|----------|
| GET | `/health` | No | Pulso del servicio y estado de Postgres |
| GET | `/docs` | No | Swagger con todas las rutas y schemas |
| POST | `/ask` | **Sí** | Un turno del agente del PB2 |
| POST | `/approve` | **Sí** | HITL: aprobar o rechazar el plan pendiente |
| GET | `/threads/{thread_id}/messages` | **Sí** | Historial del hilo, leído de Postgres |

- La `api_key` va en la **query** (`?api_key=...`), para poder probarla en Swagger.
- Sin clave o con una clave incorrecta → **401**. Body inválido → **422**.
- El historial se guarda **solo en PostgreSQL**. SQLite solo aparece en los tests unitarios, que inyectan un engine en memoria (`_set_engine_for_tests`).

### Probar la API en Swagger

1. Abre `/docs` (local: <http://127.0.0.1:8000/docs>).
2. En `POST /ask`: **Try it out** → rellena `api_key` → body:
   ```json
   {
     "pregunta": "¿Qué piscinas públicas hay en el distrito de Moncloa-Aravaca?",
     "thread_id": "demo-1",
     "auto_aprobar": true
   }
   ```
   → `200` con `done: true` (el plan se aprueba solo).
3. HITL manual: repite con otro `thread_id` y `"auto_aprobar": false` → `pendiente_hitl: true` y el `plan`.
   Después, `POST /approve` con `{"thread_id": "...", "aprobado": true}` (o `false` para rechazar).
4. `GET /threads/demo-1/messages` → la pregunta y la respuesta guardadas en Postgres.

### Front Streamlit (cliente de la API)

El front vive en `front/` y **solo habla HTTP** con la API: no importa el agente.

```bash
cd front
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # API_KEY (la del servidor) y API_BASE_URL
streamlit run streamlit_app.py
```

- `API_BASE_URL=http://127.0.0.1:8000` para la API local, o la URL de Render para la demo.
- Muestra el estado de `/health`, el chat, el plan con **Aprobar / Rechazar**, el historial y el `thread_id` («Nueva conversación» = otro `thread_id`).
