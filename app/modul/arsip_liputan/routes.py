"""Halaman web Arsip Liputan (alamat diawali /liputan). Semua pengguna yang masuk melihat seluruh arsip."""
import io
import math
import zipfile
from datetime import date
from pathlib import Path

from flask import Blueprint, abort, flash, g, redirect, render_template, request, send_file, url_for

from ... import log_proses
from ...waktu import BULAN
from ..pemecah_spt import layanan as layanan_spt
from . import layanan
from .ekspor import FOTO_PER_LEMBAR_MAKS, bagi_lembar
from .kelengkapan import daftar_kelengkapan
from .foto import UKURAN_MAKS, GalatFoto

bp = Blueprint("arsip_liputan", __name__, url_prefix="/liputan")

ID_MODUL = "arsip_liputan"
BATAS_UNGGAH_FOTO = 260 * 1024 * 1024   # satu kiriman unggah foto (dipasang di create_app)


@bp.app_template_global()
def nama_bulan(nomor):
    return BULAN[int(nomor) - 1]


@bp.app_template_filter("tanggal_id")
def tanggal_id(teks):
    """'2026-10-13' -> '13 Oktober 2026'."""
    try:
        d = date.fromisoformat(teks)
    except (TypeError, ValueError):
        return teks or ""
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


# ---------- Bantuan ----------
def _liputan_atau_404(liputan_id):
    data = layanan.ambil(liputan_id)
    if data is None:
        abort(404)
    return data


def _baca_form():
    """(data, galat) dari formulir kegiatan."""
    f = request.form
    data = {
        "tanggal": f.get("tanggal", "").strip(),
        "tokoh": f.get("tokoh", "").strip()[:120],
        "kegiatan": f.get("kegiatan", "").strip()[:200],
        "judul": f.get("judul", "").strip()[:300],
        "isi": f.get("isi", "")[:200_000],
        "spt_id": None,
        "foto_per_lembar": f.get("foto_per_lembar", "2"),
        "status": f.get("status", "draf"),
    }
    galat = {}
    try:
        date.fromisoformat(data["tanggal"])
    except ValueError:
        galat["tanggal"] = "Isi tanggal kegiatan."
    if not data["judul"]:
        galat["judul"] = "Isi judul berita."
    data["foto_per_lembar"] = int(data["foto_per_lembar"]) if data["foto_per_lembar"] in ("1", "2", "3") else 2
    if data["status"] not in layanan.STATUS:
        data["status"] = "draf"
    spt = f.get("spt_id", "")
    if spt.isdigit():
        if layanan_spt.ambil_spt(int(spt), semua_pengguna=True) is None:
            galat["spt_id"] = "SPT yang dipilih tidak ditemukan."
        else:
            data["spt_id"] = int(spt)
    return data, galat


def _render_form(liputan=None, isian=None, galat=None, status_kode=200):
    foto = layanan.daftar_foto(liputan["id"]) if liputan else []
    per_lembar = (isian or liputan or {}).get("foto_per_lembar", 2) if not liputan else liputan["foto_per_lembar"]
    lembar_ke = {f["id"]: n for n, isi in enumerate(bagi_lembar([dict(f) for f in foto], per_lembar), start=1)
                 for f in isi}
    perlu_ekspor_ulang = bool(liputan and liputan["diekspor"] and liputan["diubah"] > liputan["diekspor"])
    ada_ekspor = bool(liputan and layanan.jalur_ekspor(liputan))
    isian = isian or (dict(liputan) if liputan else {"tanggal": date.today().isoformat(), "foto_per_lembar": 2,
                                                     "status": "draf"})
    return render_template(
        "arsip_liputan/form.html",
        liputan=liputan,
        isian=isian,
        kelengkapan=daftar_kelengkapan(isian, foto, ada_ekspor, perlu_ekspor_ulang),
        galat=galat or {},
        foto=foto,
        lembar_ke=lembar_ke,
        daftar_spt=layanan_spt.daftar_spt(semua_pengguna=True)[:300],
        status=layanan.STATUS,
        foto_maks=layanan.FOTO_MAKS,
        ukuran_maks_mb=UKURAN_MAKS // (1024 * 1024),
        per_lembar_maks=FOTO_PER_LEMBAR_MAKS,
        perlu_ekspor_ulang=perlu_ekspor_ulang,
        ada_ekspor=ada_ekspor,
    ), status_kode


