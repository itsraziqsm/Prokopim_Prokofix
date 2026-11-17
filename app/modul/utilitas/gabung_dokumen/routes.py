"""Halaman web Gabungkan PDF (alamat diawali /utilitas/gabung). Sesi & hasil hanya milik pengguna yang masuk."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, send_file, url_for

from .... import log_proses
from . import layanan

bp = Blueprint("gabung_dokumen", __name__, url_prefix="/utilitas/gabung")
ID_MODUL = "gabung_dokumen"
# Batas satu kiriman unggah/tambah (dipasang di create_app, SEBELUM penjaga login): 200 MB berkas + formulir
BATAS_UNGGAH = layanan.MAKS_BYTE_SESI + 5 * 1024 * 1024


@bp.app_template_filter("ukuran_berkas")
def ukuran_berkas(byte):
    """1536000 -> '1,5 MB'; 2048 -> '2 KB'."""
    byte = int(byte or 0)
    if byte >= 1024 * 1024:
        return f"{byte / (1024 * 1024):.1f} MB".replace(".", ",")
    return f"{max(1, round(byte / 1024))} KB"


def _sesi_atau_404(token):
    sesi = layanan.baca_sesi(token, g.pengguna["id"])
    if sesi is None:
        abort(404)
    return sesi


def _hasil_atau_404(hasil_id):
    hasil = layanan.ambil_hasil(g.pengguna["id"], hasil_id)
    if hasil is None:
        abort(404)
    return hasil


def _berkas_unggahan():
    return [b for b in request.files.getlist("berkas") if b and b.filename]


def _laporkan_penolakan(ditolak):
    for pesan in ditolak[:6]:
        flash(f"Ditolak — {pesan}", "galat")
    if len(ditolak) > 6:
        flash(f"{len(ditolak) - 6} berkas lain juga ditolak.", "galat")


# ---------- Halaman awal: unggah + riwayat ----------
@bp.route("")
def index():
    layanan.bersihkan_sesi_lama()
    return render_template("utilitas/gabung/index.html", riwayat=layanan.daftar_hasil(g.pengguna["id"]),
                           maks_berkas=layanan.MAKS_BERKAS)


@bp.route("/unggah", methods=["POST"])
def unggah():
    berkas = _berkas_unggahan()
    if not berkas:
        flash("Pilih minimal satu berkas PDF.", "galat")
        return redirect(url_for(".index"))
    token, sesi = layanan.buat_sesi(g.pengguna["id"])
    ditambah, ditolak = layanan.tambah_berkas(token, sesi, berkas)
    _laporkan_penolakan(ditolak)
    if not ditambah:
        layanan.hapus_sesi(token)
        return redirect(url_for(".index"))
    return redirect(url_for(".susun", token=token))


# ---------- Penyusunan ----------
def _render_susun(token, sesi, galat=None, status_kode=200):
    galat_hitung, pilihan = layanan.periksa_rentang(sesi)
    terpilih = sum(len(h) for h in pilihan.values()) if not galat_hitung else None
    return render_template(
        "utilitas/gabung/susun.html", token=token, sesi=sesi, galat=galat or {},
        total_halaman=sum(b["halaman"] for b in sesi["berkas"]), halaman_terpilih=terpilih,
        maks_berkas=layanan.MAKS_BERKAS,
    ), status_kode


@bp.route("/<token>")
def susun(token):
    return _render_susun(token, _sesi_atau_404(token))


@bp.route("/<token>/tambah", methods=["POST"])
def tambah(token):
    """Tambah file ke penyusunan; isian (rentang, nama, daftar isi) disimpan dulu agar ketikan tidak hilang."""
    sesi = _sesi_atau_404(token)
    layanan.simpan_isian(sesi, request.form)
    berkas = _berkas_unggahan()
    if not berkas:
        layanan.simpan_sesi(token, sesi)
        flash("Pilih berkas PDF yang akan ditambahkan.", "galat")
        return redirect(url_for(".susun", token=token))
    ditambah, ditolak = layanan.tambah_berkas(token, sesi, berkas)
    _laporkan_penolakan(ditolak)
    if ditambah:
        flash(f"{ditambah} file ditambahkan.", "sukses")
    return redirect(url_for(".susun", token=token) + "#daftar-berkas")


@bp.route("/<token>/aksi", methods=["POST"])
def aksi(token):
    """Naik / Turun / Hapus file dan Periksa rentang (tombol dengan formaction dalam satu formulir)."""
    sesi = _sesi_atau_404(token)
    layanan.simpan_isian(sesi, request.form)
    perintah, _, id_berkas = request.form.get("aksi", "").partition(":")
    tujuan = url_for(".susun", token=token)
    if perintah in ("naik", "turun"):
        layanan.geser_berkas(sesi, id_berkas, perintah)
        layanan.simpan_sesi(token, sesi)
        # Fokus kembali ke tombol yang sama setelah dimuat ulang (aksesibel untuk pengguna keyboard)
        return redirect(url_for(".susun", token=token, fokus=f"{perintah}-{id_berkas}") + "#daftar-berkas")
    if perintah == "hapus":
        dihapus = layanan.hapus_berkas_sesi(token, sesi, id_berkas)
        layanan.simpan_sesi(token, sesi)
        if dihapus:
            flash(f"{dihapus['nama']} dikeluarkan dari penggabungan.", "sukses")
        return redirect(tujuan + "#daftar-berkas")
    layanan.simpan_sesi(token, sesi)
    if perintah == "periksa":
        galat, _ = layanan.periksa_rentang(sesi)
        if galat:
            flash("Ada rentang halaman yang belum benar. Perbaiki yang ditandai.", "galat")
            return _render_susun(token, sesi, galat=galat, status_kode=400)
        flash("Semua rentang halaman benar.", "sukses")
    return redirect(tujuan)


@bp.route("/<token>/gabung", methods=["POST"])
def gabungkan(token):
    sesi = _sesi_atau_404(token)
    layanan.simpan_isian(sesi, request.form)
    layanan.simpan_sesi(token, sesi)
    if not sesi["berkas"]:
        flash("Tambahkan minimal satu berkas PDF.", "galat")
        return redirect(url_for(".susun", token=token))
    galat, pilihan = layanan.periksa_rentang(sesi)
    if galat:
        flash("PDF belum digabung. Perbaiki rentang halaman yang ditandai.", "galat")
        return _render_susun(token, sesi, galat=galat, status_kode=400)
    try:
        hasil = layanan.gabungkan(token, sesi, g.pengguna["id"], pilihan)
    except Exception as e:  # PDF berubah/rusak saat digabung, disk penuh, dsb.
        log_proses.catat(ID_MODUL, "Gabungkan PDF", status="gagal",
                         detail=f"{len(sesi['berkas'])} file: {e}"[:500])
        flash("PDF gagal digabung. Periksa kembali berkasnya lalu coba lagi.", "galat")
        return redirect(url_for(".susun", token=token))
    log_proses.catat(ID_MODUL, "Gabungkan PDF",
                     detail=f"{hasil['jumlah_berkas']} file → {hasil['jumlah_halaman']} halaman",
                     lokasi=hasil["folder"])
    flash(f"PDF digabung: {hasil['nama_berkas']}", "sukses")
    return redirect(url_for(".hasil", hasil_id=hasil["id"]))


# ---------- Hasil ----------
@bp.route("/hasil/<int:hasil_id>")
def hasil(hasil_id):
    data = _hasil_atau_404(hasil_id)
    return render_template("utilitas/gabung/hasil.html", hasil=data,
                           ada_berkas=layanan.jalur_hasil_aman(data) is not None)


@bp.route("/hasil/<int:hasil_id>/unduh")
def unduh(hasil_id):
    """Unduh hanya dari rekaman database; jalur divalidasi berada di instance/data/gabung_dokumen/<id>/."""
    jalur = layanan.jalur_hasil_aman(_hasil_atau_404(hasil_id))
    if jalur is None:
        abort(404)
    return send_file(jalur, as_attachment=True, download_name=jalur.name, mimetype="application/pdf")


@bp.route("/hapus", methods=["POST"])
def hapus():
    """Hapus satu atau beberapa hasil beserta berkasnya (hanya milik pengguna)."""
    ids = sorted({int(i) for i in request.form.getlist("hasil") if i.isdigit()})
    if not ids:
        flash("Pilih minimal satu hasil untuk dihapus.", "galat")
        return redirect(url_for(".index"))
    terhapus, galat = 0, []
    for hasil_id in ids:
        data = layanan.ambil_hasil(g.pengguna["id"], hasil_id)
        if data is None:
            continue
        try:
            layanan.hapus_hasil(data)
        except layanan.GalatHapus as e:
            galat.append(str(e))
            log_proses.catat(ID_MODUL, "Hapus hasil", status="gagal", detail=str(e))
            continue
        terhapus += 1
        log_proses.catat(ID_MODUL, "Hapus hasil",
                         detail=f"{data['nama_berkas']} ({data['jumlah_halaman']} halaman)")
    if terhapus:
        flash(f"{terhapus} hasil beserta berkasnya dihapus.", "sukses")
    for pesan in galat:
        flash(pesan, "galat")
    if not terhapus and not galat:
        flash("Hasil tidak ditemukan.", "galat")
    return redirect(url_for(".index"))
