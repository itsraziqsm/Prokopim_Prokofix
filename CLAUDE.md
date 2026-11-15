# CLAUDE.md — Super App Kerja

Konteks untuk asisten AI yang bekerja di repo ini. Baca seluruhnya sebelum mengubah kode.

## Tentang proyek
"Super App Kerja": kumpulan tools kerja pribadi untuk pegawai instansi pemerintah (Bagian Prokopim),
berjalan **lokal** di komputer pengguna (Windows), dibuka lewat browser di `http://127.0.0.1:<port>`.
Setiap fitur = satu **modul** yang terdaftar di registry dan tampil sebagai kartu di dashboard.

## Pengguna & gaya kerja
- Berpengalaman membuat website, **belum pernah memakai Python** → beri komentar kode berbahasa Indonesia,
  jelaskan konsep Python/Flask bila perlu.
- Antarmuka & teks UI **sepenuhnya Bahasa Indonesia**. Nama variabel/fungsi juga Bahasa Indonesia
  (`ambil_db`, `catat`, `tombol`, `lencana`, ...).
- Bekerja **langsung di branch `main`** (sudah diizinkan). Branch `claude/happy-pascal-l5d8dh` = arsip
  placeholder lama, jangan disentuh.
- Komunikasi dengan pengguna dalam Bahasa Indonesia, ringkas. Perintah terminal dalam blok `bash` terpisah.
- Pengguna sering mengirim daftar perubahan bernomor; kerjakan semua, laporkan per nomor.
  Bila ada poin kosong/terpotong, kerjakan sisanya lalu tanyakan.

## Stack & batasan
- Python 3.10+, **Flask** (satu-satunya dependensi Python), Jinja2, SQLite (`sqlite3` bawaan).
- **Tailwind CSS v4 lewat paket npm** (`@tailwindcss/cli` 4.3.2) — BUKAN CDN.
  Hasil build `app/static/css/app.css` **di-commit** agar aplikasi jalan tanpa Node & tanpa internet.
- JS biasa (tanpa framework), satu file `app/static/js/app.js`.
- Tanpa CDN / font / skrip eksternal. System font stack. Ikon & ilustrasi = SVG inline.
- Jangan menambah dependensi Python selain Flask tanpa persetujuan pengguna.
- Jangan mengubah/menghapus file di luar folder proyek.

## Menjalankan
```bash
pip install -r requirements.txt
python run.py            # pilih port otomatis (5000, 8000, 8080, ...); atau: python run.py 8080
npm install              # sekali, hanya bila mengubah tampilan
npm run watch:css        # build CSS otomatis saat mengedit template / input.css
npm run build:css        # build minify — WAJIB dijalankan sebelum commit bila kelas Tailwind berubah
flask --app run auth reset-sandi <nama_pengguna>   # lupa kata sandi
python -m unittest -v    # uji otomatis (wajib lulus sebelum commit)
```
`run.py` menangani error Windows 10013 (port dicadangkan Hyper-V/WSL) dengan mencoba port lain.

## Struktur
```
run.py                         titik masuk; pemilihan port
package.json                   skrip build Tailwind
app/__init__.py                create_app(): config, secret key di instance/, blueprint, halaman galat
app/modules_registry.py        DAFTAR MODUL (sumber tunggal) + STATUS_LABEL
app/routes.py                  blueprint "utama": /, /log, /log/<id>/buka, /modul/<id>, /pengaturan
app/auth.py                    blueprint "auth": /siapkan, /masuk, /keluar, /akun, CLI reset-sandi, penjaga login
app/keamanan.py                CSRF (csrf_field)
app/db.py                      koneksi SQLite per request + SKEMA (pengguna, log_proses)
app/log_proses.py              catat(), per_halaman(), lokasi_terakhir(), buka_di_penjelajah()
app/waktu.py                   sapaan, tanggal_indonesia, waktu_singkat
app/templates/base.html        kerangka: sidebar + konten; wadah notifikasi; skrip tema/sidebar di <head>
app/templates/komponen/        sidebar.html, ui.html (makro), ikon.html (SVG)
app/templates/auth/            _kartu.html (tata letak 60/40), masuk, siapkan, akun
app/templates/                 dashboard, log, modul_dev, pengaturan, galat
app/static/src/input.css       SUMBER CSS (edit ini)
app/static/css/app.css         HASIL BUILD (jangan diedit manual)
app/static/img/                gambar halaman masuk opsional: masuk.jpg/.png/.webp
instance/                      superapp.db + secret_key (tidak ikut git; backup = salin folder ini)
tests/test_aplikasi.py         uji unittest (create_app(instance_path=folder_sementara))
```

