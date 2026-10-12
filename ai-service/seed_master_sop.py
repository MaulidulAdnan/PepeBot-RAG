"""Seeder data master SOP Desa Pepe (strategi: seed via kode sebelum Dashboard).

Memakai fungsi internal yang sama persis dengan endpoint POST /documents
(upsert per sop_name+varian + re-embedding sinkron + versioning).
Jalankan dari folder ai-service:  py seed_master_sop.py
Idempoten: aman diulang (upsert menaikkan version, bukan duplikat).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, _with_host, _with_driver
from app.core.config import DATABASE_URL
from app.models import document_vector  # noqa: F401 (daftarkan tabel)
from app.api.endpoints.document import DocumentUpsert, upsert_document

PLAVON = "https://plavon.sidoarjokab.go.id/"
FOTO_ASLI = "Fotokan dokumen aslinya, bukan fotokopi saat upload."
MANDIRI_PLAVON = "Bisa pengajuan mandiri via web Plavon."

# (sop_name, varian, syarat[], channel_url, note)
# Penanda [cite: N] dari dokumen sumber sudah dibersihkan.
MASTER = [
    ("Surat Keterangan Domisili Usaha", "Umum", [
        "Surat Pengantar RT RW (menerangkan jenis usaha dan alamat usaha; usaha wajib beralamat di Desa Pepe)",
        "Fotokopi KK & KTP pemilik usaha",
    ], "", "Jika berbentuk PT/CV/sejenisnya, wajib melampirkan akte pendirian dari notaris dan pemohon wajib berstatus Pimpinan/Direktur dari usaha tersebut."),
    ("Surat Keterangan Domisili Tempat Tinggal", "Umum", [
        "Surat Pengantar RT RW (menerangkan bahwa pemohon benar tinggal di alamat tersebut di Desa Pepe)",
        "Fotokopi KK & KTP",
    ], "", ""),
    ("Surat Keterangan Tidak Mampu (SKTM)", "Umum", [
        "Surat Pengantar RT RW (menerangkan bahwa pemohon benar merupakan warga Tidak Mampu)",
        "Fotokopi KK & KTP",
    ], "", ""),
    ("Surat Keterangan Belum Menikah", "Umum", [
        "Surat Pengantar RT RW (menerangkan bahwa pemohon benar Belum Menikah atau Belum Menikah Lagi)",
        "Fotokopi KK & KTP",
    ], "", "Materai 10.000 (Opsional) jika tujuan surat untuk pengajuan KUR / KPR / Menikah / dll."),
    ("Surat Keterangan Beda Nama", "Umum", [
        "Surat Pengantar RT RW",
        "Membawa dokumen asli yang memiliki perbedaan nama (contoh: Akte Kelahiran dan KK)",
        "Fotokopi KK & KTP",
        "Materai 10.000 (Wajib)",
    ], "", ""),
    ("Surat Keterangan Penghasilan", "Umum", [
        "Surat Pengantar RT RW",
        "Fotokopi KK & KTP",
        "Materai 10.000 (Wajib)",
    ], "", ""),
    ("Surat Keterangan Kematian", "Maksimal 3 Bulan", [
        "Surat Pengantar RT RW (menerangkan tanggal dan jam meninggal di rumah)",
        "Fotokopi KK & KTP Alm/Almh",
        "Fotokopi KK & KTP Pelapor (Wajib Ahli Waris atau Ketua RT/RW)",
    ], "", "Jika Alm/Almh sudah meninggal cukup lama, wajib melampirkan Materai 10.000."),
    ("Pembaharuan Desil di DTKS", "Melalui Aplikasi", [
        'Download Aplikasi "Cek Bansos" di App Store / Play Store',
        'Pilih "Masuk" lalu pilih "Daftar Baru"',
        "Jika sudah mendaftar, pilih masuk dan input data sesuai pendaftaran",
        'Pilih menu "Tambah Usulan"',
        "Isi formulir yang diperlukan dan unggah foto rumah",
    ], "", ""),
    ("KIS BPJS PBPU Pemerintah Daerah", "Pemohon KTP Desa Pepe", [
        "Surat Pernyataan Bermaterai Tidak Mampu yang diketahui oleh RT dan RW (Format surat bisa diambil di Kantor Desa atau menghubungi Pelayanan)",
        "KTP / Akte Kelahiran (jika masih di bawah umur)",
        "Fotokopi KK",
        "Surat Keterangan Rawat Inap / Rawat Jalan dari Rumah Sakit atau Puskesmas",
    ], "", "Pemohon wajib ber-KTP Desa Pepe."),
    ("Pindah", "Pindah Keluar", [
        "Foto KTP Pemohon",
        "Foto KK",
        "Bukti data kepindahan (Buku nikah jika menikah)",
        "KK tujuan (jika ingin masuk ke kk tujuan)",
        "Khusus pindah 1 kabupaten: Bukti kepemilikan rumah (PBB/Akte Jual Beli/Sertifikat) atau Surat pernyataan tidak keberatan alamat rumah dipakai sebagai tujuan alamat (unduh di Plavon) jika pindah bukan karena menikah",
        "Email",
    ], PLAVON, MANDIRI_PLAVON + " " + FOTO_ASLI),
    ("Pindah", "Pindah Masuk", [
        "Foto KTP Pemohon",
        "Foto SKPWNI",
        "Foto PBB (jika pbb sudah atas nama pemohon)",
        "Foto Akte Jual Beli (jika pbb belum atas nama pemohon)",
        "Buku Nikah Halaman Kedua (jika pindah karena alasan menikah)",
        "Email",
    ], PLAVON, MANDIRI_PLAVON + " " + FOTO_ASLI),
    ("Akte Kelahiran", "Anak Sudah Masuk KK", [
        "Foto Surat Kelahiran",
        "Foto KTP Ayah & Ibu",
        "Foto KK",
        "Foto Buku Nikah (Halaman kedua)",
        "Foto KTP Saksi (saudara/tetangga dengan alamat KTP Sidoarjo)",
        "Email",
    ], PLAVON, "Jika anak belum masuk ke dalam KK, silakan datang ke balai desa untuk mengisi form F1.01. " + MANDIRI_PLAVON + " " + FOTO_ASLI),
    ("KTP", "Hilang", [
        "Foto Surat Kehilangan Polisi",
        "Foto KK",
    ], PLAVON, MANDIRI_PLAVON + " " + FOTO_ASLI),
    ("KTP", "Pembaruan", [
        "Foto KTP Lama",
        "Foto KK",
    ], PLAVON, MANDIRI_PLAVON + " " + FOTO_ASLI),
    ("Akte Kematian", "Umum", [
        "Foto Surat Kematian RS/Puskesmas/Desa",
        "Foto KTP Almarhum",
        "Foto KK Almarhum",
        "Foto KTP Pemohon (Ahli waris, suami/istri/anak dari almarhum)",
        "Foto KTP Saksi 1 (saudara/tetangga dengan alamat KTP Sidoarjo)",
        "Foto KTP Saksi 2 (saudara/tetangga dengan alamat KTP Sidoarjo)",
        "Nama Ketua RT & RW",
        "Email",
    ], PLAVON, MANDIRI_PLAVON + " " + FOTO_ASLI),
    ("KIA", "Baru", [
        "Foto Akte Kelahiran",
        "Foto KTP Ayah dan Ibu",
        "Foto KK",
        "Foto Formal Anak (jika usia di atas 5 tahun)",
    ], PLAVON, MANDIRI_PLAVON + " " + FOTO_ASLI),
    ("KK", "Perubahan Biodata", [
        "Foto KTP Pemohon",
        "Foto KK",
        "Foto bukti kependudukan untuk perubahan data di KK (Akte kelahiran/Ijazah/Buku Nikah, dll)",
        "Email",
    ], PLAVON, MANDIRI_PLAVON + " " + FOTO_ASLI),
    ("KK", "Pecah KK", [
        "Foto KTP Pemohon",
        "Foto KK",
        "Nama orang yang dipisahkan dari KK",
        "Email",
    ], PLAVON, MANDIRI_PLAVON + " " + FOTO_ASLI),
    ("KK", "Hilang", [
        "Foto Surat Keterangan Kehilangan Polisi",
        "Foto KTP Pemohon",
        "Email",
    ], PLAVON, MANDIRI_PLAVON + " " + FOTO_ASLI),
    ("KK", "Pembaruan", [
        "Foto KTP",
        "Foto KK",
        "Email",
    ], PLAVON, MANDIRI_PLAVON + " " + FOTO_ASLI),
]


def main() -> None:
    engine = create_engine(_with_host(_with_driver(DATABASE_URL)))
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        for i, (sop, varian, syarat, kanal, note) in enumerate(MASTER, 1):
            res = upsert_document(DocumentUpsert(
                sop_name=sop, varian=varian, syarat=syarat,
                channel_url=kanal, note=note), db)
            print(f"[{i}/{len(MASTER)}] {res.sop_name} / {res.varian} -> v{res.version}")
        print(f"seed-ok {len(MASTER)} varian")
    finally:
        db.close()


if __name__ == "__main__":
    main()
