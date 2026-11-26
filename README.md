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
