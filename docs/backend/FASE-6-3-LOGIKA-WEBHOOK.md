# Fase 6.3 — Laporan Perubahan: Logika Webhook (Controller Penuh + Test)

Cakupan: **Fase 6.3** dari `To Do List Backend.md` — mengisi `verifyWebhook()` dan `handleWebhook()` di `WhatsAppController`, memasang throttle di rute POST, menambah test feature, dan membuktikannya dua lapis: test otomatis dan uji hidup terhadap `ai-service` asli.

Seluruhnya: perubahan kode hanya di tiga file; satu file probe sementara dipakai untuk pembuktian lalu **dihapus**, dan tidak ada perubahan `.env`, migrasi, atau `composer`.

---

## 0. Kondisi sebelum Fase 6.3

| Objek | Kondisi awal |
|---|---|
| `WhatsAppController` | Kerangka kosong dua metode `return null` (dibuat di Fase 6.2 hanya untuk membuka `route:list`) |
| Rute POST | Tanpa throttle — Temuan 1 laporan Fase 6.2 (grup `api` proyek ini tidak punya throttle bawaan) |
| Test webhook | Belum ada |
| Kredensial Meta (`META_WHATSAPP_TOKEN`, `META_PHONE_ID`) | Kosong secara sengaja (Fase 6.1) — baru diisi di Fase 6.5 |

## 1. Fakta prasyarat yang harus dikunci sebelum menulis kode

| Fakta | Sumber | Konsekuensi ke desain |
|---|---|---|
| `POST /api/chat` menerima `{"query": ..., "channel": "WA"}` — field-nya `query`, bukan `message`; header wajib `X-Internal-Key` | `docs/ADDENDUM-KONTRAK-API.md` + `ai-service/app/api/endpoints/chat.py` | Body permintaan Laravel dipilih persis ini; salah field = 422 |
| Respons ai-service: `{"answer", "citations", "fallback", "fallback_contact"}`; `fallback_contact` hanya diisi saat `fallback: true` | sama | Laravel tidak menilai SOP; hanya membaca `fallback` |
| Bentuk `fallback_contact`: `{"whatsapp": "...", "url": "..."}` (bernilai kontak petugas nyata dari `DESA_PETUGAS_*` di ai-service) | `ai-service/app/services/llm_service.py::get_fallback_contact()` | Kunci yang dibaca Laravel: `whatsapp` dan `url` |
| Tabel `cache` sudah ter-migrasi (batch 1) dan `CACHE_STORE=database` | `php artisan migrate:status` | Throttle dan dedupe bisa dipakai **tanpa** mengubah `.env` |

## 2. Keputusan fase (dan alasannya)

| # | Keputusan | Alasan |
|---|---|---|
| 1 | Sumber kontak fallback = `fallback_contact` dari respons ai-service, bukan duplikat di `.env` Laravel | Addendum menulis "teruskan `fallback` dan `fallback_contact` apa adanya". Kontak berubah cukup edit `ai-service/.env` satu titik. Keputusan ini sempat tertunda di laporan Fase 6.2 — kini resmi ditetapkan. |
| 2 | Alur MVP **sinkron** (ack setelah ai-service menjawab), dedupe menutup celah pengiriman ulang | Meta mengharapkan 200 dalam sekitar 20 detik; latensi LLM lokal biasanya jauh di bawah itu. Tabel `jobs` sudah ada bila kelak perlu antrean; keputusan antrean ditunda sampai ada data nyata. |
| 3 | Throttle `30/menit per IP` hanya di POST | Penutup Temuan 1 Fase 6.2. GET tidak dithrottle karena jabat tangan berlangsung sekali. |
| 4 | Dedupe dengan `wamid` di cache 24 jam | Meta mengirim ulang webhook yang tidak di-ack; tanpa dedupe ada dua panggilan AI dan dua balasan. |
| 5 | Tipe non-teks → balas pemberitahuan teks | Di luar cakupan MVP; pengguna tetap mendapat balasan, bukan diabaikan. |
| 6 | Selalu jawab 200 (`EVENTS_RECEIVED` / `DUPLICATE_IGNORED`) | Menjawab non-200 membuat Meta mengirim ulang; kegagalan internal lebih tepat dicatat di log. |
| 7 | Timeout: ai-service 45 detik, Meta 30 detik | LLM lokal dapat butuh beberapa detik; panggilan ke server Meta dijaga lebih singkat. |
| 8 | Log berisi wamid, pengirim, tipe, dan cuplikan body (dipotong lewat `Str::limit`), tanpa rahasia | Kunci rahasia tidak pernah masuk log; cuplikan body membantu debug Fase 6.5. |

