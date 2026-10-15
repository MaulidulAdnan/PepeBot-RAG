from google import genai
from app.core.config import settings
from app.services.rag_engine import RetrievedChunk

LLM_MODEL = settings.LLM_MODEL

# Kontak darurat jika data tidak ditemukan (nanti bisa dipindah ke setting Laravel jika mau)
FALLBACK_WA = "081234567890" # Ganti dengan nomor petugas desa
FALLBACK_URL = "https://pepe.desa.id"

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

def get_fallback_contact() -> dict[str, str]:
    return {"whatsapp": FALLBACK_WA, "url": FALLBACK_URL}

def build_fallback_answer() -> str:
    parts = ["Maaf, informasi tersebut tidak ada di pedoman dokumen Desa Pepe."]
    contact = get_fallback_contact()
    tambahan = []
    
    if contact.get("whatsapp"):
        tambahan.append(f"WhatsApp petugas: {contact['whatsapp']}")
    if contact.get("url"):
        tambahan.append(f"Info lanjut: {contact['url']}")
    
    if tambahan:
        parts.append("Silakan hubungi " + " / ".join(tambahan) + ".")
    else:
        parts.append("Silakan hubungi petugas Desa Pepe untuk bantuan langsung.")
    
    return " ".join(parts)

def build_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
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

def _get_client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY belum diisi di environment.")
    return genai.Client(api_key=settings.GEMINI_API_KEY)

def generate_answer(query: str, chunks: list[RetrievedChunk]) -> dict:
    citations = [
        {"sop_name": c.sop_name, "varian": c.varian, "version": c.version}
        for c in chunks
    ]
    
    # Jika chunk kosong (karena kena blokir Smart Fallback di Langkah 2)
    if not chunks:
        return {"answer": build_fallback_answer(), "citations": citations, "refused": True}
    
    client = _get_client()
    resp = client.models.generate_content(
        model=LLM_MODEL, contents=build_prompt(query, chunks)
    )
    
    text = (resp.text or "").strip()
    
    # Jika AI menyerah karena tidak tahu (Aturan 4 di System Prompt)
    if REFUSAL_MARKER in text:
        return {"answer": build_fallback_answer(), "citations": citations, "refused": True}
    
    return {"answer": text, "citations": citations, "refused": False}