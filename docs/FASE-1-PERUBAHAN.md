# Fase 1 — Rekap Perubahan: Persiapan Lingkungan & Skema Database

Cakupan Fase 1 (dari `docs/PEPEBOT-PEMBAHASAN.md` dan To-Do List): amunisi dependensi (1.1), konfigurasi aman (1.2), dan skema per-Varian dimensi Gemini (1.3). Semua keputusan mengacu Q7 (skema per-Varian) dan Q11 (Gemini 768).

> Catatan keamanan: nilai password dan API key tidak ditulis di dokumen ini. Yang ditampilkan hanya nama kunci dan bentuk struktur (masking `***`).

## 1. `ai-service/requirements.txt` — tambah amunisi Gemini + perbaiki konflik

### 1.1 Apa yang diubah dan di mana
Lokasi: `ai-service/requirements.txt` ekor file (setelah `zstandard==0.25.0`).

Sebelum (akhir file):
```
zstandard==0.25.0
```

Sesudah:
```
zstandard==0.25.0
# --- PepeBot RAG (Q11: Gemini 768 + Flash) ---
python-dotenv
google-genai==2.29.0
# Integrasi Gemini ke LangChain/LangGraph yang sudah ada
langchain-google-genai
```

Plus satu perubahan pin di tengah file:
```
# sebelum
tenacity==9.2.1
# sesudah
tenacity==9.1.2
```

### 1.2 Apa yang ditambah dan kenapa
1. `python-dotenv` — pembaca file `.env` menjadi environment variable. Dibutuhkan karena `app/core/config.py` memanggil `load_dotenv()`; tanpa paket ini konfigurasi tidak bisa dimuat dari file.
2. `google-genai==2.29.0` — SDK resmi Gemini, dipakai nanti oleh `embedding_service.py` (vektor 768 dimensi) dan `llm_service.py` (model Flash). Dipin exact agar reproduksibel.
3. `langchain-google-genai` — adaptor agar SDK Gemini bisa dipakai lewat antarmuka LangChain/LangGraph yang sudah ada di requirements (`langchain==1.4.3`, `langgraph==1.2.14`). Tanpa adaptor, kode harus memanggil SDK mentah di luar orkestrasi LangChain.
4. Rapikan duplikat —ide awal sempat ada dua baris `google-genai` (satu tanpa versi, satu `== 2.29.0` dengan spasi `== 2.29.0`) sehingga digabung menjadi satu baris bersih `google-genai==2.29.0`.

### 1.3 Kenapa `tenacity` diturunkan
`pip install` pertama gagal dengan `ResolutionImpossible`:
- Pin lama meminta `tenacity==9.2.1`.
- `google-genai 2.29.0` mensyaratkan `tenacity<9.2.0,>=8.2.3`.
- `langchain-core 1.6.7` mensyaratkan `tenacity<10.0.0,>=8.1.0`.

Irisan yang memenuhi keduanya adalah `>=8.2.3,<9.2.0`, sehingga pin digeser ke `tenacity==9.1.2`. Hasil instalasi: `filetype-1.2.0`, `langchain-google-genai-4.4.0`, `tenacity 9.1.4→9.1.2`, sisanya `Requirement already satisfied`.

### 1.4 Yang sengaja TIDAK diubah
To-Do List menyebut menghapus library yang tidak diperlukan. Tidak dilakukan: file ini hasil `pip freeze` berisi banyak dependensi transitif (`anyio`, `httpx`, `pydantic`, dll.) yang jika dicabut buta bisa memutus LangChain/FastAPI. Pembersihan ditunda sampai ada pemetaan impor yang terbukti tak terpakai.

### 1.5 Verifikasi
```console
$ py -m pip install -r requirements.txt
Successfully installed filetype-1.2.0 langchain-google-genai-4.4.0 tenacity-9.1.2

$ py -c "import fastapi, sqlalchemy, pgvector, dotenv; import google.genai; import langchain_google_genai; print('fase1-ok')"
fase1-ok
```

## 2. `ai-service/app/core/config.py` — alamat aman + interpolasi dua `.env`

### 2.1 Apa yang diubah dan di mana
Lokasi: `ai-service/app/core/config.py` seluruh kepala file.

Sebelum (versi lama yang sempat terbaca):
```python
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secretpassword@localhost:5432/pepebot_db"
)
```
Masalah versi lama: kredensial cadangan tertulis di kode dan ikut ter-commit ke git.

