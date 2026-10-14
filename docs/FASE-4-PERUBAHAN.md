# Fase 4 — Rekap Perubahan: Logika Jawaban Mutlak (LLM & Prompt)

Cakupan Fase 4 (To-Do List 4.1–4.2): system prompt ketat batas wewenang (Q1, Q5) dan injeksi konteks hasil retrieval ke LLM Gemini Flash (Q2, Q8). Prasyarat Fase 1–3 hijau (skema per-Varian, ingest berversi, retrieval + threshold 0.65).

> Nilai API key dan password tidak ditulis di dokumen ini.

## 1. `ai-service/app/services/llm_service.py` — dibuat (0 → terisi)

Satu-satunya file Fase 4. Isi final:

```python
import os

from google import genai

from app.core.config import GEMINI_API_KEY
from app.services.rag_engine import RetrievedChunk

LLM_MODEL = os.getenv("PEPEBOT_LLM_MODEL", "models/gemini-3.5-flash-lite")

FALLBACK_WA = os.getenv("DESA_PETUGAS_WA", "")
FALLBACK_URL = os.getenv("DESA_PETUGAS_URL", "")

REFUSAL_MARKER = "TIDAK_ADA_DI_SOP"

SYSTEM_PROMPT = """\
Kamu adalah PepeBot, asisten administrasi Desa Pepe (Sidoarjo).
Jawab SELALU dalam Bahasa Indonesia yang sopan dan ringkas.

Aturan mutlak:
1. Jawab HANYA dari bagian KONTEKS SOP di bawah. Dilarang menambah syarat,
   biaya, alamat, tautan, atau nomor kontak yang tidak tertulis di konteks.
2. Desa Pepe adalah PIHAK KE-3: hanya menerbitkan Surat Pengantar dan membantu
   mengajukan. Dokumen akhir (KTP, KK, dsb.) diterbitkan Kecamatan/Dispendukcapil
   atau via kanal mandiri seperti Plavon. Setiap jawaban soal pengurusan WAJIB
   meluruskan batas wewenang ini dengan satu kalimat.
3. Gunakan istilah kanon: SOP = aturan satu layanan, Varian = sub-skenario
   dalam SOP, Syarat = satu butir checklist, Surat Pengantar = output desa,
   Dokumen Akhir = output institusi pusat.
4. Jika konteks tidak memuat jawaban, balas persis dengan: TIDAK_ADA_DI_SOP
   (tanpa teks lain).
"""


def get_fallback_contact():
    return {"whatsapp": FALLBACK_WA, "url": FALLBACK_URL}


def build_fallback_answer():
    parts = ["Maaf, informasi tersebut tidak ada di pedoman dokumen Desa Pepe."]
    contact = get_fallback_contact()
    tambahan = []
    if contact["whatsapp"]:
        tambahan.append(f"WhatsApp petugas: {contact['whatsapp']}")
    if contact["url"]:
        tambahan.append(f"Info lanjut: {contact['url']}")
    if tambahan:
        parts.append("Silakan hubungi " + " / ".join(tambahan) + ".")
    else:
        parts.append("Silakan hubungi petugas Desa Pepe untuk bantuan langsung.")
    return " ".join(parts)


def build_prompt(query, chunks):
    ctx = []
    for c in chunks:
        ctx.append(
            f"[SOP: {c.sop_name} | Varian: {c.varian} | versi {c.version}]\n"
            f"{c.content}"
        )
    return (
        f"{SYSTEM_PROMPT}\nKONTEKS SOP:\n"
        + "\n\n---\n\n".join(ctx)
        + f"\n\nPERTANYAAN WARGA:\n{query}\n\nJAWABAN:"
    )


def _get_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY belum diisi di environment.")
    return genai.Client(api_key=GEMINI_API_KEY)


def generate_answer(query, chunks):
    citations = [
        {"sop_name": c.sop_name, "varian": c.varian, "version": c.version}
        for c in chunks
    ]
    if not chunks:
        return {"answer": build_fallback_answer(),
                "citations": citations, "refused": True}
    client = _get_client()
    resp = client.models.generate_content(
        model=LLM_MODEL, contents=build_prompt(query, chunks)
    )
    text = (resp.text or "").strip()
    if REFUSAL_MARKER in text:
        return {"answer": build_fallback_answer(),
                "citations": citations, "refused": True}
    return {"answer": text, "citations": citations, "refused": False}
```

