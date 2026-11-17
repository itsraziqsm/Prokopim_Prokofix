"""Penggabungan PDF — logika murni tanpa Flask (mudah diuji).

Isi:
    urai_rentang(teks, jumlah)   "1-3,5,8-" -> indeks halaman (mulai 0), urut sesuai penulisan
    tanda_pdf(awal)              True bila 1 KB pertama memuat tanda "%PDF-"
    periksa_pdf(jalur)           jumlah halaman; GalatBerkas bila rusak / terkunci kata sandi / kosong
    siapkan_sumber(jalur)        berkas sumber -> berkas PDF siap gabung (TITIK PERLUASAN untuk Word)
    gabungkan(sumber, tujuan, judul, daftar_isi)   tulis PDF gabungan ke berkas
    nama_berkas_hasil(nama, sudah_ada, bawaan)     nama aman untuk Windows, berakhiran .pdf, unik

Memperluas ke Word nanti: di siapkan_sumber(), ubah .docx menjadi PDF lewat
app/modul/pemecah_spt/pdf.py (Word COM / LibreOffice) lalu kembalikan jalur PDF-nya; sisanya tidak berubah.
"""
import logging
import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

# PDF rusak sudah dilaporkan lewat GalatBerkas; peringatan internal pypdf tidak perlu memenuhi terminal
logging.getLogger("pypdf").setLevel(logging.ERROR)

EKSTENSI_DIDUKUNG = {".pdf"}   # tambah ".docx" di sini bila konversi Word sudah dibuat
PANJANG_NAMA_MAKS = 100
_NAMA_CADANGAN = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_KARAKTER_TERLARANG = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class GalatRentang(ValueError):
    """Rentang halaman tidak valid; pesan aman untuk ditampilkan ke pengguna."""


class GalatBerkas(Exception):
    """Berkas tidak bisa dipakai (bukan PDF, rusak, terkunci); pesan aman untuk pengguna."""


# ---------- Rentang halaman ----------
def urai_rentang(teks, jumlah_halaman):
    """'1-3,5,8-' -> [0,1,2,4,7,8,...]. Kosong atau 'semua' = seluruh halaman.

    Angka tunggal, a-b, atau a- (sampai halaman terakhir), dipisah koma; spasi diabaikan.
    Urutan hasil mengikuti urutan penulisan. Melempar GalatRentang untuk 0, rentang terbalik,
    halaman di luar jumlah halaman, atau teks yang tidak dikenali."""
    bersih = re.sub(r"\s+", "", (teks or "")).replace("–", "-").replace("—", "-")
    if bersih == "" or bersih.lower() == "semua":
        return list(range(jumlah_halaman))
    hasil = []
    for bagian in bersih.split(","):
        if bagian == "":
            continue                      # koma berlebih ("1,,3" atau "1-3,") diabaikan
        m = re.fullmatch(r"(\d+)(?:(-)(\d*))?", bagian)
        if not m:
            raise GalatRentang(f"“{bagian}” bukan nomor atau rentang halaman")
        awal = int(m.group(1))
        akhir = awal if not m.group(2) else (int(m.group(3)) if m.group(3) else jumlah_halaman)
        if awal == 0 or akhir == 0:
            raise GalatRentang("halaman dimulai dari 1, bukan 0")
        if awal > jumlah_halaman:
            raise GalatRentang(f"halaman {awal} melebihi jumlah halaman ({jumlah_halaman})")
        if akhir < awal:
            raise GalatRentang(f"rentang {awal}-{akhir} terbalik")
        if akhir > jumlah_halaman:
            raise GalatRentang(f"halaman {akhir} melebihi jumlah halaman ({jumlah_halaman})")
        hasil.extend(range(awal - 1, akhir))
    if not hasil:
        raise GalatRentang("tidak ada halaman yang dipilih")
    return hasil


# ---------- Pemeriksaan berkas ----------
def tanda_pdf(awal):
    """True bila potongan awal berkas (maks. 1 KB) memuat tanda tangan PDF '%PDF-'."""
    return b"%PDF-" in awal[:1024]


def _buka(jalur):
    """PdfReader yang sudah dibuka; PDF terenkripsi tanpa kata sandi pengguna dibuka dengan sandi kosong."""
    pembaca = PdfReader(str(jalur), strict=False)
    if pembaca.is_encrypted:
        try:
            berhasil = pembaca.decrypt("")
        except Exception:          # mis. enkripsi AES butuh paket tambahan yang tidak dipasang
            berhasil = 0
        if not berhasil:
            raise GalatBerkas("PDF ini terkunci kata sandi")
    return pembaca


