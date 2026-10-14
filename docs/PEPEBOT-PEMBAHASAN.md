# PepeBot — Rekapitulasi Pembahasan Teknis

Dokumen ini merangkum hasil diskusi perencanaan, domain model (Q1–Q11), dan bedah kode `ai-service`.

## 1. Konteks Proyek

PepeBot adalah omnichannel AI chatbot administrasi Desa Pepe (Sidoarjo) dengan dua kanal input: Meta WhatsApp Cloud API dan Web Chat Widget (React). Backend orkestrator: Laravel (PHP). AI engine: Python FastAPI + LLM dengan arsitektur Retrieval-Augmented Generation (RAG) Level 2 — Generative AI yang di-grounding ketat ke SOP resmi desa untuk mencegah halusinasi.

Tiga masalah utama dari dokumen perencanaan:
1. Keterbatasan wewenang administratif — desa hanya berhak menerbitkan Surat Pengantar/rujukan, pencetakan akhir di Kecamatan/Dispendukcapil.
2. Miskonsepsi warga + beban repetitif — warga mengira semua selesai di balai desa, perangkat desa membalas WhatsApp berulang secara manual.
3. Inefisiensi bolak-balik — berkas tidak lengkap karena minim akses informasi syarat.

Tiga fitur MVP:
1. Dual-Channel Auto Responder — satu otak menjawab WA dan Web Widget.
2. Dashboard Manajemen Pengetahuan — CRUD SOP no-code oleh perangkat desa.
3. Smart Fallback — jika skor retrieval di bawah threshold, kembalikan permintaan maaf + kontak/link petugas manusia.

Data flow normatif: Warga (WA/Web) → Laravel (webhook WA / REST API Web) → FastAPI `POST /chat` → retrieval SOP + generasi jawaban → Laravel → kanal asal (Meta API / JSON ke React).

## 2. Keputusan Domain Q1–Q11

### Q1 — Batas wewenang pihak ke-3
Desa adalah perantara pengaju, bukan penerbit Dokumen Akhir. Setiap jawaban harus meluruskan batas wewenang dan mengarahkan ke institusi pusat atau kanal mandiri (contoh: Plavon Sidoarjo `https://plavon.sidoarjokab.go.id/`). Implementasi di `app/services/llm_service.py` sebagai instruksi sistem prompt.

### Q2 — SOP sebagai single source of truth
SOP terstruktur hasil kurasi Dashboard adalah satu-satunya sumber jawaban. Dilarang menjawab di luar hasil retrieval top-k. Skor rendah wajib `fallback=true`. Implementasi di `app/services/rag_engine.py` sebagai retrieval gating + threshold.

### Q3 — Laravel sebagai orkestrator
WhatsApp webhook dan Widget REST bermuara di Laravel. FastAPI tidak menerima koneksi langsung dari Meta/React. `ai-service` hanya mengekspos API internal ke Laravel. Implementasi di `ai-service/main.py` + `app/api/router.py` (CORS dan autentikasi internal antar-service).

### Q4 — Update sinkron per-baris (Opsi A)
`Simpan Dashboard = tulis DB + re-embedding dalam satu transaksi`. Retrieval berikutnya wajib membaca versi baru (read-your-write). Ditolak Opsi B async/batch karena menimbulkan jendela stale 1–5 menit, membutuhkan queue worker tambahan, dan melanggar janji dokumen seksi 8 (bot langsung pintar). Implementasi di `app/api/endpoints/document.py` + `app/services/embedding_service.py`.

### Q5 — Kanon 4 istilah
- `SOP`: kumpulan aturan satu layanan (misal SOP KK).
- `Syarat`: satu butir checklist dalam satu Varian.
- `Surat Pengantar`: output yang boleh diterbitkan desa.
- `Dokumen Akhir`: output Kecamatan/Dispendukcapil yang hanya bisa dibantu diajukan.
Larangan penggunaan kata generik `dokumen`. Lihat `GLOSSARY.md`.

### Q6 — Varian + chunking per-Varian
Satu SOP berisi N Varian (contoh: SOP KK berisi Perubahan Biodata, Pecah KK, Hilang, Pembaruan). Unit chunking dan embedding adalah satu Varian (judul varian + daftar Syarat + channel_url + note), bukan satu SOP utuh (terlalu besar, jawaban campur) dan bukan satu Syarat atomik (kehilangan konteks). Implementasi di `embedding_service.py` (chunker) dan `rag_engine.py` (retrieval filter per `varian`).