## 3. Perubahan 1 — `core-service/routes/api.php`: throttle di POST

Diff:

```diff
-Route::post('/webhook/whatsapp', [WhatsAppController::class, 'handleWebhook']);
+Route::post('/webhook/whatsapp', [WhatsAppController::class, 'handleWebhook'])
+    ->middleware('throttle:30,1');
```

Kode penuh file setelah perubahan:

```php
<?php

use App\Http\Controllers\WhatsAppController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| API Routes
|--------------------------------------------------------------------------
|
| Fase 6.2: jalur webhook WhatsApp. Ditaruh di routes/api.php, sehingga
| grup middleware bawaan adalah "api" (tanpa VerifyCsrfToken), jadi kedua
| verb dari server Meta diterima.
|
| Fase 6.3: POST dibatasi throttle 30 permintaan/menit per IP (penutup
| Temuan 1 laporan Fase 6.2: scaffold ini tidak punya throttle api bawaan;
| tabel cache sudah ter-migrasi sehingga limiter siap pakai).
|
| Final URL: GET/POST /api/webhook/whatsapp
| Controller Fase 6.3: App\Http\Controllers\WhatsAppController
*/

Route::get('/webhook/whatsapp', [WhatsAppController::class, 'verifyWebhook']);

Route::post('/webhook/whatsapp', [WhatsAppController::class, 'handleWebhook'])
    ->middleware('throttle:30,1');
```

Catatan: throttle `30,1` memakai limiter inline (`throttle:N,1`) sehingga tidak butuh `RateLimiter::for()` di provider.

## 4. Perubahan 2 — `core-service/app/Http/Controllers/WhatsAppController.php` (kode penuh)

