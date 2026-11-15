"""Paket utama aplikasi.

Pola "app factory": aplikasi dibuat di dalam fungsi create_app(),
sehingga mudah dikonfigurasi dan diuji. Mirip "bootstrap" pada framework web lain.
"""
from flask import Flask, render_template

from .modules_registry import NAMA_APLIKASI


def create_app():
    app = Flask(__name__)  # template & static otomatis dicari di app/templates dan app/static

    # Daftarkan semua route (halaman) dari file routes.py
    from .routes import bp
    app.register_blueprint(bp)

    # Variabel yang otomatis tersedia di SEMUA template Jinja
    @app.context_processor
    def variabel_global():
        return {"nama_aplikasi": NAMA_APLIKASI}

    # Halaman 404 yang senada dengan desain (bukan error mentah)
    @app.errorhandler(404)
    def tidak_ditemukan(_error):
        return render_template("404.html"), 404

    return app
