"""Data ringkasan untuk halaman Dashboard (semuanya diambil langsung dari database).

Dipisah dari routes.py agar kueri mudah dibaca & diuji.
"""
from datetime import timedelta
from pathlib import Path

from flask import current_app

from .cadangan.arsip import cadangan_terakhir
from .db import ambil_db

BATAS_UMUR_CADANGAN = timedelta(days=7)


def perlu_cadangan(sekarang):
    """True bila belum ada cadangan atau cadangan terakhir lebih dari 7 hari (untuk peringatan di Dashboard)."""
    terakhir = cadangan_terakhir(Path(current_app.instance_path) / "cadangan" / "berkas")
    return terakhir is None or sekarang - terakhir > BATAS_UMUR_CADANGAN


def ringkasan(pengguna_id, sekarang):
    """Mengembalikan dict berisi angka & daftar singkat untuk Dashboard.

    - Liputan dilihat semua pengguna (arsip bersama), jadi angkanya tidak disaring per pengguna.
    - SPT & log hanya milik pengguna yang masuk.
    """
    db = ambil_db()
    awal_bulan = f"{sekarang.year}-{sekarang.month:02d}-01"
    # Awal bulan berikutnya (Desember -> Januari tahun depan)
    if sekarang.month == 12:
        awal_bulan_depan = f"{sekarang.year + 1}-01-01"
    else:
        awal_bulan_depan = f"{sekarang.year}-{sekarang.month + 1:02d}-01"

    liputan_bulan_ini = db.execute(
        "SELECT COUNT(*) FROM liputan WHERE tanggal >= ? AND tanggal < ?", (awal_bulan, awal_bulan_depan)
    ).fetchone()[0]
    liputan_draf = db.execute("SELECT COUNT(*) FROM liputan WHERE status = 'draf'").fetchone()[0]
    spt_bulan_ini = db.execute(
        """SELECT COUNT(*) FROM spt s JOIN spt_batch b ON b.id = s.batch_id
           WHERE b.pengguna_id = ? AND s.status != 'gagal' AND s.dibuat >= ? AND s.dibuat < ?""",
        (pengguna_id, awal_bulan, awal_bulan_depan),
    ).fetchone()[0]

    liputan_terbaru = db.execute(
        """SELECT id, tanggal, tokoh, kegiatan, judul, status, diubah
           FROM liputan ORDER BY diubah DESC, id DESC LIMIT 5"""
    ).fetchall()
    log_terbaru = db.execute(
        "SELECT * FROM log_proses WHERE pengguna_id = ? ORDER BY id DESC LIMIT 5", (pengguna_id,)
    ).fetchall()

    return {
        "liputan_bulan_ini": liputan_bulan_ini,
        "liputan_draf": liputan_draf,
        "spt_bulan_ini": spt_bulan_ini,
        "liputan_terbaru": liputan_terbaru,
        "log_terbaru": log_terbaru,
    }
