"""Sistem autentikasi: penyiapan akun pertama, masuk, keluar, ganti kata sandi.

Alur:
  1. Belum ada pengguna sama sekali  -> semua halaman diarahkan ke /siapkan (buat akun pertama).
  2. Sudah ada pengguna, belum masuk  -> diarahkan ke /masuk.
  3. Sudah masuk                      -> bebas membuka halaman.
"""
import os
import secrets
from urllib.parse import urlparse

import click
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import keamanan, log_proses
from .db import ambil_db

bp = Blueprint("auth", __name__)

PANJANG_SANDI_MIN = 8
# Halaman yang boleh dibuka tanpa masuk
ENDPOINT_PUBLIK = {"auth.masuk", "auth.siapkan", "static"}
# Hash palsu untuk menyamakan waktu respons saat nama pengguna tidak ada
_HASH_PALSU = generate_password_hash(secrets.token_hex(8))


# ---------- Gambar sisi kanan halaman masuk ----------
# Letakkan gambar di app/static/img/ dengan salah satu nama ini; bila tidak ada, tampil placeholder.
NAMA_GAMBAR_AUTH = ("masuk.jpg", "masuk.jpeg", "masuk.png", "masuk.webp")


@bp.app_context_processor
def _gambar_auth():
    def gambar_auth():
        for nama in NAMA_GAMBAR_AUTH:
            if os.path.exists(os.path.join(current_app.static_folder, "img", nama)):
                return url_for("static", filename=f"img/{nama}")
        return None
    return {"gambar_auth": gambar_auth}


# ---------- Fungsi bantu ----------
def ada_pengguna():
    return ambil_db().execute("SELECT 1 FROM pengguna LIMIT 1").fetchone() is not None


def cek_sandi_baru(sandi, konfirmasi):
    """Mengembalikan pesan galat, atau None bila sandi valid."""
    if len(sandi) < PANJANG_SANDI_MIN:
        return f"Kata sandi minimal {PANJANG_SANDI_MIN} karakter."
    if sandi != konfirmasi:
        return "Konfirmasi kata sandi tidak sama."
    return None


def tujuan_aman(tujuan):
    """Hanya izinkan pengalihan ke halaman di aplikasi ini (mencegah open redirect)."""
    if tujuan and tujuan.startswith("/") and not tujuan.startswith("//") and not urlparse(tujuan).netloc:
        return tujuan
    return url_for("utama.dashboard")


def masukkan_ke_sesi(pengguna, ingat=False):
    session.clear()  # cegah session fixation
    session["uid"] = pengguna["id"]
    session["token"] = pengguna["sesi_token"]
    session.permanent = bool(ingat)  # True = tetap masuk 30 hari; False = sampai browser ditutup


# ---------- Dijalankan sebelum SETIAP request ----------
@bp.before_app_request
def jaga_halaman():
    keamanan.periksa_csrf()

    # Muat pengguna yang sedang masuk (bila ada) ke g.pengguna
    g.pengguna = None
    uid = session.get("uid")
    if uid is not None:
        baris = ambil_db().execute("SELECT * FROM pengguna WHERE id = ?", (uid,)).fetchone()
        if baris and secrets.compare_digest(session.get("token", ""), baris["sesi_token"]):
            g.pengguna = baris
        else:
            session.clear()  # akun dihapus atau sandi diganti di tempat lain

    if request.endpoint in ENDPOINT_PUBLIK:
        return None
    if not ada_pengguna():
        return redirect(url_for("auth.siapkan"))
    if g.pengguna is None:
        tujuan = request.full_path.rstrip("?")
        return redirect(url_for("auth.masuk", next=tujuan if tujuan != "/" else None))
    return None


# ---------- Route ----------
@bp.route("/siapkan", methods=["GET", "POST"])
def siapkan():
    """Membuat akun pertama. Hanya tersedia selama belum ada pengguna."""
    if ada_pengguna():
        return redirect(url_for("auth.masuk"))

    galat, isian = {}, {}
    if request.method == "POST":
        isian = {
            "nama_lengkap": request.form.get("nama_lengkap", "").strip(),
            "nama_pengguna": request.form.get("nama_pengguna", "").strip(),
        }
        sandi = request.form.get("sandi", "")
        if not isian["nama_lengkap"]:
            galat["nama_lengkap"] = "Nama lengkap wajib diisi."
        if not isian["nama_pengguna"].replace(".", "").replace("_", "").isalnum():
            galat["nama_pengguna"] = "Gunakan huruf, angka, titik, atau garis bawah tanpa spasi."
        pesan = cek_sandi_baru(sandi, request.form.get("konfirmasi", ""))
        if pesan:
            galat["sandi"] = pesan

        if not galat:
            db = ambil_db()
            cur = db.execute(
                "INSERT INTO pengguna (nama_lengkap, nama_pengguna, sandi_hash, sesi_token) VALUES (?, ?, ?, ?)",
                (isian["nama_lengkap"], isian["nama_pengguna"],
                 generate_password_hash(sandi), secrets.token_hex(16)),
            )
            db.commit()
            pengguna = db.execute("SELECT * FROM pengguna WHERE id = ?", (cur.lastrowid,)).fetchone()
            masukkan_ke_sesi(pengguna)
            log_proses.catat("akun", "Akun dibuat", pengguna_id=pengguna["id"])
            flash("Akun berhasil dibuat. Selamat datang!", "sukses")
            return redirect(url_for("utama.dashboard"))

    if galat:
        flash("Periksa kembali isian yang ditandai.", "galat")
    return render_template("auth/siapkan.html", galat=galat, isian=isian), (400 if galat else 200)


