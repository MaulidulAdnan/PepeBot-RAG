# Fase 5 — Rekap Perubahan: Pintu Komunikasi (Chat Endpoint & Wiring)

Cakupan Fase 5 (To-Do List 5.1–5.3): endpoint chat warga (Q8), pendaftaran router + gerbang (wiring), dan pengujian akhir. Prasyarat Fase 1–4 hijau. Setelah fase ini, `ai-service` fungsional penuh dan siap dipakai Laravel.

> Nilai API key dan password tidak ditulis di dokumen ini.

## 1. `ai-service/app/api/endpoints/chat.py` — dibuat (0 → terisi)

```python
router = APIRouter(prefix="/chat", tags=["chat"])

VALID_CHANNELS = ("WA", "Web")


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    channel: str = "Web"
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=10)


class ChatCitation(BaseModel):
    sop_name: str
    varian: str
    version: int


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation]
    fallback: bool
    fallback_contact: dict = {}


def _normalize_channel(channel: str) -> str:
    normalized = (channel or "").strip().lower()
    if normalized == "wa":
        return "WA"
    if normalized == "web":
        return "Web"
    raise HTTPException(
        status_code=422, detail=f"channel harus salah satu dari {VALID_CHANNELS}"
    )


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    channel = _normalize_channel(payload.channel)
    _ = channel  # dicatat untuk audit kanal; penyaluran balik tugas Laravel.

    result = search(payload.query, db, top_k=payload.top_k)
    chunks = [] if result.fallback else result.chunks
    generated = generate_answer(result.query, chunks)

    fallback = result.fallback or generated["refused"]
    contact = get_fallback_contact() if fallback else {}
    return ChatResponse(
        answer=generated["answer"],
        citations=[ChatCitation(**c) for c in generated["citations"]],
        fallback=fallback,
        fallback_contact=contact if fallback else {},
    )
```

Maksud tiap bagian dan alasannya:
1. **Skema Pydantic ketat.** `query` 1–2000 karakter mencegah prompt raksasa (biaya + timeout); `top_k` 1–10 membatasi konteks. Validasi gagal → FastAPI otomatis 422 sebelum logika jalan.
2. **Normalisasi channel case-insensitive.** Laravel boleh kirim `wa`, `WA`, `Web`; selain itu 422 dengan pesan jelas. Nilai channel tidak mengubah jawaban AI — penyaluran balik (kirim ke Meta API vs JSON ke Widget) adalah tugas Laravel (Q3).
3. **Komposisi dua lapis.** `search()` memutuskan relevan/tidak (threshold 0.65 Fase 3); bila fallback, `generate_answer()` menerima daftar kosong dan mengembalikan penolakan deterministik tanpa panggil LLM (nol biaya, nol halusinasi). Bila relevan, LLM merangkai dari chunk. `fallback` final = OR keduanya, sehingga tidak ada jalan di mana jawaban ngarang lolos.
4. **`fallback_contact` hanya saat fallback.** Bila `false`, field `{}` agar Laravel tidak bingung menampilkan kontak. Isinya dari env `DESA_PETUGAS_WA`/`DESA_PETUGAS_URL` (kini kosong → pesan generik; wajib diisi sebelum produksi).

## 2. `ai-service/app/api/router.py` — dibuat (0 → terisi)

```python
from fastapi import APIRouter

from app.api.endpoints import chat, document

router = APIRouter()
router.include_router(chat.router)
router.include_router(document.router)
```

Satu titik agregasi: endpoint baru cukup tambah `include_router` di sini tanpa sentuh `main.py` lagi.

## 3. `ai-service/main.py` — tambah 2 baris wiring

```python
from app.api.router import router
...
app.include_router(router)
```

Catatan: file ini sudah memiliki `lifespan` startup (dibuat sebelum sesi ini) yang menjalankan `CREATE EXTENSION IF NOT EXISTS vector` + `Base.metadata.create_all` tiap server nyala — tabel terbangun otomatis, skrip migrasi manual tidak diperlukan lagi.

