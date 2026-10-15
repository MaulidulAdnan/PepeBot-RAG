from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.rag_engine import search
from app.services.llm_service import generate_answer, get_fallback_contact
from app.core.config import settings

router = APIRouter(tags=["chat"])

VALID_CHANNELS = ("WA", "Web")

class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    channel: str = "Web"
    top_k: int = Field(default=settings.TOP_K, ge=1, le=10)

class ChatCitation(BaseModel):
    sop_name: str
    varian: str
    version: int

class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation]
    fallback: bool
    fallback_contact: dict = {}

def _normalize_channel(channel: str) -> str:
    normalized = (channel or "").strip().lower()
    if normalized == "wa":
        return "WA"
    if normalized == "web":
        return "Web"
    raise HTTPException(
        status_code=422, detail=f"channel harus salah satu dari {VALID_CHANNELS}"
    )

@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    channel = _normalize_channel(payload.channel)
    _ = channel  # Dicatat untuk audit kanal; penyaluran balik ke kanal asal diurus Laravel.

    # 1. Cari dokumen SOP via pgvector
    result = search(payload.query, db, top_k=payload.top_k)
    
    # 2. Komposisi dua lapis: Paksa chunks kosong jika fallback aktif agar tidak berhalusinasi
    chunks = [] if result.fallback else result.chunks
    
    # 3. Minta LLM merangkai jawaban berdasarkan konteks SOP
    generated = generate_answer(result.query, chunks)

    # 4. Tentukan status fallback final
    fallback = result.fallback or generated["refused"]
    contact = get_fallback_contact() if fallback else {}
    
    return ChatResponse(
        answer=generated["answer"],
        citations=[ChatCitation(**c) for c in generated["citations"]],
        fallback=fallback,
        fallback_contact=contact if fallback else {},
    )