"""Database untuk cadangan — logika murni tanpa Flask.

    salin_snapshot()       salinan KONSISTEN lewat sqlite3 backup API (bukan menyalin berkas .db), lalu jalur absolut
                           di salinan diubah menjadi relatif terhadap folder instance ("{instance}/data/spt/3")
    ke_relatif/ke_absolut  pengubah jalur (gaya Windows "C:\\..." dan POSIX "/home/...")
    validasi_db()          pemeriksaan database dari cadangan sebelum dipulihkan
    siapkan_untuk_pasang() jalur relatif -> absolut sesuai instance tujuan + putar ulang token sesi semua pengguna

Kolom yang menyimpan jalur absolut (diperiksa dengan grep pada seluruh kode, lihat KOLOM_JALUR). Kolom lain hanya
menyimpan NAMA berkas; foldernya dihitung dari data (mis. tanggal liputan, id materi).
"""
import re
import secrets
import sqlite3
from functools import lru_cache
from pathlib import Path

from ..db import KOLOM_SUSULAN, SKEMA

KOLOM_JALUR = {"log_proses": ("lokasi",), "spt_batch": ("folder",), "gabung_hasil": ("folder",)}
PENANDA = "{instance}"
# Tabel yang hitungannya dicatat di manifest & ditampilkan di pratinjau pemulihan
TABEL_UTAMA = ("pengguna", "log_proses", "spt_batch", "spt", "liputan", "liputan_foto", "materi_podcast",
               "materi_instansi", "materi_pertanyaan", "gabung_hasil")
LABEL_TABEL = {"pengguna": "pengguna", "log_proses": "catatan log", "spt_batch": "batch SPT", "spt": "SPT",
               "liputan": "liputan", "liputan_foto": "foto liputan", "materi_podcast": "materi podcast",
               "materi_instansi": "instansi materi", "materi_pertanyaan": "pertanyaan materi",
               "gabung_hasil": "hasil gabung PDF"}
_TABEL_SISTEM = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}


class GalatBasisData(Exception):
    """Database cadangan tidak lolos pemeriksaan; pesan aman untuk pengguna."""


# ---------- Jalur ----------
def _gaya_windows(teks):
    return bool(re.match(r"^[A-Za-z]:[\\/]", teks)) or teks.startswith("\\\\")


def ke_relatif(nilai, akar_daftar):
    """'C:\\App\\instance\\data\\spt\\3' -> '{instance}/data/spt/3' bila diawali salah satu akar instance.
    Windows: tanpa beda huruf besar/kecil, \\ dan / dianggap sama. Nilai lain dikembalikan apa adanya."""
    if not isinstance(nilai, str) or not nilai:
        return nilai
    for akar in akar_daftar:
        akar = str(akar)
        if not akar:
            continue
        if _gaya_windows(nilai) and _gaya_windows(akar):
            n, a = nilai.replace("\\", "/"), akar.replace("\\", "/").rstrip("/")
            cocok = n.lower() == a.lower() or n.lower().startswith(a.lower() + "/")
        elif not _gaya_windows(nilai) and not _gaya_windows(akar):
            n, a = nilai, akar.rstrip("/")
            cocok = n == a or n.startswith(a + "/")
        else:
            continue
        if cocok:
            sisa = n[len(a):].strip("/")
            return PENANDA + ("/" + sisa if sisa else "")
    return nilai


def ke_absolut(nilai, akar):
    """'{instance}/data/spt/3' -> akar + data/spt/3 dengan pemisah sesuai gaya akar (\\ untuk Windows)."""
    if not isinstance(nilai, str) or not (nilai == PENANDA or nilai.startswith(PENANDA + "/")):
        return nilai
    akar = str(akar)
    pemisah = "\\" if _gaya_windows(akar) else "/"
    sisa = nilai[len(PENANDA):].strip("/")
    dasar = akar.rstrip("/\\") or pemisah
    return dasar + (pemisah + sisa.replace("/", pemisah) if sisa else "")


def _ubah_kolom_jalur(koneksi, fungsi):
    for tabel, daftar_kolom in KOLOM_JALUR.items():
        ada = {b[1] for b in koneksi.execute(f"PRAGMA table_info({tabel})")}
        for kolom in daftar_kolom:
            if kolom not in ada:
                continue
            baris = koneksi.execute(f"SELECT rowid, {kolom} FROM {tabel} WHERE {kolom} IS NOT NULL").fetchall()
            perubahan = [(fungsi(nilai), rowid) for rowid, nilai in baris if fungsi(nilai) != nilai]
            koneksi.executemany(f"UPDATE {tabel} SET {kolom} = ? WHERE rowid = ?", perubahan)


# ---------- Koneksi ----------
def buka_baca_saja(jalur):
    """Koneksi baca-saja yang tidak menjalankan fungsi dari skema (trusted_schema=OFF)."""
    koneksi = sqlite3.connect(f"{Path(jalur).resolve().as_uri()}?mode=ro", uri=True)
    koneksi.execute("PRAGMA trusted_schema = OFF")
    return koneksi


