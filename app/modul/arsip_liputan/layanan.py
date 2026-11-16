"""Akses data Arsip Liputan: database, folder berkas, pencarian, foto, ekspor."""
import secrets
import shutil
from datetime import date
from pathlib import Path

from flask import current_app

from ...db import ambil_db
from . import ekspor as ekspor_word
from .foto import olah_foto
from .teks import nama_ekspor
from ...waktu import BULAN

FOTO_MAKS = 40
STATUS = {"draf": "Draf", "final": "Final"}
PER_HALAMAN = 20


# ---------- Folder ----------
def folder_data():
    """instance/data/liputan — semua berkas arsip liputan di bawah folder ini."""
    folder = Path(current_app.instance_path) / "data" / "liputan"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def folder_bulan(tanggal):
    """'2026-10-13' -> instance/data/liputan/2026/10-Oktober (berkas disusun per bulan kegiatan)."""
    try:
        d = date.fromisoformat(tanggal)
    except (TypeError, ValueError):
        return folder_data() / "tanpa-tanggal"
    return folder_data() / f"{d.year}" / f"{d.month:02d}-{BULAN[d.month - 1]}"


def folder_untuk(liputan_id, tanggal):
    return folder_bulan(tanggal) / str(int(liputan_id))


def folder_liputan(liputan_id):
    """Folder berkas kegiatan, dihitung dari tanggal kegiatan yang tersimpan di database."""
    baris = ambil_db().execute("SELECT tanggal FROM liputan WHERE id = ?", (liputan_id,)).fetchone()
    return folder_untuk(liputan_id, baris["tanggal"] if baris else "")


def _folder_kegiatan_sah(folder, liputan_id):
    """True bila folder persis instance/data/liputan/<tahun>/<bulan>/<id> (atau tanpa-tanggal/<id>)."""
    folder, akar = Path(folder).resolve(), folder_data().resolve()
    if folder.name != str(int(liputan_id)):
        return False
    return folder.parent.parent.parent == akar or (folder.parent.parent == akar and folder.parent.name == "tanpa-tanggal")


def _bersihkan_folder_kosong(folder):
    """Hapus folder bulan/tahun yang kosong setelah kegiatan dihapus atau dipindah."""
    akar = folder_data().resolve()
    folder = Path(folder).resolve()
    while folder != akar and folder.is_relative_to(akar):
        try:
            folder.rmdir()          # hanya berhasil bila kosong
        except OSError:
            break
        folder = folder.parent


def pindahkan_folder(lama, baru):
    """Pindahkan isi folder kegiatan (foto/, ekspor/) ke lokasi baru. Melempar OSError bila gagal."""
    lama, baru = Path(lama), Path(baru)
    if lama.resolve() == baru.resolve() or not lama.is_dir():
        return
    baru.mkdir(parents=True, exist_ok=True)
    for sub in ("foto", "ekspor"):
        if (lama / sub).exists():
            if (baru / sub).exists():
                shutil.rmtree(baru / sub)
            shutil.move(str(lama / sub), str(baru / sub))
    _bersihkan_folder_kosong(lama)


def rapikan_folder_lama():
    """Migrasi sekali jalan: folder versi lama instance/data/liputan/<id>/ dipindah ke susunan per bulan.
    Hanya subfolder foto/ & ekspor/ yang dipindah (aman walau nomor id sama dengan nama folder tahun)."""
    for baris in ambil_db().execute("SELECT id, tanggal FROM liputan").fetchall():
        lama = folder_data() / str(baris["id"])
        if (lama / "foto").is_dir() or (lama / "ekspor").is_dir():
            pindahkan_folder(lama, folder_untuk(baris["id"], baris["tanggal"]))


def jalur_aman(liputan_id, sub, nama):
    """Jalur berkas dari rekaman DB; None bila kosong, di luar folder liputan ini, atau tidak ada."""
    if not nama:
        return None
    akar = (folder_liputan(liputan_id) / sub).resolve()
    jalur = (akar / nama).resolve()
    if not jalur.is_relative_to(folder_data().resolve()) or jalur.parent != akar or not jalur.is_file():
        return None
    return jalur