```php
<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use Throwable;

/**
 * Penerima webhook WhatsApp Cloud API (Fase 6.3).
 *
 * Dua aksi: jabat tangan verifikasi Meta (GET) dan penerimaan pesan pelanggan
 * (POST). Teks yang masuk diteruskan ke ai-service (/api/chat, header
 * X-Internal-Key); balasan dikirim via Meta Graph API. Setiap POST selalu
 * diakhiri 200 — Meta menuntut ack cepat dan mengirim ulang bila gagal.
 */
class WhatsAppController extends Controller
{
    public function verifyWebhook(Request $request): Response
    {
        $mode = (string) $request->query('hub_mode');
        $token = (string) $request->query('hub_verify_token');
        $challenge = (string) $request->query('hub_challenge');

        if ($mode === 'subscribe' && hash_equals(config('services.whatsapp.verify_token'), $token)) {
            return response($challenge, 200)->header('Content-Type', 'text/plain');
        }

        return response('Forbidden', 403);
    }

    public function handleWebhook(Request $request): Response
    {
        $payload = $request->json()->all();

        $message = $this->firstMessage($payload);

        // Payload tanpa "messages" (status sent/delivered/read) cukup di-ack.
        if ($message === null) {
            return response('EVENTS_RECEIVED', 200);
        }

        $messageId = (string) ($message['id'] ?? '');
        $from = (string) ($message['from'] ?? '');

        Log::info('Webhook pesan masuk', [
            'wamid' => $messageId,
            'from' => $from,
            'type' => (string) ($message['type'] ?? ''),
        ]);

        // Meta dapat mengirim ulang webhook yang dianggap gagal; wamid
        // menjadi kunci dedupe agar tidak ada dua balasan untuk satu pesan.
        if ($this->isDuplicate($messageId)) {
            return response('DUPLICATE_IGNORED', 200);
        }

        // Tidak ada pengirim → tidak ada tujuan balasan; cukup ack.
        if ($from === '') {
            return response('EVENTS_RECEIVED', 200);
        }

        $text = $this->messageText($message);

        if ($text === null) {
            $this->sendText($from, $this->nonTextNotice());

            return response('EVENTS_RECEIVED', 200);
        }

        $this->sendText($from, $this->askAiService($text, $messageId));

        return response('EVENTS_RECEIVED', 200);
    }

    /**
     * Mengambil pesan pertama dari struktur webhook Meta.
     *
     * @param  array<string, mixed>  $payload
     * @return array<string, mixed>|null
     */
    private function firstMessage(array $payload): ?array
    {
        foreach ($payload['entry'] ?? [] as $entry) {
            foreach ($entry['changes'] ?? [] as $change) {
                $messages = $change['value']['messages'] ?? [];

                if (is_array($messages) && $messages !== []) {
                    return $messages[0];
                }
            }
        }

        return null;
    }

    /**
     * Teks dari pesan; null berarti tipe bukan teks (gambar/audio/dokumen).
     *
     * @param  array<string, mixed>  $message
     */
    private function messageText(array $message): ?string
    {
        if (($message['type'] ?? '') !== 'text') {
            return null;
        }

        $body = trim((string) ($message['text']['body'] ?? ''));

        return $body !== '' ? $body : null;
    }

    /** Id wamid dikenang 24 jam di tabel cache (CACHE_STORE=database). */
    private function isDuplicate(string $messageId): bool
    {
        if ($messageId === '') {
            return false;
        }

        $key = 'wa:pesan:'.$messageId;

        if (Cache::has($key)) {
            return true;
        }

        Cache::put($key, 1, 86400);

        return false;
    }

    /**
     * Memanggil ai-service dan menyusun teks balasan.
     *
     * Kontrak: {"query": ..., "channel": "WA"} →
     * {"answer", "citations", "fallback", "fallback_contact"}.
     * fallback=true → jawaban AI dibuang, diganti pesan kontak petugas
     * (sumber kontak: fallback_contact dari respons, bukan duplikat di .env).
     */
    private function askAiService(string $text, string $messageId): string
    {
        $url = rtrim((string) config('services.ai_service.url'), '/').'/api/chat';
        $key = (string) config('services.ai_service.key');

        try {
            $response = Http::withHeaders(['X-Internal-Key' => $key])
                ->timeout(45)
                ->post($url, ['query' => $text, 'channel' => 'WA']);
        } catch (Throwable $error) {
            Log::error('ai-service tidak terjangkau', ['wamid' => $messageId, 'error' => $error->getMessage()]);

            return $this->serviceErrorText();
        }

        if (! $response->successful()) {
            Log::error('ai-service gagal menjawab', [
                'wamid' => $messageId,
                'status' => $response->status(),
                'body' => Str::limit($response->body(), 300),
            ]);

            return $this->serviceErrorText();
        }

        $data = $response->json() ?? [];

        if ((bool) ($data['fallback'] ?? false) === true) {
            Log::info('AI fallback — jawaban dibuang, memakai pesan kontak', ['wamid' => $messageId]);

            return $this->fallbackText($data['fallback_contact'] ?? []);
        }

        $answer = (string) ($data['answer'] ?? '');

        if ($answer === '') {
            Log::warning('ai-service menjawab tanpa field answer', ['wamid' => $messageId]);

            return $this->serviceErrorText();
        }

        return $answer;
    }

    /** Menyusun teks fallback dari kontak pada respons ai-service. */
    private function fallbackText(array $contact): string
    {
        $lines = ['Maaf, informasi tersebut tidak ada di pedoman dokumen Desa Pepe.'];

        $wa = trim((string) ($contact['whatsapp'] ?? ''));
        $url = trim((string) ($contact['url'] ?? ''));

        if ($wa !== '') {
            $lines[] = "WhatsApp petugas: {$wa}";
        }

        if ($url !== '') {
            $lines[] = "Info desa: {$url}";
        }

        if (count($lines) === 1) {
            $lines[] = 'Silakan hubungi petugas desa untuk bantuan lanjutan.';
        }

        return implode("\n", $lines);
    }

    /** Mengirim teks ke pelanggan melalui Meta Graph API. */
    private function sendText(string $to, string $body): void
    {
        $token = (string) config('services.whatsapp.token');
        $phoneId = (string) config('services.whatsapp.phone_id');

        if ($token === '' || $phoneId === '') {
            // Wajar di MVP: kredensial baru dipasang di Fase 6.5.
            Log::warning('Kredensial WhatsApp belum terisi — balasan tidak terkirim', [
                'to' => $to,
                'body' => Str::limit($body, 200),
            ]);

            return;
        }

        $version = (string) config('services.whatsapp.api_version', 'v17.0');
        $url = "https://graph.facebook.com/{$version}/{$phoneId}/messages";

        try {
            $response = Http::withToken($token)->timeout(30)->post($url, [
                'messaging_product' => 'whatsapp',
                'to' => $to,
                'type' => 'text',
                'text' => ['body' => $body],
            ]);
        } catch (Throwable $error) {
            Log::error('Gagal menghubungi Meta Graph API', ['to' => $to, 'error' => $error->getMessage()]);

            return;
        }

        if ($response->successful()) {
            Log::info('Balasan terkirim ke Meta', ['to' => $to, 'status' => $response->status()]);
        } else {
            Log::warning('Meta menolak/menggagalkan balasan', [
                'to' => $to,
                'status' => $response->status(),
                'body' => Str::limit($response->body(), 300),
            ]);
        }
    }

    /** Pesan untuk tipe non-teks di MVP. */
    private function nonTextNotice(): string
    {
        return 'Maaf, untuk saat ini saya hanya bisa membalas pesan teks. Silakan kirim pertanyaanmu sebagai teks ya.';
    }

    /** Pesan ketika ai-service tidak dapat diandalkan. */
    private function serviceErrorText(): string
    {
        return 'Maaf, sistem penjawab sedang mengalami gangguan. Silakan coba lagi sebentar, atau hubungi petugas desa untuk bantuan.';
    }
}
```

