"""Retrieval RAG + Smart Fallback (Fase 3 / Q2, Q6).

Alur: embed pertanyaan (768) -> cari N baris terdekat di Postgres+pgvector
diurutkan cosine distance -> konversi ke similarity -> bandingkan dengan
threshold. Di bawah threshold berarti tidak ada SOP yang cocok sehingga
penjawab (Fase 4/5) wajib fallback ke kontak petugas, bukan mengarang jawaban.
"""

from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from app.models.document_vector import DocumentVector
from app.services.embedding_service import embed_query
from app.core.config import settings

SIMILARITY_THRESHOLD = settings.RETRIEVAL_THRESHOLD
DEFAULT_TOP_K = settings.TOP_K

@dataclass
class RetrievedChunk:
    sop_name: str
    varian: str
    content: str
    version: int
    distance: float
    similarity: float

@dataclass
class SearchResult:
    query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    fallback: bool = True
    best_similarity: float | None = None

def search(query: str, db: Session, top_k: int = DEFAULT_TOP_K, sop_name: str | None = None) -> SearchResult:
    """Mencari SOP desa terdekat menggunakan ekstensi pgvector (<=>)"""
    if not query or not query.strip():
        return SearchResult(query=query)

    # 1. Ubah pertanyaan jadi angka
    vector = embed_query(query.strip())

    # 2. Rumus kalkulasi Cosine Distance dari pgvector SQLAlchemy
    distance_col = DocumentVector.embedding.cosine_distance(vector).label("distance")
    q = db.query(DocumentVector, distance_col)
    
    if sop_name:
        q = q.filter(DocumentVector.sop_name == sop_name)
    
    # 3. Urutkan berdasarkan yang paling mirip (jarak terdekat), ambil 4 teratas
    rows = q.order_by(distance_col).limit(top_k).all()

    chunks = [
        RetrievedChunk(
            sop_name=row.DocumentVector.sop_name,
            varian=row.DocumentVector.varian,
            content=row.DocumentVector.content,
            version=row.DocumentVector.version,
            distance=float(row.distance),
            similarity=1.0 - float(row.distance),
        )
        for row in rows
    ]
    
    # 4. Kalau database masih kosong
    if not chunks:
        return SearchResult(query=query)

    # 5. Cek kemiripan tertinggi, blokir jika di bawah nilai ambang (0.65)
    best = max(c.similarity for c in chunks)
    return SearchResult(
        query=query,
        chunks=chunks,
        fallback=best < SIMILARITY_THRESHOLD,
        best_similarity=best,
    )