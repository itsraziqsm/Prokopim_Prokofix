"""Validasi & pengolahan foto liputan dengan Pillow (murni Python, tanpa Flask).

Aturan: foto DIOLAH hanya bila (a) ukurannya > 800 KB, (b) formatnya tidak didukung Word (mis. WebP),
atau (c) EXIF orientasinya bukan normal. Selain itu byte foto TIDAK diubah sama sekali.
"""
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

BATAS_OLAH = 800 * 1024            # 800 KB
UKURAN_MAKS = 15 * 1024 * 1024     # 15 MB per berkas unggahan
PIKSEL_MAKS = 60_000_000           # cegah "gambar bom" (mis. 60 megapiksel)
SISI_MAKS = 1920
SISI_MIN = 1200
KUALITAS_AWAL, KUALITAS_MIN = 85, 60

FORMAT_DITERIMA = {"JPEG", "PNG", "WEBP", "GIF", "BMP", "MPO"}
FORMAT_WORD = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif", "BMP": ".bmp"}   # dapat langsung dipakai Word
EXIF_ORIENTASI = 0x0112

# Pillow sendiri juga menolak gambar yang sangat besar (DecompressionBombError)
Image.MAX_IMAGE_PIXELS = PIKSEL_MAKS


class GalatFoto(Exception):
    """Pesan aman untuk pengguna."""


@dataclass
class HasilFoto:
    data: bytes
    akhiran: str        # ".jpg", ".png", ...
    lebar: int
    tinggi: int
    diolah: bool


def _buka(data):
    try:
        with Image.open(io.BytesIO(data)) as uji:
            uji.verify()                       # cek struktur berkas tanpa memuat seluruh piksel
        gambar = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise GalatFoto("bukan gambar yang valid atau berkasnya rusak")
    if gambar.format not in FORMAT_DITERIMA:
        raise GalatFoto(f"format {gambar.format} tidak diterima (gunakan JPG, PNG, WebP, GIF, atau BMP)")
    if gambar.width * gambar.height > PIKSEL_MAKS:
        raise GalatFoto("resolusi gambar terlalu besar")
    return gambar


def perlu_diolah(data, gambar):
    orientasi = gambar.getexif().get(EXIF_ORIENTASI, 1)
    return len(data) > BATAS_OLAH or gambar.format not in FORMAT_WORD or orientasi not in (0, 1)


def _ke_rgb(gambar):
    """RGBA/LA/P (transparan) -> RGB berlatar putih; mode lain -> RGB."""
    if gambar.mode in ("RGBA", "LA") or (gambar.mode == "P" and "transparency" in gambar.info):
        gambar = gambar.convert("RGBA")
        latar = Image.new("RGB", gambar.size, (255, 255, 255))
        latar.paste(gambar, mask=gambar.getchannel("A"))
        return latar
    return gambar.convert("RGB")


def _perkecil(gambar, sisi):
    if max(gambar.size) <= sisi:
        return gambar
    salinan = gambar.copy()
    salinan.thumbnail((sisi, sisi), Image.Resampling.LANCZOS)
    return salinan


def _jpeg(gambar, kualitas):
    keluar = io.BytesIO()
    gambar.save(keluar, "JPEG", quality=kualitas, optimize=True, progressive=True)
    return keluar.getvalue()


def olah_foto(data: bytes) -> HasilFoto:
    """Validasi lalu (bila perlu) olah satu foto. Melempar GalatFoto bila tidak valid."""
    if len(data) > UKURAN_MAKS:
        raise GalatFoto("lebih dari 15 MB")
    with _buka(data) as asli:
        if not perlu_diolah(data, asli):
            return HasilFoto(data, FORMAT_WORD[asli.format], asli.width, asli.height, diolah=False)
        asli.seek(0)  # GIF/WebP animasi: pakai bingkai pertama
        gambar = _ke_rgb(ImageOps.exif_transpose(asli))
    sisi = SISI_MAKS
    kecil = _perkecil(gambar, sisi)
    kualitas = KUALITAS_AWAL
    hasil = _jpeg(kecil, kualitas)
    while len(hasil) > BATAS_OLAH:
        if kualitas > KUALITAS_MIN:
            kualitas = max(KUALITAS_MIN, kualitas - 5)
        elif sisi > SISI_MIN:
            sisi = max(SISI_MIN, int(sisi * 0.85))
            kecil = _perkecil(gambar, sisi)
        else:
            break   # batas minimum tercapai; pakai hasil terakhir
        hasil = _jpeg(kecil, kualitas)
    return HasilFoto(hasil, ".jpg", kecil.width, kecil.height, diolah=True)
