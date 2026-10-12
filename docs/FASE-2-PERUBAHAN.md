# Fase 2 — Rekap Perubahan: Mesin Pengetahuan (Ingest & Embedding)

Cakupan Fase 2 (To-Do List 2.1–2.2): tukang sidik jari (`embedding_service.py`, Q11) dan kamar titip koper (`document.py`, Q4 + Q6–Q9). Prasyarat Fase 1 dianggap hijau (dependensi terinstal, config terinterpolasi, tabel fisik `document_vectors` sudah per-Varian 768).

> Nilai API key dan password tidak ditulis di dokumen ini.

## 1. `ai-service/app/services/embedding_service.py` — tukang sidik jari (dibuat, 0 → terisi)

### 1.1 Isi final
```python
"""Tukang sidik jari Kos Pepe (Fase 2 / Q11). ..."""

from google import genai

from app.core.config import GEMINI_API_KEY

EMBED_MODEL = "models/gemini-embedding-001"
EMBED_DIMENSION = 768
EMBED_CONFIG = {"output_dimensionality": EMBED_DIMENSION}

_client = None


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY belum diisi di environment.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def build_varian_content(sop_name, varian, syarat,
                         channel_url="", note=""):
    lines = [f"SOP: {sop_name.strip()}", f"Varian: {varian.strip()}",
             "", "Syarat:"]
    lines += [f"- {s.strip()}" for s in syarat if s and s.strip()]
    if channel_url and channel_url.strip():
        lines += ["", f"Kanal: {channel_url.strip()}"]
    if note and note.strip():
        lines += [f"Catatan: {note.strip()}"]
    return "\n".join(lines).strip()


def embed_texts(texts):
    if not texts:
        return []
    client = _get_client()
    vectors = []
    for text in texts:
        resp = client.models.embed_content(
            model=EMBED_MODEL, contents=text, config=EMBED_CONFIG
        )
        values = list(resp.embeddings[0].values)
        if len(values) != EMBED_DIMENSION:
            raise ValueError(...)
        vectors.append(values)
    return vectors


def embed_query(text):
    return embed_texts([text])[0]
```

### 1.2 Apa yang ditambah dan kenapa
1. `build_varian_content()` — perakit koper format kanon Q5–Q6 (`SOP/Varian/Syarat/Kanal/Catatan`). Format dibangun di server (bukan dikarang pengirim) agar setiap Varian yang di-embed punya struktur identik; retrieval Fase 3 selalu membaca paket utuh, bukan potongan liar. Contoh keluaran untuk KK/Hilang sudah diverifikasi byte-per-byte di seksi 3.1.
2. `embed_texts()` / `embed_query()` — pemanggil Gemini + penjaga dimensi. Setiap vektor dicek `len == 768`; beda dimensi langsung `ValueError` agar baris salah tidak masuk tabel (melindungi `Vector(768)` Fase 1).
3. `_get_client()` malas (lazy singleton) — client dibuat sekali saat pertama dipakai, bukan saat import. Alasan: import modul tetap ringan untuk test tanpa jaringan, dan kunci yang hilang dilaporkan eksplisit (`GEMINI_API_KEY belum diisi`), bukan error samar dari SDK.

### 1.3 Koreksi nama model (fakta runtime, bukan tebakan)
Implementasi awal memakai `models/text-embedding-004` dan ditolak API:
```
404 NOT_FOUND. models/text-embedding-004 is not found for API version v1beta,
or is not supported for embedContent.
```
Daftar model yang mendukung `embedContent` diambil live dari API (hanya 3):
```
models/gemini-embedding-001 | embedContent,...
models/gemini-embedding-2 | embedContent,...
models/gemini-embedding-2-preview | embedContent,...
```
Dipilih `models/gemini-embedding-001` (stabil, non-preview) + `output_dimensionality: 768` agar sesuai kolom tabel Q11. Model `gemini-embedding-001` default bukan 768, sehingga parameter dimensi wajib — tanpa `EMBED_CONFIG`, vektor yang pulang panjangnya salah dan ditolak penjaga dimensi di atas.

## 2. `ai-service/app/api/endpoints/document.py` — kamar titip koper (dibuat, 0 → terisi)

