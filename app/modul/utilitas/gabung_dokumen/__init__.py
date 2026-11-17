"""Fitur Gabungkan PDF (anak dari kelompok Utilitas; alamat /utilitas/gabung).

Isi paket:
    penggabung.py  logika murni tanpa Flask: rentang halaman, pemeriksaan PDF, penggabungan (pypdf), nama berkas
    layanan.py     sesi penyusunan sementara, unggahan, hasil di database, jalur berkas yang aman
    routes.py      halaman web (blueprint "gabung_dokumen")

Dukungan Word nanti: lihat penggabung.siapkan_sumber() dan EKSTENSI_DIDUKUNG.
"""
from . import layanan
from .routes import bp

__all__ = ["bp", "layanan"]
