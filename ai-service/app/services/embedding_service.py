"""Tukang sidik jari Kos Pepe (Fase 2 / Q11).

Mengubah 1 koper Varian (judul + syarat + kanal + note) menjadi vektor
768 dimensi via Gemini, dan sebaliknya untuk pertanyaan warga.
"""

from google import genai

from app.core.config import GEMINI_API_KEY

EMBED_MODEL = "models/gemini-embedding-001"
EMBED_DIMENSION = 768
EMBED_CONFIG = {"output_dimensionality": EMBED_DIMENSION}

_client = None


def _get_client():
    """Buat client Gemini sekali, pakai ulang berikutnya."""
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY belum diisi di environment.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def build_varian_content(
    sop_name: str,
    varian: str,
    syarat: list[str],
    channel_url: str = "",
    note: str = "",
) -> str:
    """Rakit 1 koper Varian dengan format kanon (Q5-Q6).

    Format ini yang di-embed dan disimpan ke kolom content,
    sehingga retrieval selalu membaca paket utuh per-Varian.
    """
    lines = [f"SOP: {sop_name.strip()}", f"Varian: {varian.strip()}", "", "Syarat:"]
    lines += [f"- {s.strip()}" for s in syarat if s and s.strip()]
    if channel_url and channel_url.strip():
        lines += ["", f"Kanal: {channel_url.strip()}"]
    if note and note.strip():
        lines += [f"Catatan: {note.strip()}"]
    return "\n".join(lines).strip()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Ubah daftar teks menjadi daftar vektor 768 dimensi."""
    if not texts:
        return []
    client = _get_client()
    vectors: list[list[float]] = []
    for text in texts:
        resp = client.models.embed_content(
            model=EMBED_MODEL, contents=text, config=EMBED_CONFIG
        )
        values = list(resp.embeddings[0].values)
        if len(values) != EMBED_DIMENSION:
            raise ValueError(
                f"Dimensi embedding {len(values)} != {EMBED_DIMENSION}. "
                f"Cek model {EMBED_MODEL}."
            )
        vectors.append(values)
    return vectors


def embed_query(text: str) -> list[float]:
    """Ubah 1 pertanyaan warga menjadi 1 vektor."""
    return embed_texts([text])[0]
