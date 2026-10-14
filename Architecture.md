# Blueprint: Sistem Informasi Administrasi Desa (RAG Chatbot)

## 1. Overview
Aplikasi pusat informasi pengurusan administrasi desa (seperti surat kematian, pindah kartu keluarga) dalam lingkup kecamatan. Sistem berjalan di dua antarmuka: Website dan WhatsApp (via Meta API). Sistem menggunakan AI LLM dengan metode RAG (*Retrieval-Augmented Generation*) untuk menjawab pertanyaan warga berdasarkan data aktual desa.

## 2. Arsitektur Sistem
Sistem menggunakan pendekatan **Dual-Service (Modular Monolith)** untuk memisahkan beban transaksional dan pemrosesan AI, guna menjaga performa dan efisiensi biaya.

*   **Core Service (Web & API):** Menangani *webhook* Meta WhatsApp, *chat* website, autentikasi admin, dan manajemen *knowledge base*.
*   **AI & RAG Service:** Didedikasikan khusus untuk menerima teks, mencari konteks (*vector search*), dan memanggil LLM untuk *generate* jawaban.

## 3. Tech Stack
*   **Backend Utama:** Laravel 11 (PHP)
*   **Frontend & Admin Portal:** React.js (via Inertia.js + TailwindCSS)
*   **AI Service:** FastAPI (Python)
*   **Database:** PostgreSQL (dengan ekstensi `pgvector` untuk penyimpanan *embedding* RAG)
*   **Infrastruktur:** Docker Compose (untuk orkestrasi lokal/production)

## 4. Alur Kerja (Workflow)
1. **User Input:** Warga mengirim pesan via WA atau Web Chat.
2. **Core Service (Laravel):** Menerima pesan, menyimpan ke PostgreSQL (`chat_messages`), lalu meneruskan *query* ke AI Service via HTTP Request.
3. **AI Service (FastAPI):** Menerima *query*, mengubahnya jadi *embedding*, mencari dokumen relevan di `pgvector`, dan merangkai *prompt* ke LLM (OpenAI/Gemini).
4. **Output:** FastAPI mengembalikan teks jawaban ke Laravel. Laravel menyimpan log jawaban ke *database*, lalu menembak Meta WhatsApp API untuk membalas pesan warga.

## 5. Struktur Direktori (Codebase)

```text
desa-ai-system/
├── 📁 core-service/        # (Backend Utama & Web Frontend - Laravel + React)
│   ├── 📁 app/
│   │   ├── 📁 Http/
│   │   │   ├── 📁 Controllers/
│   │   │   │   ├── 📁 Admin/
│   │   │   │   │   ├── AuthController.php
│   │   │   │   │   ├── DashboardController.php
│   │   │   │   │   └── KnowledgeController.php   # Upload CSV/PDF ke AI
│   │   │   │   ├── 📁 Api/
│   │   │   │   │   └── WhatsAppWebhookController.php # Webhook Meta
│   │   │   │   └── WebChatController.php
│   │   │   └── 📁 Middleware/
│   │   │       └── VerifyWhatsAppWebhook.php
│   │   ├── 📁 Models/
│   │   │   ├── Admin.php
│   │   │   ├── ChatSession.php
│   │   │   └── ChatMessage.php
│   │   └── 📁 Services/
│   │       ├── AiServiceClient.php               # Komunikasi HTTP ke FastAPI
│   │       └── WhatsAppApi.php                   # Komunikasi ke Meta API
│   ├── 📁 database/
│   │   └── 📁 migrations/
│   │       ├── 01_create_admins_table.php
│   │       ├── 02_create_chat_sessions_table.php
│   │       └── 03_create_chat_messages_table.php
│   ├── 📁 resources/
│   │   └── 📁 js/                                # (Frontend React)
│   │       ├── 📁 Components/
│   │       ├── 📁 Layouts/
│   │       │   ├── AdminLayout.jsx
│   │       │   └── PublicLayout.jsx
│   │       └── 📁 Pages/
│   │           ├── 📁 Admin/
│   │           │   ├── Login.jsx
│   │           │   └── KnowledgeBase.jsx
│   │           └── 📁 Public/
│   │               ├── Home.jsx
│   │               └── WebChatWidget.jsx
│   ├── 📁 routes/
│   │   ├── api.php
│   │   └── web.php
│   ├── vite.config.js
│   └── composer.json
│
├── 📁 ai-service/          # (Mesin RAG & LLM - FastAPI Python)
│   ├── 📁 app/
│   │   ├── 📁 api/
│   │   │   ├── 📁 endpoints/
│   │   │   │   ├── chat.py             # Endpoint menjawab chat
│   │   │   │   └── document.py         # Endpoint proses file CSV/PDF
│   │   │   └── router.py
│   │   ├── 📁 core/
│   │   │   ├── config.py
│   │   │   └── db.py
│   │   ├── 📁 models/
│   │   │   └── document_vector.py      # Skema tabel pgvector
│   │   └── 📁 services/
│   │       ├── embedding_service.py
│   │       ├── rag_engine.py
│   │       └── llm_service.py
│   ├── main.py
│   ├── requirements.txt
│   └── .env
│
├── docker-compose.yml   # Orkestrasi Laravel, FastAPI, & Postgres pgvector
└── .env.example