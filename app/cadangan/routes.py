"""Halaman web Cadangan (/cadangan). Semua rute (kecuali formulir sandi) butuh "sesi cadangan" yang masih berlaku.

Sesi cadangan: session["cadangan_sampai"] = waktu habis (10 menit setelah sandi benar). Sandi maupun kunci turunannya
TIDAK disimpan di session (cookie Flask hanya ditandatangani, tidak dienkripsi).
"""
import time
from pathlib import Path

from flask import abort, current_app, flash, g, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash

from .. import log_proses
from ..db import ambil_db
from . import arsip, audit, bp, sandi as sandi_mod

MASA_BUKA_DETIK = 10 * 60
BATAS_WEB_BYTE = 300 * 1024 * 1024
PESAN_SANDI_GAGAL = "Kata sandi cadangan salah, atau akses sedang dikunci sementara. Coba lagi beberapa saat lagi."
TERBUKA_TANPA_SESI = {"cadangan.kunci", "cadangan.sandi_baru"}


# ---------- Bantuan ----------
def sekarang():
    return time.time()


def folder_cadangan():
    return Path(current_app.instance_path) / "cadangan"


def folder_berkas():
    folder = folder_cadangan() / "berkas"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def folder_templat():
    return current_app.config["FOLDER_TEMPLAT"]


def _pelaku():
    return f"web:{g.pengguna['nama_pengguna']}"


def _catat(aksi, hasil, rincian=""):
    """Dicatat dua kali: tabel Log (ikut tertimpa saat pemulihan) dan audit.log (tidak)."""
    log_proses.catat("cadangan", aksi, status=hasil, detail=rincian or None)
    audit.tulis(folder_cadangan(), aksi, _pelaku(), hasil, rincian)


def proses_berjalan():
    """Pesan bila ada proses latar yang belum selesai (cadangan bisa menangkap keadaan setengah jadi)."""
    if ambil_db().execute("SELECT 1 FROM spt_batch WHERE status = 'proses' LIMIT 1").fetchone():
        return "Ada batch Pemecah SPT yang masih diproses. Tunggu sampai selesai, lalu buat cadangan."
    return None


def _jalur_cadangan(nama):
    """Jalur ZIP HANYA untuk nama yang cocok pola ketat dan benar-benar berada di instance/cadangan/berkas/."""
    if not arsip.nama_sah(nama):
        abort(404)
    akar = folder_berkas().resolve()
    jalur = (akar / nama).resolve()
    if jalur.parent != akar or not jalur.is_file():
        abort(404)
    return jalur


def _terbuka():
    return session.get("cadangan_sampai", 0) > sekarang()


# ---------- Gerbang ----------
@bp.before_request
def gerbang():
    """Penjaga login (auth) sudah berjalan lebih dulu. Di sini: wajib sandi cadangan dibuat & sesi cadangan berlaku."""
    if not sandi_mod.ada_sandi(folder_cadangan()):
        if request.endpoint != "cadangan.sandi_baru":
            return redirect(url_for("cadangan.sandi_baru"))
        return None
    if request.endpoint == "cadangan.sandi_baru":
        return redirect(url_for("cadangan.index"))
    if request.endpoint in TERBUKA_TANPA_SESI:
        return None
    if not _terbuka():
        session.pop("cadangan_sampai", None)
        return redirect(url_for("cadangan.kunci"))
    return None


@bp.route("/sandi-baru", methods=["GET", "POST"])
def sandi_baru():
    galat = {}
    if request.method == "POST":
        sandi, konfirmasi = request.form.get("sandi", ""), request.form.get("konfirmasi", "")
        try:
            sandi_mod.periksa_syarat(sandi, konfirmasi)
            if check_password_hash(g.pengguna["sandi_hash"], sandi):
                raise sandi_mod.GalatSandi("Gunakan kata sandi yang berbeda dari kata sandi masuk.")
        except sandi_mod.GalatSandi as e:
            galat["sandi"] = str(e)
        if not galat:
            sandi_mod.atur_sandi(folder_cadangan(), sandi)
            session["cadangan_sampai"] = sekarang() + MASA_BUKA_DETIK
            _catat("Buat kata sandi cadangan", "sukses")
            flash("Kata sandi cadangan dibuat. Simpan di tempat aman: tanpanya cadangan tidak bisa dipulihkan.",
                  "sukses")
            return redirect(url_for("cadangan.index"))
        flash("Kata sandi cadangan belum dibuat. Periksa isian yang ditandai.", "galat")
    return render_template("cadangan/sandi_baru.html", galat=galat), (400 if galat else 200)


@bp.route("/kunci", methods=["GET", "POST"])
def kunci():
    if request.method == "GET" and _terbuka():
        return redirect(url_for("cadangan.index"))
    if request.method == "POST":
        if sandi_mod.verifikasi(folder_cadangan(), request.form.get("sandi", ""), sekarang()):
            session["cadangan_sampai"] = sekarang() + MASA_BUKA_DETIK
            audit.tulis(folder_cadangan(), "Buka halaman cadangan", _pelaku(), "sukses")
            return redirect(url_for("cadangan.index"))
        _catat("Buka halaman cadangan", "gagal", "kata sandi cadangan salah atau terkunci")
        flash(PESAN_SANDI_GAGAL, "galat")
        return render_template("cadangan/kunci.html"), 401
    return render_template("cadangan/kunci.html")


