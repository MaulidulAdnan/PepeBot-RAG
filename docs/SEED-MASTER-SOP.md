# Seed Data Master SOP — Rekap Insert 20 Varian

Strategi sesuai `Persiapan Sebelum Laravel.md`: seed via kode memakai endpoint internal yang sama dengan Dashboard nanti (`POST /documents` → `upsert_document`), agar otak RAG terbukti mandiri sebelum Laravel disambung (decoupling + fail-fast).

> Nilai password dan API key tidak ditulis di dokumen ini.

## 1. File yang dimasukkan: `ai-service/seed_master_sop.py` (baru)

Skrip repo permanen (dapat dipakai ulang tim), bukan skrip TEMP. Isi:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, _with_host, _with_driver
from app.core.config import DATABASE_URL
from app.models import document_vector  # daftarkan tabel
from app.api.endpoints.document import DocumentUpsert, upsert_document

PLAVON = "https://plavon.sidoarjokab.go.id/"
# ... konstanta note + MASTER (lihat seksi 3)

def main():
    engine = create_engine(_with_host(_with_driver(DATABASE_URL)))
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        for i, (sop, varian, syarat, kanal, note) in enumerate(MASTER, 1):
            res = upsert_document(DocumentUpsert(...), db)
            print(f"[{i}/{len(MASTER)}] {res.sop_name} / {res.varian} -> v{res.version}")
    finally:
        db.close()
