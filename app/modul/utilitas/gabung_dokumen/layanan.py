"""Akses data Gabungkan PDF: sesi penyusunan sementara, unggahan, hasil di database, jalur berkas yang aman.

Sesi penyusunan:  instance/tmp/gabung_dokumen/<token>/  berisi <id>.pdf (nama acak) + sesi.json
                  (pemilik, urutan, rentang, nama asli untuk tampilan). Dihapus otomatis setelah 24 jam.
Hasil permanen:   instance/data/gabung_dokumen/<id_hasil>/<nama berkas hasil>.pdf  + baris tabel gabung_hasil.
"""
import json
import re
import secrets
import shutil
import time
from pathlib import Path

from flask import current_app

from ....db import ambil_db
from ....waktu import tanggal_tanpa_hari
from . import penggabung

MAKS_BYTE_BERKAS = 50 * 1024 * 1024      # per file
MAKS_BYTE_SESI = 200 * 1024 * 1024       # semua file dalam satu penyusunan
MAKS_BERKAS = 30
MAKS_HALAMAN = 2000                      # jumlah halaman semua file dalam satu penyusunan
UMUR_SESI_DETIK = 24 * 60 * 60
_POLA_TOKEN = re.compile(r"[A-Za-z0-9_-]{20,64}")
_POLA_ID_BERKAS = re.compile(r"[0-9a-f]{16}")


class GalatHapus(Exception):
    """Pesan aman untuk pengguna saat hasil tidak dapat dihapus."""


# ---------- Folder ----------
def folder_tmp():
    folder = Path(current_app.instance_path) / "tmp" / "gabung_dokumen"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def folder_data():
    """instance/data/gabung_dokumen — semua PDF hasil di bawah folder ini."""
    folder = Path(current_app.instance_path) / "data" / "gabung_dokumen"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def nama_bawaan():
    """'Gabungan 17 November 2026.pdf' (tanggal hari ini, format Indonesia)."""
    return f"Gabungan {tanggal_tanpa_hari()}.pdf"


# ---------- Sesi penyusunan ----------
def _folder_sesi(token):
    if not token or not _POLA_TOKEN.fullmatch(token):
        return None
    return folder_tmp() / token


def bersihkan_sesi_lama():
    """Hapus folder sesi penyusunan yang lebih dari 24 jam (dipanggil saat halaman awal dibuka)."""
    batas = time.time() - UMUR_SESI_DETIK
    for folder in folder_tmp().iterdir():
        try:
            if folder.is_dir() and _POLA_TOKEN.fullmatch(folder.name) and folder.stat().st_mtime < batas:
                shutil.rmtree(folder)
        except OSError:
            pass


def buat_sesi(pengguna_id):
    """Sesi baru dengan token acak yang terikat ke pengguna. Mengembalikan (token, sesi)."""
    token = secrets.token_urlsafe(24)
    _folder_sesi(token).mkdir(parents=True)
    sesi = {"pengguna_id": pengguna_id, "dibuat": time.time(), "berkas": [],
            "nama_hasil": nama_bawaan(), "daftar_isi": True}
    simpan_sesi(token, sesi)
    return token, sesi


def simpan_sesi(token, sesi):
    folder = _folder_sesi(token)
    (folder / "sesi.json").write_text(json.dumps(sesi, ensure_ascii=False), encoding="utf-8")
    folder.touch()            # waktu ubah folder = aktivitas terakhir (untuk pembersihan 24 jam)


