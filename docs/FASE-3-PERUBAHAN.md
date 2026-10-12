# Fase 3 — Rekap Perubahan: Otak Pencari (RAG Engine & Fallback)

Cakupan Fase 3 (To-Do List 3.1–3.2): pencarian pgvector per-Varian dan Smart Fallback berbasis threshold (Q2, Q6). Prasyarat Fase 1–2 hijau (tabel per-Varian 768 terisi via API, endpoint ingest berversi bekerja).

> Nilai API key dan password tidak ditulis di dokumen ini.

## 1. `ai-service/app/services/rag_engine.py` — dibuat (0 → terisi)

Satu-satunya file Fase 3. Isi final:

```python
import os
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.document_vector import DocumentVector
from app.services.embedding_service import embed_query

SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.65"))
DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", "3"))


@dataclass
class RetrievedChunk:
    sop_name: str
    varian: str
    content: str
    version: int
    distance: float
    similarity: float


@dataclass
class SearchResult:
    query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    fallback: bool = True
    best_similarity: float | None = None


def search(query, db, top_k=DEFAULT_TOP_K, sop_name=None):
    if not query or not query.strip():
        return SearchResult(query=query)

    vector = embed_query(query.strip())

    distance_col = DocumentVector.embedding.cosine_distance(vector).label(
        "distance"
    )
    q = db.query(DocumentVector, distance_col)
    if sop_name:
        q = q.filter(DocumentVector.sop_name == sop_name)
    rows = q.order_by(distance_col).limit(top_k).all()

    chunks = [
        RetrievedChunk(
            sop_name=row.DocumentVector.sop_name,
            varian=row.DocumentVector.varian,
            content=row.DocumentVector.content,
            version=row.DocumentVector.version,
            distance=float(row.distance),
            similarity=1.0 - float(row.distance),
        )
        for row in rows
    ]
    if not chunks:
        return SearchResult(query=query)

    best = max(c.similarity for c in chunks)
    return SearchResult(
        query=query,
        chunks=chunks,
        fallback=best < SIMILARITY_THRESHOLD,
        best_similarity=best,
    )
```

## 2. Keputusan desain dan alasannya

1. **Cosine distance, diurutkan menaik, `LIMIT top_k`.** Standar untuk embedding yang dinormalisasi; pgvector menghitung di database (`<=>`), bukan di Python, sehingga tetap cepat saat baris bertambah. `top_k=3` default: cukup untuk konteks LLM tanpa membengkakkan prompt.
2. **`similarity = 1 − distance`.** pgvector mengembalikan jarak (kecil = mirip); dikonversi ke kemiripan agar threshold terbaca intuitif (besar = mirip) dan konsisten dengan dokumentasi Q2.
3. **Default `fallback=True`.** Semua jalur gagal (query kosong, tabel kosong, skor rendah) otomatis aman — AI dilarang menjawab kecuali ada bukti kemiripan kuat. Ini implementasi langsung Q2 anti-halusinasi.
4. **`version` ikut dalam hasil.** Syarat kontrak Q8 (`citations: [{sop_name, varian, version}]`); jawaban selalu bisa dilacak ke edisi SOP.
5. **Filter `sop_name` opsional.** Bila Laravel sudah tahu layanan dari konteks (misal alur form KK), pencarian dipersempit ke SOP itu untuk presisi lebih tinggi. Default tanpa filter = cari semua SOP.
6. **Threshold dan top_k via environment.** Tuning operasional (bedakan demo vs produksi) tanpa ubah kode dan tanpa rebuild image.
7. **Query kosong ditolak sebelum embedding.** Menghemat panggilan API berbayar/gratis dan mempersempit permukaan error.

## 3. Koreksi threshold berdasar pengukuran

Default awal `0.40` terbukti longgar lewat uji live dengan 2 Varian seed (KK/Hilang, KK/Pecah KK):

| Pertanyaan | Skor terbaik | Varian teratas | Keputusan pada 0.40 |
|---|---|---|---|
| `syarat KK hilang apa saja` | 0.719 | Hilang (vs Pecah 0.676) | dijawab, benar |
| `bisa buatkan SIM?` (luar SOP) | 0.598 | — | dijawab, **salah (ngarang)** |

Karena itu default digeser ke `0.65`: relevan (`0.719`) lolos, luar SOP (`0.598`) jatuh ke fallback, varian dekat (`0.676`) tetap lolos sebagai konteks KK yang sah (LLM Fase 4 memilih Varian tepat dari isi). Dipilih presisi di atas recall sesuai prioritas domain: lebih baik dialihkan ke manusia daripada mengarang syarat dokumen.

**Batasan jujur:** sampel baru 2 baris; skor absolut bisa bergeser setelah seed 4 Varian penuh dan pertanyaan slang (`kk ilang syaratnya apa bang`). Tuning final dengan eval set parafrasa wajib sebelum sidang — tanpa ubah kode, cukup `RAG_SIMILARITY_THRESHOLD`.

