"""Modul Pemecah SPT: memecah satu .docx berisi banyak Surat Perintah Tugas menjadi satu file per SPT.

Isi paket:
    pemecah.py   logika murni (tanpa Flask): validasi, deteksi judul, nomor, pemecahan
    penamaan.py  nama file dari nomor SPT (sanitasi & duplikat)
    pdf.py       konversi .docx -> .pdf lewat Microsoft Word (Windows) atau LibreOffice
    layanan.py   akses database & berkas hasil (dipakai juga oleh modul lain, mis. Arsip Liputan)
    routes.py    halaman web (blueprint "pemecah_spt", alamat /spt)
"""
from .routes import bp

__all__ = ["bp"]
