"""Akses data Materi Podcast: database, status instansi, folder ekspor.

Semua pengguna yang masuk melihat semua materi (aplikasi internal).
Kueri dibuat agar halaman materi & mode baca cukup memakai 2-3 query (tanpa N+1).
"""
import re
import shutil
from pathlib import Path

from flask import current_app

from ....db import ambil_db
from . import ekspor as ekspor_word
from .pengurai import PANJANG_MAKS, ada_isi, rapikan

# Status instansi: "selesai" ditandai pengguna; dua lainnya dihitung dari jawaban
STATUS = {"selesai": "Selesai", "proses": "Dalam proses", "belum": "Belum ada jawaban"}
# Kelas lencana (lihat input.css) — status selalu tertulis, bukan warna saja
LENCANA = {"selesai": "siap", "proses": "peringatan", "belum": "netral"}

PANJANG = {"judul": 200, "keterangan": 300, "nama": 200, "pertanyaan": 2000, "jawaban": PANJANG_MAKS}
PERTANYAAN_MAKS = 150


def status_instansi(jumlah, terjawab, selesai):
    """Status dihitung otomatis; "selesai" hanya berlaku bila semua pertanyaan sudah berjawaban."""
    if selesai and jumlah and terjawab == jumlah:
        return "selesai"
    if terjawab == 0:
        return "belum"
    return "proses"


def _db():
    """Koneksi + fungsi SQL ada_isi() agar hitungan 'terjawab' sama persis dengan aturan di Python."""
    db = ambil_db()
    db.create_function("ada_isi", 1, lambda t: 1 if ada_isi(t) else 0, deterministic=True)
    return db


# ---------- Folder ----------
def folder_data():
    """instance/data/podcast — semua berkas fitur Podcast di bawah folder ini."""
    folder = Path(current_app.instance_path) / "data" / "podcast"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def folder_materi(materi_id):
    return folder_data() / str(int(materi_id))


def _folder_materi_sah(folder, materi_id):
    """True bila folder persis instance/data/podcast/<id>."""
    folder = Path(folder).resolve()
    return folder.parent == folder_data().resolve() and folder.name == str(int(materi_id))


def jalur_ekspor(materi):
    """Jalur Word terakhir dari rekaman DB; None bila kosong, hilang, atau di luar folder ekspor materi ini."""
    nama = materi["berkas_ekspor"]
    if not nama:
        return None
    akar = (folder_materi(materi["id"]) / "ekspor").resolve()
    jalur = (akar / nama).resolve()
    if not jalur.is_relative_to(folder_data().resolve()) or jalur.parent != akar or not jalur.is_file():
        return None
    return jalur


# ---------- Materi ----------
_RINGKAS_MATERI = """
    SELECT m.*,
           (SELECT COUNT(*) FROM materi_instansi i WHERE i.materi_id = m.id) AS jumlah_instansi,
           (SELECT COUNT(*) FROM materi_pertanyaan p JOIN materi_instansi i ON i.id = p.instansi_id
             WHERE i.materi_id = m.id) AS jumlah_pertanyaan,
           (SELECT COUNT(*) FROM materi_pertanyaan p JOIN materi_instansi i ON i.id = p.instansi_id
             WHERE i.materi_id = m.id AND ada_isi(p.jawaban)) AS jumlah_terjawab
    FROM materi_podcast m
"""


def daftar_materi(cari=""):
    """Semua materi (terbaru diubah di atas) beserta hitungan pertanyaan terjawab. Satu query."""
    sql, param = _RINGKAS_MATERI, []
    if cari:
        sql += " WHERE m.judul LIKE ? ESCAPE '\\' OR m.keterangan LIKE ? ESCAPE '\\'"
        pola = "%" + re.sub(r"([\\%_])", r"\\\1", cari) + "%"
        param = [pola, pola]
    sql += " ORDER BY m.diubah DESC, m.id DESC"
    return _db().execute(sql, param).fetchall()


def ambil_materi(materi_id):
    return _db().execute(_RINGKAS_MATERI + " WHERE m.id = ?", (materi_id,)).fetchone()


def buat_materi(judul, keterangan, pengguna_id):
    db = ambil_db()
    kursor = db.execute("INSERT INTO materi_podcast (pengguna_id, judul, keterangan) VALUES (?, ?, ?)",
                        (pengguna_id, judul, keterangan))
    db.commit()
    return kursor.lastrowid


def ubah_materi(materi_id, judul, keterangan):
    db = ambil_db()
    db.execute("UPDATE materi_podcast SET judul = ?, keterangan = ?, diubah = datetime('now', 'localtime') "
               "WHERE id = ?", (judul, keterangan, materi_id))
    db.commit()