## 4. Verifikasi saat membangun (live, API + DB asli)

Skrip TEMP `uji_rag_fase3.py`: seed 2 Varian via `upsert_document`, jalankan 4 skenario, hapus seed di `finally`:

```console
threshold 0.65
kosong-fallback True 0
tabel-kosong-fallback True 0
isi-fallback False best 0.719
- Hilang v1 0.719
- Pecah KK v1 0.6757
luar-sop-fallback True best 0.5984
```

Dilanjutkan cek kebersihan: `jumlah-baris 0` — tidak ada polusi data.

## 5. Pembuktian mandiri Fase 3 — lima bukti berurutan

Bukti 1–2 tanpa DB; bukti 3–5 butuh `postgres-db` nyala + internet (skrip memakai API dan DB asli lalu membersihkan diri).

### Bukti 1 — file ada dan terisi (klaim 3.1 dikerjakan)
```console
py -c "import os; print(os.path.getsize(r'D:\Semester 5\Project Akhir\pepebot-rag\ai-service\app\services\rag_engine.py'))"
```
Harus angka ribuan, bukan `0`. Membuktikan implementasi ada di file yang direncanakan, bukan di tempat lain.

### Bukti 2 — impor + konstanta benar tanpa jaringan (klaim modul valid)
Dari folder `ai-service`:
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py -c "from app.services.rag_engine import search, SIMILARITY_THRESHOLD, DEFAULT_TOP_K; print(SIMILARITY_THRESHOLD, DEFAULT_TOP_K)"
0.65 3
```
Kenapa membuktikan: impor menyentuh rantai `config → model → embedding`. Lulus berarti tidak ada import error dan default yang aktif adalah hasil tuning (`0.65`, bukan `0.40` awal).

### Bukti 3 — uji penuh satu perintah (klaim retrieval + fallback bekerja)
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\uji_rag_fase3.py"
threshold 0.65
kosong-fallback True 0
tabel-kosong-fallback True 0
isi-fallback False best 0.719
- Hilang v1 0.719
- Pecah KK v1 0.6757
luar-sop-fallback True best 0.5984
```
Alasan tiap baris: `kosong-fallback True` = query kosong ditolak sebelum embedding (hemat API); `tabel-kosong-fallback True` = tanpa data tidak boleh dijawab; `isi-fallback False` + peringkat Hilang di atas Pecah = retrieval membedakan Varian Q6 dengan benar; `luar-sop-fallback True` = skor 0.598 < 0.65 dialihkan ke manusia sesuai Q2. Skrip menghapus seed di `finally`, aman diulang.

### Bukti 4 — tabel kembali kosong (klaim kebersihan uji)
```console
$env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\hitung_document.py"
jumlah-baris 0
```
Kenapa membuktikan: tabel produksi tetap kosong menunggu seed kurasi final; tidak ada sisa uji yang mengotori retrieval. Jika keluar `>0`, ada sisa yang harus dilaporkan.

### Bukti 5 — threshold dapat diubah tanpa koding (opsional, klaim konfigurabilitas)
```console
$env:RAG_SIMILARITY_THRESHOLD='0.50'; $env:PYTHONPATH='D:\Semester 5\Project Akhir\pepebot-rag\ai-service'; py "C:\Users\LENOVO LOQ\AppData\Local\Temp\opencode\uji_rag_fase3.py"; Remove-Item Env:RAG_SIMILARITY_THRESHOLD
```
Baris terakhir harus berubah menjadi `luar-sop-fallback False` (0.598 > 0.50, lolos). Ini membuktikan threshold dibaca dari environment — tuning sidang cukup ubah env, tanpa sentuh kode. Perintah `Remove-Item` mengembalikan default; nilai produksi tetap `0.65` sampai eval parafrasa selesai.

### Batas scope yang benar (bukan kegagalan)
`rag_engine` hanya mengembalikan `chunks + fallback`, belum merangkai kalimat jawaban dan belum punya endpoint HTTP — itu jatah Fase 4 (`llm_service.py`) dan Fase 5 (`chat.py` + wiring). Fase 3 selesai saat bukti 1–4 hijau (5 sebagai bonus).

## 6. Istilah teknis
- **Cosine distance/similarity**: jarak/kemiripan sudut antar vektor; kecil/jarak = mirip, besar/skor = mirip setelah konversi `1 − distance`.
- **Top-k**: jumlah kandidat teratas yang diambil (`LIMIT k`).
- **Threshold gating**: palang batas skor; di bawahnya hasil dianggap tidak relevan.
- **Fail-closed**: default menolak/menyerah ke manusia bila ragu (`fallback=True`).
- **Eval set parafrasa**: kumpulan pertanyaan dengan redaksi berbeda untuk menguji ketahanan threshold.
