from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import DATABASE_URL

# 1. Membuat "Engine" (Mesin utama yang memegang koneksi ke Postgres)
engine = create_engine(DATABASE_URL)

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