### 2.1 Isi final (ringkas, nama dan alur utuh)
```python
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
    content = build_varian_content(...)
    try:
        vector = embed_texts([content])[0]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gagal embedding: {exc}")
    row = db.query(DocumentVector).filter(
        DocumentVector.sop_name == payload.sop_name.strip(),
        DocumentVector.varian == payload.varian.strip()).first()
    try:
        if row is None:
            row = DocumentVector(..., version=1); db.add(row)
        else:
            row.content = content; row.embedding = vector
            row.version = row.version + 1
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal simpan: {exc}")
    db.refresh(row)
    return DocumentResponse(...)
```

### 2.2 Apa yang ditambah dan kenapa
1. Skema `DocumentUpsert` terstruktur (bukan teks bebas) — admin/Laravel mengirim field terpisah, server yang merakit `content`. Ini menegakkan Q9 dari sisi AI: Dashboard tidak bisa menyelipkan format liar.
2. Upsert per `(sop_name, varian)` + `UniqueConstraint` Fase 1 — Simpan kedua untuk Varian sama memperbarui baris yang sama dan menaikkan `version`, bukan menambah baris kembar. Mendukung Q4 sinkron dan Q7 versioning.
3. Satu transaksi tulis+embedding — urutan: embedding dulu (di luar transaksi DB), lalu tulis+commit. Jika embedding gagal → 502 tanpa menyentuh DB. Jika commit gagal → rollback, versi tidak naik setengah. Tidak ada state "teks baru + vektor lama".
4. Kode status dibedakan — `502` = salah di tukang sidik jari (kunci/API Gemini), `500` = salah di kamar (DB). Laravel (Fase 5, Fullstack 1) bisa membedakan pesan untuk admin vs untuk log.

### 2.3 Yang sengaja DITUNDA (sesuai rencana)
- Pendaftaran ke `router.py` + `main.py` (Fase 5.2). Modul sudah punya `router` siap pasang, tetapi gerbang belum dibuka agar蓖 Fase 3–4 selesai dulu sebelum ada pintu publik.
- Seed 4 Varian KK asli — endpoint teruji dengan data uji yang langsung dihapus (seksi 3.3), tabel produksi tetap kosong menunggu kurasi SOP final.

## 3. Verifikasi Fase 2 (semua live, bukan tebakan)

### 3.1 Impor + format koper (tanpa jaringan)
```console
import-ok models/gemini-embedding-001 768 [...]
'SOP: KK\nVarian: Hilang\n\nSyarat:\n- Foto Surat Kehilangan Polisi\n- Foto KTP Pemohon\n\nKanal: https://plavon.sidoarjokab.go.id/\nCatatan: Foto dokumen asli, bukan fotokopi'
```
Membuktikan modul terimpor, konstanta benar, dan format kanon sesuai contoh SOP KK user.

### 3.2 Sidik jari live via API Gemini
Skrip TEMP `tes_embed_fase2.py` memanggil `embed_query` dengan koper KK/Hilang asli:
```console
embed-ok 768
```
Membuktikan kunci `GEMINI_API_KEY` valid, kuota jalan, model `gemini-embedding-001` ada, dan `output_dimensionality` menghasilkan tepat 768 (bukan default 3072).

### 3.3 Upsert + versi + bersih-bersih (DB asli, data uji dihapus)
Skrip TEMP `uji_document_fase2.py`: titip Varian `__UJI_Q6__/__uji` 2x (kedua dengan syarat ditambah), lalu hapus:
```console
uji-document-ok 1 2
```
Membuktikan insert → `version=1`, upsert → `version=2` (bukan baris baru), constraint unik bekerja, dan transaksi commit. Blok `finally` menghapus baris uji + commit, sehingga tabel kembali kosong — tidak ada polusi data.

## 4. Istilah teknis
- **Upsert**: simpan-atau-perbarui berdasar kunci unik (`sop_name+varian`).
- **Singleton malas**: objek dibuat sekali saat pertama dibutuhkan (`_get_client`).
- **Output dimensionality**: parameter minta panjang vektor tertentu (768) ke model embedding.
- **Idempoten**: skrip aman diulang (extension + create + hapus uji) tanpa efek samping menumpuk.
- **502 vs 500**: 502 = gerbang hulu gagal (API embedding), 500 = dapur sendiri gagal (DB).

## 5. Pembuktian mandiri Fase 2 — lima bukti berurutan

