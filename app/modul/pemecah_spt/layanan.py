"""Akses data Pemecah SPT: database, folder hasil, dan jalur berkas yang aman.

Fungsi publik untuk modul lain (mis. Arsip Liputan):
    daftar_spt(...)  -> daftar SPT hasil pecahan milik pengguna
    ambil_spt(id)    -> satu SPT beserta jalur berkas Word/PDF-nya
"""
import json
import re
import secrets
import shutil
import time
from pathlib import Path

from flask import current_app, g

from ...db import ambil_db

FORMAT_LABEL = {"word": "Word", "pdf": "PDF", "keduanya": "Word + PDF"}
UMUR_SEMENTARA_DETIK = 24 * 60 * 60
_POLA_TOKEN = re.compile(r"[A-Za-z0-9_-]{20,64}")


# ---------- Folder ----------
def folder_data():
    """instance/data/spt — semua hasil pecahan disimpan di bawah folder ini."""
    folder = Path(current_app.instance_path) / "data" / "spt"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def folder_sementara():
    folder = Path(current_app.instance_path) / "tmp"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def di_dalam_folder_data(jalur):
    """True bila jalur (setelah di-resolve) benar-benar berada di dalam instance/data/spt."""
    try:
        return Path(jalur).resolve().is_relative_to(folder_data().resolve())
    except (OSError, ValueError):
        return False


def jalur_berkas_aman(folder, nama):
    """Jalur berkas hasil dari rekaman database; None bila kosong, di luar folder data, atau tidak ada."""
    if not folder or not nama:
        return None
    jalur = (Path(folder) / nama).resolve()
    if not di_dalam_folder_data(jalur) or not jalur.is_file():
        return None
    return jalur


# ---------- Unggahan sementara (selama pratinjau) ----------
def simpan_sementara(berkas_unggahan, nama_asli, format_keluaran, pengguna_id):
    """Simpan unggahan dengan nama acak (nama dari klien TIDAK dipakai di disk). Mengembalikan token."""
    bersihkan_sementara()
    token = secrets.token_urlsafe(24)
    folder = folder_sementara()
    berkas_unggahan.save(folder / f"{token}.docx")
    _tulis_meta(token, {"pengguna_id": pengguna_id, "nama_asli": nama_asli,
                        "format": format_keluaran, "dibuat": time.time(), "analisis": None})
    return token


def _jalur_token(token, akhiran):
    if not token or not _POLA_TOKEN.fullmatch(token):
        return None
    return folder_sementara() / f"{token}{akhiran}"


