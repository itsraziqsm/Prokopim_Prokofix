"""Route (alamat halaman) aplikasi.

Blueprint = kumpulan route yang dikelompokkan, lalu didaftarkan di create_app().
"""
from datetime import datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, url_for

from . import log_proses
from .modules_registry import STATUS_LABEL, cari_modul, semua_modul
from .waktu import sapaan, tanggal_indonesia, waktu_singkat

bp = Blueprint("utama", __name__)

# Nama tampilan untuk sumber log yang bukan modul
NAMA_SUMBER_LOG = {"akun": "Akun", "sistem": "Sistem"}


def nama_sumber(modul_id):
    m = cari_modul(modul_id)
    return m["nama"] if m else NAMA_SUMBER_LOG.get(modul_id, modul_id)


@bp.app_template_filter("waktu_singkat")
def _filter_waktu(teks):
    return waktu_singkat(teks)


@bp.route("/")
def dashboard():
    sekarang = datetime.now()
    uid = g.pengguna["id"]
    return render_template(
        "dashboard.html",
        modul_list=semua_modul(),
        status_label=STATUS_LABEL,
        # Nilai awal dari server; app.js akan menyesuaikan dengan jam di komputer pengguna
        sapaan=sapaan(sekarang.hour),
        tanggal=tanggal_indonesia(sekarang),
        log_list=log_proses.terbaru(uid),
        lokasi=log_proses.lokasi_terakhir(uid),
        nama_sumber=nama_sumber,
    )


@bp.route("/buka-lokasi", methods=["POST"])
def buka_lokasi():
    """Membuka lokasi simpan terakhir di penjelajah file komputer ini.
    Lokasi diambil dari database (bukan dari isian pengguna), jadi aman."""
    baris = log_proses.lokasi_terakhir(g.pengguna["id"])
    if baris is None:
        flash("Belum ada lokasi simpan.", "info")
    else:
        try:
            log_proses.buka_di_penjelajah(baris["lokasi"])
            flash("Lokasi dibuka di penjelajah file.", "sukses")
        except FileNotFoundError:
            flash("Lokasi tidak ditemukan. File mungkin sudah dipindah atau dihapus.", "galat")
        except OSError:
            flash("Lokasi tidak dapat dibuka di komputer ini.", "galat")
    return redirect(url_for("utama.dashboard"))


@bp.route("/modul/<modul_id>")
def modul(modul_id):
    data = cari_modul(modul_id)
    if data is None:
        abort(404)  # memicu halaman galat di app/__init__.py
    return render_template(
        "modul_dev.html",
        modul=data,
        modul_list=semua_modul(),
        status_label=STATUS_LABEL,
    )


@bp.route("/pengaturan")
def pengaturan():
    # Pilihan tema disimpan di browser (localStorage) oleh app.js, jadi tidak perlu formulir server
    return render_template("pengaturan.html")