@bp.route("/kunci-kembali", methods=["POST"])
def kunci_kembali():
    session.pop("cadangan_sampai", None)
    flash("Halaman cadangan dikunci kembali.", "info")
    return redirect(url_for("utama.dashboard"))


# ---------- Halaman utama ----------
@bp.route("")
def index():
    return render_template("cadangan/index.html", daftar=arsip.daftar_cadangan(folder_berkas()),
                           jenis=arsip.JENIS, sisa_menit=max(1, round((session["cadangan_sampai"] - sekarang()) / 60)),
                           proses=proses_berjalan())


@bp.route("/buat", methods=["POST"])
def buat():
    jenis = request.form.get("jenis", "")
    if jenis not in ("lengkap", "database"):
        flash("Pilih jenis cadangan.", "galat")
        return redirect(url_for("cadangan.index"))
    if not sandi_mod.verifikasi(folder_cadangan(), request.form.get("sandi", ""), sekarang()):
        _catat("Buat cadangan", "gagal", "kata sandi cadangan salah atau terkunci")
        flash(PESAN_SANDI_GAGAL, "galat")
        return redirect(url_for("cadangan.index"))
    pesan = proses_berjalan()
    if pesan:
        flash(pesan, "galat")
        return redirect(url_for("cadangan.index"))
    try:
        hasil = arsip.buat_cadangan(instance=current_app.instance_path, folder_templat=folder_templat(),
                                    folder_tujuan=folder_berkas(), folder_kerja=folder_cadangan(), jenis=jenis,
                                    sandi=request.form.get("sandi", ""), batas_byte=BATAS_WEB_BYTE)
    except arsip.GalatCadangan as e:
        _catat("Buat cadangan", "gagal", str(e))
        flash(str(e), "galat")
        return redirect(url_for("cadangan.index"))
    _catat("Buat cadangan", "sukses", f"{hasil['nama']} ({hasil['jumlah_berkas']} berkas data)")
    flash(f"Cadangan dibuat: {hasil['nama']}", "sukses")
    return redirect(url_for("cadangan.index"))


@bp.route("/unduh/<nama>")
def unduh(nama):
    jalur = _jalur_cadangan(nama)
    audit.tulis(folder_cadangan(), "Unduh cadangan", _pelaku(), "sukses", nama)
    respons = send_file(jalur, as_attachment=True, download_name=nama, mimetype="application/zip")
    respons.headers["Cache-Control"] = "no-store"
    return respons


@bp.route("/uji/<nama>", methods=["POST"])
def uji(nama):
    jalur = _jalur_cadangan(nama)
    try:
        arsip.uji_keutuhan(jalur, folder_cadangan())
    except arsip.GalatArsip as e:
        arsip.simpan_hasil_uji(jalur, False, str(e))
        _catat("Uji cadangan", "gagal", f"{nama}: {e}")
        flash(f"{nama} gagal diuji: {e}", "galat")
    else:
        arsip.simpan_hasil_uji(jalur, True, "Utuh")
        _catat("Uji cadangan", "sukses", nama)
        flash(f"{nama} utuh: semua berkas cocok dan database lolos pemeriksaan.", "sukses")
    return redirect(url_for("cadangan.index"))


@bp.route("/hapus/<nama>", methods=["POST"])
def hapus(nama):
    jalur = _jalur_cadangan(nama)
    try:
        jalur.unlink()                                    # berkas dulu, baru pendampingnya
        arsip.jalur_pendamping(jalur).unlink(missing_ok=True)
    except OSError:
        _catat("Hapus cadangan", "gagal", f"{nama}: berkas sedang dipakai")
        flash(f"{nama} tidak dapat dihapus, mungkin sedang dibuka. Coba lagi.", "galat")
        return redirect(url_for("cadangan.index"))
    _catat("Hapus cadangan", "sukses", nama)
    flash(f"{nama} dihapus.", "sukses")
    return redirect(url_for("cadangan.index"))


@bp.route("/ganti-sandi", methods=["POST"])
def ganti_sandi():
    if not sandi_mod.verifikasi(folder_cadangan(), request.form.get("sandi_lama", ""), sekarang()):
        _catat("Ganti kata sandi cadangan", "gagal", "kata sandi lama salah atau terkunci")
        flash(PESAN_SANDI_GAGAL, "galat")
        return redirect(url_for("cadangan.index") + "#ganti-sandi")
    baru = request.form.get("sandi_baru", "")
    try:
        sandi_mod.periksa_syarat(baru, request.form.get("konfirmasi", ""))
        if check_password_hash(g.pengguna["sandi_hash"], baru):
            raise sandi_mod.GalatSandi("Gunakan kata sandi yang berbeda dari kata sandi masuk.")
    except sandi_mod.GalatSandi as e:
        flash(str(e), "galat")
        return redirect(url_for("cadangan.index") + "#ganti-sandi")
    sandi_mod.atur_sandi(folder_cadangan(), baru)
    _catat("Ganti kata sandi cadangan", "sukses")
    flash("Kata sandi cadangan diganti. Cadangan lama tetap dipulihkan dengan kata sandi lamanya.", "sukses")
    return redirect(url_for("cadangan.index"))
