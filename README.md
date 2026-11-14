# capstoneproject
Capstone Project se erige como final de trayecto colaborativo en el marco del bootcamp AI Engineering de The Bridge, con microcredenciales de UAM para los tres integrantes del equipo: Miguel, David y Héctor. En él se hace entrega de todo lo aprendido durante el itinerario formativo, así como algunas pinceladas de profesionalidad aplicada.

Las tres líneas de desarrollo del Project Break 3 son:
* API y agente en producción: exponer el agente del PB2 mediante FastAPI, con /ask, /approve, Swagger y contrato Pydantic.
* Persistencia y robustez: guardar el historial de conversaciones en PostgreSQL con SQLModel, y añadir API key, rate limit, timeout, CORS y logs.
* Despliegue y producto: empaquetar API, agente y RAG en Docker, desplegar en Render con Postgres, y conectar un front Streamlit a la URL pública.

Posible estructura de carpetas:

```text
projectcapstone/
├── README.md
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .env.example
├── .gitignore
├── config.py
├── app.py
├── schemas.py
├── security.py
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
