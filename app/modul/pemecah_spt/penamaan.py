"""Nama berkas dari nomor SPT: aman untuk Windows & Linux, dan unik di dalam satu batch."""
import re
import unicodedata

PANJANG_MAKS = 100
# Nama yang dicadangkan Windows dan tidak boleh dipakai sebagai nama berkas
NAMA_CADANGAN = {"CON", "PRN", "AUX", "NUL",
                 *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def bersihkan(nomor: str, cadangan: str = "SPT") -> str:
    """'800/12/Prokopim/2026' -> '800-12-Prokopim-2026'."""
    s = unicodedata.normalize("NFKC", nomor or "")
    s = re.sub(r"\s*[/\\]\s*", "-", s)                       # garis miring jadi tanda hubung
    s = re.sub(r'[:*?"<>|]', "", s)                           # karakter terlarang Windows
    s = "".join(c for c in s if not unicodedata.category(c).startswith("C"))  # karakter kontrol
    s = re.sub(r"\s+", " ", s).strip(" .")
    s = s[:PANJANG_MAKS].rstrip(" .")
    if not s:
        s = cadangan
    if s.split(".")[0].strip().upper() in NAMA_CADANGAN:
        s = f"_{s}"
    return s


def beri_nama(daftar_nomor: list) -> list:
    """Nama unik untuk tiap nomor (urutan dipertahankan).
    Nomor yang sama (tanpa membedakan huruf besar/kecil) -> SEMUA anggotanya diberi (1), (2), ..."""
    dasar = [bersihkan(n, f"SPT_urut-{i}") for i, n in enumerate(daftar_nomor, start=1)]
    jumlah = {}
    for nama in dasar:
        jumlah[nama.casefold()] = jumlah.get(nama.casefold(), 0) + 1

    hasil, terpakai, ke = [], set(), {}
    for nama in dasar:
        kunci = nama.casefold()
        if jumlah[kunci] > 1:
            ke[kunci] = ke.get(kunci, 0) + 1
            nama = f"{nama} ({ke[kunci]})"
        # Jaga-jaga bila tetap bentrok (mis. nomor asli memang berakhiran " (1)")
        kandidat, n = nama, 1
        while kandidat.casefold() in terpakai:
            n += 1
            kandidat = f"{nama} ({n})"
        terpakai.add(kandidat.casefold())
        hasil.append(kandidat)
    return hasil