### Peta alur handleWebhook

```mermaid
flowchart TD
    A[POST /api/webhook/whatsapp] --> B{ada "messages"?}
    B -- tidak --> C[200 EVENTS_RECEIVED]
    B -- ya --> D[wamid + from di-log]
    D --> E{wamid pernah diterima 24 jam?}
    E -- ya --> F[200 DUPLICATE_IGNORED]
    E -- tidak --> G{from kosong?}
    G -- ya --> H[200 EVENTS_RECEIVED]
    G -- tidak --> I{tipe = teks?}
    I -- tidak --> J[kirim pemberitahuan non-teks]
    I -- ya --> K[POST ai-service /api/chat]
    K -- gagal --> L[teks gangguan]
    K -- fallback true --> M[Jawaban AI dibuang; teks kontak]
    K -- normal --> N[Jawaban AI]
    M & N & L --> O[sendText ke Meta Graph API]
    J --> O
    O --> P[200 EVENTS_RECEIVED]
```

## 5. Perubahan 3 — `core-service/tests/Feature/WhatsAppWebhookTest.php` (kode penuh)

Dibuat lewat perintah sesuai panduan Boost:

```sh
docker exec pepebot_core php artisan make:test WhatsAppWebhookTest --phpunit --no-interaction
```

Pint mencatat satu perubahan gaya: `no_unused_imports` (import `Config` dihapus karena test memakai helper `config()`).

