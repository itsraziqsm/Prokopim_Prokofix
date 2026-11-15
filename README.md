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
- Semua formulir dilindungi token CSRF; login dikunci 5 menit setelah 5 kali salah.
- Ganti kata sandi di halaman **Akun**; sesi di browser lain otomatis keluar.
- **Lupa kata sandi:** dari folder proyek jalankan
  ```bash
  flask --app run auth reset-sandi <nama_pengguna>
  ```
- Backup data cukup dengan menyalin folder `instance/`.

## Struktur folder
```
run.py                      # titik masuk: python run.py
package.json                # skrip build Tailwind
app/
  __init__.py               # app factory, konfigurasi, halaman galat
  auth.py                   # masuk, keluar, penyiapan akun, ganti sandi, perintah reset-sandi
  keamanan.py               # token CSRF & pembatasan percobaan login
  db.py                     # koneksi & skema SQLite
  modules_registry.py       # DAFTAR MODUL — satu-satunya tempat menambah modul
  routes.py                 # dashboard, /modul/<id>, /pengaturan
  waktu.py                  # sapaan & tanggal Bahasa Indonesia
  templates/
    base.html               # kerangka: sidebar + konten (atau tanpa sidebar sebelum masuk)
    dashboard.html, modul_dev.html, pengaturan.html, galat.html
    auth/                   # masuk, siapkan, akun
    komponen/               # sidebar, ui (makro), ikon SVG, ilustrasi
  static/
    src/input.css           # SUMBER CSS Tailwind (edit ini)
    css/app.css             # hasil build (jangan diedit)
    js/app.js               # tema & sapaan
```

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
