"""Juru bicara Kos Pepe (Fase 4 / Q1, Q2, Q5).

Merangkai jawaban dari hasil retrieval Fase 3 dengan prompt ketat:
hanya dari konteks SOP, selipkan batas wewenang pihak ke-3,
tolak dengan pesan fallback bila konteks tidak cukup (tanpa panggil LLM).
"""

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


def get_fallback_contact() -> dict:
    """Kontak petugas untuk pesan fallback (Q2)."""
    return {"whatsapp": FALLBACK_WA, "url": FALLBACK_URL}


def build_fallback_answer() -> str:
    """Pesan penolakan deterministik — tanpa panggil LLM, tanpa risiko ngarang."""
    parts = [
        "Maaf, informasi tersebut tidak ada di pedoman dokumen Desa Pepe."
    ]
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


def build_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    """Susun prompt: system + blok konteks per chunk + pertanyaan."""
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


def generate_answer(
    query: str, chunks: list[RetrievedChunk]
) -> dict:
    """Rangkai jawaban. Return {answer, citations, refused}.

    chunks kosong -> langsung fallback tanpa panggil LLM.
    LLM menjawab marker -> diterjemahkan ke pesan fallback.
    """
    citations = [
        {"sop_name": c.sop_name, "varian": c.varian, "version": c.version}
        for c in chunks
    ]
    if not chunks:
        return {
            "answer": build_fallback_answer(),
            "citations": citations,
            "refused": True,
        }
    client = _get_client()
    resp = client.models.generate_content(
        model=LLM_MODEL, contents=build_prompt(query, chunks)
    )
    text = (resp.text or "").strip()
    if REFUSAL_MARKER in text:
        return {
            "answer": build_fallback_answer(),
            "citations": citations,
            "refused": True,
        }
    return {"answer": text, "citations": citations, "refused": False}