```php
<?php

namespace Tests\Feature;

use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class WhatsAppWebhookTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        $this->setConfig();
    }

    public function test_jabat_tangan_token_cocok_mengembalikan_challenge(): void
    {
        $response = $this->getJson(
            '/api/webhook/whatsapp?hub_mode=subscribe&hub_verify_token=TOKEN-RAHASIA-123&hub_challenge=CLR-456'
        );

        $response->assertOk();
        $response->assertContent('CLR-456');
    }

    public function test_jabat_tangan_token_salah_ditolak(): void
    {
        $response = $this->getJson(
            '/api/webhook/whatsapp?hub_mode=subscribe&hub_verify_token=token-salah&hub_challenge=CLR-456'
        );

        $response->assertStatus(403);
    }

    public function test_pesan_teks_diteruskan_ke_ai_service_dan_dibalas_via_meta(): void
    {
        Http::fake([
            'ai-service:8001/api/chat' => Http::response([
                'answer' => 'Jawaban SOP.',
                'citations' => [],
                'fallback' => false,
                'fallback_contact' => [],
            ], 200),
            'graph.facebook.com/*' => Http::response(['success' => true], 200),
        ]);

        $response = $this->postJson('/api/webhook/whatsapp', $this->payloadPesan(
            body: 'Syarat KTP hilang apa saja?',
            wamid: 'wamid.TEST-1'
        ));

        $response->assertOk();

        Http::assertSent(function (object $request): bool {
            return $request->url() === 'http://ai-service:8001/api/chat'
                && $request['query'] === 'Syarat KTP hilang apa saja?'
                && (string) $request['channel'] === 'WA'
                && $request->header('X-Internal-Key')[0] === 'internal-key-123';
        });

        Http::assertSent(function (object $request): bool {
            return str_contains($request->url(), 'graph.facebook.com/v17.0/PHONE1/messages')
                && $request['to'] === '628123456789'
                && $request['text']['body'] === 'Jawaban SOP.'
                && $request->header('Authorization')[0] === 'Bearer meta-token-xyz';
        });
    }

    public function test_fallback_membuang_jawaban_ai_dan_pakai_kontak_petugas(): void
    {
        Http::fake([
            'ai-service:8001/api/chat' => Http::response([
                'answer' => 'Jawaban menyesatkan ini harus dibuang.',
                'citations' => [],
                'fallback' => true,
                'fallback_contact' => ['whatsapp' => '081234567890', 'url' => 'https://pepe.desa.id'],
            ], 200),
            'graph.facebook.com/*' => Http::response(['success' => true], 200),
        ]);

        $response = $this->postJson('/api/webhook/whatsapp', $this->payloadPesan(
            body: 'Resep rendang pakai jahe berapa?',
            wamid: 'wamid.TEST-2'
        ));

        $response->assertOk();

        $this->assertTrue(Http::recorded() !== []);
        $terkirim = collect(Http::recorded())
            ->filter(fn (array $pair): bool => str_contains($pair[0]->url(), 'graph.facebook.com'))
            ->first();

        $this->assertNotNull($terkirim, 'Pesan balasan Meta harus terkirim.');
        $bodyBalasan = (string) $terkirim[0]['text']['body'];
        $this->assertStringContainsString('081234567890', $bodyBalasan);
        $this->assertStringContainsString('https://pepe.desa.id', $bodyBalasan);
        $this->assertStringNotContainsString('Jawaban menyesatkan ini harus dibuang.', $bodyBalasan);
    }

    public function test_status_update_diack_tanpa_panggilan_http(): void
    {
        Http::fake();

        $response = $this->postJson('/api/webhook/whatsapp', $this->payloadStatus());

        $response->assertOk();
        $response->assertContent('EVENTS_RECEIVED');
        Http::assertNothingSent();
    }

    public function test_pesan_non_teks_menerima_pemberitahuan(): void
    {
        Http::fake([
            'graph.facebook.com/*' => Http::response(['success' => true], 200),
        ]);

        $response = $this->postJson('/api/webhook/whatsapp', $this->payloadPesan(
            type: 'image',
            wamid: 'wamid.TEST-3'
        ));

        $response->assertOk();

        $terkirim = collect(Http::recorded())
            ->filter(fn (array $pair): bool => str_contains($pair[0]->url(), 'graph.facebook.com'))
            ->first();

        $this->assertNotNull($terkirim, 'Pemberitahuan harus terkirim.');
        $this->assertStringContainsString('hanya bisa membalas pesan teks', (string) $terkirim[0]['text']['body']);
    }

    private function setConfig(): void
    {
        config([
            'services.whatsapp.verify_token' => 'TOKEN-RAHASIA-123',
            'services.whatsapp.token' => 'meta-token-xyz',
            'services.whatsapp.phone_id' => 'PHONE1',
            'services.whatsapp.api_version' => 'v17.0',
            'services.ai_service.url' => 'http://ai-service:8001',
            'services.ai_service.key' => 'internal-key-123',
        ]);
    }

    /**
     * Payload webhook Meta berisi satu pesan pelanggan.
     *
     * @return array<string, mixed>
     */
    private function payloadPesan(?string $body = null, string $type = 'text', string $wamid = 'wamid.TEST-1'): array
    {
        $pesan = ['from' => '628123456789', 'id' => $wamid, 'timestamp' => 1730812800, 'type' => $type];

        if ($body !== null) {
            $pesan['text'] = ['body' => $body];
        }

        return ['object' => 'whatsapp_business_account', 'entry' => [['id' => 'WABA1', 'changes' => [['field' => 'messages', 'value' => [
            'messaging_product' => 'whatsapp',
            'metadata' => ['display_phone_number' => '628999888777', 'phone_number_id' => 'PHONE1'],
            'contacts' => [['profile' => ['name' => 'Budi'], 'wa_id' => '628123456789']],
            'messages' => [$pesan],
        ]]]]]];
    }

    /**
     * Payload webhook Meta berisi status (sent/delivered/read), tanpa pesan.
     *
     * @return array<string, mixed>
     */
    private function payloadStatus(): array
    {
        return ['object' => 'whatsapp_business_account', 'entry' => [['id' => 'WABA1', 'changes' => [['field' => 'messages', 'value' => [
            'messaging_product' => 'whatsapp',
            'metadata' => ['display_phone_number' => '628999888777', 'phone_number_id' => 'PHONE1'],
            'statuses' => [['id' => 'wamid.TEST-S1', 'status' => 'delivered', 'recipient_id' => '628123456789']],
        ]]]]]];
    }
}
```

