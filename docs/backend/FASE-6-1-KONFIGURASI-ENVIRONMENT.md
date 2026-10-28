# Fase 6.1 — Laporan Perubahan: Kamar Kosong (Konfigurasi Environment)

Cakupan: **Fase 6.1** dari `To Do List Backend.md` — menyiapkan wadah variabel di Laravel (`core-service`) supaya kunci dari Meta dapat ditempel di Fase 6.5 tanpa membongkar kode, dan seluruh konfigurasi dipanggil lewat `config()`.

Sesuai `RENCANA & PENGEMBANGAN BACKEND.md`: backend dibangun dengan strategi *scaffolding* — logika utuh ditulis lebih dulu, token Meta yang belum ada dibiarkan kosong, dan hanya `META_VERIFY_TOKEN` yang diisi sekarang dengan sandi buatan sendiri.

> Nilai `META_VERIFY_TOKEN` dan `INTERNAL_API_KEY` tidak ditulis di dokumen ini. Templat di bawah memakai placeholder; nilai aslinya berada di `core-service/.env` yang sengaja tidak di-commit.

## 1. Kondisi sebelum Fase 6.1

| Halaman pemeriksaan | Kondisi |
|---|---|
| `core-service/.env` | 48 kunci bawaan Laravel/Breeze (APP_*, DB_*, SESSION_*, MAIL_*, AWS_*, VITE_APP_NAME). **Tidak ada** `META_*`, `AI_SERVICE_URL`, `INTERNAL_API_KEY` |
| `config/services.php` | Hanya `postmark`, `resend`, `ses`, `slack` — tidak ada entri ai-service maupun Meta |
| Kredensial telusur | `AI_SERVICE_URL` hanya disuntikkan Compose ke container core saat dibuat ulang; container lama tidak membawanya |

Tanpa wadah ini, setiap fase berikutnya (rute, controller, portal Meta) harus menekan fungsi `env()` langsung di controller — praktik yang tidak dianjurkan Laravel ketika konfigurasi bisa ter-cache (`config:cache`), dan membuat kredensial tersebar di banyak file.

## 2. Perubahan 1 — `core-service/.env`: lima variabel baru

Baris berikut ditambahkan di akhir file (dibuat lewat PowerShell langsung ke file, bukan lewat percakapan, supaya nilai rahasia tidak pernah tampil di layar):

```
# --- Meta WhatsApp Cloud API (Fase 6.1) ---
META_VERIFY_TOKEN=<sandi-acak-64-karakter-buatan-sendiri>
META_WHATSAPP_TOKEN=
META_PHONE_ID=

# --- AI Service (FastAPI PepeBot) ---
AI_SERVICE_URL=http://ai-service:8001
INTERNAL_API_KEY=<disalin-persis-dari-ai-service/.env>
```

### Mengapa tiap baris begini

| Variabel | Isi saat ini | Alasan |
|---|---|---|
| `META_VERIFY_TOKEN` | sandi acak 64 karakter (dua GUID digabung) | Ini satu-satunya kunci yang harus ada **sebelum** berhadapan dengan portal Meta: Fase 6.5 memasukkan sandi yang sama ke portal, dan `verifyWebhook()` Fase 6.3 mencocokkannya. 64 karakter dari dua GUID memberi entropi yang jauh di atas kebutuhan untuk sandi jabat tangan |
| `META_WHATSAPP_TOKEN` | kosong | Sesuai strategi scaffolding: kode Fase 6.3 ditulis utuh tanpa token; token diisi di Fase 6.5 setelah di-generate dari portal Meta |
| `META_PHONE_ID` | kosong | Idem, diisi di Fase 6.5 |
| `AI_SERVICE_URL` | `http://ai-service:8001` | Alamat FastAPI yang dikenali **di dalam jaringan Docker** |
| `INTERNAL_API_KEY` | disalin persis dari `ai-service/.env` | `ai-service` menolak setiap panggilan `/api/chat` dan `/api/documents` tanpa header `X-Internal-Key` (lihat `docs/ADDENDUM-KONTRAK-API.md`). Tanpa kunci ini di sisi Laravel, panggilan pertama di Fase 6.3 pasti `401` |

