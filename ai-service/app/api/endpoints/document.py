from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.db import get_db
from app.models.document_vector import DocumentVector
from app.services.embedding_service import build_varian_content, embed_texts

router = APIRouter(tags=["documents"])

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

@router.post("/documents", response_model=DocumentResponse)
def upsert_document(payload: DocumentUpsert, db: Session = Depends(get_db)):
    content = build_varian_content(
        payload.sop_name, payload.varian, payload.syarat, payload.channel_url, payload.note
    )
    
    # 1. Proses embedding DILUAR transaksi database (mencegah DB hang kalau API Gemini lambat)
    try:
        vector = embed_texts([content])[0]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gagal memanggil API Embedding: {exc}")
        
    # 2. Cek apakah dokumen ini sudah pernah ada di DB
    row = db.query(DocumentVector).filter(
        DocumentVector.sop_name == payload.sop_name.strip(),
        DocumentVector.varian == payload.varian.strip()
    ).first()
    
    # 3. Proses simpan/update DI DALAM transaksi
    try:
        if row is None:
            # Belum ada, Insert baru sebagai versi 1
            row = DocumentVector(
                sop_name=payload.sop_name.strip(), 
                varian=payload.varian.strip(), 
                content=content, 
                embedding=vector, 
                version=1
            )
            db.add(row)
        else:
            # Sudah ada, Update data lama dan naikkan angka versi
            row.content = content # type: ignore
            row.embedding = vector # type: ignore
            row.version = row.version + 1 # type: ignore
        
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan ke Database: {exc}")
        
    db.refresh(row)
    return DocumentResponse(
        sop_name=row.sop_name, varian=row.varian, version=row.version, updated_at=row.updated_at # type: ignore
    )