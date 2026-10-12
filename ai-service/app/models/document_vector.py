from sqlalchemy import (
    Column, Integer, String, Text, DateTime, UniqueConstraint, func
)
from pgvector.sqlalchemy import Vector
from app.core.db import Base


class DocumentVector(Base):
    __tablename__ = "document_vectors"
    __table_args__ = (
        UniqueConstraint("sop_name", "varian", name="uq_sop_varian"),
    )

    id = Column(Integer, primary_key=True, index=True)
    sop_name = Column(String(255), nullable=False, index=True)
    varian = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )