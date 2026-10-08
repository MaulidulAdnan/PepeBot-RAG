from sqlalchemy import Column, Integer, String, Text
from pgvector.sqlalchemy import Vector
from app.core.db import Base

class DocumentVector(Base):
    __tablename__ = "document_vectors"

    id = Column(Integer, primary_key=True, index=True)
    document_name = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    
    # Kolom cyborg kita! 
    # Dimensi 1536 adalah standar untuk model embedding OpenAI (text-embedding-3-small).
    # Jika nanti Anda pakai LLM open-source (misal: BGE-m3 atau Gemini), dimensinya mungkin 768.
    embedding = Column(Vector(1536))