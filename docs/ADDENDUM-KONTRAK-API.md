# Addendum Kontrak `ai-service` — Setelah PR #2

Dokumen ini melengkapi `docs/FASE-5-PERUBAHAN.md` dan `docs/SEED-MASTER-SOP.md` yang ditulis sebelum PR #2 masuk. Keduanya masih menyebut `/chat`, `/documents`, `RAG_SIMILARITY_THRESHOLD`, dan `_with_host`; semua itu sudah tidak berlaku.

> Nilai API key, password, dan `INTERNAL_API_KEY` tidak ditulis di dokumen ini.

## 1. Kontrak akhir

| Method | Path | Header wajib |
|---|---|---|
| `GET` | `/` | tidak ada (health check) |
| `POST` | `/api/chat` | `X-Internal-Key: <INTERNAL_API_KEY>` |
| `POST` | `/api/documents` | `X-Internal-Key: <INTERNAL_API_KEY>` |

Prefix `/api` berasal dari `app.include_router(api_router, prefix="/api")` di `main.py`; path akhir pada endpoint adalah `/chat` dan `/documents`.

Tanpa header yang benar, endpoint mengembalikan `401 {"detail":"Header X-Internal-Key tidak valid"}`.

### `POST /api/chat`

```json
{"query": "syarat KTP hilang apa saja", "channel": "Web"}
```

```json
{
  "answer": "...",
  "citations": [{"sop_name": "KTP", "varian": "Hilang", "version": 1}],
  "fallback": false,
  "fallback_contact": {}
}
```

`channel` menerima `WA` atau `Web` (tidak peka huruf besar/kecil). Nilai lain menghasilkan `422`.

### `POST /api/documents`

```json
{
  "sop_name": "KTP",
  "varian": "Hilang",
  "syarat": ["Foto Surat Kehilangan Polisi", "Foto KK"],
  "channel_url": "https://plavon.sidoarjokab.go.id/",
  "note": "Fotokan dokumen aslinya, bukan fotokopi."
}
```

Respons: `{"sop_name": "...", "varian": "...", "version": 1, "updated_at": "..."}`. Simpan ulang pada `sop_name` + `varian` yang sama menaikkan `version`, bukan membuat baris baru.

## 2. Konfigurasi environment

| Variabel | Wajib | Default |
|---|---|---|
| `DATABASE_URL` | ya (disuntik Compose saat Docker) | tidak ada |
| `INTERNAL_API_KEY` | ya | tidak ada |
| `GEMINI_API_KEY` | ya | tidak ada |
| `EMBEDDING_MODEL` | tidak | `gemini-embedding-001` |
| `EMBEDDING_DIM` | tidak | `768` |
| `LLM_MODEL` | tidak | `gemini-3.5-flash-lite` |
| `RETRIEVAL_THRESHOLD` | tidak | `0.65` |
| `TOP_K` | tidak | `4` |
| `DESA_PETUGAS_WA` | tidak | `081234567890` |
| `DESA_PETUGAS_URL` | tidak | `https://pepe.desa.id` |

Catatan `DATABASE_URL`:
- Jalur Docker: Compose menyuntikkan nilainya dari `.env` root, jadi tidak perlu ditulis di `ai-service/.env`.
- Jalur native: wajib ditulis literal (tanpa `${...}`) dengan host `127.0.0.1`, karena `_with_host` sudah dihapus.

## 3. Perubahan yang dilakukan setelah PR #2

1. `app/core/config.py` — menambah `DESA_PETUGAS_WA` dan `DESA_PETUGAS_URL` dengan nilai lama sebagai default.
2. `app/services/llm_service.py` — kontak fallback dibaca dari settings, bukan ditulis di dalam fungsi.
3. `seed_master_sop.py` — memakai `SessionLocal` dari `app.core.db`; impor `_with_host`, `_with_driver`, dan `DATABASE_URL` yang sudah tidak ada telah dihapus.
4. `app/core/security.py` — verifikasi header `X-Internal-Key`; dipasang di `app/api/router.py` sehingga berlaku untuk `/api/chat` dan `/api/documents` sekaligus.
5. `ai-service/.env` — menambah `DESA_PETUGAS_WA` dan `DESA_PETUGAS_URL` eksplisit.
6. `.env.example` — dilengkapi seluruh variabel; `.gitignore` tidak lagi mengabaikannya.

## 4. Cara menguji di Swagger

1. Buka `http://127.0.0.1:8001/docs`.
2. Klik tombol **Authorize** di kanan atas.
3. Isi nilai `INTERNAL_API_KEY` (tanpa menulis nama header), lalu Authorize.
4. Baru jalankan `POST /api/chat` atau `POST /api/documents`.

Untuk uji lewat terminal:

```powershell
$key = "<INTERNAL_API_KEY>"
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8001/api/chat `
  -Headers @{ "X-Internal-Key" = $key } `
  -ContentType "application/json" `
  -Body '{"query":"syarat KTP hilang","channel":"Web"}'
```

## 5. Yang harus dipegang Laravel

- Header `X-Internal-Key` wajib ada pada setiap panggilan ke `/api/chat` dan `/api/documents`.
- Jangan menilai SOP di Laravel; teruskan `fallback` dan `fallback_contact` apa adanya.
- `502` dari `/api/documents` berarti pemanggilan embedding Gemini gagal; `500` berarti penyimpanan database gagal; `422` berarti input tidak lolos validasi.