```

Maksud tiap bagian:
1. **Impor `_with_host` + `_with_driver`.** Skrip jalan native Windows, sehingga butuh kedua normalisasi Fase 1/5 (driver `psycopg2`, host `127.0.0.1`). Di dalam container Docker, `_with_host` tidak mengubah apa-apa.
2. **Data `MASTER`: list 20 tuple `(sop_name, varian, syarat[], channel_url, note)`.** Ditranskripsi dari `Surat Surat Persyaratan.md` (14 SOP) + contoh KK dari chat (4 Varian). Penanda `[cite: 8/9/10]` dari dokumen sumber dibersihkan karena bukan isi SOP. Surat keterangan desa (1–7) disengaja `channel_url` kosong — urusnya via RT/RW + balai desa, bukan Plavon.
3. **Panggil `upsert_document`, bukan SQL mentah.** Fungsi yang sama persis dengan endpoint HTTP, sehingga yang terbukti adalah jalur produksi (rakit konten kanon → embedding 768 → tulis + `version` dalam satu transaksi). Idempoten: diulang → naik versi, bukan duplikat.
4. **Jalankan:** dari folder `ai-service`, `py seed_master_sop.py`.

## 2. Di mana data dimasukkan

Tabel `document_vectors` di database `pepebot_db`, container `postgres-db` (`docker-compose.yml:5-16`). Satu baris = satu Varian (Q6), kolom sesuai skema Q7 (`sop_name, varian, content, embedding Vector(768), version, updated_at`).

Hasil run:
```console
[1/20] Surat Keterangan Domisili Usaha / Umum -> v1
[2/20] Surat Keterangan Domisili Tempat Tinggal / Umum -> v1
[3/20] Surat Keterangan Tidak Mampu (SKTM) / Umum -> v1
[4/20] Surat Keterangan Belum Menikah / Umum -> v1
[5/20] Surat Keterangan Beda Nama / Umum -> v1
[6/20] Surat Keterangan Penghasilan / Umum -> v1
[7/20] Surat Keterangan Kematian / Maksimal 3 Bulan -> v1
[8/20] Pembaharuan Desil di DTKS / Melalui Aplikasi -> v1
[9/20] KIS BPJS PBPU Pemerintah Daerah / Pemohon KTP Desa Pepe -> v1
[10/20] Pindah / Pindah Keluar -> v1
[11/20] Pindah / Pindah Masuk -> v1
[12/20] Akte Kelahiran / Anak Sudah Masuk KK -> v1
[13/20] KTP / Hilang -> v1
[14/20] KTP / Pembaruan -> v1
[15/20] Akte Kematian / Umum -> v1
[16/20] KIA / Baru -> v1
[17/20] KK / Perubahan Biodata -> v1
[18/20] KK / Pecah KK -> v1
[19/20] KK / Hilang -> v1
[20/20] KK / Pembaruan -> v1
seed-ok 20 varian
```
15 SOP, 20 Varian, semua `v1`. **Data ini data produksi — jangan dihapus** (berbeda dengan baris `__UJI__`/`__COBA__` yang selalu dibersihkan).

## 3. Uji diskriminasi pasca-seed (skor asli, threshold 0.65)

| Pertanyaan | Hasil | Status |
|---|---|---|
| `KTP saya hilang, syaratnya apa?` | KTP/Hilang `0.789` (vs KK/Hilang `0.751`) | benar |
| `mau perbarui KTP yang lama gimana` | KTP/Pembaruan `0.784` | benar |
| `syarat SKTM apa saja` | SKTM `0.724` vs Penghasilan `0.660` | benar |
| `syarat surat keterangan penghasilan` | Penghasilan `0.808` | benar |
| `cara cek bansos dan ubah desil DTKS` | DTKS `0.846` | benar |
| `bisa buatkan SIM?` | fallback `True` (`0.615 < 0.65`) | benar |
| Chat penuh KTP hilang | syarat benar + kalimat wewenang + sitasi v1 | benar |
| `mau pindah keluar dari desa pepe gimana caranya` | target peringkat 4 (`0.624` < threshold) | **temuan, lihat seksi 4** |

## 4. Temuan: redaksi santai + kata lokasi mengecoh retrieval

Peringkat penuh untuk query pindah santai (top 20):
```
1. KIS BPJS/Pemohon KTP Desa Pepe 0.6705
2. Domisili Usaha/Umum 0.6676
3. Domisili Tempat Tinggal/Umum 0.6566
4. Pindah/Pindah Keluar 0.6245  <-- target, di bawah threshold
```
Tiga teratas sama-sama memuat frasa `Desa Pepe` seperti query. Bandingkan frasa formal `syarat surat pindah keluar` → Pindah Keluar `0.741` peringkat 1. Artinya redaksi santai + kata lokasi menggeser target keluar top-3 sekaligus di bawah threshold, sehingga chat menjawab dari SOP yang salah (tetap SOP asli bersitasi — terlacak, bukan halusinasi bebas — tetapi salah SOP).

Usulan perbaikan (menunggu persetujuan karena menyentuh teks resmi): tambah baris alias kata kunci per Varian, lalu eval parafrasa dan kunci threshold final. Status: arsitektur terbukti (seed→retrieval→jawab mandiri tanpa Laravel tercapai); kualitas ranking punya satu kelemahan terdokumentasi di atas.

## 5. Istilah teknis
- **Seeder**: skrip pengisi data awal yang memakai jalur produksi (endpoint/fungsi yang sama).
- **Idempoten**: diulang aman (upsert naik versi, bukan duplikat).
- **Diskriminasi retrieval**: kemampuan menempatkan Varian yang benar di peringkat 1.

## 6. Kenapa seeder wajib jadi file repo (bukan skrip TEMP)

1. **Data master harus dapat dibangun ulang.** Container Postgres bisa dihapus, laptop sidang bisa beda, tim berisi 3 orang. Tanpa skrip ter-commit, 20 Varian hanya ada di satu database satu laptop — hilang berarti ketik ulang 20 kali via Swagger. Dengan `seed_master_sop.py`, satu perintah mengembalikan semuanya identik.
2. **Memakai jalur produksi.** Skrip memanggil `upsert_document` yang sama dengan endpoint dan Dashboard nanti, sehingga tiap seed ulang sekaligus menguji pipeline asli (rakit konten → embedding → versi). Alternatif dump SQL mentah melewatkan seluruh logika itu dan rapuh saat skema berubah.
3. **Kurasi terdokumentasi sebagai kode.** Keputusan pembersihan (`[cite]` dibuang, surat desa tanpa kanal, 4 Varian KK dari chat) tertulis eksplisit dan bisa direview di git, bukan pengetahuan lisan yang hilang.
4. **Idempoten dan aman.** Diulang → naik versi, bukan duplikat.

Pembeda yang dipakai: skrip uji sekali pakai (`uji_*`, `hitung_*`) benar tetap di TEMP; yang membangun ulang keadaan produksi (seeder, migrasi, contoh config) wajib di repo.
