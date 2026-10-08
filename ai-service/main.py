from fastapi import FastAPI

# Inisialisasi aplikasi FastAPI
app = FastAPI(
    title="AI Service - PepeBot RAG",
    description="Service khusus untuk pemrosesan NLP, vector search, dan LLM",
    version="1.0.0"
)

# Endpoint root untuk mengecek status (Health Check)
@app.get("/")
def read_root():
    return {
        "status": "success", 
        "message": "AI Service PepeBot RAG berhasil berjalan!"
    }