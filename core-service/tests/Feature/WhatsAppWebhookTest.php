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
