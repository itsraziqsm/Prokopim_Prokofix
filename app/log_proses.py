"""Pencatatan riwayat proses & lokasi simpan terakhir.

Cara pakai di modul mana pun (di dalam route, saat pengguna sudah masuk):

    from app.log_proses import catat
    catat("pemecah-spt", "Memecah 12 SPT", lokasi=r"D:\\Arsip\\SPT\\2026-11")
    catat("pemecah-spt", "Gagal membaca file", status="gagal", detail=str(galat))

Data tampil otomatis di dashboard (Proses terakhir & Lokasi simpan terakhir).
"""
import os
import subprocess
import sys

from flask import g

from .db import ambil_db

STATUS_SAH = {"sukses", "gagal", "proses"}


def catat(modul, aksi, status="sukses", detail=None, lokasi=None, pengguna_id=None):
    """Simpan satu baris riwayat. pengguna_id default = pengguna yang sedang masuk."""
    if status not in STATUS_SAH:
        raise ValueError(f"status harus salah satu dari {STATUS_SAH}")
    if pengguna_id is None and getattr(g, "pengguna", None) is not None:
        pengguna_id = g.pengguna["id"]
    db = ambil_db()
    db.execute(
        "INSERT INTO log_proses (pengguna_id, modul, aksi, status, detail, lokasi) VALUES (?, ?, ?, ?, ?, ?)",
        (pengguna_id, modul, aksi, status, detail, lokasi),
    )
    db.commit()


def terbaru(pengguna_id, batas=8):
    return ambil_db().execute(
        "SELECT * FROM log_proses WHERE pengguna_id = ? ORDER BY id DESC LIMIT ?", (pengguna_id, batas)
    ).fetchall()


def lokasi_terakhir(pengguna_id):
    """Baris log terbaru yang punya lokasi simpan, atau None."""
    return ambil_db().execute(
        "SELECT * FROM log_proses WHERE pengguna_id = ? AND lokasi IS NOT NULL AND lokasi != '' "
        "ORDER BY id DESC LIMIT 1", (pengguna_id,)
    ).fetchone()


def buka_di_penjelajah(lokasi):
    """Buka lokasi di File Explorer (Windows) / Finder (macOS) / pengelola file (Linux).
    Bila lokasi berupa file, folder induknya dibuka dan file tersebut disorot (Windows/macOS)."""
    if not os.path.exists(lokasi):
        raise FileNotFoundError(lokasi)
    if sys.platform.startswith("win"):
        if os.path.isfile(lokasi):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(lokasi)])
        else:
            os.startfile(lokasi)  # noqa: S606 — hanya lokasi dari log milik pengguna sendiri
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", lokasi] if os.path.isfile(lokasi) else ["open", lokasi])
    else:
        folder = lokasi if os.path.isdir(lokasi) else os.path.dirname(lokasi)
        subprocess.Popen(["xdg-open", folder])
