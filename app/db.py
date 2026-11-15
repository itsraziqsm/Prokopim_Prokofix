"""Koneksi database SQLite.

File database disimpan di folder instance/ (tidak ikut git), dibuat otomatis.
Satu koneksi dibuka per request lalu ditutup otomatis di akhir request.
"""
import sqlite3

from flask import current_app, g

SKEMA = """
CREATE TABLE IF NOT EXISTS pengguna (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_lengkap    TEXT NOT NULL,
    nama_pengguna   TEXT NOT NULL UNIQUE COLLATE NOCASE,  -- tidak membedakan huruf besar/kecil
    sandi_hash      TEXT NOT NULL,                         -- hash, BUKAN kata sandi asli
    sesi_token      TEXT NOT NULL,                         -- diganti saat sandi berubah -> sesi lama otomatis keluar
    dibuat_pada     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    login_terakhir  TEXT
);
"""


def ambil_db():
    """Mengembalikan koneksi database untuk request saat ini."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row  # hasil query bisa diakses seperti dict: baris["nama"]
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def tutup_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def siapkan_db(app):
    """Membuat tabel (bila belum ada) dan mendaftarkan penutupan koneksi."""
    with app.app_context():
        db = ambil_db()
        db.executescript(SKEMA)
        db.commit()
    app.teardown_appcontext(tutup_db)
