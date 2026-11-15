"""Halaman web Pemecah SPT (alamat diawali /spt).

Alur: unggah (/spt) -> analisis (POST /spt/analisis) -> pratinjau (/spt/pratinjau/<token>)
      -> proses (POST /spt/proses) -> hasil batch (/spt/batch/<id>) -> unduh per berkas / ZIP.
"""
import io
import zipfile
from pathlib import Path

from flask import Blueprint, abort, flash, g, redirect, render_template, request, send_file, url_for

from ... import log_proses
from . import layanan, pdf
from .pemecah import GalatBerkas, HasilAnalisis, analisis, pecah_satu, rapikan, validasi_berkas
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
    batch_id, folder = layanan.buat_batch(g.pengguna["id"], meta["nama_asli"], format_keluaran)
    try:
        status_batch, catatan, jumlah_berhasil = _pecah_dan_simpan(meta["jalur"], daftar, folder, batch_id, format_keluaran)
    except Exception as e:  # jaring pengaman: batch ditandai gagal, bukan halaman galat mentah
        layanan.selesaikan_batch(batch_id, 0, "gagal", f"Galat tak terduga: {e}")
        log_proses.catat(ID_MODUL, "Pecah batch", status="gagal", detail=f"Galat tak terduga: {e}",
                         lokasi=str(folder))
        flash("Pemrosesan gagal karena galat tak terduga.", "galat")
        return redirect(url_for(".batch", batch_id=batch_id))
    finally:
        layanan.hapus_sementara(token)

    detail = f"{jumlah_berhasil} dari {len(daftar)} SPT → {layanan.FORMAT_LABEL[format_keluaran].replace(' ', '')}"
    if catatan:
        detail += f"; {catatan}"
    log_proses.catat(ID_MODUL, "Pecah batch", status="gagal" if status_batch == "gagal" else "sukses",
                     detail=detail, lokasi=str(folder))
    pesan = {"sukses": (f"{len(daftar)} SPT berhasil dipecah.", "sukses"),
             "sebagian": (catatan or "Sebagian berkas tidak berhasil dibuat.", "galat"),
             "gagal": ("Semua SPT gagal diproses. Lihat rinciannya di tabel.", "galat")}[status_batch]
    flash(*pesan)
    return redirect(url_for(".batch", batch_id=batch_id))


def _pecah_dan_simpan(jalur_asli, daftar, folder, batch_id, format_keluaran):
    """Pecah tiap SPT (kegagalan satu SPT tidak menghentikan yang lain), lalu buat PDF bila diminta."""
    hasil = []   # (info, nama_docx | None, galat | None)
    for info in daftar:
        tujuan = folder / f"{info.nama}.docx"
        try:
            pecah_satu(jalur_asli, info, tujuan)
            hasil.append((info, tujuan.name, None))
        except Exception as e:
            tujuan.unlink(missing_ok=True)
            hasil.append((info, None, f"Gagal memecah: {e}"))

    catatan = None
    perlu_pdf = format_keluaran in ("pdf", "keduanya")
    if perlu_pdf:
        konversi = pdf.konversi_ke_pdf([folder / n for _, n, _ in hasil if n], folder)
        catatan = konversi.galat

    jumlah_gagal = jumlah_sebagian = 0
    for info, nama_docx, galat in hasil:
        nama_pdf, status = None, "sukses"
        if nama_docx is None:
            status = "gagal"
        elif perlu_pdf:
            calon = folder / f"{Path(nama_docx).stem}.pdf"
            if calon.is_file():
                nama_pdf = calon.name
                if format_keluaran == "pdf":   # hanya PDF yang diminta: Word sementara dihapus
                    (folder / nama_docx).unlink(missing_ok=True)
                    nama_docx = None
            else:
                status = "sebagian"
                galat = "PDF tidak dibuat; berkas Word tetap tersedia."
        jumlah_gagal += status == "gagal"
        jumlah_sebagian += status == "sebagian"
        layanan.simpan_spt(batch_id, info.urutan, info.nomor, nama_docx, nama_pdf, info.cuplikan, status, galat)

    if jumlah_gagal == len(hasil):
        status_batch = "gagal"
    elif jumlah_gagal or jumlah_sebagian:
        status_batch = "sebagian"
    else:
        status_batch = "sukses"
    if jumlah_gagal and not catatan:
        catatan = f"{jumlah_gagal} SPT gagal dipecah."
    layanan.selesaikan_batch(batch_id, len(hasil), status_batch, catatan)
    return status_batch, catatan, len(hasil) - jumlah_gagal


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
