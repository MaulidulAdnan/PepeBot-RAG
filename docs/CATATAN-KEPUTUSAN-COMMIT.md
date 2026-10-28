# Catatan Keputusan Commit — Perbaikan ai-service, Fase 6.1–6.2, dan Artefak Boost

Dokumen ini menjawab tiga hal: **apa itu commit dan apa fungsinya**, **mengapa harus dilakukan (dan apa yang hilang bila tidak)**, dan **daftar keputusan yang harus kamu ambil sebelum eksekusi — lengkap dengan konsekuensi masing-masing pilihan, termasuk konsekuensi menunda keputusan**.

Fakta repo di bawah merupakan hasil pemeriksaan langsung di mesin (tanggal pembuatan dokumen), bukan asumsi.

## 1. Kondisi repo saat ini

```
branch aktif      : main
commit terakhir   : bee4a85  "Merge pull request #2 from adamnirvan/fix/ai-service"
git ls-files "*.env" → kosong (dua file .env TIDAK terlacak — rahasia aman)
penahan .env      : ai-service/.gitignore (baris .env), core-service/.gitignore (baris .env)
```

Kerja yang **sudah selesai tapi belum tercatat git** — semuanya hidup hanya di disk laptop ini:

| Blok kerja | File yang terpengaruh | Status git |
|---|---|---|
| Perbaikan ai-service pasca-PR #2 | `ai-service/app/core/config.py`, `app/core/security.py` (baru), `app/api/router.py`, `app/services/llm_service.py`, `seed_master_sop.py`, `.env.example` (baru) | diubah / baru |
| Dokumentasi ai-service | `docs/ADDENDUM-KONTRAK-API.md`, `docs/PERBAIKAN-AI-SERVICE-PASCA-PR2.md` | baru |
| Fase 6.1 | `core-service/config/services.php` (`.env` juga disentuh tapi tidak akan pernah masuk commit — ignored) | diubah |
| Instalasi Boost | `core-service/composer.json`, `composer.lock`, `CLAUDE.md`, `boost.json` (baru), `.mcp.json` (baru), `.claude/**` (baru) | diubah / baru |
| Fase 6.2 | `core-service/routes/api.php` (baru), `bootstrap/app.php`, `app/Http/Controllers/WhatsAppController.php` (baru) | diubah / baru |
| Laporan fase backend | `docs/backend/FASE-6-1-KONFIGURASI-ENVIRONMENT.md`, `docs/backend/FASE-6-2-RUTE-WEBHOOK.md` | baru |

`CLAUDE.md` berstatus **diubah** (bukan baru) karena scaffold repo sudah menyediakannya; Boost mengganti isinya (+161/−29). Sementara `boost.json`, `.mcp.json`, `.claude/` **baru** (untracked) — mereka dicetak otomatis oleh `php artisan boost:install` saat instalasi, bukan tulisan manual.

## 2. Apa itu commit, dan apa fungsinya

Commit adalah operasi git yang **membekukan keadaan sejumlah file ke dalam riwayat repo pada satu titik waktu**. Sebuah commit menyimpan:

- **snapshot** (daftar isi file pada saat itu, lewat indeks git),
- **tautan ke commit sebelumnya** (parent), sehingga seluruh sejarah membentuk rantai,
- **pengarang + tanggal**, sehingga siapa mengganti apa dan kapan bisa ditelusuri,
- **pesan keterangan**, yang mewakili alasan perubahan itu dibuat,
- **SHA hash**, yang jadi alamat abadi titik itu (mis. `bee4a85`).

Setelah file ter-commit, folder kerja boleh di-edit semau-maunya: git selalu bisa **menunjukkan siapa yang mengubah baris itu** (`git blame`), **membandingkan dua titik waktu** (`git diff <hash>`), dan **mengembalikan keadaan** (`git checkout` / `git revert`).

### Commit vs push — dua operasi berbeda

| Langkah | Ke mana hasilnya | Efek untuk temanmu |
|---|---|---|
| `git commit` | Riwayat di **mesinmu sendiri** | Tidak ada — GitHub belum tahu apa-apa |
| `git push` | GitHub (repo pemilik scaffold) | Riwayat di GitHub bertambah; bisa di-clone / di-review |

