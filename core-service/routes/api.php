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
|
| Final URL: GET/POST /api/webhook/whatsapp
| Controller Fase 6.3: App\Http\Controllers\WhatsAppController
*/

Route::get('/webhook/whatsapp', [WhatsAppController::class, 'verifyWebhook']);

Route::post('/webhook/whatsapp', [WhatsAppController::class, 'handleWebhook'])
    ->middleware('throttle:30,1');
