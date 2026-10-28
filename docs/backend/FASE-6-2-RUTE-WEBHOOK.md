# Fase 6.2 — Laporan Perubahan: Pemasangan Laravel Boost dan Jalur Webhook di Level Rute

Cakupan dokumen: satu sesi kerja yang mencakup **dua blok** —

1. **Blok A — penuhi mandat `AGENTS.md`**: pemasangan `laravel/boost` (`composer require` + `php artisan boost:install`) beserta seluruh artefak yang dihasilkannya.
2. **Blok B — Fase 6.2** menurut `To Do List Backend.md`: registrasi jalur webhook WhatsApp (rute `GET` + `POST` di `routes/api.php`) dan pendaftarannya di `bootstrap/app.php`, ditambah satu perubahan yang terpaksa maju jadwal: kerangka `WhatsAppController`.

Semua perintah PHP/Composer dijalankan **di dalam container `pepebot_core`**. PHP host (8.2.12) berada di bawah syarat `composer.json` (`php: ^8.3`), sedangkan container memakai PHP 8.5.11. Pengecualian hanya untuk baca/tulis file lewat tool editor.

> Tidak ada nilai rahasia di dokumen ini. Artefak Boost yang dihasilkan (`boost.json`, `.mcp.json`, `.claude/`, `CLAUDE.md`) memang tidak memuat kredensial apa pun — semuanya konfigurasi alat, bukan kunci.

---

## 0. Kondisi sebelum Fase 6.2

| Objek | Kondisi awal |
|---|---|
| `core-service/routes/api.php` | **Tidak ada** — scaffold Laravel 13 Breeze hanya memuat `web.php` dan `console.php` |
| `core-service/bootstrap/app.php` | `withRouting(web:..., commands:..., health:'/up')` — parameter `api:` belum ada |
| `core-service/app/Http/Controllers/WhatsAppController.php` | **Tidak ada** |
| `laravel/boost` | Belum terpasang; `AGENTS.md` menagih dua perintah instalasi sebelum perubahan aplikasi dilakukan |
| Konfigurasi dari Fase 6.1 | Sudah siap: `config('services.whatsapp.*')` dan `config('services.ai_service.*')` terbaca di container |

---

## 1. Blok A — Perubahan 1: `composer require laravel/boost --dev`

### Perintah dan output

```sh
docker exec pepebot_core sh -c "COMPOSER_ALLOW_SUPERUSER=1 composer require laravel/boost --dev --no-interaction --no-progress"
```

```
  INFO  No publishable resources for tag [laravel-assets].

No security vulnerability advisories found.
Using version ^2.10 for laravel/boost
```

Baris `COMPOSER_ALLOW_SUPERUSER=1` diperlukan karena Composer berjalan sebagai root di dalam container; flag ini meredam peringatan superuser yang berulang pada setiap eksekusi Composer.

### Kode yang berubah — `core-service/composer.json` (diff penuh)

```diff
     },
     "require-dev": {
         "fakerphp/faker": "^1.23",
+        "laravel/boost": "^2.10",
         "laravel/breeze": "^2.4",
         "laravel/pail": "^1.2.5",
         "laravel/pao": "^1.0.6",
```

Satu entri, hanya di bagian `require-dev`. `composer.lock` ikut diperbarui; pemeriksa keamanan Composer melaporkan **tanpa advisories kerentanan**.

### Mengapa dilakukan

1. **`AGENTS.md` milik repo sendiri yang mewajibkannya**, sebelum perubahan aplikasi apa pun: *"Install Laravel Boost from the application root before making application changes"*. Menunda pekerjaan aplikasi sampai selesai pemasangan adalah konsekuensi menyatakan diri mengikuti aturan repo.
2. **Panduan spesifik versi.** Fase 6.2–6.3 menyentuh registrasi rute, grup middleware `api`, controller, dan pint — justru area yang berubah antar versi Laravel. Panduan yang dihasilkan Boost (Bab 2) menurunkan risiko menulis pola versi lama (contoh: Kernel lama dengan `$middleware` manual, sedangkan Laravel 13 memakai `withRouting()`).
3. **Konsistensi antar sesi kerja.** Tanpa Boost, setiap sesi penanganan berikutnya kembali digate oleh instruksi bootstrap yang sama dan setup diulang.

### Bagaimana jika tidak dilakukan

| Konsekuensi | Uraian |
|---|---|
| Sesi berikutnya tertahan gerbang setup | `AGENTS.md` tetap menagih instalasi; pekerjaan aplikasi selalu tertunda oleh keputusan yang bisa selesai sekali saja |
| Pola kode berisiko meleset versi | Tidak ada panduan yang menyatakan versi PHP/Laravel dan konvensi proyek ini; risiko pola Laravel tua meningkat |
| Kontradiksi internal repo | Repo menyatakan diri diatur `AGENTS.md`, tetapi instruksinya tidak pernah dipenuhi — setiap pembaca repo menemukan ketidaksesuaian |