## 3. Mengapa harus commit — lima alasan dengan basis kondisi nyata

1. **Satu-satunya salinan kerja kini ada di satu disk.** Tak ada satu pun titik pemulihan; kerusakan disk, penghapusan folder, atau edit yang salah akan menghapus pekerjaan dan semua dokumentasi laporannya selamanya. Git menyimpan salinan lengkap setiap commit, jadi setelah commit, kerja ini punya **cadangan di GitHub** bila di-push.
2. **Baseline bersih untuk Fase 6.3.** Setelah kondisi sekarang di-commit, pekerjaan Fase 6.3 nanti memakai `git diff` yang bisa menampilkan *hanya* perubahan fase itu — review jauh lebih mudah, dan tidak bisa dikacaukan oleh sisa-sisa perbaikan lama yang belum tercatat.
3. **Kerja kolaboratif baru terlihat setelah commit + push.** Riwayat repo memperlihatkan cara kerja sebelumnya: lewat PR #1 dan #2. Kontribusimu di Fase 6 — yang sudah selesai kodenya — sampai sekarang **nol tercatat** di GitHub; teman kolaborator belum melihat apa pun.
4. **Titik kembali saat ada kesalahan.** Bila Fase 6.3 ternyata merusak webhook, satu perintah mengembalikan kondisi Fase 6.2 (`git checkout <hash-terakhir-fase-6.2>`). Tanpa commit, perbaikan hanya bisa ditebak-nebak.
5. **PR tertata.** Karena repo memakai alur PR, commit yang terpilah per blok membuat PR dan laporan fase nanti saling menautkan rapi (`docs/backend/*.md` menunjuk file; git menunjuk commit).

## 4. Jika tidak dilakukan — yang kamu bayar

Tidak ada yang langsung rusak hari ini: server jalan, webhook bisa diakses. Yang kamu bayar adalah **risiko yang menumpuk**:

| Biaya | Uraian | Kapan terasa |
|---|---|---|
| Salinan tunggal | Semua kerja dan dokumentasi hanya di satu disk; tiga fase lagi (6.3–6.5) menambah file, menumpuk risikonya | Kapan pun terjadi insiden |
| Diff tak bisa dipilah | Diff Fase 6.3 nanti tercampur perbaikan ai-service lama — review sendiri dan PR jadi sulit | Saat mulai Fase 6.3 |
| Kontributor tak melihat progres | Kerja lama selesai di sisi tempat kerjamu tetap tak terlihat di GitHub | Setiap sesi kolaborasi |
| Tak ada titik kembali | Kesalahan edit yang tidak tergantikan karena tidak ada versi pembanding | Saat masalah pertama muncul |
| Status git makin gemuk | Semakin lama, daftar file bebas commit makin panjang dan membingungkan; risiko `git add .` menyeret file yang tidak dimaksud ikut masuk | Mulai sekarang |

Jadi: commit tidak wajib secara mekanis, tetapi **alasannya semuanya menguntungkanmu sendiri**, dan penumpukan kerja akhirnya memaksa commit di akhir — dalam keadaan yang jauh lebih berantakan.

---

## 5. Keputusan 1 — Granularitas commit

### Opsi A — pecah per blok kerja (6 commit)  **[rekomendasi]**

| Urutan | Pesan commit | File yang masuk |
|---|---|---|
| 1 | `fix(ai-service): perbaikan pasca-PR2 (auth X-Internal-Key, config, seeder)` | `ai-service/app/core/config.py`, `app/core/security.py`, `app/api/router.py`, `app/services/llm_service.py`, `seed_master_sop.py`, `ai-service/.env.example` |
| 2 | `docs(ai-service): addendum kontrak API + laporan perbaikan pasca-PR2` | `docs/ADDENDUM-KONTRAK-API.md`, `docs/PERBAIKAN-AI-SERVICE-PASCA-PR2.md` |
| 3 | `chore(core-service): konfigurasi environment Fase 6.1` | `core-service/config/services.php` (.env otomatis tidak ikut — ignored) |
| 4 | `chore(core-service): instalasi laravel/boost` | `core-service/composer.json`, `composer.lock`, `CLAUDE.md`, `boost.json`, `.mcp.json`, `.claude/**` (sesuai Keputusan 2) |
| 5 | `feat(core-service): jalur webhook WhatsApp (Fase 6.2)` | `core-service/routes/api.php`, `bootstrap/app.php`, `app/Http/Controllers/WhatsAppController.php` |
| 6 | `docs: laporan fase backend (6.1 dan 6.2)` | `docs/backend/FASE-6-1-...md`, `docs/backend/FASE-6-2-...md` |