def tandai_diubah(materi_id):
    db = ambil_db()
    db.execute("UPDATE materi_podcast SET diubah = datetime('now', 'localtime') WHERE id = ?", (materi_id,))
    db.commit()


def hapus_materi(materi):
    """Hapus berkas dulu (hanya folder instance/data/podcast/<id>), baru rekaman DB.
    Instansi & pertanyaan ikut terhapus lewat ON DELETE CASCADE. Melempar OSError bila berkas terkunci."""
    folder = folder_materi(materi["id"])
    if folder.exists() and _folder_materi_sah(folder, materi["id"]):
        shutil.rmtree(folder)
    db = ambil_db()
    db.execute("DELETE FROM materi_podcast WHERE id = ?", (materi["id"],))
    db.commit()


def duplikat_materi(materi_id, pengguna_id):
    """Salin materi beserta instansi, pertanyaan, jawaban, dan tanda selesai (untuk rekap versi berikutnya).
    Berkas Word tidak ikut disalin. Mengembalikan id materi baru."""
    db = ambil_db()
    asal = db.execute("SELECT * FROM materi_podcast WHERE id = ?", (materi_id,)).fetchone()
    judul = f"{asal['judul']} (salinan)"[:PANJANG["judul"] + 10]
    baru = db.execute("INSERT INTO materi_podcast (pengguna_id, judul, keterangan) VALUES (?, ?, ?)",
                      (pengguna_id, judul, asal["keterangan"])).lastrowid
    for ins in db.execute("SELECT * FROM materi_instansi WHERE materi_id = ? ORDER BY urutan, id",
                          (materi_id,)).fetchall():
        iid = db.execute("INSERT INTO materi_instansi (materi_id, urutan, nama, selesai) VALUES (?, ?, ?, ?)",
                         (baru, ins["urutan"], ins["nama"], ins["selesai"])).lastrowid
        db.execute("""INSERT INTO materi_pertanyaan (instansi_id, urutan, teks, jawaban)
                      SELECT ?, urutan, teks, jawaban FROM materi_pertanyaan WHERE instansi_id = ?""",
                   (iid, ins["id"]))
    db.commit()
    return baru


# ---------- Instansi ----------
def daftar_instansi(materi_id):
    """Instansi beserta jumlah pertanyaan, terjawab, dan status. Satu query."""
    baris = _db().execute("""
        SELECT i.*, COUNT(p.id) AS jumlah, COALESCE(SUM(ada_isi(p.jawaban)), 0) AS terjawab
        FROM materi_instansi i LEFT JOIN materi_pertanyaan p ON p.instansi_id = i.id
        WHERE i.materi_id = ? GROUP BY i.id ORDER BY i.urutan, i.id""", (materi_id,)).fetchall()
    return [_dengan_status(dict(b)) for b in baris]


def _dengan_status(ins):
    ins["status"] = status_instansi(ins["jumlah"], ins["terjawab"], ins["selesai"])
    ins["label_status"] = STATUS[ins["status"]]
    ins["lencana"] = LENCANA[ins["status"]]
    return ins


def ambil_instansi(materi_id, instansi_id):
    """Satu instansi milik materi ini (None bila tidak ada)."""
    for ins in daftar_instansi(materi_id):
        if ins["id"] == instansi_id:
            return ins
    return None


def daftar_pertanyaan(instansi_id):
    return ambil_db().execute("SELECT * FROM materi_pertanyaan WHERE instansi_id = ? ORDER BY urutan, id",
                              (instansi_id,)).fetchall()


def muat_lengkap(materi_id):
    """Instansi (dengan status) + pertanyaannya, untuk mode baca & ekspor. Dua query."""
    instansi = daftar_instansi(materi_id)
    per_instansi = {i["id"]: [] for i in instansi}
    for p in ambil_db().execute("""
            SELECT p.* FROM materi_pertanyaan p JOIN materi_instansi i ON i.id = p.instansi_id
            WHERE i.materi_id = ? ORDER BY p.urutan, p.id""", (materi_id,)).fetchall():
        per_instansi[p["instansi_id"]].append(dict(p, terjawab=ada_isi(p["jawaban"])))
    for ins in instansi:
        ins["pertanyaan"] = per_instansi[ins["id"]]
    return instansi


def tambah_instansi(materi_id, nama):
    db = ambil_db()
    urutan = db.execute("SELECT COALESCE(MAX(urutan), 0) + 1 FROM materi_instansi WHERE materi_id = ?",
                        (materi_id,)).fetchone()[0]
    iid = db.execute("INSERT INTO materi_instansi (materi_id, urutan, nama) VALUES (?, ?, ?)",
                     (materi_id, urutan, nama)).lastrowid
    db.commit()
    tandai_diubah(materi_id)
    return iid