### Mengapa `--dev`, bukan dependensi produksi

`require-dev` berarti `composer install --no-dev` di build produksi **tidak** mengunduh Boost. Paket ini adalah perkakas pengembangan (generator panduan + server MCP untuk agen); tanpa `--dev`, ia ikut ter-vendor ke produksi: ukuran build membengkak dan permukaan serangan bertambah tanpa manfaat runtime. Dampak runtime di aplikasi pun memang tidak ada — Boost tidak mendaftarkan rute, middleware, maupun listener; ia hanya menambah beberapa perintah `artisan` (mis. `boost:install`, `boost:mcp`) yang berjalan saat dipanggil.

---

## 2. Blok A — Perubahan 2: `php artisan boost:install` (lima artefak)

### Perintah dan ringkasan output

```
docker exec pepebot_core php artisan boost:install --no-interaction
```

Bagian akhir output:

```
 ────────────────────────
  tailwindcss-development │ testing-best-practices
 ────────────────────────

Installing MCP servers to your selected Agents
  Claude Code... ✓

 💡 Run the infer-conventions skill to record your app conventions and sharpen code generation.

Enjoy the boost 🚀 Next steps: https://laravel.com/docs/boost
```

Status git setelahnya — daftar lengkap perubahan yang dihasilkan tahap ini:

```
 M core-service/CLAUDE.md
?? core-service/.claude/
?? core-service/.mcp.json
?? core-service/boost.json
 M core-service/composer.json        (Bab 1)
 M core-service/composer.lock
```

Tercatat: **`AGENTS.md` tidak diubah**. Teks `AGENTS.md` menulis *"Boost replaces these bootstrap instructions"*, tetapi Boost 2.10 yang dipilih `--no-interaction` memakai agen `claude_code`, sehingga panduan hasilnya ditulis ke **`CLAUDE.md`**, sedangkan `AGENTS.md` tetap sebagai instruksi bootstrap.

### Artefak 1 — `core-service/boost.json` (file baru, kode penuh)

```json
{
    "agents": [
        "claude_code"
    ],
    "cloud": true,
    "guidelines": true,
    "mcp": true,
    "nightwatch": false,
    "sail": false,
    "skills": [
        "infer-conventions",
        "deploying-to-cloud",
        "laravel-best-practices",
        "testing-best-practices",
        "inertia-react-development",
        "tailwindcss-development"
    ]
}
```

**Fungsi:** catatan keputusan instalasi — agen mana yang dipilih (`claude_code`), komponen apa yang diaktifkan (panduan, MCP), dan skill domain mana yang dicocokkan ke proyek. Ini konfigurasi perkakas, bukan kode aplikasi.

**Pengaruh:** jika pilihan berubah (mis. tidak memakai Laravel Cloud), cukup edit `cloud: false` atau jalankan ulang `boost:install`.

### Artefak 2 — `core-service/.mcp.json` (file baru, kode penuh)

```json
{
    "mcpServers": {
        "laravel-boost": {
            "command": "php",
            "args": [
                "artisan",
                "boost:mcp"
            ]
        }
    }
}
```

**Fungsi:** mendaftarkan satu server MCP (Model Context Protocol) bernama `laravel-boost` yang perintahnya `php artisan boost:mcp`. Klien agen yang mendukung MCP bisa berbicara dengan aplikasi lewat perkakas Boost (query database baca-saja, inspeksi skema, telusur dokumentasi, baca log browser). Perintah `php artisan serve` dan siklus webhook **sama sekali tidak menyentuh** file ini.

**Pengaruh di fase berikutnya:** `database-schema` dipakai sebelum membuat migrasi database di fase berikutnya; `search-docs` dipakai sebelum menulis controller Fase 6.3 untuk memastikan sintaks HTTP Client Laravel 13.

### Artefak 3 — `core-service/.claude/skills/**` (folder baru, 36 file)

Struktur yang lahir:

```
.claude/skills/
├── deploying-to-cloud/           SKILL.md, reference/checklists.md
├── inertia-react-development/    SKILL.md
├── infer-conventions/            SKILL.md, references/checklist.md
├── laravel-best-practices/       SKILL.md + 19 rules (routing.md, security.md, validation.md, ...)
├── tailwindcss-development/      SKILL.md
└── testing-best-practices/       SKILL.md + 9 rules (assertions.md, endpoint-tests.md, isolation.md, ...)
```

**Fungsi:** kumpulan panduan domain dalam bentuk file Markdown yang dibaca agen saat bekerja pada domain itu. Isinya panduan konsolidasi Laravel 13, bukan kode aplikasi.

**Pengaruh:** panduan domain routing, security, validation, dan endpoint-test kini tersedia di repo sebagai acuan tetap — bukan penilaian spontan tiap sesi.

### Artefak 4 — `core-service/CLAUDE.md` (diubah: +161 baris, −29 baris)

File sebelumnya digantikan hasil generator Boost. Struktur baru:

| Seksi | Isi utama | Dampak langsung terasa di pekerjaan Fase 6.2 |
|---|---|---|
| Foundation rules | Cek versi paket (`composer show --direct`) sebelum memakai API-nya; aktifkan skill domain yang relevan dari awal; ikuti konvensi file sekitar; tidak membuat dokumen tanpa permintaan | Laporan ini kamu minta eksplisit — jadi sah dibuat |
| Boost rules | Utamakan perkakas MCP Boost; `search-docs` sebelum mengandalkan API Laravel; aturan `.ai/rules` bila ada (di proyek ini tidak ada, diperiksa dan dinyatakan) | Dipatuhi saat menelusur `ApplicationBuilder` dan `Middleware` |
| PHP rules | Tanda kurung kurawal selalu; promotion constructor; **return type eksplisit** untuk semua metode; PHPDoc untuk blok, komentar inline terbatas | Kerangka `WhatsAppController` menaati aturan tipe eksplisit |
| Pint rules | **`vendor/bin/pint --dirty --format agent` wajib** untuk setiap file PHP yang diubah | Dijalankan di akhir sesi (Bab 6, Temuan 2) |
| Test rules | Tambah/diperbarui test untuk perubahan perilaku bila ada nilai regresi; murni perubahan konfigurasi/kopi tidak wajib | Registrasi rute + kerangka kosong = perubahan konfigurasi; tidak dibuat test |
| Inertia rules | Panduan v1 + v2 | Belum relevan hingga tahap dashboard |

**Pengaruh penting:** file ini menetapkan gaya kerja konsisten sejak awal; kode yang ditulis di Fase 6.3 nanti mengikuti prinsipnya.

### Artefak 5 — `core-service/AGENTS.md` (tidak berubah)

`AGENTS.md` tetap instruksi bootstrap. Dua implikasi:

1. Anggota tim/agen yang membaca repo nanti akan kembali melihat instruksi instalasi — tetapi Boost kini **sudah terpasang dan tercatat** di `composer.json` + `boost.json`, sehingga menjalankan ulang perintahnya aman (idempotent).
2. Panduan hasil generator berada di `CLAUDE.md`. Bila suatu saat kamu memakai agen lain (mis. Cursor), jalankan `boost:install` lagi dengan pilihan agen itu — Boost akan menghasilkan file panduan sesuai agen tersebut tanpa mengubah kode aplikasi.

### Bagaimana jika `boost:install` tidak dijalankan

`composer require` saja tidak menghasilkan apa-apa di luar `vendor`: tidak ada `CLAUDE.md` baru, tidak ada skill, tidak ada MCP. Dampak buruknya per tingkat artefak:

| Artefak yang hilang | Dampak |
|---|---|
| `CLAUDE.md` (panduan) | Agen/sesi berikut tidak tahu bahwa proyek ini Laravel 13 + PHP 8.5, tidak tahu konvensi pint/type-hint — risiko gaya file campuran versi |
| `.claude/skills/**` | Panduan domain (routing, security, validation, endpoint-tests) tidak tersedia saat domain itu dikerjakan |
| `.mcp.json` | Klien tidak bisa memakai perkakas `database-schema` / `search-docs` — satu-satunya jalur tersisa memanipulasi database secara manual, risiko kesalahan langsung ke data nyata |

### Keputusan komitmen (kepadamu)

File `boost.json`, `.mcp.json`, `.claude/**`, dan `CLAUDE.md` saat ini **untracked**. Tiga pilihan umum, semua sah:

1. **Commit semuanya** — pilihan paling konsisten: lingkungan baru langsung tahu konfigurasi alat.
2. **Commit semuanya kecuali `.claude/`** — bila `.claude/` dianggap berkas spesifik mesin.
3. **Tidak commit sama sekali** — setiap klon baru harus mengulang `boost:install`.

Saya tidak mengeksekusi salah satunya tanpa keputusanmu.

### Catatan: dari mana file-file ini, dan kenapa belum terlihat di GitHub

Ketiga artefak (`boost.json`, `.mcp.json`, `.claude/`) **bukan tulisan manual** — sampel perintahnya dilihat di awal Bab 2: semuanya dicetak otomatis oleh `php artisan boost:install` saat dijalankan di container. Sebab itu file-file ini belum ada di repo asal (GitHub pemilik scaffold):

1. **Belum pernah di-commit.** Semua pekerjaan sesi ini (perbaikan ai-service, Fase 6.1, Boost, Fase 6.2) masih bebas commit. `git status` menampilkan ketiganya `??` (untracked):

   ```
   ?? core-service/.claude/
   ?? core-service/.mcp.json
   ?? core-service/boost.json
    M core-service/CLAUDE.md
   ```

   `??` berarti file ada di disk dan tidak di-`.gitignore`, hanya belum pernah `git add`. File lokal yang belum di-commit tidak mungkin muncul di GitHub manapun, apalagi di klon repo pemilik scaffold.

