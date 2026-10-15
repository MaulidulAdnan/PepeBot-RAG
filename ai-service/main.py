from fastapi import FastAPI
from app.core.db import engine, Base
from app.api.router import api_router

# Mencetak tabel ke database secara otomatis saat server menyala
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Service - PepeBot RAG",
    description="Service khusus untuk pemrosesan NLP, vector search, dan LLM",
    version="1.0.0"
)

# Mendaftarkan seluruh endpoint dengan prefix /api
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {
        "status": "success", 
        "message": "AI Service PepeBot RAG berhasil berjalan!"
    }