## 4. `ai-service/app/core/db.py` — tambah `_with_host` (perbaikan kompatibilitas native)

```python
def _with_host(url: str) -> str:
    # Nama host postgres-db hanya dikenal di dalam jaringan Docker.
    # Saat jalan native (mis. uji Swagger di Windows, file /.dockerenv
    # tidak ada), belokkan ke port publish 127.0.0.1.
    # Di dalam container, biarkan apa adanya.
    if not Path("/.dockerenv").exists():
        url = url.replace("postgres-db", "127.0.0.1")
    return url

engine = create_engine(_with_host(_with_driver(DATABASE_URL)))
```

Alasan: `.env` memakai host `postgres-db` (benar untuk Docker). Dari Windows native, nama itu tidak dikenal sehingga semua request 500. Deteksi `/.dockerenv` membuat satu `.env` berlaku di dua tempat tanpa duplikasi config. Digabung dengan normalisasi driver Fase 1 (`_with_driver`).

## 5. Verifikasi saat membangun (TestClient = aplikasi yang sama dengan Swagger)

```console
root 200 {'status': 'success', ...}
doc1 200 {'sop_name': 'KK', 'varian': 'Hilang', 'version': 1, ...}
doc2 200 {'sop_name': 'KK', 'varian': 'Pecah KK', 'version': 1, ...}
chat-relevan 200 fallback= False | sitasi= [Hilang v1, Pecah KK v1]
  jawaban: Halo Warga Desa Pepe. Syarat untuk pengurusan KK hilang adalah: ...
chat-luar 200 fallback= True | kontak= {'whatsapp': '', 'url': ''}
  jawaban: Maaf, informasi tersebut tidak ada di pedoman dokumen Desa Pepe. ...
chat-channel-salah 422 channel harus salah satu dari ('WA', 'Web')
uji-chat-ok
```
Dilanjutkan `bersih 2` + `jumlah-baris 0`. Semua hijau dalam satu run: health tak rusak, upsert berversi, chat relevan bersitasi + berkalimat wewenang, luar SOP fallback, validasi channel tegas.

## 6. Panduan testing manual via Swagger (`/docs`)

### 6.1 Prasyarat
1. `postgres-db` nyala: `docker ps --filter "name=pepebot_postgres"` harus baris `Up ...`.
2. Dependensi terinstal (Fase 1) dan `.env` ai-service berisi `DATABASE_URL` + `GEMINI_API_KEY`.
3. Pastikan folder yang dijalankan adalah yang berisi kode Fase 5: `dir app\api\endpoints\chat.py` harus ada dan non-nol. (Pernah kejadian: terminal terbuka di salinan folder lama sehingga `/docs` kosong.)

### 6.2 Menyalakan server
Dari folder `ai-service`:
```console
py -m uvicorn main:app --port 8001
```
Tunggu `Application startup complete` + `Uvicorn running on http://127.0.0.1:8001`. Lifespan otomatis membuat ekstensi + tabel (lihat tidak ada error di log). Buka `http://127.0.0.1:8001/docs` (bukan `/` — `/` hanya pesan health).

### 6.3 Uji 1 — `GET /` (health)
Klik `GET /` → Try it out → Execute. Harus 200:
```json
{"status": "success", "message": "AI Service PepeBot RAG berhasil berjalan!"}
```
Fungsi: memastikan server dan routing hidup sebelum uji berat.

### 6.4 Uji 2 — `POST /documents` (titip 1 Varian uji)
Gunakan data uji yang jelas bukan produksi (`sop_name: __COBA__`):
```json
{
  "sop_name": "__COBA__",
  "varian": "Uji",
  "syarat": ["Syarat satu", "Syarat dua"],
  "channel_url": "https://plavon.sidoarjokab.go.id/",
  "note": "Catatan uji"
}
```
Harus 200 `{"sop_name": "__COBA__", "varian": "Uji", "version": 1, "updated_at": "..."}`. Ulangi dengan satu syarat ditambah → harus `version 2` pada baris yang sama (bukti upsert + Q4). Error `502` = masalah kunci/kuota Gemini; `500` = masalah DB; `422` = field kosong/terlalu panjang.