# ---------- Snapshot ----------
def salin_snapshot(sumber, tujuan, akar_instance):
    """Salinan konsisten database hidup ke `tujuan` (backup API), lalu jalur absolut -> relatif HANYA di salinan."""
    asal = sqlite3.connect(str(sumber))
    try:
        hasil = sqlite3.connect(str(tujuan))
        try:
            asal.backup(hasil)
            hasil.execute("PRAGMA journal_mode = DELETE")
            _ubah_kolom_jalur(hasil, lambda v: ke_relatif(v, akar_instance))
            hasil.commit()
        finally:
            hasil.close()
    finally:
        asal.close()


def hitung_baris(koneksi):
    """{tabel: jumlah baris} untuk TABEL_UTAMA yang ada."""
    ada = {b[0] for b in koneksi.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return {t: koneksi.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABEL_UTAMA if t in ada}


def ringkas_skema(koneksi):
    """{tabel: [kolom, ...]} untuk semua tabel pengguna (bukan tabel sistem SQLite)."""
    tabel = [b[0] for b in koneksi.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    return {t: [b[1] for b in koneksi.execute(f"PRAGMA table_info({t})")] for t in tabel if t not in _TABEL_SISTEM}


@lru_cache(maxsize=1)
def skema_dikenal():
    """Skema yang dikenal kode ini: SKEMA + KOLOM_SUSULAN, dibangun di database memori."""
    koneksi = sqlite3.connect(":memory:")
    try:
        koneksi.executescript(SKEMA)
        for tabel, kolom in KOLOM_SUSULAN.items():
            ada = {b[1] for b in koneksi.execute(f"PRAGMA table_info({tabel})")}
            for nama, tipe in kolom.items():
                if nama not in ada:
                    koneksi.execute(f"ALTER TABLE {tabel} ADD COLUMN {nama} {tipe}")
        return {t: frozenset(k) for t, k in ringkas_skema(koneksi).items()}
    finally:
        koneksi.close()


def integritas_ok(jalur):
    koneksi = buka_baca_saja(jalur)
    try:
        return koneksi.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    finally:
        koneksi.close()


# ---------- Validasi database dari cadangan ----------
def validasi_db(jalur):
    """Periksa database cadangan. Melempar GalatBasisData; mengembalikan hitungan baris bila lolos.

    Ditolak: integrity_check gagal, pelanggaran foreign key, trigger, view, tabel virtual, tabel/kolom yang tidak
    dikenal kode ini (termasuk skema yang lebih baru). Skema yang lebih LAMA (kolom susulan belum ada) diterima;
    kolom itu ditambahkan otomatis oleh db.siapkan_db saat aplikasi dinyalakan."""
    try:
        koneksi = buka_baca_saja(jalur)
    except sqlite3.Error:
        raise GalatBasisData("Database cadangan tidak dapat dibuka.")
    try:
        try:
            if koneksi.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise GalatBasisData("Database cadangan rusak (integrity_check gagal).")
            if koneksi.execute("PRAGMA foreign_key_check").fetchall():
                raise GalatBasisData("Database cadangan berisi rujukan antar-tabel yang rusak.")
            objek = koneksi.execute("SELECT type, name, tbl_name, sql FROM sqlite_master").fetchall()
        except sqlite3.DatabaseError:
            raise GalatBasisData("Database cadangan rusak atau bukan database SQLite.")
        dikenal = skema_dikenal()
        for jenis, nama, tabel, sql in objek:
            if jenis in ("trigger", "view"):
                raise GalatBasisData(f"Database cadangan berisi {jenis} yang tidak dikenal aplikasi ({nama}).")
            if jenis == "index":
                if tabel not in dikenal:
                    raise GalatBasisData(f"Database cadangan berisi indeks untuk tabel asing ({tabel}).")
                continue
            if jenis != "table":
                raise GalatBasisData(f"Database cadangan berisi objek yang tidak dikenal ({nama}).")
            if nama in _TABEL_SISTEM:
                continue
            if sql and re.match(r"\s*CREATE\s+VIRTUAL", sql, re.I):
                raise GalatBasisData(f"Database cadangan berisi tabel virtual ({nama}).")
            if nama not in dikenal:
                raise GalatBasisData(f"Database cadangan berisi tabel yang tidak dikenal versi aplikasi ini ({nama}).")
            kolom = {b[1] for b in koneksi.execute(f'PRAGMA table_info("{nama}")')}
            asing = kolom - dikenal[nama]
            if asing:
                raise GalatBasisData(f"Database cadangan dibuat oleh versi aplikasi yang lebih baru "
                                     f"(kolom {nama}.{sorted(asing)[0]} tidak dikenal).")
        return hitung_baris(koneksi)
    finally:
        koneksi.close()


def siapkan_untuk_pasang(jalur, akar_tujuan):
    """Di salinan yang akan dipasang: jalur relatif -> absolut sesuai instance tujuan, lalu putar ulang token sesi
    SEMUA pengguna agar cookie sesi lama (dari aplikasi mana pun) tidak lagi valid."""
    koneksi = sqlite3.connect(str(jalur))
    try:
        _ubah_kolom_jalur(koneksi, lambda v: ke_absolut(v, akar_tujuan))
        ids = [b[0] for b in koneksi.execute("SELECT id FROM pengguna")]
        koneksi.executemany("UPDATE pengguna SET sesi_token = ? WHERE id = ?",
                            [(secrets.token_hex(16), i) for i in ids])
        koneksi.commit()
    finally:
        koneksi.close()