2. **Repo asal memang pra-Boost.** `boost:install` adalah perintah yang dirancang untuk membuat file-file ini; repo yang belum pernah menjalankannya wajar tidak memilikinya. File `CLAUDE.md` dan `AGENTS.md` sudah disediakan scaffold; yang dilakukan Boost adalah memodifikasi `CLAUDE.md`, bukan menciptannya.

Dua fakta pendamping yang penting dicatat:

- **Aplikasi tidak bergantung pada ketiganya.** `php artisan serve`, webhook, dan seluruh rencana Fase 6.3 ke atas berjalan normal walaupun file itu dihapus. Fungsinya hanya untuk lapisan agen: panduan konvensi, klien MCP, dan skill.
- **Penghapusan aman dan bisa diulang.** Hapus folder/file itu kapan pun; `boost:install` bisa menghasilkannya kembali. `CLAUDE.md` (hasil generator) pun bisa diregenerasi lewat perintah yang sama.

Yang **akan** masuk repo saat pekerjaan ini di-commit: `composer.json` + `composer.lock` (entri `laravel/boost`), `routes/api.php`, `app/Http/Controllers/WhatsAppController.php`, `bootstrap/app.php`, dan `config/services.php` dari Fase 6.1 — serta artefak Boost kalau kamu memilih opsi 1 atau 2 di daftar komitmen di atas.

---

## 3. Blok B — Perubahan 3: `core-service/routes/api.php` (file baru)

### Kode penuh (verifikasi `php -l`: bersih; em-dash UTF-8 utuh)

```php
<?php

use App\Http\Controllers\WhatsAppController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| API Routes
|--------------------------------------------------------------------------
|
|  Fase 6.2: jalur webhook WhatsApp. Ditaruh di routes/api.php, sehingga
|  grup middleware bawaan adalah "api" (tanpa VerifyCsrfToken), jadi kedua
|  verb dari server Meta diterima.
|
|  Final URL: GET/POST /api/webhook/whatsapp
|  Controller Fase 6.3: App\Http\Controllers\WhatsAppController
*/

Route::get('/webhook/whatsapp', [WhatsAppController::class, 'verifyWebhook']);

Route::post('/webhook/whatsapp', [WhatsAppController::class, 'handleWebhook']);
```

### Mengapa dua verb menuju URI yang sama

Meta WhatsApp Cloud API memakai **satu URL webhook** untuk dua pekerjaan yang fungsinya berbeda:

| Verb | Kapan dijalankan | Reaksi yang diharapkan |
|---|---|---|
| `GET` | Saat tombol *Verify and save* di portal Meta ditekan (Fase 6.5) | Kirim `hub.challenge` balik (dibangun di Fase 6.3) |
| `POST` | Setiap pesan WhatsApp masuk ke nomor pengirim | Menerima payload JSON, mengirim balasan |

Portal Meta hanya menyimpan satu URL; keduanya wajib hidup di URI yang sama persis. Jika kedua pekerjaan itu ditangani URL berbeda, Meta tidak menyediakan tempat untuk itu.

### Mengapa di `routes/api.php`, bukan di `routes/web.php`

| Aspek | Di `web.php` | Di `api.php` (dipilih) |
|---|---|---|
| Prefix URL otomatis | Tidak ada — URL jadi `/webhook/whatsapp` | Ya — URL jadi `/api/webhook/whatsapp`, sama dengan rencana Fase 6.5 |
| `VerifyCsrfToken` | Terpasang — permintaan tanpa token dibantah `419 Page Expired` | Tidak terpasang — `POST` JSON dari server Meta diterima tanpa hambatan |
| Format galat saat `422/401` | Redirect + HTML | JSON (dikonfirmasi `shouldRenderJsonWhen` di `bootstrap/app.php`, berlaku untuk `api/*`) |

Server Meta adalah **server ke server**: tidak punya sesi Laravel, tidak bisa membawa token CSRF, dan memang bukan peramban. Meletakkannya di grup `web` justru membuat webhook gagal `419` untuk setiap pesan.

**Bukti komposisinya dari framework** (dibaca dan diverifikasi sebelum menulis kode):

```php
// vendor/laravel/.../Foundation/Configuration/Middleware.php:495-499
'api' => array_values(array_filter([
    $this->statefulApi ? EnsureFrontendRequestsAreStateful::class : null,
    $this->apiLimiter ? 'throttle:'.$this->apiLimiter : null,
    SubstituteBindings::class,
])),
```

Dua elemen bersifat kondisional: `$this->statefulApi` dan `$this->apiLimiter`. Scaffold proyek ini memanggil `withMiddleware()` tanpa keduanya, dan kedua field default-nya `null` — lihat **Temuan 1** di Bab 6 untuk implikasi pentingnya.

### Mengapa rute ditulis sebelum controller ada

Rute merujuk `[WhatsAppController::class, 'verifyWebhook']` dan controller baru lahir di Bab 5. Urutan ini tetap aman: konstanta `::class` di file rute hanya menulis FQCN sebagai string dan tidak memicu autoload. Yang menuntut kelas nyata adalah `route:list`, karena perintah itu menginspeksi controller lewat refleksi. Rincian dan buktinya di Bab 5.