def baca_sesi(token, pengguna_id):
    """Sesi milik pengguna, atau None (token salah, kedaluwarsa, atau milik pengguna lain)."""
    folder = _folder_sesi(token)
    if folder is None or not (folder / "sesi.json").is_file():
        return None
    try:
        sesi = json.loads((folder / "sesi.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if sesi.get("pengguna_id") != pengguna_id:
        return None
    if time.time() - folder.stat().st_mtime > UMUR_SESI_DETIK:
        hapus_sesi(token)
        return None
    return sesi


def hapus_sesi(token):
    folder = _folder_sesi(token)
    if folder is not None and folder.is_dir() and folder.parent == folder_tmp():
        shutil.rmtree(folder, ignore_errors=True)


def jalur_sumber(token, berkas):
    """Jalur PDF sumber dalam sesi; id berkas divalidasi agar tidak bisa keluar dari folder sesi."""
    if not _POLA_ID_BERKAS.fullmatch(berkas.get("id", "")):
        return None
    return _folder_sesi(token) / f"{berkas['id']}.pdf"


def _simpan_unggahan(unggahan, tujuan, sisa_byte):
    """Tulis unggahan ke disk sedikit demi sedikit. Mengembalikan ukuran, atau pesan galat (str)."""
    batas = min(MAKS_BYTE_BERKAS, sisa_byte)
    ukuran = 0
    awal = b""
    with open(tujuan, "wb") as keluar:
        while True:
            potongan = unggahan.stream.read(1024 * 1024)
            if not potongan:
                break
            if len(awal) < 1024:
                awal += potongan[:1024 - len(awal)]
                if len(awal) >= 1024 and not penggabung.tanda_pdf(awal):
                    break
            ukuran += len(potongan)
            if ukuran > batas:
                break
            keluar.write(potongan)
    if not penggabung.tanda_pdf(awal):
        return "bukan berkas PDF"
    if ukuran > MAKS_BYTE_BERKAS:
        return "lebih dari 50 MB"
    if ukuran > batas:
        return "total ukuran penyusunan melebihi 200 MB"
    return ukuran


def tambah_berkas(token, sesi, daftar_unggahan):
    """Tambahkan unggahan ke sesi. Setiap berkas diperiksa sendiri-sendiri; berkas yang ditolak
    tidak membatalkan yang lain. Mengembalikan (jumlah_ditambah, [pesan penolakan])."""
    ditolak, ditambah = [], 0
    for unggahan in daftar_unggahan:
        nama = Path((unggahan.filename or "").replace("\\", "/")).name[:200] or "berkas"   # hanya untuk tampilan
        if Path(nama).suffix.lower() not in penggabung.EKSTENSI_DIDUKUNG:
            ditolak.append(f"{nama}: bukan berkas PDF")
            continue
        if len(sesi["berkas"]) >= MAKS_BERKAS:
            ditolak.append(f"{nama}: melebihi batas {MAKS_BERKAS} file per penggabungan")
            continue
        id_berkas = secrets.token_hex(8)
        tujuan = _folder_sesi(token) / f"{id_berkas}.pdf"
        terpakai = sum(b["ukuran"] for b in sesi["berkas"])
        hasil = _simpan_unggahan(unggahan, tujuan, MAKS_BYTE_SESI - terpakai)
        if isinstance(hasil, str):
            tujuan.unlink(missing_ok=True)
            ditolak.append(f"{nama}: {hasil}")
            continue
        try:
            halaman = penggabung.periksa_pdf(tujuan)
        except penggabung.GalatBerkas as e:
            tujuan.unlink(missing_ok=True)
            ditolak.append(f"{nama}: {e}")
            continue
        if sum(b["halaman"] for b in sesi["berkas"]) + halaman > MAKS_HALAMAN:
            tujuan.unlink(missing_ok=True)
            ditolak.append(f"{nama}: total halaman melebihi {MAKS_HALAMAN}")
            continue
        sesi["berkas"].append({"id": id_berkas, "nama": nama, "ukuran": hasil, "halaman": halaman, "rentang": ""})
        ditambah += 1
    simpan_sesi(token, sesi)
    return ditambah, ditolak


def simpan_isian(sesi, form):
    """Simpan rentang per file, nama berkas hasil, dan kotak daftar isi dari formulir penyusunan."""
    for b in sesi["berkas"]:
        kunci = f"rentang_{b['id']}"
        if kunci in form:
            b["rentang"] = form.get(kunci, "")[:200]
    if "nama_hasil" in form:
        sesi["nama_hasil"] = form.get("nama_hasil", "")[:200]
    if "daftar_isi_dikirim" in form:          # kotak centang tidak terkirim bila kosong
        sesi["daftar_isi"] = form.get("daftar_isi") == "1"


def periksa_rentang(sesi):
    """(galat_per_berkas {id: pesan}, halaman_per_berkas {id: [indeks]})."""
    galat, pilihan = {}, {}
    for b in sesi["berkas"]:
        try:
            pilihan[b["id"]] = penggabung.urai_rentang(b["rentang"], b["halaman"])
        except penggabung.GalatRentang as e:
            galat[b["id"]] = f"{b['nama']}: {e}."
    return galat, pilihan


def geser_berkas(sesi, id_berkas, arah):
    urut = sesi["berkas"]
    i = next((n for n, b in enumerate(urut) if b["id"] == id_berkas), None)
    if i is None:
        return False
    j = i - 1 if arah == "naik" else i + 1 if arah == "turun" else i
    if j == i or not 0 <= j < len(urut):
        return False
    urut[i], urut[j] = urut[j], urut[i]
    return True


def hapus_berkas_sesi(token, sesi, id_berkas):
    berkas = next((b for b in sesi["berkas"] if b["id"] == id_berkas), None)
    if berkas is None:
        return None
    jalur = jalur_sumber(token, berkas)
    if jalur is not None:
        jalur.unlink(missing_ok=True)
    sesi["berkas"].remove(berkas)
    return berkas


# ---------- Hasil ----------
def gabungkan(token, sesi, pengguna_id, pilihan):
    """Gabungkan semua berkas sesi menjadi satu PDF hasil; sesi dihapus setelah berhasil (tidak bisa
    digabung dua kali). Mengembalikan baris hasil. Pengecualian diteruskan setelah folder & rekaman dibersihkan."""
    db = ambil_db()
    kur = db.execute("INSERT INTO gabung_hasil (pengguna_id, nama_berkas, jumlah_berkas) VALUES (?, '', ?)",
                     (pengguna_id, len(sesi["berkas"])))
    hasil_id = kur.lastrowid
    folder = folder_data() / str(hasil_id)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        nama = penggabung.nama_berkas_hasil(sesi["nama_hasil"], [p.name for p in folder.iterdir()], nama_bawaan())
        sumber = [{"jalur": jalur_sumber(token, b), "halaman": pilihan[b["id"]], "judul": Path(b["nama"]).stem}
                  for b in sesi["berkas"]]
        tujuan = folder / nama
        halaman = penggabung.gabungkan(sumber, tujuan, Path(nama).stem, sesi["daftar_isi"])
        db.execute("UPDATE gabung_hasil SET nama_berkas = ?, jumlah_halaman = ?, ukuran = ?, folder = ? WHERE id = ?",
                   (nama, halaman, tujuan.stat().st_size, str(folder.resolve()), hasil_id))
        db.commit()
    except Exception:
        db.rollback()
        shutil.rmtree(folder, ignore_errors=True)
        raise
    hapus_sesi(token)
    return ambil_hasil(pengguna_id, hasil_id)


def daftar_hasil(pengguna_id, batas=50):
    return ambil_db().execute("SELECT * FROM gabung_hasil WHERE pengguna_id = ? ORDER BY id DESC LIMIT ?",
                              (pengguna_id, batas)).fetchall()


def ambil_hasil(pengguna_id, hasil_id):
    return ambil_db().execute("SELECT * FROM gabung_hasil WHERE id = ? AND pengguna_id = ?",
                              (hasil_id, pengguna_id)).fetchone()


def folder_hasil_aman(hasil):
    """Folder hasil HANYA bila persis instance/data/gabung_dokumen/<id>; selain itu None."""
    if not hasil["folder"]:
        return None
    folder = Path(hasil["folder"]).resolve()
    if folder.parent != folder_data().resolve() or folder.name != str(hasil["id"]):
        return None
    return folder


def jalur_hasil_aman(hasil):
    """Jalur PDF hasil dari rekaman DB; None bila kosong, di luar folder hasil ini, atau tidak ada."""
    folder = folder_hasil_aman(hasil)
    if folder is None or not hasil["nama_berkas"]:
        return None
    jalur = (folder / hasil["nama_berkas"]).resolve()
    if jalur.parent != folder or not jalur.is_file():
        return None
    return jalur


def hapus_hasil(hasil):
    """Hapus berkas dulu, baru rekamannya. Bila berkas terkunci, rekaman dipertahankan."""
    folder = folder_hasil_aman(hasil)
    if folder is not None and folder.is_dir():
        try:
            shutil.rmtree(folder)
        except OSError:
            raise GalatHapus(f"{hasil['nama_berkas']}: berkas tidak dapat dihapus, mungkin sedang dibuka.")
    db = ambil_db()
    db.execute("DELETE FROM gabung_hasil WHERE id = ?", (hasil["id"],))
    db.commit()