# ---------- Kegiatan ----------
_PILIH = """
    SELECT l.*, spt.nomor AS nomor_spt,
           (SELECT COUNT(*) FROM liputan_foto f WHERE f.liputan_id = l.id) AS jumlah_foto
    FROM liputan l LEFT JOIN spt ON spt.id = l.spt_id
"""


def cari(teks="", tahun="", bulan="", status="", halaman=1):
    """(daftar, total, jumlah_per_bulan) arsip yang cocok, urut tanggal kegiatan terbaru.
    Pencarian di judul, tokoh, kegiatan, isi, dan nomor SPT. jumlah_per_bulan: {"2026-10": 5, ...}."""
    syarat, param = [], []
    if teks:
        syarat.append("(l.judul LIKE ? OR l.tokoh LIKE ? OR l.kegiatan LIKE ? OR l.isi LIKE ? OR spt.nomor LIKE ?)")
        param += [f"%{teks}%"] * 5
    if tahun:
        syarat.append("substr(l.tanggal, 1, 4) = ?")
        param.append(tahun)
    if bulan:
        syarat.append("substr(l.tanggal, 6, 2) = ?")
        param.append(f"{int(bulan):02d}")
    if status in STATUS:
        syarat.append("l.status = ?")
        param.append(status)
    where = (" WHERE " + " AND ".join(syarat)) if syarat else ""
    db = ambil_db()
    total = db.execute("SELECT COUNT(*) FROM liputan l LEFT JOIN spt ON spt.id = l.spt_id" + where, param).fetchone()[0]
    daftar = db.execute(_PILIH + where + " ORDER BY l.tanggal DESC, l.id DESC LIMIT ? OFFSET ?",
                        param + [PER_HALAMAN, (halaman - 1) * PER_HALAMAN]).fetchall()
    per_bulan = dict(db.execute("SELECT substr(l.tanggal, 1, 7), COUNT(*) FROM liputan l "
                                "LEFT JOIN spt ON spt.id = l.spt_id" + where + " GROUP BY 1", param).fetchall())
    return daftar, total, per_bulan


def daftar_tahun():
    return [b[0] for b in ambil_db().execute(
        "SELECT DISTINCT substr(tanggal, 1, 4) FROM liputan ORDER BY 1 DESC").fetchall()]


def ambil(liputan_id):
    return ambil_db().execute(_PILIH + " WHERE l.id = ?", (liputan_id,)).fetchone()


def simpan(liputan_id, data, pengguna_id):
    """Buat (liputan_id None) atau perbarui kegiatan. Mengembalikan id."""
    db = ambil_db()
    kolom = ("tanggal", "tokoh", "kegiatan", "judul", "isi", "spt_id", "foto_per_lembar", "status")
    nilai = [data[k] for k in kolom]
    if liputan_id is None:
        cur = db.execute(f"INSERT INTO liputan (pengguna_id, {', '.join(kolom)}) VALUES (?{', ?' * len(kolom)})",
                         [pengguna_id] + nilai)
        liputan_id = cur.lastrowid
    else:
        # Tanggal pindah bulan -> folder berkas ikut pindah. Bila gagal (berkas sedang dibuka),
        # OSError dilempar SEBELUM database diubah sehingga data & berkas tetap sejalan.
        pindahkan_folder(folder_liputan(liputan_id), folder_untuk(liputan_id, data["tanggal"]))
        db.execute(f"UPDATE liputan SET {', '.join(k + ' = ?' for k in kolom)}, "
                   "diubah = datetime('now', 'localtime') WHERE id = ?", nilai + [liputan_id])
    db.commit()
    return liputan_id


def tandai_diubah(liputan_id):
    db = ambil_db()
    db.execute("UPDATE liputan SET diubah = datetime('now', 'localtime') WHERE id = ?", (liputan_id,))
    db.commit()


def hapus(liputan):
    """Hapus folder berkas (hanya instance/data/liputan/<tahun>/<bulan>/<id>) lalu rekamannya."""
    folder = folder_liputan(liputan["id"])
    if _folder_kegiatan_sah(folder, liputan["id"]) and folder.is_dir():
        shutil.rmtree(folder)
        _bersihkan_folder_kosong(folder.parent)
    db = ambil_db()
    db.execute("DELETE FROM liputan WHERE id = ?", (liputan["id"],))
    db.commit()