# ---------- Daftar arsip ----------
@bp.route("")
def index():
    q = request.args.get("q", "").strip()[:100]
    tahun = request.args.get("tahun", "")
    bulan = request.args.get("bulan", "")
    status = request.args.get("status", "")
    tahun = tahun if tahun.isdigit() else ""
    bulan = bulan if bulan.isdigit() and 1 <= int(bulan) <= 12 else ""
    halaman = max(request.args.get("hal", 1, type=int), 1)
    daftar, total = layanan.cari(q, tahun, bulan, status, halaman)
    return render_template(
        "arsip_liputan/index.html", daftar=daftar, total=total, halaman=halaman,
        jumlah_halaman=max(math.ceil(total / layanan.PER_HALAMAN), 1),
        q=q, tahun=tahun, bulan=bulan, status_pilih=status, daftar_tahun=layanan.daftar_tahun(),
        status=layanan.STATUS)


# ---------- Kegiatan ----------
@bp.route("/baru")
def baru():
    return _render_form()


@bp.route("/baru", methods=["POST"])
def buat():
    data, galat = _baca_form()
    if galat:
        flash("Periksa kembali isian yang ditandai.", "galat")
        return _render_form(isian=data, galat=galat, status_kode=400)
    liputan_id = layanan.simpan(None, data, g.pengguna["id"])
    log_proses.catat(ID_MODUL, "Simpan kegiatan", detail=f"Baru: {data['judul']}")
    flash("Kegiatan disimpan. Sekarang Anda dapat menambahkan foto.", "sukses")
    return redirect(url_for(".detail", liputan_id=liputan_id) + "#bagian-foto")


@bp.route("/<int:liputan_id>")
def detail(liputan_id):
    return _render_form(_liputan_atau_404(liputan_id))


def _simpan_dari_form(liputan):
    data, galat = _baca_form()
    if galat:
        flash("Perubahan belum disimpan. Periksa isian yang ditandai.", "galat")
        return None, _render_form(liputan, isian=data, galat=galat, status_kode=400)
    layanan.simpan(liputan["id"], data, None)
    log_proses.catat(ID_MODUL, "Simpan kegiatan", detail=data["judul"])
    return data, None


@bp.route("/<int:liputan_id>/simpan", methods=["POST"])
def simpan(liputan_id):
    liputan = _liputan_atau_404(liputan_id)
    _, respons = _simpan_dari_form(liputan)
    if respons:
        return respons
    flash("Perubahan disimpan.", "sukses")
    return redirect(url_for(".detail", liputan_id=liputan_id))


@bp.route("/<int:liputan_id>/ekspor", methods=["POST"])
def ekspor(liputan_id):
    """Simpan isian formulir (bila dikirim bersama), lalu buat Word terbaru."""
    liputan = _liputan_atau_404(liputan_id)
    if "judul" in request.form:
        _, respons = _simpan_dari_form(liputan)
        if respons:
            return respons
        liputan = layanan.ambil(liputan_id)
    try:
        jalur, info = layanan.ekspor(liputan)
    except Exception as e:  # berkas foto/templat rusak, disk penuh, dsb.
        log_proses.catat(ID_MODUL, "Ekspor Word", status="gagal", detail=f"{liputan['judul']}: {e}")
        flash(f"Word gagal dibuat: {e}", "galat")
        return redirect(url_for(".detail", liputan_id=liputan_id))
    detail = f"{jalur.name} ({info['lembar']} lembar foto)"
    if info["templat_sementara"]:
        detail += "; templat sementara"
    log_proses.catat(ID_MODUL, "Ekspor Word", detail=detail, lokasi=str(jalur.parent))
    flash(f"Word dibuat: {jalur.name}", "sukses")
    return redirect(url_for(".detail", liputan_id=liputan_id) + "#bagian-ekspor")