**Kenapa dipilih:** setiap commit bermakna satu topik; riwayat terbaca dari judul saja; bila satu blok perlu di-revert, tidak terbawa blok lain; diff untuk setiap fase punya batas nyata.

**Kenapa jika tidak:** satu commit besar membuat `revert` menggantung semua topik sekaligus; mencari kapan satu baris tertentu berubah jadi harus membuka diff raksasa; pesan "feat: fase 6.1–6.2 + urusan ai-service" tidak menjelaskan apa pun di kolaborasi berikutnya.

### Opsi B — satu commit besar

**Kenapa dipilih:** murah (satu perintah), riwayat pendek.
**Kenapa jika tidak:** semua kelemahan yang disebut di atas — riwayat padat, revert tidak bisa per topik, review sulit.

### Konsekuensi menunda Keputusan 1

Bila tidak dipilih kapan-kapan pun: daftar file bebas commit makin panjang setiap fase; tampilan pertamamu di PR berisi gumpalan perbaikan lama — kesan pertama yang buruk bagi kolaborasi.

---

## 6. Keputusan 2 — Artefak Boost: commit, abaikan, atau tidak

Tiga artefak baru (`boost.json`, `.mcp.json`, `.claude/`) plus satu file terlacak (`CLAUDE.md`) menunggu keputusan. **Tanpa efek pada aplikasi** — `php artisan serve`, webhook, dan Fase 6.3 bekerja normal dengan pilihan mana pun. Efeknya hanya pada apa yang dilihat repo kolaborator dan keramaian `git status` lokal.

### Opsi (a) — commit semuanya  **[rekomendasi]**

- **Kenapa:** repo jadi *self-describing* — kolaborator kloningan baru langsung mendapat konfigurasi alat dan panduan konvensi; tidak perlu menjelaskan "jalankan `boost:install` dulu".
- **Kenapa jika tidak:** setiap klon baru harus menjalankan `boost:install` dari nol, dan hasil regenerasi `CLAUDE.md` antar pembaca bisa tidak seragam.

### Opsi (b) — commit kecuali `.claude/`

- **Kenapa:** bila anggapannya demikian: `.claude/**` adalah berkas preferensi perangkat, bukan kontrak proyek. Dengan `boost.json` + `.mcp.json` + perubahan `CLAUDE.md` saja, bootstrap konvensi tetap tersedia.
- **Kenapa jika tidak:** klon baru kehilangan skill domain (routing, security, validation, endpoint-tests) yang biasa dirujuk agen; tiap pembaca harus menghasilkannya ulang.

### Opsi (c) — masukkan ketiganya ke `.gitignore`

- **Kenapa:** bila kamu memutuskan Boost tetap hanya perkakas mesin lokal, bukan bagian repo.
- **Kenapa jika tidak:** tiap klon harus mengulang `boost:install`; hasil regenerasi antar pembaca bisa berbeda; dan **perubahan `CLAUDE.md` tetap harus diputuskan sendiri** — file itu sudah terlacak, sehingga masuknya ke `.gitignore` tidak menghilangkan perubahan: pilih men-commit-nya, atau kembali ke versi lama lewat `git checkout -- CLAUDE.md`.

### Konsekuensi menunda Keputusan 2

Ketiga file tetap `??` di `git status` — **risiko yang penting**: suatu saat `git add .` yang menyelesaikan pekerjaan lain bisa ikut menyertakan artefak itu tanpa sadar; keputusan "tidak diputuskan" akan berubah jadi keputusan "dimasukkan tanpa sadar".

---

## 7. Keputusan 3 — Alur pengiriman ke GitHub

### Opsi (a) — push langsung ke `main`

