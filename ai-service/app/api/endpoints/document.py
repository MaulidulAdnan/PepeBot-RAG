"""Kamar titip koper Kos Pepe (Fase 2 / Q4, Q8–Q9).

POST /documents: terima 1 Varian dari Laravel (admin tekan Simpan),
buat sidik jari via embedding_service, simpan ke database dalam
satu transaksi (tulis + embedding gagal = batal semua).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.document_vector import DocumentVector
from app.services.embedding_service import build_varian_content, embed_texts

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentUpsert(BaseModel):
    sop_name: str = Field(min_length=1, max_length=255)
    varian: str = Field(min_length=1, max_length=255)
    syarat: list[str] = Field(min_length=1)
    channel_url: str = ""
    note: str = ""


class DocumentResponse(BaseModel):
    sop_name: str
    varian: str
    version: int
    updated_at: datetime


@router.post("", response_model=DocumentResponse)
def upsert_document(payload: DocumentUpsert, db: Session = Depends(get_db)):
    """Simpan atau perbarui 1 Varian (upsert per sop_name+varian)."""
    content = build_varian_content(
        payload.sop_name,
        payload.varian,
        payload.syarat,
        payload.channel_url,
        payload.note,
    )
    try:
        vector = embed_texts([content])[0]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gagal embedding: {exc}")

    row = (
        db.query(DocumentVector)
        .filter(
            DocumentVector.sop_name == payload.sop_name.strip(),
            DocumentVector.varian == payload.varian.strip(),
        )
        .first()
    )
    try:
        if row is None:
            row = DocumentVector(
                sop_name=payload.sop_name.strip(),
                varian=payload.varian.strip(),
                content=content,
                embedding=vector,
                version=1,
            )
            db.add(row)
        else:
            row.content = content
            row.embedding = vector
            row.version = row.version + 1
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal simpan: {exc}")
    db.refresh(row)
    return DocumentResponse(
        sop_name=row.sop_name,
        varian=row.varian,
        version=row.version,
        updated_at=row.updated_at,
    )
