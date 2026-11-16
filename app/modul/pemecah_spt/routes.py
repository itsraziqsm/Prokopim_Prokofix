"""Halaman web Pemecah SPT (alamat diawali /spt).

Alur: unggah (/spt) -> analisis (POST /spt/analisis) -> pratinjau (/spt/pratinjau/<token>)
      -> proses (POST /spt/proses, berjalan di latar) -> hasil batch (/spt/batch/<id>, progres lewat
      /spt/batch/<id>/status) -> unduh per berkas / ZIP.
"""
import io
import zipfile
from dataclasses import asdict
from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request,
                   send_file, url_for)

from ... import log_proses
from . import layanan, pdf, pekerja
from .pemecah import GalatBerkas, HasilAnalisis, analisis, rapikan, validasi_berkas
from .penamaan import beri_nama

bp = Blueprint("pemecah_spt", __name__, url_prefix="/spt")

ID_MODUL = "pemecah_spt"
FORMAT_SAH = tuple(layanan.FORMAT_LABEL)


@bp.app_template_global()
def label_format(kode):
    return layanan.FORMAT_LABEL.get(kode, kode)


# ---------- 1. Unggah ----------
@bp.route("")
def index():
    return render_template(
        "pemecah_spt/index.html",
        riwayat=layanan.daftar_batch(g.pengguna["id"]),
        pengonversi=pdf.pengonversi_tersedia(),
    )


@bp.route("/analisis", methods=["POST"])
def analisis_berkas():
    berkas = request.files.get("berkas")
    format_keluaran = request.form.get("format", "word")
    if format_keluaran not in FORMAT_SAH:
        format_keluaran = "word"
    if berkas is None or not berkas.filename:
        flash("Pilih berkas .docx terlebih dahulu.", "galat")
        return redirect(url_for(".index"))

    # Nama dari klien hanya untuk tampilan: dirapikan & dipotong, tidak dipakai di disk
    nama_asli = rapikan(Path(berkas.filename.replace("\\", "/")).name)[:200] or "berkas.docx"
    token = layanan.simpan_sementara(berkas, nama_asli, format_keluaran, g.pengguna["id"])
    meta = layanan.baca_sementara(token, g.pengguna["id"])
    try:
        validasi_berkas(meta["jalur"], nama_asli)
        hasil = analisis(meta["jalur"])
    except GalatBerkas as e:
        layanan.hapus_sementara(token)
        log_proses.catat(ID_MODUL, "Analisis batch", status="gagal", detail=f"{nama_asli}: {e}")
        flash(str(e), "galat")
        return redirect(url_for(".index"))

    nama = beri_nama([i.nomor for i in hasil.daftar])
    for info, n in zip(hasil.daftar, nama):
        info.nama = n
    layanan.simpan_analisis(token, hasil.ke_dict())
    log_proses.catat(ID_MODUL, "Analisis batch", detail=f"{nama_asli}: {len(hasil.daftar)} SPT ditemukan")
    return redirect(url_for(".pratinjau", token=token))


# ---------- 2. Pratinjau ----------
def _ambil_unggahan(token):
    meta = layanan.baca_sementara(token, g.pengguna["id"])
    if meta is None or not meta.get("analisis"):
        flash("Pratinjau sudah kedaluwarsa atau tidak ditemukan. Unggah ulang berkasnya.", "galat")
        return None
    return meta


@bp.route("/pratinjau/<token>")
def pratinjau(token):
    meta = _ambil_unggahan(token)
    if meta is None:
        return redirect(url_for(".index"))
    return render_template("pemecah_spt/pratinjau.html", token=token, meta=meta,
                           hasil=HasilAnalisis.dari_dict(meta["analisis"]),
                           pengonversi=pdf.pengonversi_tersedia())


