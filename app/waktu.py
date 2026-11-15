"""Fungsi bantu tanggal & sapaan dalam Bahasa Indonesia."""
from datetime import datetime, timedelta

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]


def sapaan(jam):
    """Sapaan sesuai jam (0-23)."""
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


def waktu_singkat(teks):
    """'2026-11-15 03:09:46' -> 'Hari ini, 03.09' / 'Kemarin, 03.09' / '12 Nov 2026, 03.09'."""
    try:
        w = datetime.strptime(teks, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return teks or ""
    jam = w.strftime("%H.%M")
    hari_ini = datetime.now().date()
    if w.date() == hari_ini:
        return f"Hari ini, {jam}"
    if w.date() == hari_ini - timedelta(days=1):
        return f"Kemarin, {jam}"
    return f"{w.day} {BULAN[w.month - 1][:3]} {w.year}, {jam}"