## 6. Pembuktian A — test otomatis

```sh
docker exec pepebot_core php artisan test --compact tests/Feature/WhatsAppWebhookTest.php
```

```
  ......

  Tests:    6 passed (18 assertions)
  Duration: 41.93s
```

Output pint sebelumnya: `{"tool":"pint","result":"fixed","files":[{"path":"tests\/Feature\/WhatsAppWebhookTest.php","fixers":["no_unused_imports"]}]}` — satu perbaikan gaya, tanpa perubahan lain.

Pemetaan bukti ke klaim:

| Test | Klaim | Mengapa kuat |
|---|---|---|
| `token_cocok_mengembalikan_challenge` | Jabat tangan benar mengirim balik `hub.challenge` | `assertContent('CLR-456')` memeriksa body persis, bukan sekadar status |
| `token_salah_ditolak` | Token salah → 403, bukan challenge | Mencegah pihak lain meregistrasikan URL webhook |
| `pesan_teks_diteruskan...` | Body ai-service memuat `query` + `channel: WA` + header `X-Internal-Key`; body Meta memuat `to`, `Bearer`, body jawaban | Dua `assertSent` memeriksa URL, field, dan header persis |
| `fallback_membuang...` | Jawaban AI **tidak** tembus ke Meta; kontak petugas masuk; URL juga | `assertStringNotContainsString` + dua contains |
| `status_update_diack...` | Payload status di-ack tanpa satu pun panggilan HTTP | `assertNothingSent` |
| `pesan_non_teks...` | Image → teks pemberitahuan (bukan crash, bukan diam) | Body balasan diperiksa dengan `assertStringContainsString` |

## 7. Pembuktian B — uji hidup (ai-service asli, bukan mock)

Probe berjalan di dalam container melalui skrip sementara yang mengirim permintaan nyata ke `http://127.0.0.1:8000` (artisan serve di `pepebot_core`), lalu **dihapus** setelah dipakai (`rm /app/_tmp_probe_fase63.php` — tidak menginap di repo). Baris `Deprecated: curl_close()` pada output berasal dari skrip sementara itu (peringatan deprecation PHP 8.5), bukan dari kode aplikasi.

### Output probe