def geser_instansi(materi_id, instansi_id, arah):
    """Tukar urutan dengan instansi di atas ("naik") atau di bawahnya ("turun"). True bila bergeser."""
    db = ambil_db()
    urut = [b["id"] for b in db.execute("SELECT id FROM materi_instansi WHERE materi_id = ? ORDER BY urutan, id",
                                        (materi_id,))]
    if instansi_id not in urut:
        return False
    i = urut.index(instansi_id)
    j = i - 1 if arah == "naik" else i + 1 if arah == "turun" else i
    if j == i or not 0 <= j < len(urut):
        return False
    urut[i], urut[j] = urut[j], urut[i]
    db.executemany("UPDATE materi_instansi SET urutan = ? WHERE id = ?", [(n, iid) for n, iid in enumerate(urut, 1)])
    db.commit()
    tandai_diubah(materi_id)
    return True


def hapus_instansi(materi_id, instansi_id):
    db = ambil_db()
    db.execute("DELETE FROM materi_instansi WHERE id = ? AND materi_id = ?", (instansi_id, materi_id))
    db.commit()
    tandai_diubah(materi_id)


def simpan_instansi(materi_id, instansi_id, nama, selesai, pertanyaan):
    """Simpan nama, tanda selesai, dan SELURUH daftar pertanyaan sesuai urutan formulir.

    pertanyaan = [(id_lama atau None, teks, jawaban), ...]. Pertanyaan lama yang tidak dikirim lagi dihapus,
    yang baru ditambahkan. Semua dalam satu transaksi."""
    db = ambil_db()
    lama = {b["id"] for b in db.execute("SELECT id FROM materi_pertanyaan WHERE instansi_id = ?", (instansi_id,))}
    dipakai = set()
    with db:   # transaksi: commit bila berhasil, rollback bila galat
        db.execute("UPDATE materi_instansi SET nama = ?, selesai = ? WHERE id = ? AND materi_id = ?",
                   (nama, 1 if selesai else 0, instansi_id, materi_id))
        for urutan, (pid, teks, jawaban) in enumerate(pertanyaan, start=1):
            if pid in lama and pid not in dipakai:
                db.execute("UPDATE materi_pertanyaan SET urutan = ?, teks = ?, jawaban = ? WHERE id = ?",
                           (urutan, teks, jawaban, pid))
                dipakai.add(pid)
            else:
                db.execute("INSERT INTO materi_pertanyaan (instansi_id, urutan, teks, jawaban) VALUES (?, ?, ?, ?)",
                           (instansi_id, urutan, teks, jawaban))
        for pid in lama - dipakai:
            db.execute("DELETE FROM materi_pertanyaan WHERE id = ?", (pid,))
        db.execute("UPDATE materi_podcast SET diubah = datetime('now', 'localtime') WHERE id = ?", (materi_id,))


# ---------- Ekspor ----------
def nama_berkas(judul, keterangan):
    """Nama berkas Word yang aman untuk Windows: 'Judul - Keterangan.docx'."""
    dasar = rapikan(f"{judul} - {keterangan}" if rapikan(keterangan) else judul)
    dasar = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", dasar).strip(" .")[:150].strip(" .")
    return f"{dasar or 'Materi Podcast'}.docx"


def ekspor(materi):
    """Buat Word terbaru di instance/data/podcast/<id>/ekspor/ (hanya satu Word terbaru disimpan)."""
    instansi = muat_lengkap(materi["id"])
    folder = folder_materi(materi["id"]) / "ekspor"
    if folder.is_dir():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    tujuan = folder / nama_berkas(materi["judul"], materi["keterangan"])
    ekspor_word.buat_dokumen(dict(materi), instansi, tujuan)
    db = ambil_db()
    db.execute("UPDATE materi_podcast SET berkas_ekspor = ?, diekspor = datetime('now', 'localtime') WHERE id = ?",
               (tujuan.name, materi["id"]))
    db.commit()
    return tujuan


# ---------- Contoh ----------
def buat_contoh(pengguna_id=None):
    """Buat materi contoh FIKTIF (lihat contoh.py). Mengembalikan id materi."""
    from . import contoh

    materi_id = buat_materi(contoh.JUDUL, contoh.KETERANGAN, pengguna_id)
    for ins in contoh.INSTANSI:
        iid = tambah_instansi(materi_id, ins["nama"])
        simpan_instansi(materi_id, iid, ins["nama"], ins["selesai"],
                        [(None, teks, jawaban) for teks, jawaban in ins["pertanyaan"]])
    return materi_id
