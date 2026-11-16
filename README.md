# Super App Prokopim

Kumpulan tools kerja pribadi yang berjalan **lokal** di komputer sendiri (tanpa internet).
Python + Flask + python-docx + Pillow + Jinja2, tampilan dengan **Tailwind CSS v4** (paket npm), JS biasa.

> Status: **Fitur 1 Pemecah SPT**, **Fitur 2 Arsip Liputan**, dan **Fitur 3 Data Podcast › Materi Podcast** siap.

## Data Podcast › Materi Podcast
Menyimpan pertanyaan untuk tiap instansi (OPD) beserta jawabannya per tema podcast.
1. **Alat → Data Podcast → Materi Podcast → Materi baru**: isi judul (mis. "Rekap Jawaban Podcast ... 2026") dan keterangan ("Per 11 November").
2. **Tambah instansi**, lalu buka instansinya: tulis pertanyaan & jawaban (pratinjau tampil langsung), klik **Simpan**.
   Format jawaban: `1. ` daftar bernomor, `- ` poin, indentasi 2 spasi = bersarang, `**tebal**`, `*miring*`,
   baris `**judul**` = judul kecil, baris `| a | b |` = tabel (`|---|---|` menandai header).
3. **Tandai selesai** bila semua pertanyaan sudah berjawaban. **Mode baca** untuk membaca/mencari/mencetak,
   **Ekspor Word** (A4) lalu **Unduh Word**. **Duplikat materi** untuk rekap versi berikutnya.

Data contoh fiktif untuk mencoba: `flask --app run podcast contoh`.

## Arsip Liputan
Menyimpan liputan kegiatan resmi (data kegiatan, isi berita, foto) lalu membuat satu Word F4:
berita, kemudian lembar foto bergaris potong (1–3 foto per lembar) untuk dicetak dan digunting.
1. **Arsip Liputan → Kegiatan baru**: isi tanggal, tokoh, kegiatan, judul, SPT terkait (opsional), isi berita.
2. **Foto**: pilih, seret, atau tempel (Ctrl+V). Foto di atas 800 KB dikompres otomatis. Isi keterangan & sumber,
   atur urutan dengan Naik/Turun, centang "Mulai lembar baru" bila perlu.
3. **Buat Word** → **Unduh Word** (`13 Oktober Wali - Zoom Meeting.docx`) atau **Unduh paket ZIP** (Word + SPT).

Templat Word: `app/templat_docx/berita.docx` (lihat README di folder itu).

## Pemecah SPT
Memecah satu `.docx` berisi banyak Surat Perintah Tugas menjadi satu berkas per SPT (Word, PDF, atau keduanya).
1. Buka **Pemecah SPT** di dashboard, pilih berkas dan keluaran, klik **Analisis berkas**.
2. Periksa **pratinjau** (nomor kembar / tidak terbaca ditandai), hapus centang SPT yang tidak perlu, klik **Proses**.
3. Unduh per berkas atau **ZIP**, atau **Buka folder** (`instance/data/spt/<id>/`).

Judul tiap SPT harus paragraf tersendiri "SURAT PERINTAH TUGAS" yang **tebal dan bergaris bawah**.
Nama berkas diambil dari baris "Nomor :"; nomor kembar diberi `(1)`, `(2)`, ...
PDF memakai Microsoft Word (Windows) atau LibreOffice; tanpa keduanya hasil tetap berupa Word.
Di Ubuntu: `sudo apt install libreoffice-writer`.

## Menjalankan
Butuh Python 3.10+.

