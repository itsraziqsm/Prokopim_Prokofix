# Super App Kerja

Kumpulan tools kerja pribadi yang berjalan **lokal** di komputer sendiri (tanpa internet).
Python + Flask + Jinja2, tampilan dengan **Tailwind CSS v4** (paket npm), JS biasa.

> Status: **desain placeholder + sistem masuk (auth)**. Logika fitur modul belum ada.

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
    dashboard.html, log.html, modul_dev.html, pengaturan.html, galat.html
    auth/                   # masuk, siapkan, akun
    komponen/               # sidebar, ui (makro), ikon SVG
  static/
    src/input.css           # SUMBER CSS Tailwind (edit ini)
    css/app.css             # hasil build (jangan diedit)
    js/app.js               # tema, sidebar ringkas, notifikasi, tombol salin
tests/test_aplikasi.py      # uji otomatis: python -m unittest -v
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