### Catatan encoding (temuan kecil tapi dokumentasinya wajib)

Karakter em-dash (`—`) di komentar tampil sebagai `??` bila file dibaca lewat `Get-Content` PowerShell (encoding ANSI bawaan). **File sesungguhnya utuh UTF-8**:

```sh
php -l /app/routes/api.php
# No syntax errors detected in /app/routes/api.php

php -r 'var_dump(strpos(file_get_contents("/app/routes/api.php"), "\u{2014}") !== false);'
# bool(true)
```

---

## 4. Blok B — Perubahan 4: `bootstrap/app.php` mendaftarkan jalur api

### Kode penuh file sesudah perubahan

```php
<?php

use App\Http\Middleware\HandleInertiaRequests;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Middleware\AddLinkHeadersForPreloadedAssets;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->web(append: [
            HandleInertiaRequests::class,
            AddLinkHeadersForPreloadedAssets::class,
        ]);

        //
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*') || $request->expectsJson(),
        );
    })->create();
```

### Satu baris inti — `api:`

Diff pentingnya:

```diff
     ->withRouting(
         web: __DIR__.'/../routes/web.php',
+        api: __DIR__.'/../routes/api.php',
         commands: __DIR__.'/../routes/console.php',
         health: '/up',
     )
```

Tanpa baris tersebut, Laravel 13 tidak memuat `routes/api.php` sama sekali. File boleh ada di disk, tetapi tidak pernah diload — berbeda dari versi lama yang memuat semua file rute lewat `RouteServiceProvider`. Seluruh hasil Fase 6.2 bergantung pada satu baris ini.

### Bukti tanda tangan dari framework

```php
// vendor/laravel/.../Foundation/Configuration/ApplicationBuilder.php:157-162
$api = null,
$apiPrefix = 'api',
```

`$apiPrefix` bawaan `'api'` — itulah mengapa URI akhirnya menjadi `/api/webhook/whatsapp` **tanpa menulis `/api/` prefix manual** di file rute.

### Dua perbaikan gaya dari pint di file yang sama

```diff
+use App\Http\Middleware\HandleInertiaRequests;
 use Illuminate\Foundation\Application;
 use Illuminate\Foundation\Configuration\Exceptions;
 use Illuminate\Foundation\Configuration\Middleware;
+use Illuminate\Http\Middleware\AddLinkHeadersForPreloadedAssets;
 use Illuminate\Http\Request;
 ...
         $middleware->web(append: [
-            \App\Http\Middleware\HandleInertiaRequests::class,
-            \Illuminate\Http\Middleware\AddLinkHeadersForPreloadedAssets::class,
+            HandleInertiaRequests::class,
+            AddLinkHeadersForPreloadedAssets::class,
         ]);
```

Dua fixer pint yang berjalan: `ordered_imports` (daftar use diurut alfabetis) dan `fully_qualified_strict_types` (FQCN di badan file dipersingkat ke alias use). Nol perubahan perilaku; `result: fixed` juga hanya untuk file ini (file rute dan controller lolos tanpa catatan).

### Bagaimana jika baris `api:` tidak ditulis

| Simulasi | Hasil |
|---|---|
| `php artisan route:list --path=webhook` | Kosong — "Showing [0] routes" |
| `GET /api/webhook/whatsapp` dari Meta | `404 Not Found` |
| Fase 6.5 di portal Meta | Jabat tangan gagal: Meta menganggap URL tidak sah |
| Bug menunggu waktu | File rute tetap terlihat di disk — tersamar, paling mahal dicari |

---

## 5. Blok B — Perubahan 5: kerangka `WhatsAppController` (maju jadwal dari Fase 6.3)

### Kode penuh

```php
<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Http\Response;

class WhatsAppController extends Controller
{
    public function verifyWebhook(Request $request): ?Response
    {
        return null;
    }

    public function handleWebhook(Request $request): ?Response
    {
        return null;
    }
}
```

Sengaja **tidak ada logika**. Seluruh isi `verifyWebhook()` (cocokkan `META_VERIFY_TOKEN`, kirim `hub.challenge`) dan `handleWebhook()` (memanggil `ai-service`, menyusun balasan, kirim ke `graph.facebook.com`) dibangun di Fase 6.3 sesuai rencanamu. Tanda tangan metode, namespace, dan deklarasi tipe sudah final sehingga Fase 6.3 hanya mengganti badan.

### Mengapa lahir di Fase 6.2, bukan Fase 6.3

Bukti langsung: `route:list` saat rute sudah terdaftar tetapi controller belum ada:

```
  ReflectionException

  Class "App\Http\Controllers\WhatsAppController" does not exist

  at vendor/laravel/framework/src/Illuminate/Foundation/Console/RouteListCommand.php:290
    286▕             if ($this->isFrameworkController($route)) {
    287▕                 return false;
    288▕             }
    289▕
  ➜  290▕             $path = (new ReflectionClass($route->getControllerClass()))
    291▕                 ->getFileName();
```