### Q7 — Skema per-Varian
Tabel `document_vectors` diperluas dari `(document_name, content, embedding)` menjadi `(sop_name, varian, content, embedding, version, updated_at)`. `content` adalah gabungan checklist + channel + note per Varian. `version`/`updated_at` mendukung audit dan update sinkron Q4. Status kini: `ai-service/app/models/document_vector.py:5-15` belum memiliki kolom tersebut.

### Q8 — Kontrak chat
- Request: `POST /chat {query: string, channel: WA | Web, top_k?: int}`.
- Response: `{answer: string, citations: [{sop_name, varian, version}], fallback: bool, fallback_contact?: {phone, url}}`.
- `fallback=false`: jawaban AI + sitasi cukup, Laravel teruskan ke kanal asal.
- `fallback=true`: jawaban permintaan maaf + kontak petugas, Laravel kirim nomor/link manusia.
Implementasi di `app/api/endpoints/chat.py`. Status kini: file 0 byte, `router.py` 0 byte, `main.py` tanpa `include_router` sehingga endpoint me-return 404.

### Q9 — Field Dashboard (sisi AI)
Form per-Varian: `sop_name, varian, syarat_list (textarea, satu baris satu Syarat), channel_url, note`. Tombol Simpan memicu pipeline sinkron Q4 dan menampilkan `version`/`updated_at` baru. Sisi AI menerima via `POST /documents` di `app/api/endpoints/document.py` (kini 0 byte).

### Q10 — Urutan dan jobdesk MVP
1. Data Scientist: migrasi skema Q7 + seed 4 Varian KK + `POST /chat` + fallback Q8 + 3 service.
2. Fullstack 1: webhook WhatsApp + proxy Laravel → FastAPI → Meta API.
3. Fullstack 2: Widget REST + Dashboard Q9.
Fitur MVP tetap tiga: Dual-Channel, Dashboard no-code, Smart Fallback.

### Q11 — Paket provider
Direkomendasikan Gemini untuk MVP (memanfaatkan kuota gratis proyek kampus): embedding 768 dimensi + LLM seri Flash. Konsekuensi: ubah `Vector(1536)` menjadi `Vector(768)` satu kali di awal + tambah SDK (`google-generativeai` / `langchain-google-genai`) ke `ai-service/requirements.txt` + implementasi di `embedding_service.py` dan `llm_service.py`. Alternatif OpenAI (embedding 1536 + GPT mini) lebih stabil untuk bahasa santai dan tanpa migrasi dimensi, tetapi membutuhkan billing berbayar dan data keluar ke server US.

## 3. Bedah `ai-service` per File

### 3.1 Root `ai-service/`

- `ai-service/__pycache__/main.cpython-312.pyc`: bytecode CPython 3.12 hasil kompilasi `main.py`. Artefak cache untuk startup lebih cepat, diregenerasi saat source berubah. Tidak diedit, tidak di-commit.
- `ai-service/main.py:4-16`: instansiasi `FastAPI(title, description, version)` + satu route `GET /` (`read_root`) sebagai health check. Belum ada `include_router`, `Base.metadata.create_all`, CORS, middleware, maupun dependensi `get_db`.
- `ai-service/requirements.txt:9,19-26,32`: `fastapi==0.142.2`, `uvicorn==0.54.0`, `langchain==1.4.3`, `langgraph==1.2.14`, `pgvector==0.5.0`, `SQLAlchemy==2.1.3`, `psycopg2-binary`. Belum ada SDK embedding/LLM (OpenAI/Gemini), `sentence-transformers`, maupun `tiktoken`.
- `ai-service/Dockerfile:1-15`: `FROM python:3.12-slim`, `WORKDIR /app`, instal `libpq-dev gcc` untuk kompilasi `psycopg2`/`pgvector`, `COPY requirements.txt` + `pip install`, `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]`. Port 8001 untuk AI (8000 untuk Laravel). `--reload` untuk development, dimatikan di produksi.

### 3.2 `app/` Overview

- `app/__init__.py`: penanda package agar `from app.core.db import Base` valid.
- `app/api/`: lapisan presentasi HTTP (routing + endpoint).
- `app/core/`: konfigurasi dan koneksi database.
- `app/models/`: deklarasi ORM.
- `app/services/`: logika bisnis RAG.

### 3.3 `app/core/`