Dua keputusan menyimpang dari teks rencanamu, dan alasannya terukur:

1. **`AI_SERVICE_URL` memakai `ai-service`, bukan `127.0.0.1:8001` seperti tertulis di rencana.** Dari dalam container Laravel, `127.0.0.1` menunjuk ke dirinya sendiri, bukan ke FastAPI — pembuktiannya di Bab 6. Nilai `127.0.0.1` baru benar bila menjalankan `php artisan serve` langsung di Windows host.
2. **`INTERNAL_API_KEY` ditambahkan meski tidak ada di daftar rencanamu.** Rencana ditulis sebelum `ai-service` memberlakukan header rahasia. Menambahkannya di Fase 6.1 berarti Fase 6.3 tidak perlu revisi konfigurasi di tengah jalan.

### Catatan precedence

Composer Compose juga menyuntikkan `AI_SERVICE_URL` ke container core bila dibuat ulang (jaringan sama: `http://ai-service:8001`). Laravel** tidak** membiarkan isi `.env` menimpa variabel environment yang sudah ada (phpdotenv bersifat *immutable* secara default). Karena kedua sumber bernilai sama, hasilnya identik di mana pun aplikasi berjalan.

## 3. Perubahan 2 — `config/services.php`: dua seksi baru

Kode penuh file setelah perubahan:

```php
<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Third Party Services
    |--------------------------------------------------------------------------
    |
    | This file is for storing the credentials for third party services such
    | as Resend, Postmark, AWS, and more. This file provides the de facto
    | location for this type of information, allowing packages to have
    | a conventional file to locate the various service credentials.
    |
    */

    'postmark' => [
        'key' => env('POSTMARK_API_KEY'),
    ],

    'resend' => [
        'key' => env('RESEND_API_KEY'),
    ],

    'ses' => [
        'key' => env('AWS_ACCESS_KEY_ID'),
        'secret' => env('AWS_SECRET_ACCESS_KEY'),
        'region' => env('AWS_DEFAULT_REGION', 'us-east-1'),
    ],

    'slack' => [
        'notifications' => [
            'bot_user_oauth_token' => env('SLACK_BOT_USER_OAUTH_TOKEN'),
            'channel' => env('SLACK_BOT_USER_DEFAULT_CHANNEL'),
        ],
    ],

    /*
    |--------------------------------------------------------------------------
    | WhatsApp Cloud API (Meta)
    |--------------------------------------------------------------------------
    |
    | Kredensial untuk Fase 6: verifikasi webhook (verify_token), pengiriman
    | balasan (token), identitas nomor pengirim (phone_id), dan versi endpoint
    | graph.facebook.com. Dua nilai teratas sengaja kosong sampai Fase 6.5.
    */

    'whatsapp' => [
        'verify_token' => env('META_VERIFY_TOKEN'),
        'token' => env('META_WHATSAPP_TOKEN'),
        'phone_id' => env('META_PHONE_ID'),
        'api_version' => env('META_API_VERSION', 'v17.0'),
    ],

    /*
    |--------------------------------------------------------------------------
    | AI Service (FastAPI PepeBot)
    |--------------------------------------------------------------------------
    |
    | Alamat internal dan kunci antar-service. Controller Fase 6.3 memanggil
    | POST {url}/api/chat dengan header X-Internal-Key = key.
    */

    'ai_service' => [
        'url' => env('AI_SERVICE_URL', 'http://ai-service:8001'),
        'key' => env('INTERNAL_API_KEY'),
    ],

];
```

### Mengapa lewat `config()` dan bukan `env()` di controller

1. **Satu titik kebenaran.** `Fase 6.3` dan `Fase 6.5` cukup memanggil `config('services.whatsapp')` dan `config('services.ai_service')`; tidak ada string `META_` tersebar di controller.
2. **Tahan `config:cache`.** Setelah konfigurasi di-cache, `env()` mengembalikan `null` — panggilan `env()` di kode aplikasi adalah sumber runtime error klasik. `config()` selalu benar.
3. **Testable.** Feature test dapat menimpa nilai dengan `config()->set(...)` tanpa menyentuh `.env`.
4. **`api_version` jadi configurable.** Rencanamu menulis `v17.0`; disimpan sebagai default `config` yang bisa diubah lewat `META_API_VERSION` bila nanti versi Meta diperbarui, tanpa mengubah kode.