Laravel **menginspeksi controller** (`new ReflectionClass`) saat menyusun daftar rute. Yang terjadi tanpa kelas nyata:

| Simulasi | Hasil |
|---|---|
| `php artisan route:list --path=webhook` | Crash `ReflectionException` — verifikasi rute mustahil |
| `GET|POST /api/webhook/whatsapp` | `500` — "Target class does not exist" |
| Ciri khusus | File rute tampak "aman" sekilas, tetapi rute tak bisa diakses |

Kerangka ini semata membuka verifikasi Fase 6.2: setelah ada, semua pengukuran di Bab 7 berlaku.

### Perilaku `return null`

Controller yang mengembalikan `null` — Laravel memakai `Router::toResponse()`, yang menggulung `null` menjadi **`Response 200` dengan body kosong**. Dari sinilah hasil smoke test di Bab 7 (bukan 500). Catatan: bila Meta sudah dikonfigurasi berhadapan dengan kerangka ini di Fase 6.5, jabat tangan `GET` akan gagal karena `hub.challenge` tidak dikirim — itulah pekerjaan Fase 6.3, bukan kegagalan desain Fase 6.2.

---

## 6. Temuan penting selama pengerjaan (dan implikasinya)

### Temuan 1 — Grup `api` di proyek ini **tidak punya throttle bawaan**

Temuan yang ikut memengaruhi Fase 6.3.

**Kondisi.** Komposisi grup `api` ditentukan dua field kondisional (cuplikannya di Bab 3). Verifikasi dilakukan di tiga tempat:

```sh
# hasil penelusuran: satu-satunya setter adalah apiLimiter(), field bawaan null
grep -rn apiLimiter /app/vendor/laravel/framework/src/Illuminate/Foundation/
# Middleware.php:119: protected $apiLimiter;         (bawaan: null)
# Middleware.php:497: $this->apiLimiter ? 'throttle:'.$this->apiLimiter : null;
# Middleware.php:745: $this->apiLimiter = $limiter;   (setter)

# tak ada definisi RateLimiter untuk 'api' di framework
grep -rn "for(\"api\"" /app/vendor/laravel/framework/src/
# (kosong)
```

**Kesimpulannya:** grup `api` proyek ini hanya berisi `[SubstituteBindings]` — **tanpa `throttle:api`**. Laravel 10 dulu memasangnya bawaan via Kernel; scaffold Laravel 13 tidak.

**Implikasi:** webhook WhatsApp kini belum punya pelindung tingkat request. Meta dapat mengirim banyak webhook beruntun (termasuk pengirim ulang pesan). Setiap `POST` langsung diteruskan ke `ai-service` — jumlah panggilan FastAPI membesar tanpa bendungan.

**Pilihan mitigasi** (keputusan ditunda ke Fase 6.3 sesuai rencana):

```php
// pilihan 1: di route khusus webhook
Route::post('/webhook/whatsapp', ...)->middleware('throttle:20,1');

// pilihan 2: global di bootstrap/app.php
$middleware->apiLimiter('api');
// + RateLimiter::for('api', ...) di AppServiceProvider
```

### Temuan 2 — `pint --dirty` terhalang karena container tak melihat `.git`

```
$ docker exec pepebot_core sh -c "php /app/vendor/bin/pint --dirty --format agent"
  The [--dirty] option is only available when using Git.
```

**Sebab:** Compose bind mount-nya `./core-service:/app` — folder `.git` berada di root repo, **di luar** mount. Pint `--dirty` memanfaatkan `git diff` untuk menentukan file mana yang berubah.

**Solusi:** pint dijalankan dengan daftar file eksplisit — `bootstrap/app.php routes/api.php app/Http/Controllers/WhatsAppController.php config/services.php` (empat file PHP yang berubah; `config/services.php` warisan Fase 6.1). Berhasil: satu file diperbaiki.

```json
{"tool":"pint","result":"fixed","files":[{"path":"bootstrap\/app.php","fixers":["fully_qualified_strict_types","ordered_imports"]}]}
```

Catatan: di sisi host, `php vendor/bin/pint` juga mustahil (composer.json menuntut PHP `^8.3`, host 8.2; platform check menolak). Apa pun jalurnya, pint **harus** lewat container.

### Temuan 3 — `POST` tanpa token CSRF tetap diterima (bukan `419`)

Smoke test langsung di dalam container:

```sh
curl -s -o /dev/null -w 'status=%{http_code}\n' \
  -X POST -H 'Content-Type: application/json' -d '{}' \
  http://127.0.0.1:8000/api/webhook/whatsapp
# status=200
```

Jika rute ini di `web.php`, pola yang sama mengembalikan `419 Page Expired` (middleware CSRF menolak permintaan tanpa token). Bukti ini menjelaskan bahwa pilihan `routes/api.php` bekerja sebagaimana dibutuhkan Fase 6.5.

