"""Modul Arsip Liputan: data kegiatan, isi berita, dan foto; ekspor Word F4 (berita lalu lembar foto).

Isi paket:
    teks.py     normalisasi isi berita & nama berkas ekspor
    foto.py     validasi & pengolahan foto (Pillow)
    ekspor.py   pembuatan Word dari templat (app/templat_docx/berita.docx) + lembar foto
    layanan.py  database, folder berkas, pencarian
    routes.py   halaman web (blueprint "arsip_liputan", alamat /liputan)
"""
from .routes import bp

__all__ = ["bp"]