## 2. Maksud tiap bagian dan alasannya

1. **`SYSTEM_PROMPT` empat aturan (4.1).** Aturan 1 mengunci Q2 (grounding SOP, larangan menambah fakta). Aturan 2 mengunci Q1 (pihak ke-3, wajib satu kalimat pelurusan tiap jawaban pengurusan). Aturan 3 mengunci Q5 (istilah kanon agar jawaban konsisten dengan Dashboard dan GLOSSARY). Aturan 4 adalah katup pengaman kedua setelah threshold Fase 3: bila konteks tidak memuat jawaban, LLM wajib keluar marker, bukan mengarang.
2. **`build_prompt()`.** Setiap chunk diberi label `[SOP | Varian | versi N]` sehingga jawaban dan sitasi terlacak ke edisi SOP (syarat kontrak Q8 `citations`). Tanpa label, LLM bisa mencampur dua Varian dalam satu kalimat.
3. **`generate_answer()` tiga jalur.** (a) `chunks` kosong → fallback deterministik tanpa panggil LLM: nol biaya API, nol risiko halusinasi. (b) Marker terdeteksi → diterjemahkan ke pesan fallback yang sama. (c) Normal → teks LLM + sitasi + `refused False`. Pembedaan `refused` memungkinkan endpoint Fase 5 dan Laravel memutuskan penyaluran (jawab vs alihkan ke manusia).
4. **`build_fallback_answer()` + `get_fallback_contact()`.** Pesan penolakan tunggal dan deterministik (selalu sama huruf per huruf — penting untuk testing). Kontak dibaca dari env `DESA_PETUGAS_WA` / `DESA_PETUGAS_URL`; kini keduanya kosong sehingga pesan generik. Wajib diisi nomor/link asli sebelum produksi agar fallback Q2 benar-benar mengantar warga ke manusia.
5. **`LLM_MODEL` via env (`PEPEBOT_LLM_MODEL`).** Ganti model tanpa ubah kode, sama polanya dengan threshold Fase 3.

## 3. Pemilihan model (fakta respons API, bukan tebakan)

Rantai yang diukur langsung:
1. `models/gemini-2.5-flash` → `404 NOT_FOUND`: pensiun untuk user baru.
2. `models/gemini-3.8-flash` (saran pesan error di atas) → menggantung >120 detik tanpa respons pada dua percobaan (prompt satu kata maupun penuh).
3. `models/gemini-2.5-flash-lite` → `404 NOT_FOUND` pensiun juga.
4. `models/gemini-3.5-flash-lite` → jawab dalam hitungan detik.

Daftar `generateContent` dari `ListModels` memang memuat ketiganya sebagai tersedia, tetapi hanya `3.5-flash-lite` yang merespons akun ini. Dikunci sebagai default; jika di masa depan 2.5/3.8 dibuka untuk akun ini, cukup set env tanpa koding ulang.

## 4. Verifikasi saat membangun (live, API + DB asli)

Skrip TEMP `uji_llm_fase4.py`: seed 2 Varian KK → retrieval → `generate_answer` untuk relevan dan luar SOP → hapus seed di `finally`:

```console
relevan-refused False | sitasi [{'sop_name': 'KK', 'varian': 'Hilang', 'version': 2}, {'sop_name': 'KK', 'varian': 'Pecah KK', 'version': 2}]
relevan-jawaban: Halo Warga Desa Pepe, berikut adalah syarat untuk pengurusan KK dengan Varian Hilang: | - Foto Surat Keterangan Kehilangan Polisi | - Foto KTP Pemohon | - Email |  | Sebagai catatan, Desa Pepe hanya menerbitkan Surat Pengantar dan membantu mengajukan, sedangkan dokumen akhir diterbitkan oleh instansi berwenang.
luar-refused True
luar-jawaban: Maaf, informasi tersebut tidak ada di pedoman dokumen Desa Pepe. Silakan hubungi petugas Desa Pepe untuk bantuan langsung.
uji-llm-ok
```

