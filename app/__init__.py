"""Paket utama aplikasi.

Pola "app factory": aplikasi dibuat di dalam fungsi create_app(),
sehingga mudah dikonfigurasi dan diuji. Mirip "bootstrap" pada framework web lain.
"""
import os
import secrets
from datetime import timedelta

from flask import Flask, render_template
from werkzeug.exceptions import HTTPException

from .modules_registry import NAMA_APLIKASI


def _kunci_rahasia(folder):
    """Kunci untuk menandatangani cookie sesi. Dibuat sekali, disimpan di instance/secret_key."""
    lokasi = os.path.join(folder, "secret_key")
    if not os.path.exists(lokasi):
        with open(lokasi, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
    with open(lokasi, encoding="utf-8") as f:
        return f.read().strip()


def create_app(konfigurasi=None):
    # instance_relative_config: folder "instance/" (di samping folder app/) untuk data lokal
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.update(
        SECRET_KEY=_kunci_rahasia(app.instance_path),
        DATABASE=os.path.join(app.instance_path, "superapp.db"),
        SESSION_COOKIE_HTTPONLY=True,          # cookie tidak bisa dibaca JavaScript
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),  # berlaku bila "Ingat saya" dicentang
    )
    if konfigurasi:
        app.config.update(konfigurasi)

    from . import db
    db.siapkan_db(app)

    # Daftarkan route
    from . import auth, routes
    app.register_blueprint(auth.bp)
    app.register_blueprint(routes.bp)

    # Variabel/fungsi yang otomatis tersedia di SEMUA template Jinja
    from .keamanan import csrf_field

    @app.context_processor
    def variabel_global():
        return {"nama_aplikasi": NAMA_APLIKASI, "csrf_field": csrf_field}

    # Halaman galat (400, 404, dst.) yang senada dengan desain, bukan error mentah
    @app.errorhandler(HTTPException)
    def halaman_galat(e):
        judul = {404: "Halaman tidak ditemukan", 400: "Permintaan tidak valid",
                 405: "Metode tidak diizinkan"}.get(e.code, e.name)
        pesan = (e.description if e.code != 404
                 else "Alamat yang Anda buka tidak tersedia, atau modul tersebut belum terdaftar.")
        return render_template("galat.html", kode=e.code, judul=judul, pesan=pesan), e.code

    return app