### Temuan 4 — Windows PowerShell hanya pengganggu tampilan, bukan pemecah file

Membaca file UTF-8 via `Get-Content` dengan encoding ANSI bawaan membuat karakter multi-byte (em-dash) tampil `??`. `php -l` + audit-byte `strpos(..., "\u{2014}")` membuktikan file aslinya utuh (Bab 3). Karena itu, pengecekan isi file yang menentukan selalu lewat `docker exec ... sh`, bukan pembacaan PowerShell.

---

## 7. Pembuktian — Fase 6.2 selesai

### Langkah 1: daftar rute

```sh
docker exec pepebot_core php artisan route:list --path=webhook
```

```
  GET|HEAD   api/webhook/whatsapp ........... WhatsAppController@verifyWebhook
  POST       api/webhook/whatsapp ........... WhatsAppController@handleWebhook

                                                            Showing [2] routes
```

```sh
docker exec pepebot_core php artisan route:list --path=webhook --json
```

```json
[{"domain":null,"method":"GET|HEAD","uri":"api\/webhook\/whatsapp","name":null,"action":"App\\Http\\Controllers\\WhatsAppController@verifyWebhook","middleware":["api"],"path":null},
 {"domain":null,"method":"POST","uri":"api\/webhook\/whatsapp","name":null,"action":"App\\Http\\Controllers\\WhatsAppController@handleWebhook","middleware":["api"],"path":null}]
```

### Smoke test HTTP di dalam container

```sh
curl -s -o /dev/null -w 'status=%{http_code}\n' \
  http://127.0.0.1:8000/api/webhook/whatsapp                # status=200 (GET)
curl -s -o /dev/null -w 'status=%{http_code}\n' \
  -X POST -H 'Content-Type: application/json' -d '{}' \
  http://127.0.0.1:8000/api/webhook/whatsapp                # status=200 (POST, tanpa CSRF)
```

### Pemetaan bukti ke klaim

| Bukti | Klaim yang dibuktikan | Alasan kekuatannya |
|---|---|---|
| Dua baris `route:list` | `routes/api.php` benar-benar **dimuat** | `withRouting()` tanpa `api:` **tidak** pernah memuat file itu; munculnya baris membuktikan baris `api:` di `bootstrap/app.php` bekerja |
| URI `api/webhook/whatsapp` (bukan `webhook/whatsapp`) | Prefix bawaan `'api'` bekerja | Sama dengan URL yang akan diregistrasi di portal Meta (Fase 6.5) |
| `middleware: ["api"]` | Rute berada di grup `api`, bukan `web` | Grup yang menentukan apakah POST terkena `VerifyCsrfToken` |
| `route:list` berhasil (bukan ReflectionException) | `WhatsAppController` nyata di disk & autoload | Controller lolos inspeksi `new ReflectionClass` |
| Smoke `POST` → `200` (bukan `419`) | Rute bebas CSRF | Syarat Meta: server-to-server tidak bisa membawa token CSRF |
| Smoke `GET` → `200` kosong | Kerangka jalan (masih null → Response 200) | Bukan `404`/`500` — hanya body kosong, menunggu isi Fase 6.3 |
| `composer.json` diff (Bab 1) | Boost terpasang tepat di `require-dev` | Posisi entri (`require-dev`) tampil penuh dalam diff |
| Output `boost:install` (Bab 2) | Lima artefak dihasilkan | git status mengonfirmasi file benar ada |
| Pint lulus (Bab 6, Temuan 2) | Aturan format terpenuhi | `result: fixed` mengonfirmasi perbaikan |

### Membuktikan ulang sendiri

```powershell
# daftar rute webhook
docker exec pepebot_core php artisan route:list --path=webhook

# middleware dalam format JSON
docker exec pepebot_core php artisan route:list --path=webhook --json

# smoke GET dan POST
docker exec pepebot_core sh -c "curl -s -o /dev/null -w 'GET status=%{http_code}\n'  http://127.0.0.1:8000/api/webhook/whatsapp"
docker exec pepebot_core sh -c "curl -s -o /dev/null -w 'POST status=%{http_code}\n' -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8000/api/webhook/whatsapp"
```

Yang diharapkan: dua baris rute, middleware `["api"]`, dua baris `status=200`.

---

## 8. Risiko bila Fase 6.2 tidak dilakukan, atau dilakukan salah