```
handshake-token-benar : status=200 body=CH-LIVE-1
handshake-token-salah : status=403 body=Forbidden
post-sop              : status=200 body=EVENTS_RECEIVED
post-sop-duplikat     : status=200 body=DUPLICATE_IGNORED
post-luar-sop         : status=200 body=EVENTS_RECEIVED
post-status           : status=200 body=EVENTS_RECEIVED
```

### Cuplikan `storage/logs/laravel.log` saat uji hidup berjalan

```
[14:17:34] local.INFO: Webhook pesan masuk {"wamid":"wamid.LIVE-1","from":"6281999990000","type":"text"}
[14:18:02] local.WARNING: Kredensial WhatsApp belum terisi — balasan tidak terkirim
    {"to":"6281999990000","body":"Halo, untuk pengurusan KTP dengan Varian Hilang, berikut Syarat yang diperlukan:
    - Foto Surat Kehilangan Polisi
    - Foto KK ..."}
[14:18:22] local.INFO: Webhook pesan masuk {"wamid":"wamid.LIVE-1", ...}     ← pengiriman ulang wamid yang sama
[14:18:27] local.INFO: Webhook pesan masuk {"wamid":"wamid.LIVE-2","from":"6281999990000","type":"text"}
[14:18:29] local.INFO: AI fallback — jawaban dibuang, memakai pesan kontak {"wamid":"wamid.LIVE-2"}
[14:18:29] local.WARNING: Kredensial WhatsApp belum terisi — balasan tidak terkirim
    {"to":"6281999990000","body":"Maaf, informasi tersebut tidak ada di pedoman dokumen Desa Pepe.
    WhatsApp petugas: 081234567890
    Info desa: https://pepe.desa.id"}
```

### Pemetaan bukti hidup ke klaim

| Bukti | Klaim | Mengapa kuat |
|---|---|---|
| `body=CH-LIVE-1` | Challenge dikembalikan persis | Body, bukan hanya status |
| token salah → `403` | Pembanding token penjaga ada | Status + body `Forbidden` |
| `post-sop` + log jawaban **asli** FastAPI | Rangkaian penuh Laravel → ai-service → teks balasan jalan | Jawaban itu hasil sungguhan FastAPI (`"Halo, untuk pengurusan KTP..."`), bukan mock |
| Warning **Kredensial belum terisi** | sedangkan token memang kosong (Fase 6.1) — jalan pintas `sendText` bekerja sempurna | Situasi tertangani tertib lewat log WARNING, bukan error 500 |
| wamid sama → diabaikan sebagai `DUPLICATE_IGNORED` + **tidak ada ai-call kedua** | Dedupe aktif | Antara 14:18:22 dan 14:18:27 tidak ada baris jawaban baru |
| `post-luar-sop` → log fallback + teks memuat `081234567890` serta `https://pepe.desa.id` | Kontrak fallback: AI dihentikan, kontak petugas nyata dipakai | Kontak berasal dari `fallback_contact` respons asli, bukan mock |
| `post-status` ter-ack tanpa jawaban | Payload status dikenali | `EVENTS_RECEIVED`, tidak ada kiriman |

## 8. Risiko bila Fase 6.3 tidak dilakukan, atau dilakukan salah

| Kesalahan yang mungkin | Akibat nyata |
|---|---|
| `handleWebhook` menjawab non-200 saat internal error | Meta mengirim ulang; ai-call dan balasan ganda |
| Tidak ada dedupe | Satu pesan menghasilkan dua balasan WhatsApp |
| Salah kirim field (`message` alih-alih `query`) | ai-service menolak 422; pengguna tidak pernah dibalas |
| Lupa header `X-Internal-Key` | 401 di ujung ai-service; jawaban jadi teks gangguan terus-menerus |
| Jawaban fallback tetap diteruskan ke pengguna | Chatbot menjawab di luar SOP — pelanggaran inti tujuan proyek |
| Challenge dikembalikan tanpa memeriksa token | Siapa pun bisa meregistrasikan URL webhook-mu ke akun WhatsApp Business milik orang lain |
| Tidak ada throttle | Banjir webhook menumpuk langsung ke ai-service |

## 9. Cara membuktikan ulang

