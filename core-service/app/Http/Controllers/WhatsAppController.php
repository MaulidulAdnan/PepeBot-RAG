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
