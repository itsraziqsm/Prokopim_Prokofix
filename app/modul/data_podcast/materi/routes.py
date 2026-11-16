"""Halaman web Materi Podcast (alamat diawali /podcast/materi). Semua pengguna yang masuk melihat semua materi."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, send_file, url_for

from .... import log_proses
from . import layanan
from .pengurai import PANJANG_MAKS, ada_isi, html as jawaban_html, rapikan

bp = Blueprint("materi_podcast", __name__, url_prefix="/podcast/materi")
ID_MODUL = "materi_podcast"


@bp.app_template_filter("jawaban_html")
def _filter_jawaban(teks):
    """{{ p.jawaban|jawaban_html }} -> HTML aman hasil penguraian (dipakai juga oleh pratinjau langsung)."""
    return jawaban_html(teks)


# ---------- Bantuan ----------
def _materi_atau_404(materi_id):
    materi = layanan.ambil_materi(materi_id)
    if materi is None:
        abort(404)
    return materi


def _instansi_atau_404(materi_id, instansi_id):
    ins = layanan.ambil_instansi(materi_id, instansi_id)
    if ins is None:
        abort(404)
    return ins


def _baca_materi():
    """(isian, galat) dari formulir judul & keterangan materi."""
    isian = {"judul": rapikan(request.form.get("judul", "")),
             "keterangan": rapikan(request.form.get("keterangan", ""))}
    galat = {}
    if not isian["judul"]:
        galat["judul"] = "Isi judul materi."
    elif len(isian["judul"]) > layanan.PANJANG["judul"]:
        galat["judul"] = f"Judul maksimal {layanan.PANJANG['judul']} karakter."
    if len(isian["keterangan"]) > layanan.PANJANG["keterangan"]:
        galat["keterangan"] = f"Keterangan maksimal {layanan.PANJANG['keterangan']} karakter."
    return isian, galat


def _perlu_ekspor_ulang(materi):
    return bool(materi["diekspor"] and materi["diubah"] > materi["diekspor"])


# ---------- Daftar materi ----------
@bp.route("")
def index():
    q = request.args.get("q", "").strip()[:100]
    return render_template("data_podcast/materi/index.html", daftar=layanan.daftar_materi(q), q=q)


@bp.route("/baru")
def baru():
    return render_template("data_podcast/materi/baru.html", isian={}, galat={})


@bp.route("/baru", methods=["POST"])
def buat():
    isian, galat = _baca_materi()
    if galat:
        return render_template("data_podcast/materi/baru.html", isian=isian, galat=galat), 400
    materi_id = layanan.buat_materi(isian["judul"], isian["keterangan"], g.pengguna["id"])
    log_proses.catat(ID_MODUL, "Buat materi", detail=isian["judul"])
    flash("Materi dibuat. Tambahkan instansi yang akan ditanya.", "sukses")
    return redirect(url_for(".detail", materi_id=materi_id))


# ---------- Halaman kerja materi ----------
def _render_detail(materi, isian=None, galat=None, galat_instansi=None, status_kode=200):
    instansi = layanan.daftar_instansi(materi["id"])
    return render_template(
        "data_podcast/materi/detail.html",
        materi=materi,
        instansi=instansi,
        selesai=sum(1 for i in instansi if i["status"] == "selesai"),
        isian=isian or dict(materi),
        galat=galat or {},
        galat_instansi=galat_instansi,
        ada_ekspor=layanan.jalur_ekspor(materi) is not None,
        perlu_ekspor_ulang=_perlu_ekspor_ulang(materi),
    ), status_kode


@bp.route("/<int:materi_id>")
def detail(materi_id):
    return _render_detail(_materi_atau_404(materi_id))


@bp.route("/<int:materi_id>/simpan", methods=["POST"])
def simpan(materi_id):
    materi = _materi_atau_404(materi_id)
    isian, galat = _baca_materi()
    if galat:
        flash("Perubahan belum disimpan. Periksa isian yang ditandai.", "galat")
        return _render_detail(materi, isian=isian, galat=galat, status_kode=400)
    layanan.ubah_materi(materi_id, isian["judul"], isian["keterangan"])
    log_proses.catat(ID_MODUL, "Ubah materi", detail=isian["judul"])
    flash("Judul dan keterangan disimpan.", "sukses")
    return redirect(url_for(".detail", materi_id=materi_id))


@bp.route("/<int:materi_id>/hapus", methods=["POST"])
def hapus(materi_id):
    materi = _materi_atau_404(materi_id)
    try:
        layanan.hapus_materi(materi)
    except OSError:
        log_proses.catat(ID_MODUL, "Hapus materi", status="gagal", detail=f"{materi['judul']}: berkas terkunci")
        flash("Berkas Word materi ini tidak dapat dihapus, mungkin sedang dibuka. Tutup berkasnya lalu coba lagi.",
              "galat")
        return redirect(url_for(".detail", materi_id=materi_id))
    log_proses.catat(ID_MODUL, "Hapus materi",
                     detail=f"{materi['judul']} ({materi['jumlah_instansi']} instansi, "
                            f"{materi['jumlah_pertanyaan']} pertanyaan)")
    flash("Materi beserta instansi, pertanyaan, dan berkas Word-nya dihapus.", "sukses")
    return redirect(url_for(".index"))


@bp.route("/<int:materi_id>/duplikat", methods=["POST"])
def duplikat(materi_id):
    materi = _materi_atau_404(materi_id)
    baru_id = layanan.duplikat_materi(materi_id, g.pengguna["id"])
    log_proses.catat(ID_MODUL, "Duplikat materi", detail=f"{materi['judul']} → salinan #{baru_id}")
    flash("Salinan materi dibuat. Ubah judul atau keterangannya untuk rekap versi berikutnya.", "sukses")
    return redirect(url_for(".detail", materi_id=baru_id))


# ---------- Instansi ----------
@bp.route("/<int:materi_id>/instansi", methods=["POST"])
def tambah_instansi(materi_id):
    materi = _materi_atau_404(materi_id)
    nama = rapikan(request.form.get("nama", ""))
    if not nama or len(nama) > layanan.PANJANG["nama"]:
        pesan = "Isi nama instansi." if not nama else f"Nama maksimal {layanan.PANJANG['nama']} karakter."
        return _render_detail(materi, galat_instansi=pesan, status_kode=400)
    iid = layanan.tambah_instansi(materi_id, nama)
    log_proses.catat(ID_MODUL, "Tambah instansi", detail=f"{materi['judul']} · {nama}")
    flash(f"{nama} ditambahkan. Isi pertanyaannya di bawah.", "sukses")
    return redirect(url_for(".instansi", materi_id=materi_id, instansi_id=iid))


@bp.route("/<int:materi_id>/instansi/<int:instansi_id>/geser", methods=["POST"])
def geser_instansi(materi_id, instansi_id):
    _materi_atau_404(materi_id)
    ins = _instansi_atau_404(materi_id, instansi_id)
    arah = request.form.get("arah", "")
    if layanan.geser_instansi(materi_id, instansi_id, arah):
        flash(f"{ins['nama']} dipindah {'ke atas' if arah == 'naik' else 'ke bawah'}.", "sukses")
    # Kembali ke baris yang sama, dengan fokus pada tombol yang sama agar mudah digeser lagi (aksesibel)
    return redirect(url_for(".detail", materi_id=materi_id, fokus=f"geser-{arah}-{instansi_id}")
                    + f"#instansi-{instansi_id}")


def _render_instansi(materi, ins, pertanyaan, galat=None, status_kode=200):
    semua = layanan.daftar_instansi(materi["id"])
    posisi = next((n for n, i in enumerate(semua) if i["id"] == ins["id"]), 0)
    return render_template(
        "data_podcast/materi/instansi.html",
        materi=materi,
        ins=ins,
        nomor=posisi + 1,
        sebelumnya=semua[posisi - 1] if posisi > 0 else None,
        berikutnya=semua[posisi + 1] if posisi + 1 < len(semua) else None,
        pertanyaan=pertanyaan,
        galat=galat or {},
        panjang=layanan.PANJANG,
        pertanyaan_maks=layanan.PERTANYAAN_MAKS,
    ), status_kode


@bp.route("/<int:materi_id>/instansi/<int:instansi_id>")
def instansi(materi_id, instansi_id):
    materi = _materi_atau_404(materi_id)
    ins = _instansi_atau_404(materi_id, instansi_id)
    pertanyaan = [dict(p) for p in layanan.daftar_pertanyaan(instansi_id)]
    return _render_instansi(materi, ins, pertanyaan)


@bp.route("/<int:materi_id>/instansi/<int:instansi_id>", methods=["POST"])
def simpan_instansi(materi_id, instansi_id):
    materi = _materi_atau_404(materi_id)
    ins = _instansi_atau_404(materi_id, instansi_id)
    f = request.form
    pid, teks, jawaban = f.getlist("pid"), f.getlist("teks"), f.getlist("jawaban")
    if not len(pid) == len(teks) == len(jawaban):
        abort(400, description="Formulir pertanyaan tidak lengkap. Muat ulang halaman lalu coba lagi.")

    nama = rapikan(f.get("nama", ""))
    galat, baris, isian = {}, [], []
    if not nama:
        galat["nama"] = "Isi nama instansi."
    elif len(nama) > layanan.PANJANG["nama"]:
        galat["nama"] = f"Nama maksimal {layanan.PANJANG['nama']} karakter."
    for p, t, j in zip(pid, teks, jawaban):
        t = t.strip()
        if not t and not ada_isi(j):
            continue                                # baris kosong diabaikan
        nomor = len(isian) + 1
        isian.append({"id": int(p) if p.isdigit() else None, "teks": t, "jawaban": j})
        if not t:
            galat[f"teks-{nomor}"] = "Isi teks pertanyaan, atau hapus pertanyaan ini."
        elif len(t) > layanan.PANJANG["pertanyaan"]:
            galat[f"teks-{nomor}"] = f"Pertanyaan maksimal {layanan.PANJANG['pertanyaan']} karakter."
        if len(j) > PANJANG_MAKS:
            galat[f"jawaban-{nomor}"] = f"Jawaban maksimal {PANJANG_MAKS:,} karakter.".replace(",", ".")
        baris.append((isian[-1]["id"], t, j))
    if len(isian) > layanan.PERTANYAAN_MAKS:
        galat["umum"] = f"Maksimal {layanan.PERTANYAAN_MAKS} pertanyaan per instansi."
    if galat:
        flash("Perubahan belum disimpan. Periksa isian yang ditandai.", "galat")
        ins = dict(ins, nama=nama or ins["nama"], selesai=1 if f.get("selesai") == "1" else 0)
        return _render_instansi(materi, ins, isian, galat=galat, status_kode=400)

    # "Tandai selesai" hanya berlaku bila semua pertanyaan sudah berjawaban (pengaman di server)
    minta_selesai = f.get("selesai") == "1"
    semua_terjawab = bool(baris) and all(ada_isi(j) for _, _, j in baris)
    selesai = minta_selesai and semua_terjawab
    layanan.simpan_instansi(materi_id, instansi_id, nama, selesai, baris)

    terjawab = sum(1 for _, _, j in baris if ada_isi(j))
    log_proses.catat(ID_MODUL, "Simpan instansi",
                     detail=f"{materi['judul']} · {nama}: {len(baris)} pertanyaan, {terjawab} terjawab")
    if selesai and not ins["selesai"]:
        log_proses.catat(ID_MODUL, "Tandai selesai", detail=f"{materi['judul']} · {nama}")
    if minta_selesai and not semua_terjawab:
        flash("Pertanyaan disimpan, tetapi belum bisa ditandai selesai: masih ada pertanyaan tanpa jawaban.", "galat")
    else:
        flash("Pertanyaan dan jawaban disimpan.", "sukses")
    return redirect(url_for(".instansi", materi_id=materi_id, instansi_id=instansi_id))


@bp.route("/<int:materi_id>/instansi/<int:instansi_id>/hapus", methods=["POST"])
def hapus_instansi(materi_id, instansi_id):
    materi = _materi_atau_404(materi_id)
    ins = _instansi_atau_404(materi_id, instansi_id)
    layanan.hapus_instansi(materi_id, instansi_id)
    log_proses.catat(ID_MODUL, "Hapus instansi", detail=f"{materi['judul']} · {ins['nama']} ({ins['jumlah']} pertanyaan)")
    flash(f"{ins['nama']} beserta pertanyaannya dihapus.", "sukses")
    return redirect(url_for(".detail", materi_id=materi_id))


@bp.route("/pratinjau", methods=["POST"])
def pratinjau():
    """Pratinjau langsung jawaban: dikirim app.js saat mengetik, memakai penguraian yang sama dengan ekspor."""
    teks = request.form.get("teks", "")[:PANJANG_MAKS + 1]
    return jawaban_html(teks), 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


# ---------- Mode baca ----------
@bp.route("/<int:materi_id>/baca")
def baca(materi_id):
    materi = _materi_atau_404(materi_id)
    instansi = layanan.muat_lengkap(materi_id)
    return render_template("data_podcast/materi/baca.html", materi=materi, instansi=instansi,
                           status=layanan.STATUS,
                           selesai=sum(1 for i in instansi if i["status"] == "selesai"))


# ---------- Ekspor ----------
@bp.route("/<int:materi_id>/ekspor", methods=["POST"])
def ekspor(materi_id):
    materi = _materi_atau_404(materi_id)
    try:
        jalur = layanan.ekspor(materi)
    except Exception as e:  # disk penuh, berkas lama terkunci, dsb.
        log_proses.catat(ID_MODUL, "Ekspor Word", status="gagal", detail=f"{materi['judul']}: {e}")
        flash(f"Word gagal dibuat: {e}", "galat")
        return redirect(url_for(".detail", materi_id=materi_id))
    log_proses.catat(ID_MODUL, "Ekspor Word",
                     detail=f"{jalur.name} ({materi['jumlah_instansi']} instansi, {materi['jumlah_pertanyaan']} pertanyaan)",
                     lokasi=str(jalur.parent))
    flash(f"Word dibuat: {jalur.name}", "sukses")
    return redirect(url_for(".detail", materi_id=materi_id) + "#bagian-word")


@bp.route("/<int:materi_id>/unduh")
def unduh(materi_id):
    """Unduh hanya dari rekaman database; jalur divalidasi berada di instance/data/podcast/<id>/ekspor/."""
    jalur = layanan.jalur_ekspor(_materi_atau_404(materi_id))
    if jalur is None:
        abort(404)
    return send_file(jalur, as_attachment=True, download_name=jalur.name)