| Kesalahan yang mungkin | Akibat nyata |
|---|---|
| `routes/api.php` tidak dibuat | Meta menerima `404` untuk kedua verb; Fase 6.5 gagal di jabat tangan pertama |
| Rute ditaruh di `routes/web.php` | POST dari Meta kena `419` (CSRF); URL tanpa prefix `/api` tidak sesuai rencana |
| File api ada tapi baris `api:` di `bootstrap/app.php` dilupakan | Rute tak pernah dimuat: `404`, `route:list` kosong — bug menyamar karena file terlihat "ada" |
| Rute merujuk controller yang belum ada | `route:list` crash + `500` saat diakses; Fase 6.2 jadi tidak dapat diukur |
| Controller dibuat tanpa tipe return (mengabaikan panduan) | Gaya tidak konsisten; pint akan memperbaikinya, tetapi konsisten sejak awal lebih murah |
| Boost tidak diinstal | Setiap sesi berikutnya kembali dipagar; panduan versi tidak tersedia; risiko pola versi lama |
| Boost dipasang sebagai `require` (bukan `require-dev`) | Paket ikut ke build produksi: ukuran build membengkak, permukaan serangan bertambah tanpa manfaat runtime |
| Temuan 1 (tanpa throttle) diabaikan sampai produksi | Kerumunan webhook Meta memanggil `ai-service` tanpa bendungan — beban membanjiri FastAPI |

---

## 9. Daftar file yang berubah di Fase 6.2 (lengkap, tak ada yang terlewat)

| File | Jenis | Asal | Isi |
|---|---|---|---|
| `core-service/composer.json` | diubah | Blok A | `+1` entri `require-dev`: `"laravel/boost": "^2.10"` |
| `core-service/composer.lock` | diubah | Blok A | Sinkron dengan diff composer.json; tanpa advisories |
| `core-service/CLAUDE.md` | diubah | Blok A | Panduan generator Boost (+161/−29) |
| `core-service/boost.json` | baru | Blok A | Keputusan instalasi Boost |
| `core-service/.mcp.json` | baru | Blok A | Registrasi MCP server `laravel-boost` |
| `core-service/.claude/skills/**` | baru | Blok A | 6 skill domain (36 file Markdown) |
| `core-service/routes/api.php` | baru | Blok B | 2 rute: `GET` + `POST` `/api/webhook/whatsapp` |
| `core-service/bootstrap/app.php` | diubah | Blok B | `+1` baris `api:`; `+2` use statement & FQCN dipersingkat pint |
| `core-service/app/Http/Controllers/WhatsAppController.php` | baru | Blok B | Kerangka dua metode kosong |
| `core-service/AGENTS.md` | **tidak berubah** | Blok A | Panduan hasil Boost jatuh ke `CLAUDE.md`, bukan file ini |

Dua catatan anti-terlewat:

1. `git status` juga menampilkan `M core-service/config/services.php` — itu perubahan **Fase 6.1** (sudah dilaporkan di `docs/backend/FASE-6-1-KONFIGURASI-ENVIRONMENT.md`), bukan bagian Fase 6.2.
2. Status git menyisakan file dari fase ai-service (`.env.example`, `app/core/security.py`, dua dokumen `docs/`) yang tetap untracked — tidak tersentuh Fase 6.2.

---

## 10. Istilah teknis

- **Grup middleware `api`**: kumpulan middleware yang diterapkan ke semua rute dalam `routes/api.php`. Di proyek ini isinya `[SubstituteBindings]` (tanpa CSRF, tanpa throttle — Temuan 1).
- **`VerifyCsrfToken` / `419`**: middleware pembela CSRF pada grup `web`. Tanpa token, Laravel menjawab `419 Page Expired`.
- **Throttle / rate limiter**: pembatas jumlah permintaan per unit waktu; ditulis `throttle:N,1` atau `throttle:api` bila limiter bernama tersedia.
- **Refleksi (ReflectionClass)**: introspeksi kelas PHP saat runtime; `route:list` memakainya untuk memetakan nama file controller.
- **`withRouting()`**: API Laravel 11+ untuk mendaftarkan jalur rute di `bootstrap/app.php`, menggantikan `RouteServiceProvider`.
- **`::class` di rute**: konstanta kelas yang melempar FQCN sebagai string tanpa memicu autoload — kelas baru benar-benar dipakai saat rute dipanggil.
- **MCP (Model Context Protocol)**: protokol untuk membuat klien agen membaca perkakas (database, dokumentasi) yang diekspos oleh server, di sini `php artisan boost:mcp`.
- **`require-dev`**: bagian Composer yang hanya terunduh saat pengembangan (`composer install`); hilang dari build produksi (`--no-dev`).
- **pint fixer**: formatter PHP dari Laravel; `--dirty` memakai diff git, alternatifnya daftar file eksplisit.
- **Bind mount**: memasang folder host ke container (`./core-service:/app`) — sebab itu `.git` di root repo tak terlihat container.

---

## 11. Status fase

| Fase | Status |
|---|---|
| 6.1 Konfigurasi environment | ✅ Selesai — laporan: `docs/backend/FASE-6-1-KONFIGURASI-ENVIRONMENT.md` |
| 6.2 Jalur webhook di level rute | ✅ Selesai — dokumen ini; ditambah mandate Boost dipenuhi |
| 6.3 Controller penuh | 🔜 Berikutnya — badan `verifyWebhook()` + `handleWebhook()`; kunci `config()` dari 6.1 sudah siap |
| 6.4 Ngrok | 🔜 Setelahnya |
| 6.5 Portal Meta & uji end-to-end | 🔜 Menunggu kredensial |
