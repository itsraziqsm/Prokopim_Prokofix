"""Kata sandi cadangan — logika murni tanpa Flask (dipakai web & terminal).

Disimpan di instance/cadangan/kunci.json (DI LUAR database, agar tidak ikut tertimpa saat pemulihan) sebagai
hash scrypt + salt + parameter. Sandinya sendiri dan kunci turunannya TIDAK pernah disimpan di mana pun.

Pembatas percobaan: 5 kali salah -> terkunci 5 menit (berulang bila terus salah). Statusnya disimpan di
instance/cadangan/percobaan.json agar tetap berlaku walau aplikasi dimulai ulang.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

PANJANG_MIN = 12
# Parameter scrypt (sama untuk kunci.json dan tanda tangan manifest)
PARAMETER_KDF = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}
BATAS_GAGAL = 5
LAMA_KUNCI_DETIK = 5 * 60


class GalatSandi(ValueError):
    """Sandi baru tidak memenuhi syarat; pesan aman untuk pengguna."""


# ---------- Penurunan kunci ----------
def turunkan_kunci(sandi, salt, n, r, p, dklen):
    """scrypt(sandi, salt) -> bytes. Dipakai untuk hash sandi & kunci HMAC tanda tangan cadangan."""
    return hashlib.scrypt(sandi.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=int(dklen),
                          maxmem=64 * 1024 * 1024)


def _b64(data):
    return base64.b64encode(data).decode("ascii")


def _dari_b64(teks):
    return base64.b64decode(teks.encode("ascii"), validate=True)


# ---------- Berkas ----------
def tulis_atomik(jalur, isi):
    """Tulis berkas JSON secara atomik (berkas sementara lalu os.replace) dengan izin hanya-pemilik bila didukung."""
    jalur = Path(jalur)
    jalur.parent.mkdir(parents=True, exist_ok=True)
    sementara = jalur.with_name(f".{jalur.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(sementara, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(isi, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(sementara, jalur)
    except BaseException:
        Path(sementara).unlink(missing_ok=True)
        raise
    try:
        os.chmod(jalur, 0o600)          # di Windows hanya memengaruhi atribut baca-saja; tidak masalah
    except OSError:
        pass


def _baca_json(jalur, bawaan):
    try:
        return json.loads(Path(jalur).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return bawaan


# ---------- Sandi ----------
def ada_sandi(folder):
    return (Path(folder) / "kunci.json").is_file()


def periksa_syarat(sandi, konfirmasi):
    """Melempar GalatSandi bila sandi baru tidak memenuhi syarat."""
    if len(sandi) < PANJANG_MIN:
        raise GalatSandi(f"Kata sandi cadangan minimal {PANJANG_MIN} karakter.")
    if sandi != konfirmasi:
        raise GalatSandi("Konfirmasi kata sandi cadangan tidak sama.")


def atur_sandi(folder, sandi):
    """Simpan hash scrypt sandi cadangan ke kunci.json (menimpa yang lama) dan hapus catatan percobaan."""
    salt = secrets.token_bytes(16)
    tulis_atomik(Path(folder) / "kunci.json", {
        "versi": 1, "algoritma": "scrypt", "salt": _b64(salt), **PARAMETER_KDF,
        "hash": _b64(turunkan_kunci(sandi, salt, **PARAMETER_KDF)),
    })
    reset_percobaan(folder)


def cocok(folder, sandi):
    """True bila sandi sama dengan hash di kunci.json (perbandingan waktu-konstan). TANPA pembatas percobaan."""
    data = _baca_json(Path(folder) / "kunci.json", None)
    if not data:
        return False
    try:
        salt, harapan = _dari_b64(data["salt"]), _dari_b64(data["hash"])
        hasil = turunkan_kunci(sandi, salt, data["n"], data["r"], data["p"], data["dklen"])
    except (KeyError, ValueError, TypeError):
        return False
    return hmac.compare_digest(hasil, harapan)


# ---------- Pembatas percobaan ----------
def _berkas_percobaan(folder):
    return Path(folder) / "percobaan.json"


def reset_percobaan(folder):
    _berkas_percobaan(folder).unlink(missing_ok=True)


def terkunci(folder, sekarang=None):
    sekarang = time.time() if sekarang is None else sekarang
    return _baca_json(_berkas_percobaan(folder), {}).get("terkunci_sampai", 0) > sekarang


def verifikasi(folder, sandi, sekarang=None):
    """True bila sandi benar DAN tidak sedang terkunci. Kegagalan dicatat; 5x salah -> terkunci 5 menit.
    Pemanggil menampilkan satu pesan yang sama untuk sandi salah maupun terkunci (tidak membedakan penyebab)."""
    sekarang = time.time() if sekarang is None else sekarang
    if terkunci(folder, sekarang):
        return False
    if cocok(folder, sandi):
        reset_percobaan(folder)
        return True
    data = _baca_json(_berkas_percobaan(folder), {})
    gagal = int(data.get("gagal", 0)) + 1
    if gagal >= BATAS_GAGAL:
        data = {"gagal": 0, "terkunci_sampai": sekarang + LAMA_KUNCI_DETIK}
    else:
        data = {"gagal": gagal, "terkunci_sampai": 0}
    tulis_atomik(_berkas_percobaan(folder), data)
    return False