Kondisi awal sesi ini (sudah ada di disk): `load_dotenv()` + `_require()` untuk `DATABASE_URL` dan `GEMINI_API_KEY`, tanpa hardcode. Versi ini benar untuk Docker tetapi gagal saat jalan native Windows — penyebabnya di seksi 2.3.

Sesudah (final):
```python
import os
import re
from dotenv import load_dotenv
from pathlib import Path

_HERE = Path(__file__).resolve()
# Muat .env root dulu sebagai sumber DB_USERNAME/DB_PASSWORD/DB_DATABASE,
# lalu .env ai-service (menang) agar ${VAR:-default} terinterpolasi benar
# baik saat jalan native Windows maupun di dalam Docker.
load_dotenv(_HERE.parents[3] / ".env", override=False)
load_dotenv(_HERE.parents[2] / ".env", override=True)


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value or "${" in value:
        value = _expand(value or "")
    if not value:
        raise RuntimeError(f"Environment variable {name} wajib diisi")
    return value


def _expand(value: str) -> str:
    # Dukung ${VAR}, $VAR, dan ${VAR:-default} (tidak didukung os.path.expandvars).
    def repl(m: re.Match) -> str:
        var, default = m.group(1), m.group(2)
        return os.getenv(var, default if default is not None else "")

    value = re.sub(r"\$\{([^}:]+)(?::-(.*?))?\}", repl, value)
    return os.path.expandvars(value)


DATABASE_URL = _require("DATABASE_URL")
GEMINI_API_KEY = _require("GEMINI_API_KEY")
```

### 2.2 Apa yang ditambah dan kenapa
1. `load_dotenv` ganda (root lalu ai-service) — `ai-service/.env` berisi placeholder `postgresql://${DB_USERNAME:-admin}:${DB_PASSWORD:...}@postgres-db:5432/${DB_DATABASE:-pepebot_db}` yang merujuk ke variabel `DB_*` milik `.env` root (yang dipakai `docker-compose.yml` untuk interpolasi `POSTGRES_DB/USER/PASSWORD`). Saat jalan native, variabel OS `DB_*` tidak ada sehingga password hasil interpolasi kosong. Dengan memuat `.env` root lebih dulu, `${DB_PASSWORD}` terisi dari nilai root.
2. `_expand()` kustom — `os.path.expandvars` hanya paham `$VAR`/`${VAR}`, tidak paham sintaks `${VAR:-default}` yang dipakai file ini. Regex di atas menangani ketiganya.
3. `_require()` diperketat — nilai kosong atau yang masih mengandung `${` dianggap belum jadi dan diekspansi ulang; jika tetap kosong, raise `RuntimeError` eksplisit (fail-fast) alih-alih jalan setengah dengan kredensial salah.

### 2.3 Bukti diagnosis (masking, tanpa nilai asli)
```console
# ai-service/.env mentah (password disensor):
DATABASE_URL=postgresql://${DB_USERNAME:-admin}:${DB_PASSWORD:***@postgres-db:5432/${DB_DATABASE:-pepebot_db}

# setelah perbaikan, hasil ekspansi (nilai disembunyikan, hanya status):
{'placeholder_sisa': False, 'user': 'admin', 'host': 'postgres-db',
 'db': 'pepebot_db', 'pass_terisi': True, 'gemini_terisi': True}
```
Sebelum perbaikan, `pass_terisi` False sehingga Postgres menolak dengan `FATAL: password authentication failed for user "admin"` — server terjangkau (host benar) tetapi kunci kosong.

## 3. `ai-service/app/core/db.py` — normalisasi driver psycopg2

### 3.1 Apa yang diubah dan di mana
Lokasi: `ai-service/app/core/db.py` kepala file.

Sebelum:
```python
from app.core.config import DATABASE_URL

# 1. Membuat "Engine" (Mesin utama yang memegang koneksi ke Postgres)
engine = create_engine(DATABASE_URL)
```

Sesudah:
```python
from app.core.config import DATABASE_URL


def _with_driver(url: str) -> str:
    # SQLAlchemy 2.x default driver psycopg (v3), padahal yang terinstal psycopg2-binary.
    # Normalisasi agar selalu pakai psycopg2 tanpa ubah isi .env.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


# 1. Membuat "Engine" (Mesin utama yang memegang koneksi ke Postgres)
engine = create_engine(_with_driver(DATABASE_URL))
```
Sisa file (`SessionLocal`, `Base`, `get_db`) tidak berubah.

