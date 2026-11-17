"""Modul induk "Utilitas" (id utilitas).

Induk TIDAK punya halaman sendiri: di halaman Alat ia menjadi judul kelompok dengan kartu fitur anaknya
(dari registry: modul dengan induk "utilitas"). Alamat /utilitas dialihkan ke bagian itu.
Fitur anak = sub-paket sendiri dengan blueprint sendiri, mis. gabung_dokumen/ (Gabungkan PDF, /utilitas/gabung).
Menambah fitur anak baru: buat sub-paket baru di sini, tambahkan blueprint-nya ke SEMUA_BLUEPRINT, lalu tambahkan
modul dengan "induk": "utilitas" di app/modules_registry.py.
"""
from flask import Blueprint, redirect, url_for

from . import gabung_dokumen

bp = Blueprint("utilitas", __name__, url_prefix="/utilitas")
ID_MODUL = "utilitas"

# Semua blueprint paket ini (induk + anak), didaftarkan di create_app
SEMUA_BLUEPRINT = [bp, gabung_dokumen.bp]


@bp.route("")
def index():
    """/utilitas -> kelompok "Utilitas" di halaman Alat."""
    return redirect(url_for("utama.alat", _anchor="utilitas"))
