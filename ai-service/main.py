from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.router import router
from app.core.db import engine, Base
from app.models import document_vector  # noqa: F401  (agar model terdaftar di Base)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dijalankan sekali saat server start
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    yield
    # (kode setelah yield dijalankan saat server berhenti, belum diperlukan)


# Inisialisasi aplikasi FastAPI
app = FastAPI(
    title="AI Service - PepeBot RAG",
    description="Service khusus untuk pemrosesan NLP, vector search, dan LLM",
    version="1.0.0",
    lifespan=lifespan,
)


# Daftarkan lorong API (Fase 5): /chat dan /documents
app.include_router(router)


# Endpoint root untuk mengecek status (Health Check)
@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "AI Service PepeBot RAG berhasil berjalan!"
    }