### 3.2 Kenapa harus diubah
Import `app.core.db` meledak sebelum sempat konek:
```
ModuleNotFoundError: No module named 'psycopg'
```
SQLAlchemy 2.1 memetakan skema `postgresql://` ke driver `psycopg` (v3), sedangkan yang terinstal (sesuai `requirements.txt:33` dan `Dockerfile:8` yang menginstal `libpq-dev gcc` untuk kompilasi `psycopg2`) adalah `psycopg2-binary`. Normalisasi di atas memaksa driver `psycopg2` tanpa mengubah isi `.env`. Verifikasi metadata tanpa koneksi DB:
```console
['content', 'embedding', 'id', 'sop_name', 'updated_at', 'varian', 'version']
postgresql psycopg2
```

## 4. `ai-service/app/models/document_vector.py` — denah per-Varian (sudah ada, diverifikasi)

### 4.1 Status
File ini sudah dalam bentuk target sebelum sesi ini berjalan, sehingga tidak diedit. Diverifikasi isinya via byte-level read:

```python
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
```

### 4.2 Kenapa bentuk ini (Q6–Q7, Q11)
- `document_name` → `sop_name` + `varian`: satu baris = satu Varian (misal SOP `KK` varian `Hilang`), mendukung chunking per-Varian Q6. Tanpa ini retrieval mencampur 4 checklist KK dalam satu vektor.
- `Vector(1536)` → `Vector(768)`: dimensi Gemini Q11. Laci 1536 tidak muat diisi sidik jari 768 dan sebaliknya.
- `version` + `updated_at`: audit dan prasyarat update sinkron Q4 (Simpan menaikkan versi, retrieval berikutnya membaca versi baru).
- `UniqueConstraint(sop_name, varian)`: menolak duplikat varian dalam satu SOP.
- `nullable=False` di `embedding`: melarang baris tanpa vektor (mencegah jawaban dari teks yang belum di-embed).

## 5. Database fisik — ekstensi + tabel

### 5.1 Di mana
Container `postgres-db` (`docker-compose.yml:5-16`, image `ankane/pgvector:latest`), dijalankan dari folder utama via `docker compose up -d postgres-db`. Nama host `postgres-db` hanya dikenal di dalam jaringan Docker; dari Windows native dipakai override host `127.0.0.1` (hanya di skrip verifikasi, bukan di file).

### 5.2 Perintah yang dijalankan (skrip verifikasi, bukan file repo)
```python
from sqlalchemy import create_engine, text
from app.core.db import Base
import app.models.document_vector

# url = DATABASE_URL terenkripsi, host dioverride ke 127.0.0.1 + driver psycopg2
with e.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()
Base.metadata.create_all(e)
```

### 5.3 Hasil
```console
db-ok ['id', 'sop_name', 'varian', 'content', 'embedding', 'version', 'updated_at']
```
Tabel fisik kini sama dengan denah kode, dan ekstensi `vector` aktif sehingga kolom `embedding` bisa diindeks/dicari kemiripan pada Fase 3.

## 6. Istilah teknis
- **SDK/adaptor**: paket siap pakai (`google-genai`) dan colokannya ke framework (`langchain-google-genai`).
- **Dependency resolver/backtracking**: algoritma pip yang mencoba kombinasi versi sampai semua syarat cocok; pin bertabrakan (`tenacity`) membuatnya gagal.
- **Interpolasi `.env`**: penggantian `${VAR:-default}` dengan nilai variabel saat file dimuat.
- **Fail-fast**: gagal tegas di awal (missing env) daripada berjalan dengan kredensial salah.
- **Driver DBAPI**: penerjemah Python↔Postgres (`psycopg2` vs `psycopg` v3); skema URL menentukan pilihannya.
- **Connection leak**: sesi DB yang dipinjam tapi tidak dikembalikan (`get_db` menutup via `finally`).
- **UniqueConstraint / server_default / onupdate**: aturan anti-duplikat, nilai default dari server DB, dan pembaruan jam otomatis.

## 7. Pembuktian Fase 1 — lima bukti berurutan