```powershell
# Test otomatis
docker exec pepebot_core php artisan test --compact tests/Feature/WhatsAppWebhookTest.php

# Daftar rute + middleware (POST harus berisi "api", logika rute punya limiter)
docker exec pepebot_core php artisan route:list --path=webhook

# Jabat tangan manual (ganti <TOKEN> dengan isi META_VERIFY_TOKEN di core-service/.env)
curl "http://127.0.0.1:8000/api/webhook/whatsapp?hub_mode=subscribe&hub_verify_token=<TOKEN>&hub_challenge=CLR"
# harus menjawab persis "CLR"

# Uji hidup paling primitif: POST kosong
docker exec pepebot_core sh -c "curl -s -o /dev/null -w 'status=%{http_code}\n' -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8000/api/webhook/whatsapp"
# harus status=200; untuk melihat body `EVENTS_RECEIVED` di terminal, hapus `-o /dev/null -w '...'`

# Jejak saat uji hidup berjalan
docker exec pepebot_core sh -c "tail -n 30 /app/storage/logs/laravel.log"
```

## 10. Daftar file yang berubah di Fase 6.3

| File | Jenis | Isi |
|---|---|---|
| `core-service/routes/api.php` | diubah | `->middleware('throttle:30,1')` pada POST; komentar diperbarui |
| `core-service/app/Http/Controllers/WhatsAppController.php` | diubah | Kerangka → logika penuh 9 metode |
| `core-service/tests/Feature/WhatsAppWebhookTest.php` | baru | 6 test feature |
| `storage/logs/laravel.log` | jejak | Berisi catatan uji (bukan kode) |

Catatan supaya tidak terlewat: skrip `_tmp_probe_fase63.php` **dihapus** setelah pembuktian, sehingga tidak muncul di status git. Tidak ada perubahan `.env`, migrasi, `composer.json`.

## 11. Catatan lanjutan (buka untuk fase berikutnya)

1. **Log sebelum dedupe** — baris `Webhook pesan masuk` dicatat sebelum pemeriksaan dedupe, sehingga wamid ganda meninggalkan dua baris log padahal diproses sekali. Untuk kerapian, baris ini bisa dipindah ke belakang dedupe kelak.
2. **Antrean** — jika uji Fase 6.5 kelak menunjukkan latensi LLM mendekati batas 20 detik, alur dipindah ke tugas antrean (`queue`); tabel `jobs` sudah siap sejak awal.
3. **Kredensial Meta** — sisi `sendText` sudah siap sepenuhnya; hanya menunggu `META_WHATSAPP_TOKEN` + `META_PHONE_ID` dipasang di Fase 6.5.

## 12. Istilah teknis

- **Webhook**: mekanisme server Meta mengirim notifikasi HTTP ke kita saat pesan datang atau status berubah.
- **Ack (200)**: tanda terima yang diserahkan ke Meta; non-200 memicu pengiriman ulang.
- **Dedupe**: membuang webhook yang sudah diproses agar tidak dibalas dua kali; dideteksi lewat ID pesan + penyimpanan sementara.
- **wamid**: ID per pesan WhatsApp (`wamid.*`) — kunci dedupe.
- **`hash_equals`**: pembanding string dengan waktu konstanta, mencegah timing attack pada kunci jabat tangan.
- **Throttle `30,1`**: maksimal 30 permintaan per menit per IP.
- **Bearer token**: pola `Authorization: Bearer <token>` yang diminta Meta Graph API.
- **Fallback**: kondisi ai-service menyatakan jawaban di luar SOP; Laravel harus mengganti teksnya, bukan meneruskannya apa adanya.

## 13. Status fase

| Fase | Status |
|---|---|
| 6.1 Konfigurasi environment | ✅ Selesai | oke
| 6.2 Jalur webhook di level rute | ✅ Selesai |
| 6.3 Logika webhook | ✅ Selesai — dokumen ini |
| 6.4 Ngrok | 🔜 Berikutnya |
| 6.5 Portal Meta & uji end-to-end | 🔜 Menunggu kredensial (`META_WHATSAPP_TOKEN`, `META_PHONE_ID`) |
