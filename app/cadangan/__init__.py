"""Cadangan & pemulihan data aplikasi (halaman sistem di sidebar, bukan modul registry).

Pembuatan cadangan: web (/cadangan, dilindungi kata sandi cadangan terpisah) + terminal.
Pemulihan: HANYA terminal (tidak ada rute web yang menerima unggahan ZIP).

Isi paket (logika murni tanpa Flask dipakai bersama web & terminal):
    sandi.py      kunci.json (hash scrypt sandi cadangan), pembatas percobaan, penurunan kunci
    basisdata.py  snapshot konsisten, jalur relatif<->absolut, ringkas & validasi skema
    arsip.py      buat ZIP + manifest bertanda HMAC, pemeriksaan ZIP (daftar putih, ukuran, SHA-256, zip bomb)
    pulihkan.py   prosedur pemulihan berurutan dengan rollback
    audit.py      instance/cadangan/audit.log (append-only)
    routes.py     halaman web (blueprint "cadangan")
    perintah.py   perintah terminal (cli_group "cadangan"): buat, periksa, pulihkan, reset-sandi
"""
from flask import Blueprint

bp = Blueprint("cadangan", __name__, url_prefix="/cadangan", cli_group="cadangan")

from . import perintah, routes  # noqa: E402,F401  (mendaftarkan rute & perintah ke bp)

__all__ = ["bp"]