## Pola & konvensi penting
- **Menambah modul**: tambah satu dict di `MODUL` (`app/modules_registry.py`): id, nama, deskripsi,
  tujuan, ikon, status (`"siap"`/`"pengembangan"`), url (None → `/modul/<id>`), urutan, rencana.
  Modul "pengembangan" tetap bisa diklik → template tunggal `modul_dev.html`.
  Lencana status di dashboard hanya muncul bila status modul berbeda-beda, dan hanya pada modul yang belum siap.
  Logika modul nyata: buat blueprint sendiri (mis. `app/modul/pemecah_spt/`), daftarkan di `create_app`,
  isi `url` di registry, ubah status jadi `"siap"`.
- **Semua halaman wajib login** (penjaga `before_app_request` di `auth.py`); pengecualian di `ENDPOINT_PUBLIK`.
- **Setiap `<form method="post">` wajib `{{ csrf_field() }}`.**
- **Pencatatan proses**: modul memanggil `catat(modul_id, aksi, status="sukses"|"gagal", detail=..., lokasi=...)`.
  Lokasi tampil di tabel Log; buka folder hanya dari lokasi di DB milik pengguna (bukan input bebas).
- **Notifikasi**: server `flash(pesan, "sukses"|"info"|"galat")`; JS `window.notifikasi(pesan, jenis)`.
  Tampil pop-up kanan atas (fixed), jangan pakai alert inline untuk pesan umum. Galat per-field tetap inline (makro `field`).
- **Komponen ulang-pakai** di `komponen/ui.html`: `lencana`, `kartu_modul`, `breadcrumb`, `tombol`, `toast`, `field`. Kelas komponen CSS: `.tombol(-primer|-sekunder|-teks)`, `.lencana(-siap|-pengembangan)`,
  `.panel`, `.input`, `.label`, `.petunjuk`, `.galat-field`, `.ikon`.
- **Warna**: hanya lewat CSS variable di `input.css` (`--warna-aksen`, `--latar`, `--permukaan`, `--teks`, `--teks-redup`,
  `--garis`, ...) yang dipetakan ke kelas Tailwind (`bg-aksen`, `text-redup`, `border-garis`, `bg-siap-latar`, ...).
  Jangan menulis warna hex langsung di template.
- **Tema**: `<html data-theme="light|dark">`, dipilih di halaman Pengaturan (Terang/Gelap/Ikuti sistem),
  disimpan di `localStorage["tema"]`. **Sidebar**: `<html data-sidebar="lebar|ringkas">`, `localStorage["sidebar"]`.
- Tanggal/waktu tampil format Indonesia (`waktu.py`, filter Jinja `waktu_singkat`, `jalur` untuk path panjang).
  Sapaan & tanggal dihitung di server saja (server = komputer pengguna); jangan duplikasi di JS.
- **Ukuran**: pakai skala bawaan Tailwind (`text-sm`, `size-4`, `min-h-10`, ...). Hindari nilai sembarang `[...]`.
- Ikon baru: tambahkan cabang di `komponen/ikon.html`, warna `currentColor`.

## Standar UI/UX
- Rapi, tenang, profesional (kantor pemerintahan); satu warna aksen biru tua + netral; tanpa gradasi mencolok.
- Kontras WCAG AA, fokus keyboard terlihat, elemen HTML semantik + ARIA seperlunya, hormati `prefers-reduced-motion`.
- Responsif 1366×768 sampai monitor lebar; tetap rapi di tablet/ponsel (sidebar jadi ikon saja).
- Navigasi **hanya sidebar**: atas = Dashboard (ikon jendela), Log; bawah (dipisah garis) = Pengaturan, Akun.
- Tanpa footer. Halaman auth: formulir 60% kiri, gambar 40% kanan, satu layar tanpa scroll.
- Jangan membuat form/tombol palsu yang seolah berfungsi.
- **Hindari AI-slop**: tanpa ilustrasi/kartu pengisi, tanpa teks pengisi, tanpa instruksi developer di UI,
  tanpa ikon centang untuk hal yang belum selesai, tanpa lencana yang nilainya sama di semua item,
  tanpa judul kecil huruf kapital berjarak. Breadcrumb hanya untuk halaman tingkat kedua (mis. halaman modul);
  satu jalan kembali saja.
- Keamanan secukupnya untuk aplikasi lokal satu pengguna: hash sandi, CSRF, wajib login, rotasi token sesi
  saat ganti sandi. Tanpa pembatas percobaan login.

## Verifikasi sebelum selesai
1. `npm run build:css` bila ada kelas Tailwind baru.
2. `python -m unittest -v` harus lulus; tambah uji untuk perilaku baru di `tests/`.
3. Jalankan aplikasi, cek halaman yang diubah di mode terang & gelap, lebar 1366 dan 390 (tanpa scroll horizontal).
4. Commit ke `main` dengan pesan Bahasa Indonesia, lalu push.
