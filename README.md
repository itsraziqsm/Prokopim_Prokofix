# Arsip Berita + SPT (Prokopim)

Aplikasi lokal (berjalan di komputer sendiri, tanpa internet) untuk:
- **Arsip Berita** – mencatat berita liputan beserta foto dokumentasi.
- **SPT** – membuat Surat Perintah Tugas.

Semua keluaran berupa file **Word (.docx) ukuran F4 (215 × 330 mm)**.

> Status: **placeholder** – kerangka aplikasi & menu sudah ada, fitur menyusul.

## Menjalankan
Butuh Python 3.10+.

Windows: klik dua kali `jalankan.bat`.

Manual:
```bash
pip install -r requirements.txt
python app.py
```
Lalu buka http://127.0.0.1:5000

## Struktur
- `app.py` – aplikasi Flask (rute/menu)
- `docx_export.py` – pembuatan dokumen Word F4
- `templates/`, `static/` – tampilan