Catatan jujur: sitasi tertulis `version 2` karena run sebelumnya (yang menggantung di model 3.8) sempat commit seed sebelum hang; run ini menaikkan ke v2 lalu membersihkan. Tabel akhir `jumlah-baris 0`. Jawaban relevan memuat tiga syarat Hilang yang benar plus kalimat wewenang — redaksi boleh bervariasi antar run, dua unsur itu yang diassert.

## 5. Pembuktian mandiri Fase 4 — lima bukti berurutan

Catatan: jawaban relevan dirangkai LLM sehingga redaksinya bisa beda tiap run. Yang diuji adalah sifatnya (tidak ditolak, sebut syarat benar, selipkan wewenang), bukan kesamaan huruf. Pesan fallback deterministik, selalu sama.

### Bukti 1 — file ada dan terisi (klaim 4.1–4.2 dikerjakan)
```console
py -c "import os; print(os.path.getsize(r'D:\Semester 5\Project Akhir\pepebot-rag\ai-service\app\services\llm_service.py'))"
```
Harus angka ribuan, bukan `0`. Membuktikan implementasi ada di file yang direncanakan.

### Bukti 2 — konstanta dan impor benar tanpa jaringan (klaim modul valid)
Dari folder `ai-service`:
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py -c "from app.services.llm_service import LLM_MODEL, REFUSAL_MARKER, SYSTEM_PROMPT; print(LLM_MODEL, '|', REFUSAL_MARKER, '|', 'PIHAK KE-3' in SYSTEM_PROMPT)"
models/gemini-3.5-flash-lite | TIDAK_ADA_DI_SOP | True
```
Kenapa membuktikan: model default adalah hasil koreksi API (bukan 2.5 yang pensiun), marker penolakan ada, dan prompt memuat aturan wewenang Q1. Gagal di sini = salah kode, bukan salah jaringan/kunci.

### Bukti 3 — model LLM hidup, satu panggilan murah (klaim kunci + nama model benar)
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\tes_llm_model.py" "models/gemini-3.5-flash-lite"
llm-ok models/gemini-3.5-flash-lite : Tes.
```
Harus kembali dalam hitungan detik. Membuktikan kunci valid, kuota jalan, dan nama model tepat. Jangan pakai `tes_llm_min.py` — isinya model lama yang menggantung.

### Bukti 4 — pipa penuh: seed → jawab relevan → tolak luar SOP → bersih (klaim end-to-end Fase 2–4)
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\uji_llm_fase4.py"
```
Harus diakhiri `uji-llm-ok`, dengan `relevan-refused False` + sitasi 2 Varian (jawaban dari retrieval, bukan karangan), jawaban memuat syarat Hilang dan satu kalimat wewenang, serta `luar-refused True` + pesan `Maaf...` deterministik tanpa panggil LLM. Membuktikan pertahanan dua lapis: threshold Fase 3 menyaring, prompt Fase 4 mengunci.

### Bukti 5 — tabel kembali kosong (klaim kebersihan uji)
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\hitung_document.py"
jumlah-baris 0
```
Kenapa membuktikan: skrip uji menghapus seed di `finally`; tabel produksi tetap kosong menunggu seed kurasi final.

### Batas scope yang benar (bukan kegagalan)
`app/api/endpoints/chat.py` masih `0 byte` dan endpoint HTTP belum dipasang — itu jatah Fase 5. Fase 4 selesai saat bukti 1–4 hijau + 5 nol. Satu utang terbuka: `DESA_PETUGAS_WA`/`DESA_PETUGAS_URL` masih kosong — isi sebelum produksi agar fallback mengantar ke manusia sungguhan.

## 6. Istilah teknis
- **System prompt**: instruksi permanen yang menyertai setiap panggilan LLM.
- **Grounding**: mengikat jawaban hanya pada konteks yang diberikan.
- **Refusal deterministik**: penolakan dengan teks tetap (dapat diassert), tanpa panggil model.
- **Marker penolakan**: token khusus (`TIDAK_ADA_DI_SOP`) sebagai sinyal terstruktur dari model ke kode.
- **Sitasi**: rujukan sumber jawaban (`sop_name, varian, version`).
