"""Route (alamat halaman) aplikasi.

Blueprint = kumpulan route yang dikelompokkan, lalu didaftarkan di create_app().
"""
import math
from datetime import datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from markupsafe import Markup, escape

from . import log_proses
from .modules_registry import STATUS_LABEL, cari_modul, modul_utama
from .ringkasan import ringkasan
from .waktu import BULAN, sapaan, tanggal_indonesia, waktu_singkat

bp = Blueprint("utama", __name__)

# Nama tampilan untuk sumber log yang bukan modul
NAMA_SUMBER_LOG = {"akun": "Akun", "sistem": "Sistem"}


def nama_sumber(modul_id):
    m = cari_modul(modul_id)
    return m["nama"] if m else NAMA_SUMBER_LOG.get(modul_id, modul_id)


@bp.app_template_filter("waktu_singkat")
def _filter_waktu(teks):
    return waktu_singkat(teks)


@bp.app_template_filter("jalur")
def _filter_jalur(teks):
    """Sisipkan titik patah baris (<wbr>) setelah \\ dan / agar lokasi panjang patah di tempat yang wajar."""
    aman = escape(teks or "")
    return Markup(aman.replace("\\", Markup("\\<wbr>")).replace("/", Markup("/<wbr>")))


@bp.route("/")
def dashboard():
    """Halaman awal: sapaan + ringkasan data (dibuka lewat logo di sidebar)."""
    sekarang = datetime.now()
    return render_template(
        "dashboard.html",
        # Server berjalan di komputer pengguna, jadi jam server = jam pengguna
        sapaan=sapaan(sekarang.hour),
        tanggal=tanggal_indonesia(sekarang),
        nama_bulan=BULAN[sekarang.month - 1],
        data=ringkasan(g.pengguna["id"], sekarang),
        nama_sumber=nama_sumber,
    )


@bp.route("/alat")
def alat():
    """Daftar semua alat (modul) dalam bentuk kartu."""
    daftar = modul_utama()   # modul anak tampil di halaman induknya
    return render_template(
        "alat.html",
        modul_list=daftar,
        status_label=STATUS_LABEL,
        # Lencana hanya berguna bila status modul berbeda-beda
        status_campur=len({m["status"] for m in daftar}) > 1,
    )


PER_HALAMAN_LOG = 20


@bp.route("/log")
def log():
    """Tabel riwayat proses, termasuk lokasi simpan setiap proses."""
    uid = g.pengguna["id"]
    halaman = max(request.args.get("hal", 1, type=int), 1)
    baris, total = log_proses.per_halaman(uid, halaman, PER_HALAMAN_LOG)
    terakhir = log_proses.lokasi_terakhir(uid)
    return render_template(
        "log.html",
        log_list=baris,
        total=total,
        halaman=halaman,
        jumlah_halaman=max(math.ceil(total / PER_HALAMAN_LOG), 1),
        id_lokasi_terakhir=terakhir["id"] if terakhir else None,
        nama_sumber=nama_sumber,
    )


@bp.route("/log/<int:log_id>/buka", methods=["POST"])
def buka_lokasi(log_id):
    """Membuka lokasi simpan sebuah log di penjelajah file komputer ini.
    Lokasi diambil dari database milik pengguna (bukan isian bebas), jadi aman."""
    baris = log_proses.ambil(g.pengguna["id"], log_id)
    if baris is None or not baris["lokasi"]:
        abort(404)
    try:
        log_proses.buka_di_penjelajah(baris["lokasi"])
        flash("Lokasi dibuka di penjelajah file.", "sukses")
    except FileNotFoundError:
        flash("Lokasi tidak ditemukan. File mungkin sudah dipindah atau dihapus.", "galat")
    except OSError:
        flash("Lokasi tidak dapat dibuka di komputer ini.", "galat")
    return redirect(url_for("utama.log", hal=request.form.get("hal", 1, type=int)))


@bp.route("/modul/<modul_id>")
def modul(modul_id):
    data = cari_modul(modul_id)
    if data is None:
        abort(404)
    return render_template("modul_dev.html", modul=data, status_label=STATUS_LABEL)


@bp.route("/pengaturan")
def pengaturan():
    # Pilihan tema disimpan di browser (localStorage) oleh app.js
    return render_template("pengaturan.html")