@bp.route("/<int:liputan_id>/unduh")
def unduh(liputan_id):
    jalur = layanan.jalur_ekspor(_liputan_atau_404(liputan_id))
    if jalur is None:
        abort(404)
    return send_file(jalur, as_attachment=True, download_name=jalur.name)


@bp.route("/<int:liputan_id>/paket")
def paket(liputan_id):
    """ZIP berisi Word terbaru + berkas SPT terhubung (.docx/.pdf)."""
    liputan = _liputan_atau_404(liputan_id)
    word = layanan.jalur_ekspor(liputan)
    if word is None:
        flash("Buat Word terlebih dahulu.", "galat")
        return redirect(url_for(".detail", liputan_id=liputan_id))
    penyangga = io.BytesIO()
    with zipfile.ZipFile(penyangga, "w", zipfile.ZIP_DEFLATED) as arsip:
        arsip.write(word, arcname=word.name)
        if liputan["spt_id"]:
            spt = layanan_spt.ambil_spt(liputan["spt_id"], semua_pengguna=True)
            for jalur in (spt["jalur_docx"], spt["jalur_pdf"]) if spt else ():
                if jalur is not None:
                    arsip.write(jalur, arcname=f"SPT/{jalur.name}")
    penyangga.seek(0)
    return send_file(penyangga, as_attachment=True, download_name=f"{word.stem}.zip", mimetype="application/zip")


@bp.route("/<int:liputan_id>/hapus", methods=["POST"])
def hapus(liputan_id):
    liputan = _liputan_atau_404(liputan_id)
    try:
        layanan.hapus(liputan)
    except OSError:
        flash("Sebagian berkas tidak dapat dihapus, mungkin sedang dibuka. Tutup berkasnya lalu coba lagi.", "galat")
        log_proses.catat(ID_MODUL, "Hapus kegiatan", status="gagal", detail=f"{liputan['judul']}: berkas terkunci")
        return redirect(url_for(".detail", liputan_id=liputan_id))
    log_proses.catat(ID_MODUL, "Hapus kegiatan", detail=f"{liputan['judul']} ({liputan['jumlah_foto']} foto)")
    flash("Kegiatan beserta foto dan berkasnya dihapus.", "sukses")
    return redirect(url_for(".index"))


# ---------- Foto ----------
@bp.route("/<int:liputan_id>/foto", methods=["POST"])
def unggah_foto(liputan_id):
    liputan = _liputan_atau_404(liputan_id)
    berkas = [b for b in request.files.getlist("foto") if b and b.filename]
    if not berkas:
        flash("Pilih, seret, atau tempel foto terlebih dahulu.", "galat")
        return redirect(url_for(".detail", liputan_id=liputan_id) + "#bagian-foto")
    sisa = layanan.FOTO_MAKS - liputan["jumlah_foto"]
    ditolak, berhasil, diolah = [], 0, 0
    for i, b in enumerate(berkas):
        nama = Path(b.filename.replace("\\", "/")).name[:200] or "foto"
        if i >= sisa:
            ditolak.append(f"{nama}: melebihi batas {layanan.FOTO_MAKS} foto per kegiatan")
            continue
        data = b.stream.read(UKURAN_MAKS + 1)
        try:
            hasil = layanan.tambah_foto(liputan_id, data, nama)
        except GalatFoto as e:
            ditolak.append(f"{nama}: {e}")
            continue
        berhasil += 1
        diolah += hasil.diolah
    if berhasil:
        layanan.tandai_diubah(liputan_id)
        log_proses.catat(ID_MODUL, "Unggah foto", detail=f"{liputan['judul']}: {berhasil} foto ({diolah} diolah)")
        flash(f"{berhasil} foto ditambahkan" + (f", {diolah} di antaranya dikompres." if diolah else "."), "sukses")
    if ditolak:
        log_proses.catat(ID_MODUL, "Unggah foto", status="gagal", detail="; ".join(ditolak)[:500])
        for pesan in ditolak[:5]:
            flash(f"Ditolak — {pesan}", "galat")
        if len(ditolak) > 5:
            flash(f"{len(ditolak) - 5} berkas lain juga ditolak.", "galat")
    return redirect(url_for(".detail", liputan_id=liputan_id) + "#bagian-foto")


