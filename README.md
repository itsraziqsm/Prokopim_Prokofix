# Super App Kerja

Kumpulan tools kerja pribadi yang berjalan **lokal** di komputer sendiri (tanpa internet).
Dibangun dengan Python + Flask + Jinja2, CSS dan JS biasa (tanpa framework/CDN).

> Status: **desain placeholder**. Dashboard dan halaman "Dalam pengembangan" sudah ada; logika fitur belum.

## Menjalankan
Butuh Python 3.10+.

```bash
pip install -r requirements.txt
python run.py
```
Buka http://127.0.0.1:5000

## Struktur folder
```
run.py                      # titik masuk: python run.py
app/
  __init__.py               # app factory (create_app) + halaman 404
  modules_registry.py       # DAFTAR MODUL — satu-satunya tempat menambah modul
  routes.py                 # route: / dan /modul/<id>
  waktu.py                  # sapaan & tanggal Bahasa Indonesia
  templates/
    base.html               # kerangka halaman: header, footer, tombol tema
    dashboard.html          # halaman utama
    modul_dev.html          # template "Under Development" untuk semua modul
    404.html
    komponen/
      ui.html               # makro: lencana, kartu_modul, kartu_segera, breadcrumb, tombol
      ikon.html             # ikon SVG inline
      ilustrasi_bangun.html # ilustrasi "sedang dibangun"
  static/
    css/app.css             # semua gaya + variabel warna tema
    js/app.js               # alih tema & sapaan
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
Simpan, muat ulang browser: kartu baru langsung muncul di dashboard, dan halamannya otomatis tersedia.

## Mengganti warna tema
Semua warna ada sebagai CSS variable di bagian atas `app/static/css/app.css`
(`--warna-aksen`, `--latar`, `--teks`, dst.), untuk mode terang dan gelap.