- **Kenapa:** murah dan cepat; cocok bila kamu dan teman sepakat bahwa semua kerja Fase 6 adalah lanjutan langsung.
- **Kenapa jika tidak:** tidak ada pembacaan (review) sebelum masuk `main`; kalau teman sedang bekerja di `main` juga, konflik antar pengomitan langsung saling menabrak.

### Opsi (b) — push branch + PR  **[rekomendasi]**

- **Kenapa:** mengikuti pola riwayat repo ini sendiri (PR #1, PR #2); memberi kesempatan teman menyetujui atau memberi catatan; diff PR otomatis setara dengan rentetan commit baru, sehingga pembacaan laporan `docs/backend/` ikut mudah.
- **Kenapa jika tidak:** seluruh keuntungan peninjauan hilang; commit masuk `main` tanpa satu pun pembacaan kedua.

### Konsekuensi menunda Keputusan 3

Kerja tetap tak terlihat di GitHub meski sudah di-commit — kerugian nomor 3 di Bab 4 tidak pernah selesai. Commit lokal tetap memberi manfaat pemulihan (Bab 3 no. 1, 2, 4), tetapi hanya push yang memberi salinan kedua di luar diskmu.

---

## 8. Keselamatan rahasia — sudah diverifikasi

| Hal | Status | Bukti |
|---|---|---|
| `ai-service/.env` | TIDAK terlacak, diabaikan git | `.gitignore` baris `.env`; `git ls-files "*.env"` kosong |
| `core-service/.env` | TIDAK terlacak, diabaikan git | `core-service/.gitignore` baris `.env`; sama |
| `META_*`, `INTERNAL_API_KEY`, kunci AI | hanya hidup di `.env` dan `config`; tidak akan ikut commit | kedua di atas |

Aturan yang tidak boleh dilanggar walau .env sudah diabaikan: **jangan pernah memaksa file rahasia masuk git** (`git add -f ai-service/.env` menembak mekanisme ignore). Sanity-check sebelum setiap commit tetap `git status --short`, lalu periksa daftar yang akan di-commit.

Cara mengecek ulang kapan pun:

```powershell
git ls-files "*.env"          # harus kosong
git check-ignore -v ai-service\.env core-service\.env   # harus menampilkan baris ignore
```

---

## 9. Ringkasan rekomendasi

| Keputusan | Rekomendasi | Tiga kata alasannya |
|---|---|---|
| 1. Granularitas | 6 commit per blok kerja | Riwayat terbaca; revert per topik |
| 2. Artefak Boost | Opsi (a) — commit semuanya | Repo self-describing |
| 3. Pengiriman | Opsi (b) — branch + PR | Mengikuti pola repo |

Semua rekomendasi di atas dipilih karena menurunkan risiko; pilihan lain tetap sah — yang tidak tepat hanyalah **menunda tanpa diputuskan**, karena penundaan juga sebuah pilihan, hanya yang mengambil keputusannya kebetulan, bukan kamu.

## 10. Checklist eksekusi (setelah ketiga keputusan jatuh)

```powershell
# 0. validasi mulai
git status --short

# 1..6: commit per blok (urutan & isi menurut tabel Bab 5)
git add <file per blok>; git commit -m "<pesan>"

# Keputusan 2 opsi (c): tambahkan tiga baris ini ke .gitignore
# boost.json
# .mcp.json
# .claude/

# Keputusan 3 opsi (b): branch + PR
git switch -c feature/backend-fase-6
git push -u origin feature/backend-fase-6
# lalu buka PR dari GitHub (atau: gh pr create)
```

## 11. Istilah teknis

- **Commit**: bekukan keadaan file ke riwayat repo lokal, lengkap dengan pengarang, pesan, dan SHA.
- **Push**: kirim commit dari repo lokal ke remote (GitHub).
- **PR (pull request)**: permintaan menggabungkan branch ke `main` agar diperiksa dulu oleh pemilik repo.
- **Untracked (`??`)**: file ada di disk, tidak di-`.gitignore`, belum pernah `git add`.
- **Ignored**: file sengaja dikecuali git lewat `.gitignore` — tidak akan muncul di snapshot.
- **Staging/index**: daftar berkas yang dipilih untuk commit berikutnya (`git add` mengisinya).
- **Diff**: perbedaan dua keadaan (commit vs commit, atau commit vs folder kerja) — bahan utama review.
