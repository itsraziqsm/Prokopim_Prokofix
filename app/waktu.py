"""Fungsi bantu tanggal & sapaan dalam Bahasa Indonesia."""
from datetime import datetime

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]


def sapaan(jam):
    """Sapaan sesuai jam (0-23). Batas jam sama persis dengan versi JS di app.js."""
    if 4 <= jam < 11:
        return "Selamat pagi"
    if 11 <= jam < 15:
        return "Selamat siang"
    if 15 <= jam < 18:
        return "Selamat sore"
    return "Selamat malam"


def tanggal_indonesia(waktu=None):
    """Contoh hasil: 'Minggu, 15 November 2026'."""
    waktu = waktu or datetime.now()
    return f"{HARI[waktu.weekday()]}, {waktu.day} {BULAN[waktu.month - 1]} {waktu.year}"