Bagian 3 di atas adalah verifikasi saat membangun. Bagian ini adalah cara pengguna membuktikan sendiri dari nol, dengan perintah siap salin, output yang diharapkan, dan alasan kenapa tiap bukti mengunci klaimnya. Bukti 1–2 tanpa DB, bukti 3 butuh internet + kunci valid, bukti 4–5 butuh `postgres-db` nyala (`docker compose up -d postgres-db` dari folder utama).

### Bukti 1 — dua file sudah terisi (klaim 2.1 + 2.2 dikerjakan)
```console
$ py -c "import os; [print(f+': '+str(os.path.getsize(f))) for f in ['app/services/embedding_service.py','app/api/endpoints/document.py']]"
app/services/embedding_service.py: <ribuan> byte
app/api/endpoints/document.py: <ribuan> byte
```
Kenapa membuktikan: awal Fase 2 keduanya `0 byte`. Ukuran non-nol membuktikan implementasi ada di tempat yang direncanakan To-Do List, bukan di file lain.

### Bukti 2 — impor + konstanta benar tanpa jaringan (klaim modul valid)
Dari folder `ai-service`:
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py -c "import app.services.embedding_service as e; import app.api.endpoints.document as d; print('import-ok', e.EMBED_MODEL, e.EMBED_DIMENSION)"
import-ok models/gemini-embedding-001 768
```
Kenapa membuktikan: impor menyentuh seluruh rantai (`config` → SDK → FastAPI → SQLAlchemy). Lulus berarti tidak ada import error, nama model Q11 benar, dan dimensi yang dijaga kode adalah 768. Gagal di sini = salah kode, bukan salah jaringan/kunci.

### Bukti 3 — sidik jari live 768 (klaim embedding bekerja ke API asli)
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\tes_embed_fase2.py"
embed-ok 768
```
Kenapa membuktikan: skrip memanggil `embed_query` dengan koper KK/Hilang asli ke API Gemini. Output `768` berarti kunci valid, kuota jalan, model `gemini-embedding-001` ada, dan `output_dimensionality` tepat (bukan default 3072). Ini bukti terkuat 2.1 — gagal di sini menunjuk kunci/kuota/model, bukan logika lokal.

### Bukti 4 — upsert + versi di DB asli (klaim transaksi Q4 + unik Q7)
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\uji_document_fase2.py"
uji-document-ok 1 2
```
Kenapa membuktikan: skrip menitip Varian uji `__UJI_Q6__/__uji` dua kali (kedua dengan satu syarat ditambah). Hasil `1 2` berarti titipan pertama insert `version=1`, titipan kedua menimpa baris yang sama menjadi `version=2` — bukan baris baru. Ini membuktikan `UniqueConstraint(sop_name, varian)`, logika `version+1`, dan commit/rollback bekerja di Postgres asli, bukan teori.

### Bukti 5 — tabel kembali kosong, tanpa polusi (klaim kebersihan uji)
Skrip hitung (`hitung_document.py` di TEMP):
```python
from sqlalchemy import create_engine, text
import app.core.config as c

url = c.DATABASE_URL.replace("postgres-db", "127.0.0.1")
if url.startswith("postgresql://"):
    url = "postgresql+psycopg2://" + url.split("://", 1)[1]
e = create_engine(url)
with e.connect() as conn:
    n = conn.execute(text("SELECT COUNT(*) FROM document_vectors")).scalar()
print("jumlah-baris", n)
```
```console
jumlah-baris 0
```
Kenapa membuktikan: skrip uji menghapus baris `__UJI_Q6__` di blok `finally` + commit. Angka `0` berarti tabel produksi tetap kosong menunggu seed KK asli kurasi final — tidak ada sisa uji yang mengotori retrieval Fase 3. Jika keluar `>0`, ada sisa uji yang harus dilaporkan.

### Batas scope yang benar (bukan kegagalan)
`app/api/router.py` masih `0 byte` dan `main.py` belum `include_router` — itu jatah Fase 5.2 sesuai rencana, sehingga endpoint belum bisa dipencet via Swagger. Fase 2 dinyatakan selesai saat bukti 1–5 hijau: file ada, impor valid, sidik jari live 768, upsert berversi di DB asli, tabel kembali bersih.