@bp.route("/<int:liputan_id>/foto/<int:foto_id>")
def tampil_foto(liputan_id, foto_id):
    """Foto ditampilkan lewat rute yang wajib login, bukan dari folder statis."""
    foto = layanan.ambil_foto(liputan_id, foto_id)
    jalur = layanan.jalur_aman(liputan_id, "foto", foto["nama_berkas"]) if foto else None
    if jalur is None:
        abort(404)
    return send_file(jalur, max_age=3600)


def _simpan_semua_foto(liputan_id):
    """Simpan keterangan/sumber/lembar baru semua foto dari formulir foto (dipakai tombol mana pun)."""
    for foto in layanan.daftar_foto(liputan_id):
        if f"keterangan_{foto['id']}" in request.form:
            layanan.perbarui_foto(liputan_id, foto["id"],
                                  request.form.get(f"keterangan_{foto['id']}", "").strip()[:500],
                                  request.form.get(f"sumber_{foto['id']}", "").strip()[:200],
                                  request.form.get(f"lembar_baru_{foto['id']}") == "1")


@bp.route("/<int:liputan_id>/foto/simpan", methods=["POST"])
def simpan_semua_foto(liputan_id):
    _liputan_atau_404(liputan_id)
    _simpan_semua_foto(liputan_id)
    layanan.tandai_diubah(liputan_id)
    flash("Keterangan foto disimpan.", "sukses")
    return redirect(url_for(".detail", liputan_id=liputan_id) + "#bagian-foto")


@bp.route("/<int:liputan_id>/foto/<int:foto_id>/simpan", methods=["POST"])
def simpan_foto(liputan_id, foto_id):
    _liputan_atau_404(liputan_id)
    if layanan.ambil_foto(liputan_id, foto_id) is None:
        abort(404)
    _simpan_semua_foto(liputan_id)
    layanan.tandai_diubah(liputan_id)
    flash("Keterangan foto disimpan.", "sukses")
    return redirect(url_for(".detail", liputan_id=liputan_id) + f"#foto-{foto_id}")


@bp.route("/<int:liputan_id>/foto/<int:foto_id>/geser", methods=["POST"])
def geser_foto(liputan_id, foto_id):
    _liputan_atau_404(liputan_id)
    if layanan.ambil_foto(liputan_id, foto_id) is None:
        abort(404)
    _simpan_semua_foto(liputan_id)
    layanan.geser_foto(liputan_id, foto_id, request.form.get("arah", ""))
    layanan.tandai_diubah(liputan_id)
    return redirect(url_for(".detail", liputan_id=liputan_id) + f"#foto-{foto_id}")


@bp.route("/<int:liputan_id>/foto/<int:foto_id>/hapus", methods=["POST"])
def hapus_foto(liputan_id, foto_id):
    _liputan_atau_404(liputan_id)
    foto = layanan.ambil_foto(liputan_id, foto_id)
    if foto is None:
        abort(404)
    _simpan_semua_foto(liputan_id)
    layanan.hapus_foto(liputan_id, foto)
    layanan.tandai_diubah(liputan_id)
    flash("Foto dihapus.", "sukses")
    return redirect(url_for(".detail", liputan_id=liputan_id) + "#bagian-foto")


# ---------- SPT ----------
@bp.route("/spt/<int:spt_id>/<jenis>")
def unduh_spt(spt_id, jenis):
    """Unduh berkas SPT (hasil Pemecah SPT) dari pemilih SPT; jalur divalidasi oleh layanan SPT."""
    if jenis not in ("docx", "pdf"):
        abort(404)
    spt = layanan_spt.ambil_spt(spt_id, semua_pengguna=True)
    jalur = spt and spt["jalur_docx" if jenis == "docx" else "jalur_pdf"]
    if not jalur:
        abort(404)
    return send_file(jalur, as_attachment=True, download_name=jalur.name)
