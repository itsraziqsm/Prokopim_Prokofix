"""Paket utama aplikasi.

Pola "app factory": aplikasi dibuat di dalam fungsi create_app(),
sehingga mudah dikonfigurasi dan diuji. Mirip "bootstrap" pada framework web lain.
"""
import os
import secrets
from datetime import timedelta

from flask import Flask, render_template, request
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


def create_app(konfigurasi=None, instance_path=None):
    """konfigurasi: dict tambahan; instance_path: folder data lain (dipakai saat pengujian)."""
    # Folder "instance/" (di samping folder app/) menyimpan database & kunci rahasia
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.update(
        SECRET_KEY=_kunci_rahasia(app.instance_path),
        DATABASE=os.path.join(app.instance_path, "superapp.db"),
        SESSION_COOKIE_HTTPONLY=True,          # cookie tidak bisa dibaca JavaScript
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),  # berlaku bila "Ingat saya" dicentang
        MAX_CONTENT_LENGTH=30 * 1024 * 1024,   # batas unggahan (berkas SPT maks. 25 MB + formulir)
    )
    # Folder templat Word (ikut dicadangkan); bisa diganti lewat konfigurasi (dipakai uji)
    app.config["FOLDER_TEMPLAT"] = os.path.join(app.root_path, "templat_docx")
    if konfigurasi:
        app.config.update(konfigurasi)

    from . import db
    db.siapkan_db(app)

    from . import auth, cadangan, routes
    from .modul import arsip_liputan, data_podcast, pemecah_spt, utilitas

    # Batas unggahan khusus per rute. Harus dipasang SEBELUM penjaga login (yang membaca formulir untuk
    # cek CSRF), karena batas ukuran berlaku saat formulir pertama kali dibaca.
    batas_khusus = {
        "arsip_liputan.unggah_foto": arsip_liputan.routes.BATAS_UNGGAH_FOTO,
        "gabung_dokumen.unggah": utilitas.gabung_dokumen.routes.BATAS_UNGGAH,
        "gabung_dokumen.tambah": utilitas.gabung_dokumen.routes.BATAS_UNGGAH,
    }

    @app.before_request
    def batas_unggahan():
        if request.endpoint in batas_khusus:
            request.max_content_length = batas_khusus[request.endpoint]

    app.register_blueprint(auth.bp)
    app.register_blueprint(routes.bp)
    app.register_blueprint(cadangan.bp)          # halaman sistem (sidebar), bukan modul registry
    app.register_blueprint(pemecah_spt.bp)
    app.register_blueprint(arsip_liputan.bp)
    for bp in data_podcast.SEMUA_BLUEPRINT + utilitas.SEMUA_BLUEPRINT:   # induk + fitur anaknya
        app.register_blueprint(bp)

    # Tersedia otomatis di SEMUA template Jinja
    from .keamanan import csrf_field

    @app.context_processor
    def variabel_global():
        return {"nama_aplikasi": NAMA_APLIKASI, "csrf_field": csrf_field}

    # Halaman galat (400, 404, dst.) yang senada dengan desain, bukan error mentah
    @app.errorhandler(HTTPException)
    def halaman_galat(e):
        judul = {404: "Halaman tidak ditemukan", 400: "Permintaan tidak valid",
                 405: "Metode tidak diizinkan", 413: "Berkas terlalu besar"}.get(e.code, e.name)
        pesan = {404: "Alamat yang Anda buka tidak tersedia, atau modul tersebut belum terdaftar.",
                 413: "Ukuran unggahan melebihi batas (berkas SPT maks. 25 MB, foto maks. 15 MB per berkas, "
                      "PDF untuk digabung maks. 200 MB per penggabungan)."
                 }.get(e.code, e.description)
        return render_template("galat.html", kode=e.code, judul=judul, pesan=pesan), e.code

    return app