@bp.route("/masuk", methods=["GET", "POST"])
def masuk():
    if not ada_pengguna():
        return redirect(url_for("auth.siapkan"))
    if g.pengguna is not None:
        return redirect(url_for("utama.dashboard"))

    tujuan = request.values.get("next", "")
    nama_pengguna, pesan_galat = "", None

    if request.method == "POST":
        nama_pengguna = request.form.get("nama_pengguna", "").strip()
        sandi = request.form.get("sandi", "")
        sisa = keamanan.sisa_kunci(nama_pengguna)
        if sisa:
            pesan_galat = f"Terlalu banyak percobaan gagal. Coba lagi dalam {sisa // 60 + 1} menit."
        else:
            db = ambil_db()
            pengguna = db.execute("SELECT * FROM pengguna WHERE nama_pengguna = ?", (nama_pengguna,)).fetchone()
            cocok = check_password_hash(pengguna["sandi_hash"] if pengguna else _HASH_PALSU, sandi)
            if pengguna and cocok:
                keamanan.hapus_catatan(nama_pengguna)
                db.execute("UPDATE pengguna SET login_terakhir = datetime('now', 'localtime') WHERE id = ?",
                           (pengguna["id"],))
                db.commit()
                masukkan_ke_sesi(pengguna, ingat=request.form.get("ingat") == "1")
                log_proses.catat("akun", "Masuk ke aplikasi", pengguna_id=pengguna["id"])
                return redirect(tujuan_aman(tujuan))
            keamanan.catat_gagal(nama_pengguna)
            if pengguna:  # catat agar pemilik akun tahu ada percobaan salah sandi
                log_proses.catat("akun", "Percobaan masuk gagal (kata sandi salah)",
                                 status="gagal", pengguna_id=pengguna["id"])
            # Pesan sengaja umum, agar tidak membocorkan nama pengguna mana yang terdaftar
            pesan_galat = "Nama pengguna atau kata sandi salah."

    if pesan_galat:
        flash(pesan_galat, "galat")  # tampil sebagai notifikasi pop-up
    return render_template("auth/masuk.html", nama_pengguna=nama_pengguna, tujuan=tujuan), \
        (401 if pesan_galat else 200)


@bp.route("/keluar", methods=["POST"])
def keluar():
    session.clear()
    flash("Anda telah keluar.", "info")
    return redirect(url_for("auth.masuk"))


@bp.route("/akun", methods=["GET", "POST"])
def akun():
    """Profil singkat & ganti kata sandi."""
    galat = {}
    if request.method == "POST":
        if not check_password_hash(g.pengguna["sandi_hash"], request.form.get("sandi_lama", "")):
            galat["sandi_lama"] = "Kata sandi saat ini salah."
        pesan = cek_sandi_baru(request.form.get("sandi_baru", ""), request.form.get("konfirmasi", ""))
        if pesan:
            galat["sandi_baru"] = pesan
        if galat:
            flash("Kata sandi belum diganti. Periksa isian yang ditandai.", "galat")
        else:
            token_baru = secrets.token_hex(16)  # sesi lain di browser/perangkat lain otomatis keluar
            db = ambil_db()
            db.execute("UPDATE pengguna SET sandi_hash = ?, sesi_token = ? WHERE id = ?",
                       (generate_password_hash(request.form["sandi_baru"]), token_baru, g.pengguna["id"]))
            db.commit()
            session["token"] = token_baru  # sesi ini tetap masuk
            log_proses.catat("akun", "Kata sandi diganti")
            flash("Kata sandi berhasil diganti.", "sukses")
            return redirect(url_for("auth.akun"))
    return render_template("auth/akun.html", galat=galat), (400 if galat else 200)


# ---------- Perintah terminal: lupa kata sandi ----------
@bp.cli.command("reset-sandi")
@click.argument("nama_pengguna")
def reset_sandi(nama_pengguna):
    """Atur ulang kata sandi.  Pemakaian:  flask --app run auth reset-sandi admin"""
    db = ambil_db()
    pengguna = db.execute("SELECT id FROM pengguna WHERE nama_pengguna = ?", (nama_pengguna,)).fetchone()
    if not pengguna:
        raise click.ClickException(f"Pengguna '{nama_pengguna}' tidak ditemukan.")
    sandi = click.prompt("Kata sandi baru", hide_input=True, confirmation_prompt="Ulangi kata sandi")
    if len(sandi) < PANJANG_SANDI_MIN:
        raise click.ClickException(f"Kata sandi minimal {PANJANG_SANDI_MIN} karakter.")
    db.execute("UPDATE pengguna SET sandi_hash = ?, sesi_token = ? WHERE id = ?",
               (generate_password_hash(sandi), secrets.token_hex(16), pengguna["id"]))
    db.commit()
    click.echo("Kata sandi berhasil diatur ulang.")
