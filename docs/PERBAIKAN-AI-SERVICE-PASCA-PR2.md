# Perbaikan `ai-service` Setelah PR #2 — Rekap Perubahan dan Alasannya

Dokumen ini mencatat seluruh perubahan yang dilakukan setelah commit `30f2295` ("fix ai-service logic, and code testing") masuk ke branch `main`, mengapa perubahan itu diperlukan, apa risiko bila tidak dilakukan, dan di mana tepatnya perubahan berada.

Ruang lingkup: `ai-service` saja. `core-service` belum disentuh.

> Nilai `GEMINI_API_KEY`, password database, dan `INTERNAL_API_KEY` tidak ditulis di dokumen ini.

## 1. Ringkasan eksekutif

PR #2 mengubah arsitektur konfigurasi `ai-service`: dari `os.getenv` + dua file `.env` menjadi `pydantic-settings`, menghapus helper koneksi `_with_driver`/`_with_host`, memindahkan seluruh rute ke prefix `/api`, dan menaruh kontak fallback langsung di dalam kode.

Refactor itu membuat kode lebih rapi, tetapi meninggalkan empat hal yang membuat layanan tidak bisa dioperasikan atau sulit dipelihara:

| # | Temuan | Dampak |
|---|---|---|
| 1 | Kontak petugas hardcode di `llm_service.py` | Nomor tidak bisa diganti tanpa mengubah kode dan build ulang |
| 2 | `seed_master_sop.py` mengimpor simbol yang sudah dihapus | Seeder pasti `ImportError`; data tidak bisa dibangun ulang |
| 3 | `INTERNAL_API_KEY` wajib tetapi tidak dipakai | Variabel rahasia tidak melindungi apa pun; endpoint terbuka |
| 4 | `.env.example` tidak lengkap dan tidak terlacak git | Anggota tim tidak punya templat; aplikasi gagal start bila menyalin yang lama |

Perbaikan dilakukan dengan prinsip **kompatibel ke belakang**: nilai lama tetap menjadi default, sehingga perilaku temanmu tidak berubah bila environment tidak diisi.

Hasil akhir: 4 file kode diubah (`config.py`, `llm_service.py`, `seed_master_sop.py`, `router.py`), 1 modul keamanan baru (`security.py`), 1 file contoh dilengkapi, dan 2 dokumen baru (addendum kontrak serta laporan ini). Seluruh perilaku diuji ulang secara native.

## 2. Kronologi singkat