def periksa_pdf(jalur):
    """Jumlah halaman PDF. Melempar GalatBerkas bila rusak, terkunci kata sandi, atau tanpa halaman.
    Semua pengecualian pypdf ditangkap agar satu berkas bermasalah tidak menggagalkan yang lain."""
    try:
        pembaca = _buka(jalur)
        jumlah = len(pembaca.pages)
        if jumlah:
            pembaca.pages[0].mediabox    # pastikan halaman benar-benar bisa dibaca
    except GalatBerkas:
        raise
    except Exception:
        raise GalatBerkas("PDF rusak atau tidak dapat dibaca")
    if jumlah == 0:
        raise GalatBerkas("PDF tidak berisi halaman")
    return jumlah


def siapkan_sumber(jalur):
    """Berkas sumber -> berkas PDF yang siap digabung. Untuk PDF: berkas itu sendiri.

    TITIK PERLUASAN: untuk Word (.docx), konversi dulu lewat app/modul/pemecah_spt/pdf.py lalu kembalikan
    jalur PDF hasil konversi. Jangan diimplementasikan sebelum diputuskan."""
    jalur = Path(jalur)
    if jalur.suffix.lower() == ".pdf":
        return jalur
    raise GalatBerkas("Format berkas ini belum didukung; saat ini hanya PDF")


# ---------- Penggabungan ----------
def gabungkan(sumber, tujuan, judul, daftar_isi=True):
    """Gabungkan halaman terpilih dari beberapa PDF ke berkas `tujuan`.

    sumber = [{"jalur": Path, "halaman": [indeks...], "judul": "nama file tanpa ekstensi"}, ...] (urut).
    Hanya halaman yang disalin: tindakan otomatis tingkat dokumen (OpenAction, JavaScript) TIDAK ikut,
    dan aksi otomatis per halaman (/AA) dibuang. Mengembalikan jumlah halaman hasil."""
    penulis = PdfWriter()
    for s in sumber:
        pembaca = _buka(siapkan_sumber(s["jalur"]))
        halaman_pertama = len(penulis.pages)
        for i in s["halaman"]:
            halaman = penulis.add_page(pembaca.pages[i])
            if NameObject("/AA") in halaman:
                del halaman[NameObject("/AA")]
        if daftar_isi and s["halaman"]:
            penulis.add_outline_item(s["judul"], halaman_pertama)
    penulis.add_metadata({"/Title": judul, "/Producer": "Super App Prokopim"})
    if daftar_isi and sumber:
        penulis.page_mode = "/UseOutlines"      # panel daftar isi terbuka saat PDF dibuka
    with open(tujuan, "wb") as berkas:          # ditulis langsung ke berkas, bukan ke memori
        penulis.write(berkas)
    return len(penulis.pages)


# ---------- Nama berkas hasil ----------
def nama_berkas_hasil(nama, sudah_ada=(), bawaan="Gabungan.pdf"):
    """Nama aman untuk Windows: karakter terlarang diganti '-', maks. 100 karakter, bukan nama cadangan
    (CON, PRN, COM1, ...), selalu berakhiran .pdf, dan unik terhadap `sudah_ada` (tambah ' (1)', ' (2)', ...)."""
    dasar = _KARAKTER_TERLARANG.sub("-", nama or "")
    dasar = re.sub(r"\s+", " ", dasar).strip()
    if dasar.lower().endswith(".pdf"):
        dasar = dasar[:-4]
    dasar = dasar.strip(" .")
    if not dasar:
        dasar = Path(bawaan).stem
    if dasar.split(".")[0].strip().upper() in _NAMA_CADANGAN:
        dasar = f"{dasar} (berkas)"
    ruang = PANJANG_NAMA_MAKS - len(".pdf")
    dasar = dasar[:ruang].rstrip(" .")
    sudah = {n.lower() for n in sudah_ada}
    kandidat, n = f"{dasar}.pdf", 1
    while kandidat.lower() in sudah:
        akhiran = f" ({n})"
        kandidat = f"{dasar[:ruang - len(akhiran)].rstrip(' .')}{akhiran}.pdf"
        n += 1
    return kandidat
