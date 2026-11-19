"""db - Capa relacional del RAG PB3/MLOps.

Tablas:
    Conversation  · Hilo identificado por thread_id (PK externa)
    Message       · Mensajes dentro de una conversación, ordenados por sequence

Motor:
    get_engine()  · Singleton SQLAlchemy; Postgres si DATABASE_URL, SQLite local si no.
    init_db()     · Crea tablas si no existen (idempotente).

Funciones públicas (usadas por app.py):
    ensure_conversation(thread_id)   → Asegura que existe la Conversation del hilo.
    add_message(thread_id, role, content) → Inserta un mensaje en el hilo.
    get_messages(thread_id, limit)  → Devuelve los mensajes ordenados cronológicamente.

Compatible con PostgreSQL (producción/Render) y SQLite local (desarrollo).

Subm贸dulos: models, db_engine.
"""