# ---------- Foto ----------
def daftar_foto(liputan_id):
    return ambil_db().execute("SELECT * FROM liputan_foto WHERE liputan_id = ? ORDER BY urutan, id",
                              (liputan_id,)).fetchall()


def ambil_foto(liputan_id, foto_id):
    return ambil_db().execute("SELECT * FROM liputan_foto WHERE id = ? AND liputan_id = ?",
                              (foto_id, liputan_id)).fetchone()


def tambah_foto(liputan_id, data, nama_asli):
    """Olah (bila perlu) lalu simpan satu foto dengan nama acak. Melempar foto.GalatFoto bila tidak valid."""
    hasil = olah_foto(data)
    folder = folder_liputan(liputan_id) / "foto"
    folder.mkdir(parents=True, exist_ok=True)
    nama = secrets.token_hex(12) + hasil.akhiran
    (folder / nama).write_bytes(hasil.data)
    db = ambil_db()
    urutan = db.execute("SELECT COALESCE(MAX(urutan), 0) + 1 FROM liputan_foto WHERE liputan_id = ?",
                        (liputan_id,)).fetchone()[0]
    db.execute("INSERT INTO liputan_foto (liputan_id, urutan, nama_berkas, nama_asli, lebar, tinggi, ukuran, diolah) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (liputan_id, urutan, nama, nama_asli[:200], hasil.lebar, hasil.tinggi, len(hasil.data), int(hasil.diolah)))
    db.commit()
    return hasil


def perbarui_foto(liputan_id, foto_id, keterangan, sumber, lembar_baru):
    db = ambil_db()
    db.execute("UPDATE liputan_foto SET keterangan = ?, sumber = ?, lembar_baru = ? WHERE id = ? AND liputan_id = ?",
               (keterangan, sumber, int(lembar_baru), foto_id, liputan_id))
    db.commit()


def geser_foto(liputan_id, foto_id, arah):
    """Tukar urutan foto dengan tetangganya (arah 'naik' / 'turun')."""
    foto = list(daftar_foto(liputan_id))
    ids = [f["id"] for f in foto]
    if foto_id not in ids:
        return False
    i = ids.index(foto_id)
    j = i - 1 if arah == "naik" else i + 1
    if not 0 <= j < len(ids):
        return False
    ids[i], ids[j] = ids[j], ids[i]
    db = ambil_db()
    for urutan, fid in enumerate(ids, start=1):
        db.execute("UPDATE liputan_foto SET urutan = ? WHERE id = ?", (urutan, fid))
    db.commit()
    return True


def hapus_foto(liputan_id, foto):
    jalur = jalur_aman(liputan_id, "foto", foto["nama_berkas"])
    if jalur is not None:
        jalur.unlink(missing_ok=True)
    db = ambil_db()
    db.execute("DELETE FROM liputan_foto WHERE id = ?", (foto["id"],))
    db.commit()


# ---------- Ekspor ----------
def ekspor(liputan):
    """Buat Word terbaru di instance/data/liputan/<id>/ekspor/. Mengembalikan (jalur, info)."""
    foto = []
    for f in daftar_foto(liputan["id"]):
        jalur = jalur_aman(liputan["id"], "foto", f["nama_berkas"])
        if jalur is not None:
            foto.append({**dict(f), "jalur": jalur})
    folder = folder_liputan(liputan["id"]) / "ekspor"
    if folder.is_dir():
        shutil.rmtree(folder)       # hanya simpan satu Word terbaru
    tujuan = folder / f"{nama_ekspor(liputan['tanggal'], liputan['tokoh'], liputan['kegiatan'], liputan['judul'])}.docx"
    info = ekspor_word.buat_dokumen(dict(liputan), foto, tujuan)
    db = ambil_db()
    db.execute("UPDATE liputan SET berkas_ekspor = ?, diekspor = datetime('now', 'localtime') WHERE id = ?",
               (tujuan.name, liputan["id"]))
    db.commit()
    return tujuan, info


def jalur_ekspor(liputan):
    return jalur_aman(liputan["id"], "ekspor", liputan["berkas_ekspor"])