def _tulis_meta(token, data):
    _jalur_token(token, ".json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def simpan_analisis(token, hasil_dict):
    meta = baca_sementara(token)
    meta["analisis"] = hasil_dict
    _tulis_meta(token, {k: v for k, v in meta.items() if k != "jalur"})


def baca_sementara(token, pengguna_id=None):
    """Metadata unggahan sementara milik pengguna, atau None (token salah/kedaluwarsa/milik orang lain)."""
    meta_jalur, docx_jalur = _jalur_token(token, ".json"), _jalur_token(token, ".docx")
    if meta_jalur is None or not meta_jalur.is_file() or not docx_jalur.is_file():
        return None
    meta = json.loads(meta_jalur.read_text(encoding="utf-8"))
    if pengguna_id is not None and meta.get("pengguna_id") != pengguna_id:
        return None
    if time.time() - meta.get("dibuat", 0) > UMUR_SEMENTARA_DETIK:
        hapus_sementara(token)
        return None
    meta["jalur"] = docx_jalur
    return meta


def ambil_alih_sementara(token, batch_id):
    """Pindahkan unggahan ke tmp/proses-<batch_id>.docx dan hapus metadatanya.
    Token langsung habis terpakai, sehingga batch yang sama tidak bisa diproses dua kali."""
    sumber = _jalur_token(token, ".docx")
    tujuan = folder_sementara() / f"proses-{batch_id}.docx"
    sumber.replace(tujuan)
    hapus_sementara(token)
    return tujuan


def hapus_sementara(token):
    for akhiran in (".docx", ".json"):
        jalur = _jalur_token(token, akhiran)
        if jalur is not None:
            jalur.unlink(missing_ok=True)


def bersihkan_sementara():
    """Hapus unggahan sementara yang lebih dari 24 jam."""
    batas = time.time() - UMUR_SEMENTARA_DETIK
    for jalur in folder_sementara().iterdir():
        try:
            if jalur.is_file() and jalur.stat().st_mtime < batas:
                jalur.unlink()
        except OSError:
            pass


# ---------- Batch ----------
def buat_batch(pengguna_id, nama_asli, format_keluaran, total_langkah=0):
    """Membuat rekaman batch (status "proses") + foldernya. Mengembalikan (id, folder)."""
    db = ambil_db()
    cur = db.execute(
        "INSERT INTO spt_batch (pengguna_id, nama_berkas_asli, format_keluaran, status, total_langkah, tahap) "
        "VALUES (?, ?, ?, 'proses', ?, 'Menyiapkan...')",
        (pengguna_id, nama_asli, format_keluaran, total_langkah))
    folder = folder_data() / str(cur.lastrowid)
    folder.mkdir(parents=True, exist_ok=True)
    db.execute("UPDATE spt_batch SET folder = ? WHERE id = ?", (str(folder.resolve()), cur.lastrowid))
    db.commit()
    return cur.lastrowid, folder


def simpan_spt(batch_id, urutan, nomor, nama_docx, nama_pdf, cuplikan, status, galat):
    ambil_db().execute(
        "INSERT INTO spt (batch_id, urutan, nomor, nama_docx, nama_pdf, cuplikan, status, galat) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (batch_id, urutan, nomor, nama_docx, nama_pdf, cuplikan, status, galat))


def perbarui_progres(batch_id, progres, tahap):
    db = ambil_db()
    db.execute("UPDATE spt_batch SET progres = ?, tahap = ? WHERE id = ?", (progres, tahap, batch_id))
    db.commit()


def selesaikan_batch(batch_id, jumlah, status, catatan):
    db = ambil_db()
    db.execute("UPDATE spt_batch SET jumlah = ?, status = ?, catatan = ?, tahap = NULL, progres = total_langkah "
               "WHERE id = ?", (jumlah, status, catatan, batch_id))
    db.commit()


def daftar_batch(pengguna_id, batas=10):
    return ambil_db().execute(
        "SELECT * FROM spt_batch WHERE pengguna_id = ? ORDER BY id DESC LIMIT ?", (pengguna_id, batas)).fetchall()


def ambil_batch(pengguna_id, batch_id):
    return ambil_db().execute(
        "SELECT * FROM spt_batch WHERE id = ? AND pengguna_id = ?", (batch_id, pengguna_id)).fetchone()


def spt_dalam_batch(batch_id):
    return ambil_db().execute("SELECT * FROM spt WHERE batch_id = ? ORDER BY urutan", (batch_id,)).fetchall()


class GalatHapus(Exception):
    """Pesan aman untuk pengguna saat batch tidak dapat dihapus."""


def folder_batch_aman(batch):
    """Folder hasil batch HANYA bila persis instance/data/spt/<id_batch>; selain itu None.
    Mencegah penghapusan folder lain walau isi kolom `folder` di database berubah."""
    if not batch["folder"]:
        return None
    folder = Path(batch["folder"]).resolve()
    if folder.parent != folder_data().resolve() or folder.name != str(batch["id"]):
        return None
    return folder


def hapus_batch(batch):
    """Hapus berkas hasil (folder batch) lalu rekamannya di database (baris spt ikut terhapus).
    Mengembalikan jumlah berkas yang dihapus. Bila berkas gagal dihapus (mis. sedang dibuka di Word),
    rekaman TIDAK dihapus agar bisa dicoba lagi."""
    if batch["status"] == "proses":
        raise GalatHapus("Batch masih diproses. Tunggu sampai selesai, lalu hapus.")
    folder = folder_batch_aman(batch)
    jumlah = 0
    if folder is not None and folder.is_dir():
        jumlah = sum(1 for f in folder.iterdir() if f.is_file())
        try:
            shutil.rmtree(folder)
        except OSError:
            raise GalatHapus("Sebagian berkas tidak dapat dihapus, mungkin sedang dibuka. "
                             "Tutup berkasnya lalu coba lagi.")
    db = ambil_db()
    db.execute("DELETE FROM spt WHERE batch_id = ?", (batch["id"],))
    db.execute("DELETE FROM spt_batch WHERE id = ?", (batch["id"],))
    db.commit()
    return jumlah


def jumlah_berkas(batch):
    """Jumlah berkas hasil di folder batch (untuk teks konfirmasi)."""
    folder = folder_batch_aman(batch)
    if folder is None or not folder.is_dir():
        return 0
    return sum(1 for f in folder.iterdir() if f.is_file())


# ---------- Untuk modul lain ----------
def _ke_dict(baris):
    data = dict(baris)
    data["jalur_docx"] = jalur_berkas_aman(data["folder"], data["nama_docx"])
    data["jalur_pdf"] = jalur_berkas_aman(data["folder"], data["nama_pdf"])
    return data


_PILIH_SPT = """
    SELECT spt.*, b.folder, b.nama_berkas_asli, b.dibuat AS dibuat_batch, b.pengguna_id
    FROM spt JOIN spt_batch b ON b.id = spt.batch_id
"""


def daftar_spt(pengguna_id=None, batch_id=None, hanya_berhasil=True):
    """SPT hasil pecahan milik pengguna (default: pengguna yang sedang masuk), terbaru dulu.
    Tiap item berisi kolom tabel spt + folder, jalur_docx, jalur_pdf (Path atau None)."""
    pengguna_id = pengguna_id if pengguna_id is not None else g.pengguna["id"]
    sql, param = _PILIH_SPT + " WHERE b.pengguna_id = ?", [pengguna_id]
    if batch_id is not None:
        sql += " AND spt.batch_id = ?"
        param.append(batch_id)
    if hanya_berhasil:
        sql += " AND spt.status != 'gagal'"
    sql += " ORDER BY spt.batch_id DESC, spt.urutan"
    return [_ke_dict(b) for b in ambil_db().execute(sql, param).fetchall()]


def ambil_spt(spt_id, pengguna_id=None):
    """Satu SPT milik pengguna beserta jalur berkasnya, atau None."""
    pengguna_id = pengguna_id if pengguna_id is not None else g.pengguna["id"]
    baris = ambil_db().execute(_PILIH_SPT + " WHERE spt.id = ? AND b.pengguna_id = ?",
                               (spt_id, pengguna_id)).fetchone()
    return _ke_dict(baris) if baris else None