Setiap bukti di bawah mengunci satu klaim Fase 1. Semua dijalankan dari folder `ai-service`, kecuali varian docker dari folder utama.

### Bukti 1 — dependensi terpasang tanpa konflik (klaim 1.1)
```console
$ py -m pip install -r requirements.txt
# lulus: tanpa ResolutionImpossible/ERROR,
# hanya "Requirement already satisfied" + instal paket baru

$ py -c "import dotenv, google.genai, langchain_google_genai; print('deps-ok')"
deps-ok
```
Kenapa membuktikan: perintah pertama memaksa resolver pip memeriksa seluruh pin; jika `tenacity` masih `9.2.1`, ia gagal dengan konflik `google-genai<9.2.0` vs pin lama. Perintah kedua membuktikan tiga paket baru benar-benar bisa diimpor (bukan sekadar tertulis). Bonus: `py -m pip show tenacity` harus `Version: 9.1.2` — bukti perbaikan pin.

### Bukti 2 — tidak ada kredensial di kode (klaim 1.2)
```console
$ findstr /n "secretpassword" app\core\config.py
# lulus: tidak ketemu apa-apa
```
Kenapa membuktikan: versi lama menyimpan password cadangan di source yang ikut ter-commit. Tidak adanya string tersebut plus `_require()` yang raise saat env kosong membuktikan tidak ada jalan pintas: aplikasi gagal tegas di awal daripada berjalan dengan kredensial salah. Pasangannya adalah cek status (bukan nilai) hasil ekspansi: `placeholder_sisa False, pass_terisi True, gemini_terisi True` — membuktikan interpolasi `${VAR:-default}` bekerja tanpa menampilkan secret.

### Bukti 3 — denah kode benar tanpa perlu DB nyala (klaim 1.3 level kode)
```console
$ py -c "from app.core.db import Base; import app.models.document_vector; print(sorted(Base.metadata.tables['document_vectors'].columns.keys()))"
['content', 'embedding', 'id', 'sop_name', 'updated_at', 'varian', 'version']
```
Kenapa membuktikan: perintah ini hanya membaca metadata ORM (tanpa koneksi), sehingga lulus/gagalnya murni soal kode. Daftar kolom tersebut persis kontrak Q6–Q7/Q11: `sop_name+varian` (chunk per-Varian), `version/updated_at` (update sinkron), `embedding` 768 (Gemini). Kolom lama `document_name` sudah tidak ada — bukti rename terjadi.

### Bukti 4 — supir database benar (klaim perbaikan `db.py`)
```console
$ py -c "from app.core.db import engine; print(engine.url.get_backend_name(), engine.url.get_driver_name())"
postgresql psycopg2
```
Kenapa membuktikan: sebelum `_with_driver()`, baris import yang sama meledak `ModuleNotFoundError: No module named 'psycopg'` karena SQLAlchemy 2.x memetakan `postgresql://` ke driver v3 yang tidak terinstal. Output `postgresql psycopg2` membuktikan setiap koneksi berikutnya naik supir yang benar (yang terinstal via `psycopg2-binary`/`Dockerfile:8`), tanpa mengubah isi `.env`.

### Bukti 5 — bangunan fisik sama dengan denah (klaim 1.3 level database)
Skrip idempoten `migrasi_fase1.py` (TEMP, bukan repo; kunci dibaca dari `.env`, host dioverride ke `127.0.0.1` khusus tes native):
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\migrasi_fase1.py"
db-ok ['id', 'sop_name', 'varian', 'content', 'embedding', 'version', 'updated_at']
```
Kenapa membuktikan: skrip membaca kolom langsung dari `information_schema` di Postgres container (bukan dari kode), sehingga `db-ok` berarti tiga hal sekaligus — server terjangkau dengan kredensial `.env` yang benar, ekstensi `vector` aktif (`CREATE EXTENSION`), dan tabel fisik sama dengan model. Alternatif via docker dari folder utama (`docker exec pepebot_postgres psql -U admin -d pepebot_db -c "\d document_vectors"`) harus menampilkan kolom yang sama.

### Kapan Fase 1 dinyatakan selesai
1–5 hijau semua berarti: amunisi ada dan cocok, alamat aman dan terisi, denah benar, supir benar, bangunan sama dengan denah. Isi tabel masih kosong — itu disengaja, karena pengisian 4 Varian KK adalah jatah Fase 2.
