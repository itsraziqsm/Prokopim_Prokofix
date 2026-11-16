"""Pemrosesan batch di LATAR (thread terpisah) dengan laporan progres.

Mengapa thread: memecah & membuat PDF bisa makan waktu. Dengan thread, permintaan web langsung
selesai, lalu halaman hasil menampilkan progress bar yang menanyakan progres tiap detik.
Progres disimpan di database (bukan di memori) agar tetap terbaca walau nanti di server
memakai beberapa proses worker.
"""
import threading
from pathlib import Path

from ... import log_proses
from . import layanan, pdf
from .pemecah import InfoSPT, pecah_satu

ID_MODUL = "pemecah_spt"


def jalankan_latar(app, batch_id, pengguna_id, sumber, daftar, folder, format_keluaran):
    """Mulai pemrosesan di thread latar. `app` = objek Flask asli (bukan proxy current_app)."""
    thread = threading.Thread(
        target=_kerjakan, name=f"pemecah-spt-{batch_id}", daemon=True,
        args=(app, batch_id, pengguna_id, Path(sumber), daftar, Path(folder), format_keluaran))
    thread.start()
    return thread


def _kerjakan(app, batch_id, pengguna_id, sumber, daftar, folder, format_keluaran):
    # Thread tidak punya "konteks request"; buka konteks aplikasi agar database bisa dipakai
    with app.app_context():
        try:
            status, catatan, berhasil = pecah_dan_simpan(sumber, daftar, folder, batch_id, format_keluaran)
            detail = f"{berhasil} dari {len(daftar)} SPT → {layanan.FORMAT_LABEL[format_keluaran].replace(' ', '')}"
            if catatan:
                detail += f"; {catatan}"
            log_proses.catat(ID_MODUL, "Pecah batch", status="gagal" if status == "gagal" else "sukses",
                             detail=detail, lokasi=str(folder), pengguna_id=pengguna_id)
        except Exception as e:  # jaring pengaman: batch ditandai gagal, thread tidak mati diam-diam
            layanan.selesaikan_batch(batch_id, 0, "gagal", f"Galat tak terduga: {e}")
            log_proses.catat(ID_MODUL, "Pecah batch", status="gagal", detail=f"Galat tak terduga: {e}",
                             lokasi=str(folder), pengguna_id=pengguna_id)
        finally:
            sumber.unlink(missing_ok=True)


def pecah_dan_simpan(sumber, daftar, folder, batch_id, format_keluaran):
    """Pecah tiap SPT (kegagalan satu SPT tidak menghentikan yang lain), lalu buat PDF bila diminta.
    Mengembalikan (status_batch, catatan, jumlah_berhasil)."""
    daftar = [i if isinstance(i, InfoSPT) else InfoSPT(**i) for i in daftar]
    n = len(daftar)
    perlu_pdf = format_keluaran in ("pdf", "keduanya")

    hasil = []   # (info, nama_docx | None, galat | None)
    for ke, info in enumerate(daftar, start=1):
        layanan.perbarui_progres(batch_id, ke - 1, f"Memecah SPT {ke} dari {n}")
        tujuan = folder / f"{info.nama}.docx"
        try:
            pecah_satu(sumber, info, tujuan)
            hasil.append((info, tujuan.name, None))
        except Exception as e:
            tujuan.unlink(missing_ok=True)
            hasil.append((info, None, f"Gagal memecah: {e}"))

    catatan = None
    if perlu_pdf:
        siap = [folder / nama for _, nama, _ in hasil if nama]
        terakhir = {"jumlah": -1}

        def saat_progres(jadi, pengonversi):
            if jadi != terakhir["jumlah"]:   # tulis ke database hanya bila angkanya berubah
                terakhir["jumlah"] = jadi
                layanan.perbarui_progres(batch_id, n + jadi,
                                         f"Membuat PDF {min(jadi + 1, len(siap))} dari {len(siap)} ({pengonversi})")

        layanan.perbarui_progres(batch_id, n, f"Membuat PDF 1 dari {len(siap)}")
        catatan = pdf.konversi_ke_pdf(siap, folder, saat_progres).galat

    jumlah_gagal = jumlah_sebagian = 0
    for info, nama_docx, galat in hasil:
        nama_pdf, status = None, "sukses"
        if nama_docx is None:
            status = "gagal"
        elif perlu_pdf:
            calon = folder / f"{Path(nama_docx).stem}.pdf"
            if calon.is_file():
                nama_pdf = calon.name
                if format_keluaran == "pdf":   # hanya PDF yang diminta: Word perantara dihapus
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


def pesan_selesai(batch):
    """(pesan, jenis) notifikasi untuk batch yang sudah selesai."""
    if batch["status"] == "sukses":
        return f"{batch['jumlah']} SPT berhasil dipecah.", "sukses"
    if batch["status"] == "sebagian":
        return batch["catatan"] or "Sebagian berkas tidak berhasil dibuat.", "galat"
    return batch["catatan"] or "Pemrosesan gagal. Lihat rinciannya di tabel.", "galat"
