"""Modul induk Data Podcast (alamat /podcast).

Induk hanya menampilkan kartu fitur anaknya (dari registry: modul dengan induk "data_podcast").
Fitur anak = sub-paket sendiri dengan blueprint sendiri, mis. materi/ (Materi Podcast, alamat /podcast/materi).
Menambah fitur anak baru: buat sub-paket baru di sini, daftarkan blueprint-nya di create_app, lalu tambahkan
modul dengan "induk": "data_podcast" di app/modules_registry.py.

Perintah terminal (cli_group "podcast"):
    flask --app run podcast contoh     -> buat satu materi contoh fiktif untuk mencoba tampilan
"""
import click
from flask import Blueprint, render_template

from ...modules_registry import STATUS_LABEL, anak_dari, cari_modul
from . import materi

bp = Blueprint("data_podcast", __name__, url_prefix="/podcast", cli_group="podcast")
ID_MODUL = "data_podcast"

# Semua blueprint paket ini (induk + anak), didaftarkan di create_app
SEMUA_BLUEPRINT = [bp, materi.bp]


@bp.route("")
def index():
    daftar = anak_dari(ID_MODUL)
    return render_template(
        "data_podcast/index.html",
        induk=cari_modul(ID_MODUL),
        anak=daftar,
        status_label=STATUS_LABEL,
        status_campur=len({m["status"] for m in daftar}) > 1,
    )


@bp.cli.command("contoh")
def contoh():
    """Buat satu materi contoh FIKTIF (3 instansi: selesai, dalam proses, belum ada jawaban)."""
    materi_id = materi.layanan.buat_contoh()
    click.echo(f"Materi contoh dibuat (id {materi_id}). Buka /podcast/materi/{materi_id} di aplikasi.")
