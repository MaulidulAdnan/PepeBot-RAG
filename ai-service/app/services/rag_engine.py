"""Retrieval RAG + Smart Fallback (Fase 3 / Q2, Q6).

Alur: embed pertanyaan (768) -> cari N baris terdekat di Postgres+pgvector
diurutkan cosine distance -> konversi ke similarity -> bandingkan dengan
threshold. Di bawah threshold berarti tidak ada SOP yang cocok sehingga
penjawab (Fase 4/5) wajib fallback ke kontak petugas, bukan mengarang jawaban.
"""

import os
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.document_vector import DocumentVector
from app.services.embedding_service import embed_query

# Batas minimum kemiripan agar hasil dianggap relevan.
# Di bawah nilai ini, jawaban AI dilarang dan fallback wajib.
# Nilai awal 0.65 dari pengukuran 2 Varian KK: pertanyaan relevan 0.719,
# varian dekat 0.676, pertanyaan luar SOP 0.598. Presisi diutamakan
# (lebih baik fallback ke manusia daripada mengarang).
# Dapat dioverride via environment tanpa ubah kode; wajib tuning ulang
# dengan eval set parafrasa setelah seed penuh.
SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.65"))
DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", "3"))


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


def search(
    query: str,
    db: Session,
    top_k: int = DEFAULT_TOP_K,
    sop_name: str | None = None,
) -> SearchResult:
    """Cari SOP paling relevan untuk pertanyaan.

    Returns SearchResult dengan fallback=True bila tabel kosong,
    query kosong, atau kemiripan terbaik di bawah SIMILARITY_THRESHOLD.
    """
    if not query or not query.strip():
        return SearchResult(query=query)

    vector = embed_query(query.strip())

    distance_col = DocumentVector.embedding.cosine_distance(vector).label(
        "distance"
    )
    q = db.query(DocumentVector, distance_col)
    if sop_name:
        q = q.filter(DocumentVector.sop_name == sop_name)
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
    if not chunks:
        return SearchResult(query=query)

    best = max(c.similarity for c in chunks)
    return SearchResult(
        query=query,
        chunks=chunks,
        fallback=best < SIMILARITY_THRESHOLD,
        best_similarity=best,
    )