# ---------- 3. Proses ----------
@bp.route("/proses", methods=["POST"])
def proses():
    """Membuat batch lalu menjalankan pemrosesan di latar; pengguna langsung diarahkan ke halaman hasil
    yang menampilkan progres."""
    token = request.form.get("token", "")
    meta = _ambil_unggahan(token)
    if meta is None:
        return redirect(url_for(".index"))
    hasil = HasilAnalisis.dari_dict(meta["analisis"])
    dipilih = {int(u) for u in request.form.getlist("pilih") if u.isdigit()}
    daftar = [i for i in hasil.daftar if i.urutan in dipilih]
    if not daftar:
        flash("Centang minimal satu SPT untuk diproses.", "galat")
        return redirect(url_for(".pratinjau", token=token))

    format_keluaran = meta["format"]
    langkah = len(daftar) * (2 if format_keluaran in ("pdf", "keduanya") else 1)
    batch_id, folder = layanan.buat_batch(g.pengguna["id"], meta["nama_asli"], format_keluaran, langkah)
    sumber = layanan.ambil_alih_sementara(token, batch_id)
    pekerja.jalankan_latar(current_app._get_current_object(), batch_id, g.pengguna["id"],
                           sumber, [asdict(i) for i in daftar], folder, format_keluaran)
    return redirect(url_for(".batch", batch_id=batch_id))


# ---------- 4. Hasil ----------
def _batch_milik_pengguna(batch_id):
    batch = layanan.ambil_batch(g.pengguna["id"], batch_id)
    if batch is None:
        abort(404)
    return batch


@bp.route("/batch/<int:batch_id>")
def batch(batch_id):
    data = _batch_milik_pengguna(batch_id)
    return render_template("pemecah_spt/batch.html", batch=data, daftar=layanan.spt_dalam_batch(batch_id))


@bp.route("/batch/<int:batch_id>/status")
def status_batch(batch_id):
    """Progres batch dalam JSON, ditanyakan halaman hasil tiap detik selama status "proses"."""
    data = _batch_milik_pengguna(batch_id)
    total = max(data["total_langkah"], 1)
    jawaban = {
        "status": data["status"],
        "selesai": data["status"] != "proses",
        "progres": data["progres"],
        "total": data["total_langkah"],
        "persen": min(100, round(data["progres"] * 100 / total)),
        "tahap": data["tahap"] or "",
    }
    if jawaban["selesai"]:
        jawaban["pesan"], jawaban["jenis"] = pekerja.pesan_selesai(data)
    return jsonify(jawaban)


@bp.route("/unduh/<int:spt_id>/<jenis>")
def unduh(spt_id, jenis):
    if jenis not in ("docx", "pdf"):
        abort(404)
    data = layanan.ambil_spt(spt_id, g.pengguna["id"])
    if data is None:
        abort(404)
    jalur = data["jalur_docx" if jenis == "docx" else "jalur_pdf"]
    if jalur is None:   # tidak tercatat, di luar folder data, atau sudah terhapus
        abort(404)
    return send_file(jalur, as_attachment=True, download_name=jalur.name)


@bp.route("/batch/<int:batch_id>/zip")
def unduh_zip(batch_id):
    data = _batch_milik_pengguna(batch_id)
    penyangga = io.BytesIO()
    jumlah = 0
    with zipfile.ZipFile(penyangga, "w", zipfile.ZIP_DEFLATED) as arsip:
        for baris in layanan.spt_dalam_batch(batch_id):
            for nama in (baris["nama_docx"], baris["nama_pdf"]):
                jalur = layanan.jalur_berkas_aman(data["folder"], nama)
                if jalur is not None:
                    arsip.write(jalur, arcname=jalur.name)
                    jumlah += 1
    if not jumlah:
        flash("Tidak ada berkas untuk diunduh.", "galat")
        return redirect(url_for(".batch", batch_id=batch_id))
    penyangga.seek(0)
    return send_file(penyangga, as_attachment=True, download_name=f"SPT_batch_{batch_id}.zip",
                     mimetype="application/zip")


@bp.route("/batch/<int:batch_id>/buka", methods=["POST"])
def buka_folder(batch_id):
    data = _batch_milik_pengguna(batch_id)
    if not layanan.di_dalam_folder_data(data["folder"]):
        abort(404)
    try:
        log_proses.buka_di_penjelajah(data["folder"])
        flash("Folder dibuka di penjelajah file.", "sukses")
    except FileNotFoundError:
        flash("Folder tidak ditemukan. Mungkin sudah dipindah atau dihapus.", "galat")
    except OSError:
        flash("Folder tidak dapat dibuka di komputer ini.", "galat")
    return redirect(url_for(".batch", batch_id=batch_id))
