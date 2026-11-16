"""Pengolahan teks Arsip Liputan (murni Python, tanpa Flask)."""
import re
from datetime import date

from ..pemecah_spt.penamaan import bersihkan
from ...waktu import BULAN

# Karakter lebar-nol yang sering terbawa saat menyalin dari web/medsos
_LEBAR_NOL = re.compile("[​‌‍⁠﻿]")
# Spasi horizontal: spasi biasa, tab, NBSP, dan spasi Unicode lain (bukan baris baru)
_SPASI = re.compile(r"[ \t   -   　]+")


def paragraf_berita(isi: str) -> list:
    """Isi berita -> daftar paragraf untuk Word. Data di database tidak diubah.
    Tiap baris tak kosong = satu paragraf; spasi ganda/NBSP jadi satu spasi; karakter lebar-nol dibuang;
    tanda kutip lengkung & Unicode lain dipertahankan."""
    hasil = []
    for baris in _LEBAR_NOL.sub("", isi or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        baris = _SPASI.sub(" ", baris).strip()
        if baris:
            hasil.append(baris)
    return hasil


def nama_ekspor(tanggal: str, tokoh: str, kegiatan: str, judul: str = "") -> str:
    """'2026-10-13', 'Wali', 'Zoom Meeting' -> '13 Oktober Wali - Zoom Meeting' (tanpa ekstensi).
    Tokoh kosong -> '13 Oktober - Zoom Meeting'. Kegiatan kosong -> judul dipakai."""
    try:
        d = date.fromisoformat(tanggal)
        bagian = f"{d.day} {BULAN[d.month - 1]}"
    except (TypeError, ValueError):
        bagian = "Tanpa tanggal"
    tokoh = (tokoh or "").strip()
    kegiatan = (kegiatan or "").strip() or (judul or "").strip()
    if tokoh:
        bagian += f" {tokoh}"
    if kegiatan:
        bagian += f" - {kegiatan}"
    return bersihkan(bagian, "Liputan")
