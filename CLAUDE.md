# CLAUDE.md — Super App Kerja

Konteks untuk asisten AI yang bekerja di repo ini. Baca seluruhnya sebelum mengubah kode.

## Tentang proyek
"Super App Kerja": kumpulan tools kerja pribadi untuk pegawai instansi pemerintah (Bagian Prokopim),
berjalan **lokal** di komputer pengguna (Windows), dibuka lewat browser di `http://127.0.0.1:<port>`.
Rencana: aplikasi akan dipindah ke **server Ubuntu** — lihat "Catatan pindah ke server".
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
- Python 3.10+, Jinja2, SQLite (`sqlite3` bawaan). Dependensi Python yang **disetujui**: `flask`,
  `python-docx` (membawa `lxml`). Tidak ada yang lain (lihat `requirements.txt`).
- PDF dibuat **tanpa paket Python**: Windows → Microsoft Word lewat PowerShell/COM; Linux/Windows tanpa Word →
  LibreOffice `soffice --headless`. Bila keduanya tidak ada, hasil tetap Word dan batch berstatus "sebagian".
- **Tailwind CSS v4 lewat paket npm** (`@tailwindcss/cli` 4.3.2) — BUKAN CDN.
  Hasil build `app/static/css/app.css` **di-commit** agar aplikasi jalan tanpa Node & tanpa internet.
- JS biasa (tanpa framework), satu file `app/static/js/app.js`.
- Tanpa CDN / font / skrip eksternal. System font stack. Ikon & ilustrasi = SVG inline.
- Jangan menambah dependensi Python lain tanpa persetujuan pengguna.
- `subprocess` selalu dengan daftar argumen, tanpa `shell=True`; jalur lewat `pathlib`.
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
app/db.py                      koneksi SQLite per request + SKEMA (pengguna, log_proses, spt_batch, spt)
app/log_proses.py              catat(), per_halaman(), lokasi_terakhir(), buka_di_penjelajah()
app/waktu.py                   sapaan, tanggal_indonesia, waktu_singkat
app/modul/pemecah_spt/         Fitur 1 — blueprint "pemecah_spt" di /spt:
  pemecah.py                     logika murni tanpa Flask: validasi .docx, deteksi judul, nomor, pecah_satu()
  penamaan.py                    nama berkas dari nomor (sanitasi, duplikat → (1),(2) untuk SEMUA anggota)
  pdf.py                         konversi PDF (Word COM / LibreOffice), deteksi otomatis
  layanan.py                     DB & berkas; daftar_spt(), ambil_spt(id) untuk modul lain (Arsip Liputan)
  pekerja.py                     pemrosesan batch di thread latar + laporan progres ke DB
  routes.py                      /spt, /spt/analisis, /spt/pratinjau/<token>, /spt/proses, /spt/batch/<id>,
                                 /spt/batch/<id>/status (JSON progres), /spt/batch/<id>/zip,
                                 /spt/batch/<id>/buka, /spt/unduh/<spt_id>/<docx|pdf>,
                                 POST /spt/hapus (satu/banyak batch + berkas hasilnya)
app/templates/pemecah_spt/     index (unggah + riwayat), pratinjau, batch (hasil)
app/templates/base.html        kerangka: sidebar + konten; wadah notifikasi; skrip tema/sidebar di <head>
app/templates/komponen/        sidebar.html, ui.html (makro), ikon.html (SVG)
app/templates/auth/            _kartu.html (tata letak 60/40), masuk, siapkan, akun
app/templates/                 dashboard, log, modul_dev, pengaturan, galat
app/static/src/input.css       SUMBER CSS (edit ini)
app/static/css/app.css         HASIL BUILD (jangan diedit manual)
app/static/img/                gambar halaman masuk opsional: masuk.jpg/.png/.webp
instance/                      superapp.db + secret_key (tidak ikut git; backup = salin folder ini)
instance/data/spt/<id_batch>/  berkas hasil Pemecah SPT
instance/tmp/                  unggahan sementara selama pratinjau (<token>.docx + .json), dihapus >24 jam
tests/test_aplikasi.py         uji inti (create_app(instance_path=folder_sementara))
tests/test_pemecah_spt.py      uji Pemecah SPT; tests/fixture_spt.py membangun .docx contoh (batch_contoh())
```

## Pola & konvensi penting
- **Id modul**: huruf kecil dengan tanda hubung/garis bawah (mis. `pemecah_spt`); id yang sama dipakai di `catat()`
  agar nama modul tampil di tabel Log. Modul siap: `status="siap"`, `url` diisi (mis. `/spt`).
- **Menambah modul**: tambah satu dict di `MODUL` (`app/modules_registry.py`): id, nama, deskripsi,
  tujuan, ikon, status (`"siap"`/`"pengembangan"`), url (None → `/modul/<id>`), urutan, rencana.
  Modul "pengembangan" tetap bisa diklik → template tunggal `modul_dev.html`.
  Lencana status di dashboard hanya muncul bila status modul berbeda-beda, dan hanya pada modul yang belum siap.
  Logika modul nyata: buat blueprint sendiri (mis. `app/modul/pemecah_spt/`), daftarkan di `create_app`,
  isi `url` di registry, ubah status jadi `"siap"`. Logika berat ditaruh di modul murni tanpa Flask agar mudah diuji.
  Sidebar menandai "Dashboard" aktif untuk semua blueprint modul.
- **Semua halaman wajib login** (penjaga `before_app_request` di `auth.py`); pengecualian di `ENDPOINT_PUBLIK`.
- **Setiap `<form method="post">` wajib `{{ csrf_field() }}`.**
- **Pencatatan proses**: modul memanggil `catat(modul_id, aksi, status="sukses"|"gagal", detail=..., lokasi=...)`.
  Lokasi tampil di tabel Log; buka folder hanya dari lokasi di DB milik pengguna (bukan input bebas).
- **Berkas hasil & unduhan**: simpan di `instance/data/<modul>/<id>/` dengan nama dari data tepercaya
  (nama berkas dari klien hanya untuk tampilan). Unduh HANYA dari rekaman database, lalu resolve dan pastikan
  jalurnya di dalam folder data modul (lihat `layanan.jalur_berkas_aman`) → `send_file(as_attachment=True)`.
  ZIP dibuat di memori. "Buka folder" hanya dari lokasi yang tercatat. Unggahan: validasi ekstensi, signature,
  isi ZIP & batas ukuran; simpan dengan nama acak; token sementara terikat ke pengguna.
- **Hapus data + berkas**: selalu lewat `<form data-konfirmasi="... {n} ..." data-konfirmasi-judul="..."
  data-konfirmasi-tombol="Hapus">` (dialog `#dialog-konfirmasi` di base.html; `{n}` = jumlah `data-pilih-item` tercentang),
  tombol `.tombol-bahaya` di dialog. Server: hanya milik pengguna, tolak yang masih "proses", hapus folder HANYA
  bila jalurnya persis `instance/data/<modul>/<id>` (lihat `layanan.folder_batch_aman`), hapus berkas dulu baru
  rekaman DB (bila berkas terkunci, rekaman dipertahankan), lalu `catat(..., "Hapus batch", ...)`.
  Catatan: SPT yang dihapus juga hilang dari `daftar_spt()` (Arsip Liputan nanti harus siap menghadapi ini).