1. `main` berisi `2b7f6e1` (pekerjaan Fase 1–5) lalu `bee4a85` (merge PR #2).
2. PR #2 menulis ulang 9 modul inti dan `docker-compose.yml`.
3. Container `pepebot_ai` mati karena image lama belum memuat `pydantic-settings`.
4. Setelah dependensi dipasang dan image di-build, muncul temuan berikutnya: `INTERNAL_API_KEY` tidak dipakai, kontak hardcode, seeder rusak.
5. Perbaikan diterapkan dan diuji tanpa Docker terlebih dahulu, agar bila ada kesalahan tidak bercampur dengan masalah container.

## 3. Temuan awal dan buktinya

### 3.1 Image tidak memuat dependensi baru

```
File "/app/app/core/config.py", line 1, in <module>
ModuleNotFoundError: No module named 'pydantic_settings'
```

Penyebab: `requirements.txt` diubah `2026-10-24 22:37`, sedangkan image dibangun sebelum itu. Container juga hanya di-*restart* (`Created 2026-10-10`, `Started 2026-10-25`), sehingga konfigurasi Compose baru belum diterapkan.

### 3.2 Seeder mengimpor simbol yang sudah tidak ada

```python
from app.core.db import Base, _with_host, _with_driver
from app.core.config import DATABASE_URL
```

Ketiga nama itu sudah dihapus pada PR #2. Mengimpor modul seeder akan langsung gagal.

### 3.3 Kontak fallback berada di dalam kode

```python
FALLBACK_WA = "081234567890"
FALLBACK_URL = "https://pepe.desa.id"
```

Nilai ini benar (kontak asli petugas), tetapi tidak bisa diubah lewat konfigurasi. Padahal `config.py` sudah mendeklarasikan pola yang sama untuk variabel lain.

### 3.4 `INTERNAL_API_KEY` wajib tetapi tidak dibaca siapa pun

```python
class Settings(BaseSettings):
    ...
    INTERNAL_API_KEY: str
```

Pencarian di seluruh `ai-service` hanya menemukan satu kemunculan: deklarasi itu sendiri. Artinya variabel wajib tanpa fungsi.

### 3.5 `.env.example` hanya berisi dua baris

```
DATABASE_URL=postgresql://${DB_USERNAME:-admin}:...@postgres-db:5432/${DB_DATABASE:-pepebot_db}
GEMINI_API_KEY=isi_dengan_api_key_gemini_anda
```

Dua masalah: `INTERNAL_API_KEY` tidak ada (padahal wajib), dan `${...}` tidak diekspansi oleh `pydantic-settings`, sehingga baris `DATABASE_URL` pada contoh itu menyesatkan.

## 4. Perubahan 1 — `app/core/config.py`: kontak menjadi konfigurasi

### Kode akhir

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    INTERNAL_API_KEY: str
    GEMINI_API_KEY: str
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = 768
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    RETRIEVAL_THRESHOLD: float = 0.65
    TOP_K: int = 4
    # Kontak fallback: nilai di bawah adalah default lama (tetap dipakai bila env
    # tidak diisi), tetapi bisa ditimpa lewat environment/.env tanpa ubah kode.
    DESA_PETUGAS_WA: str = "081234567890"
    DESA_PETUGAS_URL: str = "https://pepe.desa.id"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings() # type: ignore
```

### Di mana

Di dalam `class Settings`, tepat setelah `TOP_K`.

### Mengapa

`pydantic-settings` membaca field dengan urutan prioritas: variabel environment proses lebih tinggi daripada isi `.env`. Dengan menambahkan dua field ini, nomor petugas bisa diganti lewat `.env` atau `docker-compose.yml` tanpa menyentuh Python.

### Mengapa tetap diberi default

Temanmu sengaja menaruh nilai langsung di kode agar layanan bisa jalan tanpa konfigurasi tambahan. Default mempertahankan sifat itu: salin repo, isi tiga variabel wajib, layanan langsung berfungsi. Kalau field ini dibuat wajib tanpa default, setiap kali env lupa diisi aplikasi gagal start — padahal kontak punya nilai yang sudah benar.

### Alternatif yang ditolak

| Alternatif | Alasan ditolak |
|---|---|
| Tanpa default, wajib di env | Menambah titik gagal startup tanpa manfaat; kontak sudah diketahui |
| Tetap hardcode | Nomor tidak bisa diganti saat petugas berganti; setiap perubahan butuh build ulang |
| Simpan kontak di database | Menambah tabel, migrasi, dan endpoint baru untuk satu nilai statis |

### Risiko bila tidak diubah

1. Pergantian nomor petugas mengharuskan edit kode, commit, build image, dan recreate container.
2. `DESA_PETUGAS_WA`/`DESA_PETUGAS_URL` di `.env` akan diabaikan tanpa peringatan, sehingga operator mengira sudah mengganti kontak padahal tidak.
3. Nilai uji dan produksi bercampur di dalam kode, menyulitkan audit saat sidang.

## 5. Perubahan 2 — `app/services/llm_service.py`: membaca settings

### Kode akhir

```python
from google import genai
from app.core.config import settings
from app.services.rag_engine import RetrievedChunk

LLM_MODEL = settings.LLM_MODEL

# Kontak darurat jika data tidak ditemukan. Default ada di config.py; isi
# DESA_PETUGAS_WA / DESA_PETUGAS_URL di environment bila ingin menimpanya.
FALLBACK_WA = settings.DESA_PETUGAS_WA
FALLBACK_URL = settings.DESA_PETUGAS_URL
```

### Di mana

Lima baris pertama modul, menggantikan dua konstanta hardcode.

### Mengapa

Satu sumber kebenaran. Sebelumnya `config.py` dan `llm_service.py` sama-sama menyimpan nilai yang seharusnya satu. Dengan pembacaan dari `settings`, tidak ada lagi dua tempat yang bisa berbeda.

### Risiko bila tidak diubah

- Nilai di `.env` tidak berpengaruh, tetapi tetap terlihat seolah berpengaruh. Ini jenis kesalahan yang paling mahal saat demo: operator mengubah env, menguji, tetap melihat nomor lama.
- Tidak ada cara mengganti kontak pada instalasi desa lain tanpa fork kode.

### Catatan perilaku

Nilai default di `config.py` identik dengan hardcode sebelumnya, sehingga jawaban fallback saat ini **tidak berubah**:

```
Maaf, informasi tersebut tidak ada di pedoman dokumen Desa Pepe.
Silakan hubungi WhatsApp petugas: 081234567890 / Info lanjut: https://pepe.desa.id.
```

## 6. Perubahan 3 — `seed_master_sop.py`: memakai session aplikasi

### Kode sebelum

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, _with_host, _with_driver
from app.core.config import DATABASE_URL
...
def main() -> None:
    engine = create_engine(_with_host(_with_driver(DATABASE_URL)))
    Session = sessionmaker(bind=engine)
    db = Session()
```

### Kode sesudah

```python
from app.core.db import SessionLocal
from app.models import document_vector  # noqa: F401 (daftarkan tabel)
from app.api.endpoints.document import DocumentUpsert, upsert_document
...
def main() -> None:
    # Memakai engine/session yang sama dengan aplikasi (app.core.db) agar
    # konfigurasi koneksi hanya ada di satu tempat.
    db = SessionLocal()
```

### Di mana

Blok impor (baris 9–15) dan awal fungsi `main()`.

### Mengapa

1. **Membuat seeder bisa dijalankan kembali.** Sebelumnya pasti gagal karena tiga nama yang diimpor sudah tidak ada.
2. **Menghapus duplikasi konfigurasi koneksi.** `app/core/db.py` sudah membangun engine dari `settings.DATABASE_URL`; seeder tidak perlu membangun engine sendiri.
3. **Konsisten dengan jalur produksi.** Seed memakai `upsert_document` yang sama dengan endpoint `POST /api/documents`, sehingga pengujian seeder sekaligus menguji logika versi dan embedding.

### Risiko bila tidak diubah

1. **Data tidak dapat dibangun ulang.** Saat ini 20 Varian hanya ada di volume `pepebot-rag_pgdata`. Jika volume dihapus (`docker compose down -v`), atau proyek dipindah ke laptop sidang, tidak ada cara memulihkan data selain mengetik ulang 20 Varian lewat Swagger.
2. **Pengetahuan kurasi hilang.** Keputusan seperti membuang penanda `[cite: N]`, mengosongkan `channel_url` untuk surat desa, dan menambah 4 Varian KK dari percakapan tertulis di file itu. Tanpa seeder yang jalan, keputusan tersebut tidak dapat direproduksi.
3. **Regresi tidak terdeteksi.** Seeder adalah satu-satunya jalan menguji ulang seluruh 20 Varian dalam satu perintah.

### Catatan penting

Seeder **tidak dijalankan ulang** dalam sesi ini. Menjalankannya akan menaikkan seluruh baris dari `v1` ke `v2` tanpa perubahan isi. Verifikasi dilakukan dengan mengimpor modul dan menguji `SessionLocal`, bukan dengan mengeksekusi `main()`.

## 7. Penambahan 4 — `app/core/security.py` dan pemasangan di router

### Kode baru

```python
"""Autentikasi antar-service.

Laravel wajib mengirim header `X-Internal-Key` yang nilainya sama dengan
INTERNAL_API_KEY. Endpoint kesehatan (`/`) sengaja dibiarkan terbuka agar
monitoring tetap bisa mengecek status tanpa membawa rahasia.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

_internal_key_header = APIKeyHeader(name="X-Internal-Key", auto_error=False)


def verify_internal_key(key: str | None = Security(_internal_key_header)) -> None:
    if not settings.INTERNAL_API_KEY or key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Internal-Key tidak valid",
        )
```

### Perubahan pada `app/api/router.py`

```python
from fastapi import APIRouter, Depends

from app.api.endpoints import chat, document
from app.core.security import verify_internal_key

api_router = APIRouter(dependencies=[Depends(verify_internal_key)])
api_router.include_router(chat.router)
api_router.include_router(document.router)
```

### Mengapa dipasang di router, bukan di setiap endpoint

Satu baris melindungi semua endpoint yang didaftarkan. Bila nanti ada endpoint baru, cukup `include_router` dan otomatis ikut terlindungi. Ini mencegah kesalahan lupa memasang dependency pada endpoint baru.

### Mengapa `auto_error=False`

`APIKeyHeader` dengan `auto_error=True` akan melempar `403` dengan pesan bawaan saat header tidak ada. Dengan `False`, kode kita sendiri yang memutuskan status dan pesan, sehingga perilakunya seragam: header hilang dan header salah sama-sama `401` dengan pesan yang bisa dipahami.

### Mengapa `GET /` tidak dilindungi

Health check dipakai untuk memastikan proses hidup. Membutuhkan rahasia untuk mengecek status menyulitkan monitoring dan tidak menambah keamanan berarti, karena endpoint itu tidak menyentuh data maupun Gemini.

### Risiko bila tidak diubah

1. **Variabel rahasia tanpa fungsi.** `INTERNAL_API_KEY` wajib diisi, tetapi tidak memverifikasi apa pun. Ini memberi rasa aman yang salah.
2. **Endpoint terbuka bagi proses lokal mana pun.** Selama port hanya diikat ke `127.0.0.1`, risikonya terbatas pada proses di mesin yang sama. Namun bila nanti port dibuka untuk jaringan, reverse proxy dipasang, atau `ai-service` dijalankan di server bersama, siapa pun dapat memanggil `/api/documents` dan menaikkan versi data, atau memicu biaya Gemini berulang.
3. **Kontrak Laravel tidak teruji.** Tanpa verifikasi, integrasi nanti tidak membuktikan bahwa Laravel memang mengirim identitas service.

### Konsekuensi yang harus diterima

- Swagger memerlukan tombol **Authorize** sebelum endpoint bisa dipanggil.
- Laravel **wajib** mengirim `X-Internal-Key` pada setiap panggilan.
- Skrip uji manual harus menyertakan header tersebut.

### Mengapa tetap dipilih

Alternatifnya adalah membiarkan variabel wajib yang tidak berguna, atau menghapus `INTERNAL_API_KEY` dari `Settings`. Menghapus berarti membuang niat temanmu menyiapkan autentikasi antar-service. Memasang verifikasi sekarang membuat kontraknya eksplisit sebelum Laravel ditulis, sehingga Laravel sejak awal dibangun dengan header yang benar.

## 8. Penambahan 5 — `ai-service/.env`: kontak eksplisit

### Isi yang ditambahkan

```
# Kontak petugas untuk jawaban fallback (dipakai llm_service)
DESA_PETUGAS_WA=081234567890
DESA_PETUGAS_URL=https://pepe.desa.id
```

### Mengapa

Kamu mencarinya di `.env` dan tidak menemukannya karena sebelumnya hanya ada di kode. Menuliskannya membuat konfigurasi terlihat di tempat yang diharapkan operator. Nilainya sama dengan default, jadi tidak ada perubahan perilaku.

### Risiko bila tidak ditambahkan

Tidak ada risiko teknis, karena default sudah benar. Risikonya operasional: operator tidak tahu variabel itu ada, lalu mengubah kode untuk mengganti nomor.

## 9. Perubahan 6 — `ai-service/.env.example`: templat lengkap

### Isi akhir

```
# --- Wajib ---
INTERNAL_API_KEY=ganti_dengan_string_acak_panjang
GEMINI_API_KEY=isi_dengan_api_key_gemini_anda

# --- Opsional (semua punya default di app/core/config.py) ---
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIM=768
LLM_MODEL=gemini-3.5-flash-lite
RETRIEVAL_THRESHOLD=0.65
TOP_K=4
DESA_PETUGAS_WA=081234567890
DESA_PETUGAS_URL=https://pepe.desa.id

# --- Hanya untuk menjalankan native (tanpa Docker) ---
# Di Docker, Compose sudah menyuntikkan DATABASE_URL dari .env root,
# sehingga tidak perlu ditulis di sini. Nilai harus literal (tanpa ${...})
# dan host 127.0.0.1 karena nama "postgres-db" hanya ada di jaringan Docker.
# DATABASE_URL=postgresql://admin:password_database_disini@127.0.0.1:5432/pepebot_db
```

### Mengapa

Templat adalah satu-satunya cara anggota tim mengetahui variabel mana yang wajib. Sebelumnya templat tidak memuat `INTERNAL_API_KEY`, sehingga siapa pun yang menyalinnya akan mendapat `ValidationError` saat start tanpa tahu penyebabnya. Baris `DATABASE_URL` lama juga menyesatkan karena memakai `${...}` yang tidak diekspansi.

### Mengapa `DATABASE_URL` dikomentari

Di Docker, nilai itu disuntikkan Compose dari `.env` root. Menuliskannya kembali di `ai-service/.env` berarti menyimpan kredensial yang sama di dua tempat. Komentar menjelaskan cara memakainya untuk jalur native tanpa mendorong duplikasi.

### Risiko bila tidak diubah

1. Onboarding tim gagal pada langkah pertama.
2. Developer mengira `DATABASE_URL` dengan `${...}` akan bekerja, lalu menghabiskan waktu menelusuri error koneksi yang sebenarnya berasal dari placeholder.
3. Pengetahuan bahwa `INTERNAL_API_KEY` wajib hanya tersimpan di kepala.

## 10. Perubahan 7 — `.gitignore` dan keterlacakan contoh env

`.gitignore` sebelumnya memuat `.env.example`, sehingga templat tidak pernah masuk repositori. Baris itu sudah dihapus (perubahan sudah ada di working tree), dan sekarang `ai-service/.env.example` terlihat sebagai file untracked yang siap di-commit.

### Risiko bila dibiarkan diabaikan

Contoh konfigurasi tidak pernah ikut terkloning. Setiap anggota tim harus menanyakan isi variabel lewat pesan pribadi, dan rahasia berisiko terkirim di saluran yang tidak tepat.

## 11. Penambahan 8 — `docs/ADDENDUM-KONTRAK-API.md`

Dokumen kontrak baru berisi path final, header wajib, contoh request/response, tabel environment, cara memakai tombol Authorize, dan hal yang harus dipegang Laravel.

### Mengapa tidak mengedit dokumen lama

`docs/FASE-1` sampai `FASE-5` dan `SEED-MASTER-SOP.md` adalah laporan historis pada masanya. Mengubahnya membuat catatan proses kehilangan kejujuran. Addendum menandai secara eksplisit bagian mana yang sudah tidak berlaku.

### Risiko bila tidak dibuat

Developer baru membaca `FASE-5` dan memanggil `/chat`, lalu mendapat `404`. Ia juga akan mencoba `RAG_SIMILARITY_THRESHOLD`, yang sekarang bernama `RETRIEVAL_THRESHOLD`, dan menyimpulkan tuning tidak berfungsi.

## 12. Daftar file yang berubah

| File | Jenis | Isi perubahan |
|---|---|---|
| `ai-service/app/core/config.py` | diubah | Tambah `DESA_PETUGAS_WA`, `DESA_PETUGAS_URL` dengan default |
| `ai-service/app/services/llm_service.py` | diubah | Kontak dibaca dari `settings` |
| `ai-service/seed_master_sop.py` | diubah | Impor `SessionLocal`, hapus helper yang sudah tidak ada |
| `ai-service/app/core/security.py` | **baru** | Verifikasi `X-Internal-Key` |
| `ai-service/app/api/router.py` | diubah | Dependency keamanan dipasang di router |
| `ai-service/.env` | diubah | Tambah dua variabel kontak (tidak di-commit) |
| `ai-service/.env.example` | diubah | Templat lengkap |
| `.gitignore` | diubah | `.env.example` tidak lagi diabaikan |
| `docs/ADDENDUM-KONTRAK-API.md` | **baru** | Kontrak final dan panduan uji |

## 13. Bukti pengujian

Pengujian dilakukan native dengan `DATABASE_URL` diarahkan ke `127.0.0.1` (nilai diambil dari `.env` root saat proses berjalan, tidak ditulis di dokumen).

### 13.1 Fungsi dasar dan data

```
seed-modul-import-ok, jumlah-data-master: 20
default-kontak: 081234567890 | https://pepe.desa.id
openapi: 200 ['/', '/api/chat', '/api/documents']
root: 200
chat-relevan: 200 fallback= False sitasi= [('KTP','Hilang',1), ('KK','Hilang',1), ...]
  kontak-kosong: True
chat-luar: 200 fallback= True kontak= {'whatsapp': '081234567890', 'url': 'https://pepe.desa.id'}
channel-salah: 422
upsert: 200 1 -> 200 2
bersih: dihapus 1 | sisa-baris 20
```

### 13.2 Override env tanpa mengubah kode

```
override-terbaca: {'whatsapp': '081299998888', 'url': 'https://contoh-desa.test/layanan'}
pesan: Maaf, informasi tersebut tidak ada di pedoman dokumen Desa Pepe.
       Silakan hubungi WhatsApp petugas: 081299998888 / Info lanjut: https://contoh-desa.test/layanan.
session-seeder: 20
```

Ini membuktikan dua hal sekaligus: hardcode sudah tidak mengikat, dan `SessionLocal` yang dipakai seeder benar-benar terhubung ke database.

### 13.3 Autentikasi

```
health-tanpa-header: 200
chat-tanpa-header: 401
doc-tanpa-header: 401
chat-header-salah: 401
security-scheme: ['APIKeyHeader']
security-di-chat: [{'APIKeyHeader': []}]
```

### 13.4 Isi image Docker

```
deps-image-ok 2.16.1
```

`pydantic-settings` tersedia di dalam image. Catatan: Dockerfile tidak menyalin kode aplikasi (tidak ada `COPY . .`), sehingga kode dibaca dari bind mount `./ai-service:/app`. Build ulang hanya diperlukan ketika `requirements.txt` berubah.

## 14. Keputusan yang sengaja tidak diambil

| Keputusan | Alasan |
|---|---|
| Menjalankan ulang seeder | Akan menaikkan 20 baris ke `v2` tanpa perubahan isi; hanya mengotori versi |
| Menulis `DATABASE_URL` ke `ai-service/.env` | Kredensial tersimpan di dua tempat; Compose sudah menyuntikkannya |
| Menghapus `INTERNAL_API_KEY` dari `Settings` | Bertentangan dengan niat temanmu menyiapkan autentikasi antar-service |
| Mengubah laporan Fase 1–5 | Merusak catatan historis; diganti addendum |
| Memaksa kontak wajib lewat env | Menghilangkan kemampuan jalan tanpa konfigurasi yang sengaja dipertahankan |

## 15. Risiko yang masih tersisa

1. **Threshold 0.65** diukur dari 20 Varian dengan frasa formal. Query santai seperti `mau pindah keluar dari desa pepe gimana caranya` masih menempatkan `Pindah/Pindah Keluar` di peringkat 4 dengan skor `0.624`, di bawah threshold. Jawaban tetap bersitasi SOP asli, tetapi bisa salah SOP.
2. **`--reload` aktif di container.** Mode ini untuk pengembangan; sebaiknya dimatikan saat demo agar tidak ada proses watcher yang membebani.
3. **Tidak ada pembatasan laju.** Satu klien lokal dapat memicu pemanggilan Gemini berulang selama header valid.
4. **`create_all` berjalan saat import.** Bila database belum siap, container langsung gagal dan diulang oleh `restart: unless-stopped`; tidak ada penantian eksplisit selain healthcheck Compose.
5. **Image Postgres belum berganti.** Compose menunjuk `pgvector/pgvector:pg15`, sedangkan container berjalan masih `ankane/pgvector:latest`. Keduanya PostgreSQL 15 (yang berjalan 15.4), sehingga penggantian aman terhadap data, tetapi container akan dibuat ulang pada `docker compose up -d` berikutnya.
6. **Tidak ada uji otomatis ter-commit.** Semua verifikasi memakai skrip sementara di folder TEMP.

## 16. Langkah Docker yang tersisa

Satu perintah, hanya menyentuh `ai-service`:

```
docker compose up -d --no-deps --force-recreate ai-service
```

Yang perlu dipahami:

- `--no-deps` mencegah Compose ikut membuat ulang Postgres dan Laravel.
- `--force-recreate` tidak menghapus volume. Data 20 Varian ada di `pepebot-rag_pgdata` dan tidak tersentuh.
- Yang berbahaya adalah `docker compose down -v`, `docker volume prune`, dan `docker volume rm pepebot-rag_pgdata`.

Setelah recreate:

```
docker logs pepebot_ai --tail 30
```

Harus berakhir `Application startup complete`. Lalu buka `http://127.0.0.1:8001/docs`, klik **Authorize**, isi `INTERNAL_API_KEY`, dan jalankan `POST /api/chat` dengan `{"query":"syarat KTP hilang apa saja","channel":"Web"}`.

## 17. Yang harus dipegang saat menulis Laravel

1. Header `X-Internal-Key` wajib pada `/api/chat` dan `/api/documents`.
2. `channel` hanya `WA` atau `Web`.
3. Jangan menilai SOP di Laravel; teruskan `fallback` dan `fallback_contact`.
4. Arti status: `401` header salah, `422` input tidak valid, `502` embedding Gemini gagal, `500` penyimpanan database gagal.
5. `POST /api/documents` bersifat sinkron dan menaikkan `version`; tampilkan indikator proses, jangan menganggapnya instan.

## 18. Bukti mandiri

Perintah native memerlukan `DATABASE_URL` aktif, karena `Settings` mewajibkannya. Paling mudah dijalankan dari dalam container setelah recreate, sebab Compose sudah menyuntikkan `DATABASE_URL`:

```
docker compose exec ai-service python -c "..."
```

Bila tetap ingin native, set dulu `$env:DATABASE_URL` dengan nilai literal dan host `127.0.0.1`.

### 18.1 Memastikan modul seeder bisa diimpor

```
docker compose exec ai-service python -c "import seed_master_sop; print('ok', len(seed_master_sop.MASTER))"
```

Harus mencetak `ok 20`. Sebelum perbaikan, perintah ini gagal `ImportError`.

### 18.2 Memastikan kontak bisa ditimpa env

```
docker compose exec -e DESA_PETUGAS_WA=081200000000 ai-service python -c "from app.services.llm_service import get_fallback_contact; print(get_fallback_contact())"
```

Harus menampilkan nomor yang baru, bukan `081234567890`.

### 18.3 Memastikan header wajib

```
docker compose exec ai-service python -c "from fastapi.testclient import TestClient; from main import app; print(TestClient(app).post('/api/chat', json={'query':'halo','channel':'Web'}).status_code)"
```

Harus `401`.

### 18.4 Memastikan skema keamanan terdaftar

```
docker compose exec ai-service python -c "from fastapi.testclient import TestClient; from main import app; print(list(TestClient(app).get('/openapi.json').json()['components']['securitySchemes'].keys()))"
```

Harus memuat `APIKeyHeader`.

## 19. Istilah teknis

- **`pydantic-settings`**: pustaka yang memetakan environment dan file `.env` ke atribut class dengan validasi tipe.
- **Prioritas environment**: variabel proses menang atas isi `.env`; `.env` menang atas nilai default di kode.
- **Default field**: nilai yang dipakai bila tidak ada sumber lain, sehingga aplikasi tetap dapat berjalan tanpa konfigurasi.
- **Dependency router**: fungsi yang dijalankan sebelum setiap endpoint pada router tersebut; dipakai untuk autentikasi.
- **`APIKeyHeader`**: skema keamanan FastAPI untuk header berisi kunci; muncul sebagai tombol Authorize di Swagger.
- **Bind mount**: direktori host dipasang ke dalam container; perubahan file langsung terlihat tanpa build ulang.
- **Idempoten**: aman dijalankan berulang tanpa efek ganda; seeder memakai upsert sehingga menaikkan versi, bukan menduplikasi baris.
