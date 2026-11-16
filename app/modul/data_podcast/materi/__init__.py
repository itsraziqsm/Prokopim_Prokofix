"""Fitur Materi Podcast (anak dari Data Podcast; alamat /podcast/materi).

Isi paket:
    pengurai.py  penguraian teks jawaban berformat ringan -> struktur blok / HTML aman (tanpa Flask)
    ekspor.py    pembuatan Word A4 dari materi (python-docx)
    layanan.py   database, status instansi, folder ekspor
    contoh.py    data contoh fiktif untuk perintah "flask --app run podcast contoh"
    routes.py    halaman web (blueprint "materi_podcast")
"""
from . import layanan
from .routes import bp

__all__ = ["bp", "layanan"]
