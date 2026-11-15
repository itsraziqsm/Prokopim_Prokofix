"""Perlindungan formulir dengan token CSRF.

CSRF = serangan yang membuat browser Anda mengirim formulir tanpa sepengetahuan Anda.
Setiap formulir POST wajib menyertakan {{ csrf_field() }}; token dicek di sini.
"""
import hmac
import secrets

from flask import abort, request, session
from markupsafe import Markup


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
