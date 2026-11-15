"""Titik masuk aplikasi.

Cara menjalankan (dari folder proyek):
    python run.py
Lalu buka http://127.0.0.1:5000 di browser.
"""
from app import create_app

# Membuat objek aplikasi Flask lewat "app factory" (lihat app/__init__.py)
app = create_app()

if __name__ == "__main__":
    # host 127.0.0.1 = hanya bisa diakses dari komputer ini (aman, lokal)
    # debug=True = server otomatis memuat ulang saat kode diubah (khusus pengembangan)
    app.run(host="127.0.0.1", port=5000, debug=True)