## 4. Pengaruh ke fase berikutnya

| Fase | Bagian yang terbantu | Uraian |
|---|---|---|
| 6.2 (sudah dilaporkan tersendiri) | — | Tidak menyentuh konfigurasi |
| 6.3 | `verifyWebhook()` dan `handleWebhook()` | `config('services.whatsapp.verify_token')`, `config('services.ai_service.url')`, `config('services.ai_service.key')` untuk header `X-Internal-Key` |
| 6.4 | Ngrok | Tidak butuh perubahan konfigurasi |
| 6.5 | Portal Meta | Tinggal tempel `META_WHATSAPP_TOKEN` dan `META_PHONE_ID`; controller dan config tidak berubah |

`.env` tetap tidak masuk git — `.gitignore` di root memuat `/core-service/.env`.

## 5. Pembuktian

Perintah dijalankan di dalam container `pepebot_core` melalui `php artisan tinker`, dan output dibuat tidak menyebut nilai rahasia (yang dicetak: panjang kunci, boolean kekosongan, URL, dan versi):

```php
echo 'verify-token-len: ' . strlen((string) config('services.whatsapp.verify_token')) . PHP_EOL;
echo 'wa-token-empty: ' . var_export(trim((string) config('services.whatsapp.token')) === '', true) . PHP_EOL;
echo 'phone-id-empty: ' . var_export(trim((string) config('services.whatsapp.phone_id')) === '', true) . PHP_EOL;
echo 'api-version: ' . config('services.whatsapp.api_version') . PHP_EOL;
echo 'ai-url: ' . config('services.ai_service.url') . PHP_EOL;
echo 'ai-key-len: ' . strlen((string) config('services.ai_service.key')) . PHP_EOL;
echo '---' . PHP_EOL;
echo 'ai-service-via-nama-container: ';
try { echo strlen(file_get_contents('http://ai-service:8001/')) . ' byte' . PHP_EOL; } catch (Throwable $e) { echo 'GAGAL: ' . $e->getMessage() . PHP_EOL; }
echo 'ai-service-via-127.0.0.1: ';
try { echo strlen(file_get_contents('http://127.0.0.1:8001/')) . ' byte' . PHP_EOL; } catch (Throwable $e) { echo 'GAGAL (diharapkan saat di dalam container)' . PHP_EOL; }
```

Output aslinya:

```
verify-token-len: 64
wa-token-empty: true
phone-id-empty: true
api-version: v17.0
ai-url: http://ai-service:8001
ai-key-len: 32
---
ai-service-via-nama-container: 74 byte
ai-service-via-127.0.0.1:      WARNING  file_get_contents(http://127.0.0.1:8001/):
Failed to open stream: Connection refused
0 byte
```

### Mengapa rentetan itu membuktikan Fase 6.1 selesai

| Buktian | Klaim yang dibuktikan | Alasan kekuatannya |
|---|---|---|
| `verify-token-len: 64` | `META_VERIFY_TOKEN` terisi | `config()` dibaca **lewat aplikasi Laravel yang jalan di container**, bukan membaca file mentah; berarti `.env` benar terbaca oleh PHP dotenv di lokasi kerja yang benar |
| `wa-token-empty: true`, `phone-id-empty: true` | Prasyarat scaffolding terpelihara | Token disengaja kosong; bila tertulis nilai rahasia di sini, strategi "koding dulu, daftar kemudian" justru gagal dijalankan |
| `api-version: v17.0` | Default config terpasang | Nilai muncul walaupun `META_API_VERSION` tidak ada di `.env` — bukti jalur *fallback* `config` bekerja |
| `ai-url: http://ai-service:8001` | Alamat AI tersuntik benar | Nilai persis seperti yang diminta, dan bukan bawaan hardcode yang tertinggal |
| `ai-key-len: 32` | `INTERNAL_API_KEY` terbaca | Terkalin panjangnya persis dengan kunci di `ai-service/.env` (32 karakter) — dua layanan berbinjai kunci rahasia yang sama |
| `ai-service-via-nama-container: 74 byte` | FastAPI terfetisi dari Laravel | `GET /` pada `http://ai-service:8001/` mengembalikan respons (*health JSON*, 74 byte), membuktikan nama service dan port benar serta jaringan Docker merangkai keduanya |
| `ai-service-via-127.0.0.1: Connection refused` | Pilihan `127.0.0.1` memang salah di dalam container | Kegagalan ini **diharapkan dan dibuktikan** — inilah alasan perubahan nilai di rencana |