```bash
pip install -r requirements.txt
python run.py
```
Buka alamat yang tercetak di terminal (misalnya http://127.0.0.1:5000).

Saat pertama kali dibuka, aplikasi meminta Anda **membuat akun pertama**. Setelah itu setiap halaman wajib masuk.

Aplikasi otomatis mencari port yang bisa dipakai (5000, 8000, 8080, ...). Port tertentu: `python run.py 8080`.

> **Error "An attempt was made to access a socket in a way forbidden by its access permissions"?**
> Windows mencadangkan port tertentu (Hyper-V/WSL/Docker). `run.py` sudah memilih port lain otomatis.
> Lihat port yang dicadangkan: `netsh interface ipv4 show excludedportrange protocol=tcp`

## Tampilan (Tailwind)
`app/static/css/app.css` adalah **hasil build** dan ikut di-commit, jadi aplikasi bisa jalan tanpa Node.
Node.js hanya dibutuhkan bila Anda mengubah tampilan:

```bash
npm install            # sekali saja
npm run watch:css      # build otomatis selama mengedit template / input.css
npm run build:css      # build sekali (minify) sebelum commit
```
- Sumber CSS: `app/static/src/input.css` (variabel warna tema, kelas komponen `.tombol`, `.lencana`, `.panel`, `.input`).
- Warna tema = CSS variable (`--warna-aksen`, `--latar`, ...) yang dipetakan ke kelas Tailwind (`bg-aksen`, `text-redup`, ...).
- Tema terang/gelap dipilih di halaman **Pengaturan** (Terang / Gelap / Ikuti sistem), disimpan di browser.

## Akun & keamanan
- Kata sandi disimpan sebagai hash (scrypt), bukan teks asli. Database: `instance/superapp.db` (tidak ikut git).
- Semua formulir dilindungi token CSRF; percobaan masuk yang salah tercatat di Log.
- Ganti kata sandi di halaman **Akun**; sesi di browser lain otomatis keluar.
- **Lupa kata sandi:** dari folder proyek jalankan
  ```bash
  flask --app run auth reset-sandi <nama_pengguna>
  ```
- Backup data cukup dengan menyalin folder `instance/`.

## Fitur tampilan
- **Sidebar** satu-satunya navigasi: Dashboard & Log di atas; Pengaturan & Akun di bawah. Tombol bulat di tepi kanan
  sidebar untuk menciutkan/melebarkan (diingat browser).
- **Notifikasi pop-up** di kanan atas: melayang di atas halaman, menutup sendiri, berhenti saat disorot.
  Dari server: `flash("Pesan", "sukses" | "info" | "galat")`. Dari JavaScript: `notifikasi("Pesan", "sukses")`.
- **Halaman masuk**: formulir 60% kiri, gambar 40% kanan, satu layar tanpa scroll.
  Panel kanan memakai `app/static/img/masuk.jpg` (atau `.png` / `.webp`) bila ada; tanpa gambar tampil pola polos.

## Log proses & lokasi simpan terakhir
Menu **Log** di sidebar berisi satu tabel: waktu, modul, proses, status, dan **lokasi simpan**.
Lokasi simpan terakhir ditandai lencana *Terakhir*; setiap lokasi punya tombol *Buka folder* & *Salin lokasi*.
Modul mencatat proses dengan satu baris:

```python
from app.log_proses import catat

catat("pemecah-spt", "Memecah 12 SPT", lokasi=r"D:\Arsip\SPT\2026-11")
catat("pemecah-spt", "Gagal membaca file", status="gagal", detail=str(galat))
```
Status hanya `"sukses"` atau `"gagal"`; di tabel Log hanya proses gagal yang diberi lencana.
Aktivitas akun (masuk, percobaan gagal, ganti sandi) sudah tercatat otomatis.

## Struktur folder
```
run.py                      # titik masuk: python run.py
package.json                # skrip build Tailwind
app/
  __init__.py               # app factory, konfigurasi, halaman galat
  auth.py                   # masuk, keluar, penyiapan akun, ganti sandi, perintah reset-sandi
  keamanan.py               # token CSRF
  db.py                     # koneksi & skema SQLite (pengguna, log_proses)
  log_proses.py             # catat() riwayat proses & lokasi simpan, buka folder
  modules_registry.py       # DAFTAR MODUL — satu-satunya tempat menambah modul
  routes.py                 # dashboard, /log, /modul/<id>, /pengaturan
  waktu.py                  # sapaan & tanggal Bahasa Indonesia
  templates/
    base.html               # kerangka: sidebar + konten (atau tanpa sidebar sebelum masuk)
    dashboard.html, alat.html, log.html, modul_dev.html, pengaturan.html, galat.html
    auth/                   # masuk, siapkan, akun
    komponen/               # sidebar, ui (makro), ikon SVG
  static/
    src/input.css           # SUMBER CSS Tailwind (edit ini)
    css/app.css             # hasil build (jangan diedit)
    js/app.js               # tema, sidebar, notifikasi, konfirmasi, unggah foto, editor pertanyaan, mode baca
app/modul/pemecah_spt/      # Fitur 1: pemecah, penamaan, pdf, layanan, routes
app/modul/arsip_liputan/    # Fitur 2: teks, foto, ekspor, layanan, routes
app/modul/data_podcast/     # Fitur 3 (induk): materi/ = Materi Podcast (pengurai, ekspor, layanan, routes)
app/templat_docx/           # templat Word berita (berita.docx)
tests/                      # uji otomatis: python -m unittest -v
```

## Uji otomatis
```bash
python -m unittest -v
```
Memakai `unittest` bawaan Python dan folder data sementara (database asli tidak tersentuh).

## Menambah modul baru
Tambahkan satu entri di `MODUL` pada `app/modules_registry.py`:

```python
{
    "id": "rekap-absensi",            # dipakai di URL: /modul/rekap-absensi
    "nama": "Rekap Absensi",
    "deskripsi": "Satu kalimat untuk kartu dashboard.",
    "tujuan": "Paragraf singkat di halaman modul.",
    "ikon": "dokumen-pecah",          # nama ikon di komponen/ikon.html
    "status": "pengembangan",         # atau "siap"
    "url": None,                      # isi alamat halaman asli bila status "siap"
    "urutan": 3,
    "rencana": ["Butir 1", "Butir 2", "Butir 3"],
},
```
Muat ulang browser: kartu baru langsung muncul di dashboard dan halamannya otomatis tersedia (dan otomatis dilindungi login).
Bila memakai kelas Tailwind baru di template, jalankan `npm run build:css`.
