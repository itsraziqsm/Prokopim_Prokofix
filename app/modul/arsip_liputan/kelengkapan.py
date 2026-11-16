"""Daftar kelengkapan laporan liputan (murni Python, tanpa Flask) untuk panel samping.

Tiap butir: kunci, label, lengkap (bool), detail (teks kecil), wajib (bool), target (id elemen di halaman),
cek (aturan pemeriksaan langsung di browser untuk isian formulir; None = hanya dari data tersimpan).
"""
from .teks import paragraf_berita


def daftar_kelengkapan(isian, foto=(), ada_ekspor=False, perlu_ekspor_ulang=False):
    """isian: dict data kegiatan (tersimpan atau isian formulir); foto: daftar foto tersimpan."""
    def ada(kunci):
        return bool(str(isian.get(kunci) or "").strip())

    def kosong_pertama(kolom, awalan):
        """Id isian foto pertama yang kolomnya masih kosong (tujuan klik di panel), atau bagian Foto."""
        for f in foto:
            if not (f[kolom] or "").strip() and "id" in f.keys():
                return f"{awalan}-{f['id']}"
        return "bagian-foto"

    jumlah_foto = len(foto)
    berketerangan = sum(1 for f in foto if (f["keterangan"] or "").strip())
    bersumber = sum(1 for f in foto if (f["sumber"] or "").strip())
    paragraf = len(paragraf_berita(isian.get("isi") or ""))

    return [
        # ---------- Wajib (urut sesuai posisi isian di formulir) ----------
        {"kunci": "tanggal", "label": "Tanggal kegiatan", "lengkap": ada("tanggal"), "detail": "",
         "wajib": True, "target": "f-tanggal", "cek": "isi:f-tanggal"},
        {"kunci": "kegiatan", "label": "Nama kegiatan", "lengkap": ada("kegiatan"),
         "detail": "untuk nama berkas", "wajib": True, "target": "f-kegiatan", "cek": "isi:f-kegiatan"},
        {"kunci": "judul", "label": "Judul berita", "lengkap": ada("judul"), "detail": "",
         "wajib": True, "target": "f-judul", "cek": "isi:f-judul"},
        {"kunci": "isi", "label": "Isi berita", "lengkap": paragraf > 0,
         "detail": f"{paragraf} paragraf" if paragraf else "", "wajib": True, "target": "f-isi", "cek": "isi:f-isi"},
        {"kunci": "foto", "label": "Foto dokumentasi", "lengkap": jumlah_foto > 0,
         "detail": f"{jumlah_foto} foto" if jumlah_foto else "", "wajib": True, "target": "bagian-foto", "cek": None},
        # ---------- Pelengkap (urut sesuai formulir; Word terbaru paling akhir) ----------
        {"kunci": "status", "label": "Status final", "lengkap": isian.get("status") == "final", "detail": "",
         "wajib": False, "target": "judul-data", "cek": "nilai:status=final"},
        {"kunci": "spt", "label": "SPT terkait", "lengkap": bool(isian.get("spt_id")), "detail": "",
         "wajib": False, "target": "pilihan-spt", "cek": "pilih:spt_id"},
        {"kunci": "keterangan", "label": "Keterangan foto",
         "lengkap": jumlah_foto > 0 and berketerangan == jumlah_foto,
         "detail": f"{berketerangan} dari {jumlah_foto} foto" if jumlah_foto else "",
         "wajib": False, "target": kosong_pertama("keterangan", "ket"), "cek": None},
        {"kunci": "sumber", "label": "Sumber foto", "lengkap": jumlah_foto > 0 and bersumber == jumlah_foto,
         "detail": f"{bersumber} dari {jumlah_foto} foto" if jumlah_foto else "",
         "wajib": False, "target": kosong_pertama("sumber", "sum"), "cek": None},
        {"kunci": "word", "label": "Word terbaru", "lengkap": ada_ekspor and not perlu_ekspor_ulang,
         "detail": "perlu dibuat ulang" if ada_ekspor and perlu_ekspor_ulang else "",
         "wajib": False, "target": "panel-laporan", "cek": None},
    ]


def wajib_belum(daftar):
    """Label butir wajib yang belum lengkap (kosong = Word boleh dibuat)."""
    return [b["label"] for b in daftar if b["wajib"] and not b["lengkap"]]
