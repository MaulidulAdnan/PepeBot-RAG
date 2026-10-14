import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import DATABASE_URL


def _with_driver(url: str) -> str:
    # SQLAlchemy 2.x default driver psycopg (v3), padahal yang terinstal psycopg2-binary.
    # Normalisasi agar selalu pakai psycopg2 tanpa ubah isi .env.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def _with_host(url: str) -> str:
    # Nama host postgres-db hanya dikenal di dalam jaringan Docker.
    # Saat jalan native (mis. uji Swagger di Windows, file /.dockerenv
    # tidak ada), belokkan ke port publish 127.0.0.1.
    # Di dalam container, biarkan apa adanya.
    if not Path("/.dockerenv").exists():
        url = url.replace("postgres-db", "127.0.0.1")
    return url


# 1. Membuat "Engine" (Mesin utama yang memegang koneksi ke Postgres)
engine = create_engine(_with_host(_with_driver(DATABASE_URL)))

# 2. Membuat "Session" (Setiap kali ada request masuk, kita buka sesi baru)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Base class (Cetakan dasar untuk semua tabel/model kita nanti)
Base = declarative_base()

# 4. Dependency function untuk FastAPI
# Fungsi ini memastikan setiap koneksi ke DB selalu ditutup (db.close()) setelah selesai dipakai, 
# agar memori server tidak bocor (memory leak).
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
