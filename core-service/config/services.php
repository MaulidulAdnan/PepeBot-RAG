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