- **Proses lama + progres**: kerjakan di thread latar (`threading.Thread(daemon=True)` dengan
  `app.app_context()`, kirim `current_app._get_current_object()`), simpan progres di DB (kolom `status="proses"`,
  `progres`, `total_langkah`, `tahap`), sediakan endpoint JSON `{selesai, progres, total, persen, tahap, pesan, jenis}`,
  lalu tampilkan makro `progres(url_status, ...)` dari `ui.html`. app.js menanyakan status tiap detik, lalu memuat
  ulang halaman dengan notifikasi. Di thread tidak ada `g.pengguna`: panggil `catat(..., pengguna_id=...)`.
  Batch yang tertinggal berstatus "proses" ditandai gagal saat aplikasi dinyalakan (`db.siapkan_db`).
  Kolom baru pada tabel lama: tambahkan ke `KOLOM_SUSULAN` di `db.py` (ALTER TABLE otomatis).
- **Notifikasi**: server `flash(pesan, "sukses"|"info"|"galat")`; JS `window.notifikasi(pesan, jenis)`.
  Tampil pop-up kanan atas (fixed), jangan pakai alert inline untuk pesan umum. Galat per-field tetap inline (makro `field`).
- **Komponen ulang-pakai** di `komponen/ui.html`: `lencana`, `kartu_modul`, `breadcrumb`, `tombol`, `toast`, `field`,
  `alert` (peringatan inline yang menetap, jenis info|peringatan|galat). Kelas komponen CSS: `.tombol(-primer|-sekunder|-teks|-bahaya)`,
  `.lencana(-siap|-pengembangan|-peringatan|-gagal)`,
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
- **Tabel lebar**: bungkus dengan `<div class="relative overflow-x-auto" tabindex="0" role="region" aria-label="...">`.
  `relative` WAJIB: tanpa itu teks `sr-only` (absolute) di dalam tabel lolos dan melebarkan halaman di ponsel.
  Teks panjang berisi garis miring (nomor surat, jalur) pakai filter `|jalur` + `wrap-break-word`.
- **Perilaku JS siap pakai** (app.js): `<form data-kirim-sekali data-teks-proses="Memproses...">` (cegah kirim ganda),
  `data-pilih-semua` + `data-pilih-item` + `data-jumlah-dipilih` (centang semua), `data-pilih-berkas` +
  `data-nama-berkas` (input berkas bergaya tombol), `data-salin="teks"` (salin ke clipboard),
  `data-pantau-progres="url"` (dipasang makro `progres`), `data-konfirmasi` (dialog konfirmasi),
  `data-perlu-pilihan` (tombol nonaktif bila belum ada `data-pilih-item` tercentang), notifikasi titipan lewat
  `sessionStorage["notifikasi-tertunda"]` agar tetap tampil setelah halaman dimuat ulang.

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

## Catatan pindah ke server (perlu ditinjau)
Keputusan "hanya 127.0.0.1, satu pengguna" belum cocok untuk server Ubuntu. Sebelum pindah, tinjau:
host/port & reverse proxy (nginx) + HTTPS, server WSGI (mis. gunicorn) menggantikan `python run.py` (debug=True),
`SESSION_COOKIE_SECURE`, multi-pengguna (saat ini hanya /siapkan untuk akun pertama), pembatas percobaan login,
tombol "Buka folder" (membuka folder di mesin SERVER, bukan di komputer pengguna — sembunyikan atau ganti dengan unduhan),
proses latar memakai thread di dalam proses web (dengan gunicorn: worker harus tetap hidup selama proses,
pertimbangkan antrean bila batch besar/banyak pengguna), dan LibreOffice terpasang di server.

## Verifikasi sebelum selesai
1. `npm run build:css` bila ada kelas Tailwind baru.
2. `python -m unittest -v` harus lulus; tambah uji untuk perilaku baru di `tests/`.
3. Jalankan aplikasi, cek halaman yang diubah di mode terang & gelap, lebar 1366 dan 390 (tanpa scroll horizontal).
4. Commit ke `main` dengan pesan Bahasa Indonesia, lalu push.
