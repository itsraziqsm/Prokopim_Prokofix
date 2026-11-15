"""Route (alamat halaman) aplikasi.

Blueprint = kumpulan route yang dikelompokkan, lalu didaftarkan di create_app().
"""
from datetime import datetime

from flask import Blueprint, abort, render_template

from .modules_registry import STATUS_LABEL, cari_modul, semua_modul
from .waktu import sapaan, tanggal_indonesia

bp = Blueprint("utama", __name__)


@bp.route("/")
def dashboard():
    sekarang = datetime.now()
    return render_template(
        "dashboard.html",
        modul_list=semua_modul(),
        status_label=STATUS_LABEL,
        # Nilai awal dari server; app.js akan menyesuaikan dengan jam di komputer pengguna
        sapaan=sapaan(sekarang.hour),
        tanggal=tanggal_indonesia(sekarang),
    )


@bp.route("/modul/<modul_id>")
def modul(modul_id):
    data = cari_modul(modul_id)
    if data is None:
        abort(404)  # memicu halaman 404 di app/__init__.py
    return render_template(
        "modul_dev.html",
        modul=data,
        modul_list=semua_modul(),
        status_label=STATUS_LABEL,
    )