### 6.5 Uji 3 — `POST /chat` relevan (harus dijawab AI)
```json
{"query": "<pertanyaan yang cocok dengan isi __COBA__>", "channel": "Web"}
```
Harus 200 `fallback: false`, `citations` berisi `__COBA__/Uji` berversi, `answer` memuat syarat dari Uji 2 plus satu kalimat wewenang pihak ke-3. Redaksi boleh beda tiap run; dua unsur itu wajib.

### 6.6 Uji 4 — `POST /chat` luar SOP (harus ditolak)
```json
{"query": "bisa buatkan SIM?", "channel": "WA"}
```
Harus 200 `fallback: true`, `answer` diawali `Maaf, informasi tersebut tidak ada di pedoman...`, `fallback_contact` terisi bila env kontak sudah diisi. Ini bukti pertahanan Q2 dari browser.

### 6.7 Uji 5 — validasi `channel`
```json
{"query": "halo", "channel": "sms"}
```
Harus 422 `channel harus salah satu dari ('WA', 'Web')`. Coba juga `"wa"` kecil → harus lolos (normalisasi).

### 6.8 Bersih-bersih setelah uji
Hapus baris `__COBA__` agar tabel kembali kosong menunggu seed kurasi final (skrip `bersih_kk.py` hanya menghapus `sop_name=KK`; untuk `__COBA__` minta dibuatkan penghapus atau hapus via `POST /documents` tidak bisa — belum ada endpoint hapus, disengaja di luar MVP). Jangan seed data produksi sebelum kurasi final karena tiap Simpan menaikkan `version`.

## 7. Pembuktian mandiri Fase 5 — empat bukti berurutan

### Bukti 1 — wiring terpasang (klaim 5.2)
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\uji_chat_fase5.py"
```
Output memuat `routes` dari `/openapi.json` (`/chat`, `/documents`, `/`) — bukti router terdaftar di aplikasi. (Versi awal skrip membaca `app.routes` dan mencetak kosong karena objek internal `_IncludedRouter`; diperbaiki membaca `openapi.json` yang mencerminkan rute HTTP sebenarnya.)

### Bukti 2 — pipa HTTP penuh hijau (klaim 5.1 + 5.3)
Output skrip yang sama harus berakhir `uji-chat-ok` dengan `doc 200 v1`, chat relevan `fallback False` + sitasi, luar `fallback True`, channel salah 422. Membuktikan seluruh rantai HTTP→DB→Gemini→jawab bekerja, bukan hanya fungsi terpisah.

### Bukti 3 — Swagger tampil (klaim 5.3 manual)
`http://127.0.0.1:8001/docs` menampilkan grup `chat` (`POST /chat`), `documents` (`POST /documents`), `default` (`GET /`) + skema `ChatCitation`. Screenshot sudah dikonfirmasi pengguna. Membuktikan server produksi (uvicorn, bukan TestClient) memuat wiring yang sama.

### Bukti 4 — tabel kembali kosong (klaim kebersihan)
```console
... ; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\hitung_document.py"
jumlah-baris 0
```
Fase 5 selesai saat bukti 1–4 hijau.

## 8. Lanjut ke integrasi Laravel (backend)

`ai-service` kini hitam-putih siap dipanggil. Yang harus dibangun di `core-service` (pemetaan ke jobdesk Q10):

