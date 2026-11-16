"""Daftar kelengkapan laporan liputan (murni Python, tanpa Flask) untuk panel samping.

Tiap butir: kunci, label, lengkap (bool), detail (teks kecil), wajib (bool), target (id elemen di halaman),
cek (aturan pemeriksaan langsung di browser untuk isian formulir; None = hanya dari data tersimpan).
"""
from .teks import paragraf_berita


def daftar_kelengkapan(isian, foto=(), ada_ekspor=False, perlu_ekspor_ulang=False):
    """isian: dict data kegiatan (tersimpan atau isian formulir); foto: daftar foto tersimpan."""
    def ada(kunci):
        return bool(str(isian.get(kunci) or "").strip())

    jumlah_foto = len(foto)
    berketerangan = sum(1 for f in foto if (f["keterangan"] or "").strip())
    bersumber = sum(1 for f in foto if (f["sumber"] or "").strip())
    paragraf = len(paragraf_berita(isian.get("isi") or ""))

    return [
        # ---------- Wajib ----------
        {"kunci": "tanggal", "label": "Tanggal kegiatan", "lengkap": ada("tanggal"), "detail": "",
         "wajib": True, "target": "f-tanggal", "cek": "isi:f-tanggal"},
        {"kunci": "judul", "label": "Judul berita", "lengkap": ada("judul"), "detail": "",
         "wajib": True, "target": "f-judul", "cek": "isi:f-judul"},
        {"kunci": "isi", "label": "Isi berita", "lengkap": paragraf > 0,
         "detail": f"{paragraf} paragraf" if paragraf else "", "wajib": True, "target": "f-isi", "cek": "isi:f-isi"},
        {"kunci": "foto", "label": "Foto dokumentasi", "lengkap": jumlah_foto > 0,
         "detail": f"{jumlah_foto} foto" if jumlah_foto else "", "wajib": True, "target": "bagian-foto", "cek": None},
        {"kunci": "keterangan", "label": "Keterangan foto",
         "lengkap": jumlah_foto > 0 and berketerangan == jumlah_foto,
         "detail": f"{berketerangan} dari {jumlah_foto} foto" if jumlah_foto else "",
         "wajib": True, "target": "bagian-foto", "cek": None},
        # ---------- Pelengkap ----------
        {"kunci": "kegiatan", "label": "Nama kegiatan", "lengkap": ada("kegiatan"),
         "detail": "untuk nama berkas", "wajib": False, "target": "f-kegiatan", "cek": "isi:f-kegiatan"},
        {"kunci": "spt", "label": "SPT terkait", "lengkap": bool(isian.get("spt_id")), "detail": "",
         "wajib": False, "target": "f-cari-spt", "cek": "pilih:spt_id"},
        {"kunci": "sumber", "label": "Sumber foto", "lengkap": jumlah_foto > 0 and bersumber == jumlah_foto,
         "detail": f"{bersumber} dari {jumlah_foto} foto" if jumlah_foto else "",
         "wajib": False, "target": "bagian-foto", "cek": None},
        {"kunci": "status", "label": "Status final", "lengkap": isian.get("status") == "final", "detail": "",
         "wajib": False, "target": "judul-data", "cek": "nilai:status=final"},
        {"kunci": "word", "label": "Word terbaru", "lengkap": ada_ekspor and not perlu_ekspor_ulang,
         "detail": "perlu dibuat ulang" if ada_ekspor and perlu_ekspor_ulang else "",
         "wajib": False, "target": "panel-laporan", "cek": None},
    ]
