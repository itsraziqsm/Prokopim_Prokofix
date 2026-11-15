"""Perlindungan dasar: token CSRF dan pembatasan percobaan login.

CSRF = serangan yang membuat browser Anda mengirim formulir tanpa sepengetahuan Anda.
Setiap formulir POST wajib menyertakan {{ csrf_field() }}; token dicek di sini.
"""
import hmac
import secrets
import time

from flask import abort, request, session
from markupsafe import Markup


# ---------- CSRF ----------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def csrf_field():
    """Input tersembunyi untuk dimasukkan ke setiap <form method="post">."""
    return Markup(f'<input type="hidden" name="csrf_token" value="{csrf_token()}">')


def periksa_csrf():
    """Dipanggil sebelum setiap request; menolak POST tanpa token yang cocok."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        dikirim = request.form.get("csrf_token", "")
        disimpan = session.get("_csrf", "")
        if not disimpan or not hmac.compare_digest(dikirim, disimpan):
            abort(400, description="Formulir kedaluwarsa atau tidak sah. Muat ulang halaman lalu coba lagi.")


# ---------- Pembatasan percobaan login ----------
# Disimpan di memori: cukup untuk aplikasi lokal; ter-reset saat server dimulai ulang.
BATAS_GAGAL = 5             # jumlah salah sandi yang diizinkan
JENDELA_DETIK = 15 * 60     # dihitung dalam rentang 15 menit
KUNCI_DETIK = 5 * 60        # lama terkunci

_gagal = {}  # kunci -> daftar waktu gagal


def _kunci(nama_pengguna):
    return f"{request.remote_addr}|{(nama_pengguna or '').lower()}"


def sisa_kunci(nama_pengguna):
    """Detik tersisa sebelum boleh mencoba lagi (0 = tidak terkunci)."""
    sekarang = time.time()
    daftar = [t for t in _gagal.get(_kunci(nama_pengguna), []) if sekarang - t < JENDELA_DETIK]
    _gagal[_kunci(nama_pengguna)] = daftar
    if len(daftar) >= BATAS_GAGAL:
        return max(0, int(daftar[-1] + KUNCI_DETIK - sekarang))
    return 0


def catat_gagal(nama_pengguna):
    _gagal.setdefault(_kunci(nama_pengguna), []).append(time.time())


def hapus_catatan(nama_pengguna):
    _gagal.pop(_kunci(nama_pengguna), None)