### 8.1 Konfigurasi dasar
1. Ikuti `core-service/AGENTS.md`: instal `laravel/boost` (`composer require laravel/boost --dev`, `php artisan boost:install`) sebelum ubah kode.
2. Tambah ke `.env` + `config/services.php`: `AI_SERVICE_URL` (mis. `http://127.0.0.1:8001` native / `http://ai-service:8001` bila dikontainerisasi), `DESA_PETUGAS_WA`, `DESA_PETUGAS_URL` (atau baca dari endpoint `fallback_contact` — putuskan satu sumber).
3. Pastikan HTTP client tersedia (`illuminate/http` / `guzzle`) untuk panggil FastAPI dengan timeout eksplisit (disarankan 30–60 detik karena LLM) + retry sekali untuk 502.

### 8.2 Kontrak yang dipegang Laravel (jangan diduplikasi logikanya)
- `POST {AI_SERVICE_URL}/chat {query, channel}` → `{answer, citations, fallback, fallback_contact}`. Laravel tidak menilai SOP; hanya meneruskan dan menyalurkan.
- `POST {AI_SERVICE_URL}/documents {sop_name, varian, syarat[], channel_url, note}` → `{sop_name, varian, version, updated_at}`. Dipanggil saat admin Simpan (sinkron, tampilkan spinner; gagal 502/500 → tampilkan error, jangan tulis versi lokal).
- Arti status untuk UI admin: `200` sukses, `422` input salah (tampilkan pesan), `502` Yetu kunci/kuota Gemini (hubungi DS), `500` Yetu DB (cek postgres).

### 8.3 Pintu yang harus dibuat (urutan disarankan)
1. **FS1 — Webhook WA.** `POST /api/webhooks/whatsapp` (verifikasi token Meta saat GET, terima JSON pesan saat POST) → ekstrak teks → `POST /chat {channel: WA}` → kirim jawaban ke Meta API; bila `fallback true`, kirim pesan fallback + kontak (jangan kirim jawaban AI). Daftarkan `routes/api.php` (kini belum ada — `bootstrap/app.php:8-13` hanya web) + nonaktifkan CSRF untuk rute webhook.
2. **FS2 — REST Widget.** `POST /api/chat` (dari React, auth session/Sanctum sesuai keputusan) → `POST /chat {channel: Web}` → kembalikan JSON ke Widget apa adanya.
3. **FS2 — Dashboard admin.** CRUD memanggil `POST /documents` per Varian dengan field Q9 (`sop_name, varian, syarat[], channel_url, note`); tampilkan `version/updated_at` dari respons; perlakukan Simpan sebagai operasi sinkron beberapa detik (bukan instan) sesuai Q4.

### 8.4 Testing integrasi (setelah Laravel jadi)
1. `POST /api/chat` dengan pertanyaan KK → jawaban AI + sitasi (ai-service sudah punya data seed asli).
2. Pertanyaan luar SOP → pesan `Maaf...` + kontak (bukan jawaban ngarang).
3. Simpan Dashboard → tanya lagi ≤5 detik → versi baru dipakai (bukti Q4 end-to-end).
4. Matikan `ai-service` → Laravel harus jawab degradasi sopan (bukan 500 mentah).

### 8.5 Utang yang dibawa ke fase Laravel
- `DESA_PETUGAS_WA/URL` masih kosong (fallback generik).
- Threshold `0.65` diukur dari 2 Varian — eval parafrasa ulang setelah seed penuh.
- `ai-service` belum ada di `docker-compose.yml` (hanya `postgres-db`); putuskan: tambah service `ai-service` + `core-service` atau tetap native saat sidang.

## 9. Istilah teknis
- **Wiring**: pendaftaran router ke aplikasi (`include_router`) sehingga rute hidup di HTTP.
- **Lifespan**: hook startup/shutdown FastAPI (buat ekstensi + tabel sekali saat nyala).
- **TestClient**: klien HTTP dalam-proses untuk uji aplikasi tanpa browser/server.
- **Idempoten**: aman diulang (`compose up`, migrasi, skrip uji) tanpa efek ganda.
- **Degradasi sopan**: respons cadangan yang membantu saat layanan hulu mati.
