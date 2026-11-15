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

-- Riwayat proses: dicatat oleh modul lewat app/log_proses.py -> catat(...)
CREATE TABLE IF NOT EXISTS log_proses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pengguna_id  INTEGER REFERENCES pengguna(id) ON DELETE CASCADE,
    waktu        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    modul        TEXT NOT NULL,              -- id modul di registry, atau "akun"/"sistem"
    aksi         TEXT NOT NULL,              -- kalimat singkat, mis. "Memecah 12 SPT"
    status       TEXT NOT NULL DEFAULT 'sukses',  -- sukses | gagal
    detail       TEXT,
    lokasi       TEXT                         -- lokasi file/folder hasil simpan (bila ada)
);
CREATE INDEX IF NOT EXISTS idx_log_pengguna_waktu ON log_proses (pengguna_id, id DESC);
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
