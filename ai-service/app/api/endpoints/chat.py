"""Gerbang tanya warga Kos Pepe (Fase 5 / Q8).

POST /chat: terima {query, channel} dari Laravel (WA/Web),
kembalikan {answer, citations, fallback, fallback_contact?}.
Keputusan jawab vs alihkan mengikuti rag_engine + llm_service.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.llm_service import generate_answer, get_fallback_contact
from app.services.rag_engine import DEFAULT_TOP_K, search

router = APIRouter(prefix="/chat", tags=["chat"])

VALID_CHANNELS = ("WA", "Web")


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    channel: str = "Web"
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=10)


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


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    """Terima pertanyaan warga, kembalikan jawaban atau fallback manusia."""
    channel = _normalize_channel(payload.channel)
    _ = channel  # dicatat untuk audit kanal; penyaluran balik tugas Laravel.

    result = search(payload.query, db, top_k=payload.top_k)
    chunks = [] if result.fallback else result.chunks
    generated = generate_answer(result.query, chunks)

    fallback = result.fallback or generated["refused"]
    contact = get_fallback_contact() if fallback else {}
    return ChatResponse(
        answer=generated["answer"],
        citations=[ChatCitation(**c) for c in generated["citations"]],
        fallback=fallback,
        fallback_contact=contact if fallback else {},
    )