Baru di sini satu hal lagi yang diperiksa sebelum verifikasi: `bootstrap/cache/config.php` tidak ada (bila ada, konfigurasi lama akan di-cache dan `.env` baru takkan terbaca tanpa `config:clear`).

## 6. Risiko bila Fase 6.1 tidak dilakukan, atau dilakukan salah

| Kesalahan yang mungkin | Akibat nyata |
|---|---|
| Tidak dibuat `config/services.php`, controller memanggil `env()` langsung | Setelah `config:cache`, seluruh `env()` mengembalikan `null` — webhook gagal di produksi yang tidak terjadi di lokal |
| `AI_SERVICE_URL=127.0.0.1:8001` disalin mentah dari rencana | Panggilan dari container: `Connection refused` (dibuktikan di atas) — seluruh Fase 6.3 menolak setiap tujukan |
| `INTERNAL_API_KEY` tidak didaftarkan | Setiap `POST /api/chat` mendapat `401`; debugging akan mengira masalahnya di controller |
| `META_VERIFY_TOKEN` kosong | `verifyWebhook()` tak bisa membandingkan apa pun; jabat tangan Fase 6.5 selalu gagal dan portal Meta menolak URL |
| `META_WHATSAPP_TOKEN` diisi angka rekaan | Kode pengiriman di Fase 6.3 tampak "hampir jalan", tetapi setiap tujukan ke `graph.facebook.com` menghasilkan `401 Unauthorized` — lebih mahal ditelusuri daripada dibiarkan kosong |
| Kunci rahasia dicetak dalam percakapan/dokumen | Rahasia menembak riwayat chat dan file yang bisa di-commit |

## 7. Cara membuktikan ulang sendiri

Dari folder root repo (semuanya lewat container, karena PHP host 8.2 berada di bawah syarat `^8.3`):

```powershell
@'
echo 'verify-token-len: ' . strlen((string) config('services.whatsapp.verify_token')) . PHP_EOL;
echo 'wa-token-empty: ' . var_export(trim((string) config('services.whatsapp.token')) === '', true) . PHP_EOL;
echo 'phone-id-empty: ' . var_export(trim((string) config('services.whatsapp.phone_id')) === '', true) . PHP_EOL;
echo 'ai-url: ' . config('services.ai_service.url') . PHP_EOL;
echo 'ai-key-len: ' . strlen((string) config('services.ai_service.key')) . PHP_EOL;
'@ | docker exec -i pepebot_core php artisan tinker
```

```powershell
docker exec pepebot_core sh -c "curl -s -o NUL -w 'status=%{http_code}' http://ai-service:8001/"
```

Harus mengembalikan `200`.

## 8. Daftar file yang berubah di Fase 6.1

| File | Jenis | Isi |
|---|---|---|
| `core-service/.env` | diubah | 5 variabel baru (tidak di-commit) |
| `core-service/config/services.php` | diubah | Seksi `whatsapp` dan `ai_service` |

## 9. Istilah teknis

- **`env()`**: pembaca kunci dari file `.env` (memakai phpdotenv). Nilainya dipetakan sekali saat boot.
- **`config()`**: pembaca nilai dari file konfigurasi Laravel; konfigurasi yang di-cache tetap benar dan bisa ditimpa oleh tester.
- **Precedence phpdotenv**: variabel environment yang sudah ada tidak ditimpa isi `.env` (default *immutable*).
- **Scaffolding**: menulis logika utuh dengan beberapa kunci sengaja dikosongkan, menggantinya nanti saat kredensial resmi tersedia.
- **Jabat tangan (handshake)**: proses GET verifikasi ketika Meta mengirim `hub.challenge` dan mengharapkan huruf yang sama dikembalikan.
