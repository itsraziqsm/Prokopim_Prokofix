"""Pembuat foto contoh untuk uji Arsip Liputan (Pillow)."""
import io
import os

from PIL import Image, ImageDraw

ISI_CONTOH = (
    "  Wali Kota Medan, Rico Tri Putra Bayu Waas, mengikuti Zoom Meeting  bersama Kementerian Dalam Negeri dari Rumah Dinas.\n"
    "\n\n\n"
    "“Kita harus bergerak cepat dan terukur,” ujar Wali​ Kota.   \n"
    "\tRapat diikuti seluruh perangkat daerah.\n"
)


def foto(lebar=800, tinggi=600, format_="JPEG", mode="RGB", warna=(30, 90, 160), derau=False, exif_orientasi=None):
    """Bytes gambar. derau=True membuat JPEG besar (sulit dikompres)."""
    if derau:
        gambar = Image.frombytes("RGB", (lebar, tinggi), os.urandom(lebar * tinggi * 3))
    else:
        gambar = Image.new(mode, (lebar, tinggi), warna if mode != "RGBA" else warna + (128,))
        ImageDraw.Draw(gambar).line([0, 0, lebar, tinggi], fill="white", width=8)
    keluar = io.BytesIO()
    simpan = {"quality": 95} if format_ == "JPEG" else {}
    if exif_orientasi:
        exif = Image.Exif()
        exif[0x0112] = exif_orientasi
        simpan["exif"] = exif
    gambar.save(keluar, format_, **simpan)
    return keluar.getvalue()


def tujuh_foto():
    """7 foto bermacam format & ukuran (potret dan lanskap) untuk uji alur lengkap."""
    return [
        ("lanskap.jpg", foto(1600, 1200)),
        ("potret.png", foto(900, 1600, "PNG")),
        ("besar.jpg", foto(2400, 1800, derau=True)),
        ("medsos.webp", foto(1080, 1080, "WEBP")),
        ("transparan.png", foto(1200, 1800, "PNG", mode="RGBA", derau=False)),
        ("animasi.gif", foto(600, 400, "GIF")),
        ("kamera.jpg", foto(1200, 900, exif_orientasi=6)),
    ]