- `app/core/__init__.py`: penanda package `core`.
- `app/core/config.py:1-6`: `DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:secretpassword@localhost:5432/pepebot_db")`. Membaca environment variable, dengan fallback hardcoded yang mengandung kredensial plaintext dan ikut ter-commit — harus dihapus dan diganti validasi wajib env.
- `app/core/db.py:1-22`:
  - `engine = create_engine(DATABASE_URL)` (`db.py:6`): connection pool utama, dibuat sekali saat startup.
  - `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)` (`db.py:9`): factory sesi per-request.
  - `Base = declarative_base()` (`db.py:12`): basis deklaratif ORM.
  - `get_db()` (`db.py:17-22`): dependensi FastAPI dengan pola `yield` + `finally: db.close()` untuk mencegah connection leak.

### 3.4 `app/models/`

- `app/models/__init__.py`: penanda package.
- `app/models/document_vector.py:1-15`: `class DocumentVector(Base)`, `__tablename__ = "document_vectors"`, kolom `id Integer PK indexed`, `document_name String(255) NOT NULL`, `content Text NOT NULL`, `embedding Vector(1536)`. Komentar inline mendokumentasikan asumsi 1536 (OpenAI) vs 768 (BGE-m3/Gemini). Belum ada kolom `varian`, `version`, `updated_at` sesuai Q7. Tabel fisik belum dibuat karena tidak ada `create_all`/Alembic.

### 3.5 `app/api/`

- `app/api/__init__.py`, `app/api/endpoints/__init__.py`: penanda package.
- `app/api/router.py` (0 byte): seharusnya agregator `APIRouter` (`chat`, `document`) yang di-`include_router` di `main.py`.
- `app/api/endpoints/chat.py` (0 byte): seharusnya `POST /chat` sesuai kontrak Q8 — validasi Pydantic, panggil `embedding_service` → `rag_engine` → `llm_service`, return `answer/citations/fallback`.
- `app/api/endpoints/document.py` (0 byte): seharusnya `POST /documents` (upsert Varian + re-embedding sinkron Q4) dan `GET /search` (inspeksi retrieval).

### 3.6 `app/services/`

- `app/services/__init__.py`: penanda package.
- `app/services/embedding_service.py` (0 byte): seharusnya klien embedding (teks → vektor 768/1536, Q11), dipakai saat ingest dan query.
- `app/services/rag_engine.py` (0 byte): seharusnya retrieval `pgvector` (`cosine_distance`/`l2_distance`, `order_by`, `limit top_k`), threshold gating Q2, dan seleksi sitasi per Varian Q6.
- `app/services/llm_service.py` (0 byte): seharusnya prompt assembly (system prompt batas wewenang Q1 + konteks SOP + riwayat) dan pemanggilan LLM dengan pelarangan jawaban di luar konteks.

## 4. Kesenjangan Kode vs Dokumen

1. Tidak ada endpoint RAG (`router.py`, `chat.py`, `document.py` kosong; `main.py` tanpa router).
2. Tidak ada logika RAG (`embedding_service.py`, `rag_engine.py`, `llm_service.py` kosong).
3. Skema belum mendukung Varian/versioning (Q6–Q7).
4. Tidak ada SDK provider (Q11) di `requirements.txt`.
5. Kredensial fallback hardcoded di `config.py:5`.
6. `docker-compose.yml:5-16` hanya berisi `postgres-db` (`ankane/pgvector:latest`), tanpa service `ai-service`/`core-service`, healthcheck, maupun network.
7. Sisi Laravel (`core-service/routes/web.php:8-27`, `bootstrap/app.php:8-13`) belum memiliki webhook WA, REST Widget, maupun proxy ke FastAPI.

## 5. Backlog Prioritas

**P0 (blocker MVP):** migrasi skema Q7, tambah SDK Q11, implementasi 3 service + 2 endpoint (Q4, Q6, Q8), seed 4 Varian KK, hapus fallback kredensial, tambah service ke compose.
**P1 (layak pakai):** validasi Pydantic, pagination search, error handling timeout, CORS antar-service, rate-limit chat, autentikasi internal, test `pytest` (embed → search → chat).
**P2 (hardening):** observabilitas LangSmith, `README` arsitektur, `Dockerfile` produksi tanpa `--reload`, CI lint+test, bulk import async sebagai pengecualian dari sinkron default.

## 6. Referensi Istilah

Lihat `GLOSSARY.md` di root: `SOP`, `Varian`, `Syarat`, `Surat Pengantar`, `Dokumen Akhir`.
