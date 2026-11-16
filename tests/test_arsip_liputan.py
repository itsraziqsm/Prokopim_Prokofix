"""Uji modul Arsip Liputan. Jalankan: python -m unittest -v"""
import io
import re
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock
import zipfile
from pathlib import Path

from docx import Document
from PIL import Image
from werkzeug.test import EnvironBuilder

from app import create_app
from app.modul.arsip_liputan import ekspor
from app.modul.arsip_liputan.foto import BATAS_OLAH, GalatFoto, olah_foto
from app.modul.arsip_liputan.kelengkapan import daftar_kelengkapan
from app.modul.arsip_liputan.teks import nama_ekspor, paragraf_berita
from tests import fixture_liputan as fl
from tests import fixture_spt as fx

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class UjiTeks(unittest.TestCase):
    def test_normalisasi_berita(self):
        self.assertEqual(paragraf_berita(fl.ISI_CONTOH), [
            "Wali Kota Medan, Rico Tri Putra Bayu Waas, mengikuti Zoom Meeting bersama Kementerian Dalam Negeri dari Rumah Dinas.",
            "“Kita harus bergerak cepat dan terukur,” ujar Wali Kota.",
            "Rapat diikuti seluruh perangkat daerah.",
        ])
        self.assertEqual(paragraf_berita(""), [])
        self.assertEqual(paragraf_berita("a\r\nb\rc"), ["a", "b", "c"])

    def test_nama_ekspor(self):
        self.assertEqual(nama_ekspor("2026-10-13", "Wali", "Zoom Meeting"), "13 Oktober Wali - Zoom Meeting")
        self.assertEqual(nama_ekspor("2026-10-13", "", "Zoom Meeting"), "13 Oktober - Zoom Meeting")
        self.assertEqual(nama_ekspor("2026-03-05", "Wakil", "", "Rapat"), "5 Maret Wakil - Rapat")
        self.assertEqual(nama_ekspor("2026-10-13", "Wali", 'Rapat: "A/B" <C>?'), "13 Oktober Wali - Rapat A-B C")
        self.assertLessEqual(len(nama_ekspor("2026-10-13", "Wali", "x" * 300)), 100)


class UjiKelengkapan(unittest.TestCase):
    def status(self, *a, **k):
        return {b["kunci"]: b["lengkap"] for b in daftar_kelengkapan(*a, **k)}

    def test_kosong_semua_belum_kecuali_tanggal(self):
        hasil = self.status({"tanggal": "2026-10-13", "status": "draf"})
        self.assertTrue(hasil["tanggal"])
        self.assertFalse(any(v for k, v in hasil.items() if k != "tanggal"))

    def test_lengkap(self):
        foto = [{"keterangan": "a", "sumber": "IG"}, {"keterangan": "b", "sumber": "Web"}]
        hasil = self.status({"tanggal": "2026-10-13", "judul": "J", "isi": "x", "kegiatan": "Rapat",
                             "spt_id": 3, "status": "final"}, foto, ada_ekspor=True)
        self.assertTrue(all(hasil.values()), hasil)

    def test_keterangan_sebagian_dan_isi_hanya_spasi(self):
        foto = [{"keterangan": "a", "sumber": ""}, {"keterangan": " ", "sumber": ""}]
        daftar = daftar_kelengkapan({"tanggal": "2026-10-13", "judul": "J", "isi": " \n\u00a0\n"}, foto)
        butir = {b["kunci"]: b for b in daftar}
        self.assertFalse(butir["isi"]["lengkap"])
        self.assertFalse(butir["keterangan"]["lengkap"])
        self.assertEqual(butir["keterangan"]["detail"], "1 dari 2 foto")
        self.assertTrue(butir["foto"]["lengkap"])

    def test_tujuan_klik_ke_isian_foto_kosong_pertama(self):
        foto = [{"id": 7, "keterangan": "a", "sumber": ""}, {"id": 9, "keterangan": "", "sumber": ""}]
        butir = {b["kunci"]: b for b in daftar_kelengkapan({"tanggal": "2026-10-13"}, foto)}
        self.assertEqual(butir["keterangan"]["target"], "ket-9")
        self.assertEqual(butir["sumber"]["target"], "sum-7")
        foto_butir = next(b for b in daftar_kelengkapan({}) if b["kunci"] == "foto")
        self.assertEqual(foto_butir["target"], "bagian-foto")

    def test_urutan_mengikuti_formulir(self):
        daftar = daftar_kelengkapan({})
        self.assertEqual([b["kunci"] for b in daftar if b["wajib"]], ["tanggal", "kegiatan", "judul", "isi", "foto"])
        self.assertEqual([b["kunci"] for b in daftar if not b["wajib"]],
                         ["status", "spt", "keterangan", "sumber", "word"])

    def test_word_perlu_dibuat_ulang(self):
        hasil = daftar_kelengkapan({"tanggal": "2026-10-13"}, ada_ekspor=True, perlu_ekspor_ulang=True)
        word = next(b for b in hasil if b["kunci"] == "word")
        self.assertFalse(word["lengkap"])
        self.assertEqual(word["detail"], "perlu dibuat ulang")

    def test_wajib_dan_pelengkap(self):
        wajib = {b["kunci"] for b in daftar_kelengkapan({}) if b["wajib"]}
        self.assertEqual(wajib, {"tanggal", "judul", "isi", "foto", "kegiatan"})


class UjiFoto(unittest.TestCase):
    def test_jpg_png_kecil_tidak_diubah(self):
        for fmt, akhiran in (("JPEG", ".jpg"), ("PNG", ".png")):
            data = fl.foto(800, 600, fmt)
            hasil = olah_foto(data)
            self.assertFalse(hasil.diolah)
            self.assertEqual(hasil.data, data)
            self.assertEqual(hasil.akhiran, akhiran)

    def test_foto_besar_dikompres(self):
        data = fl.foto(2400, 1800, derau=True)
        self.assertGreater(len(data), BATAS_OLAH)
        hasil = olah_foto(data)
        self.assertTrue(hasil.diolah)
        self.assertLessEqual(len(hasil.data), BATAS_OLAH)
        self.assertLessEqual(max(hasil.lebar, hasil.tinggi), 1920)
        self.assertEqual(Image.open(io.BytesIO(hasil.data)).format, "JPEG")

    def test_webp_dikonversi(self):
        hasil = olah_foto(fl.foto(500, 500, "WEBP"))
        self.assertTrue(hasil.diolah)
        self.assertIn(Image.open(io.BytesIO(hasil.data)).format, ("JPEG", "PNG"))

    def test_rgba_jadi_rgb(self):
        data = fl.foto(500, 500, "WEBP", mode="RGBA")
        with Image.open(io.BytesIO(data)) as asli:
            self.assertEqual(asli.mode, "RGBA")
        with Image.open(io.BytesIO(olah_foto(data).data)) as hasil:
            self.assertEqual(hasil.mode, "RGB")

    def test_exif_orientasi_diterapkan(self):
        hasil = olah_foto(fl.foto(1200, 900, exif_orientasi=6))   # 6 = putar 90 derajat
        self.assertTrue(hasil.diolah)
        self.assertEqual((hasil.lebar, hasil.tinggi), (900, 1200))

    def test_bukan_gambar_ditolak(self):
        with self.assertRaises(GalatFoto):
            olah_foto(b"bukan gambar sama sekali")
        with self.assertRaises(GalatFoto):
            olah_foto(b"%PDF-1.4 palsu")

    def test_terlalu_besar_ditolak(self):
        with self.assertRaisesRegex(GalatFoto, "15 MB"):
            olah_foto(b"0" * (15 * 1024 * 1024 + 1))


class UjiLembar(unittest.TestCase):
    def f(self, n, baru=()):
        return [{"id": i, "lembar_baru": i in baru} for i in range(1, n + 1)]

    def test_tujuh_foto_tiga_per_lembar(self):
        lembar = ekspor.bagi_lembar(self.f(7), 3)
        self.assertEqual([len(l) for l in lembar], [3, 3, 1])

    def test_mulai_lembar_baru_memecah(self):
        lembar = ekspor.bagi_lembar(self.f(7, baru={3, 6}), 3)
        self.assertEqual([[x["id"] for x in l] for l in lembar], [[1, 2], [3, 4, 5], [6, 7]])

    def test_tidak_pernah_lebih_dari_tiga(self):
        for per in (1, 2, 3, 5, 0, None):
            for l in ekspor.bagi_lembar(self.f(10), per):
                self.assertLessEqual(len(l), 3)
        self.assertEqual(len(ekspor.bagi_lembar(self.f(4), 1)), 4)

    def test_ukuran_foto_proporsional_dan_muat(self):
        for px in ((4000, 1000), (1000, 4000), (1000, 1000)):
            lebar, tinggi = ekspor.ukuran_foto(*px, kotak_tinggi_cm=8.5, isi_lebar_cm=15.2,
                                               keterangan="Keterangan foto", sumber="Instagram @akun")
            self.assertAlmostEqual(tinggi / lebar, px[1] / px[0], places=6)
            self.assertLessEqual(lebar, 15.2)
            self.assertLessEqual(tinggi, 8.5)


class UjiDokumen(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def foto_siap(self, daftar):
        hasil = []
        for i, (nama, data) in enumerate(daftar):
            f = olah_foto(data)
            jalur = self.folder / f"{i}{f.akhiran}"
            jalur.write_bytes(f.data)
            hasil.append({"jalur": jalur, "lebar": f.lebar, "tinggi": f.tinggi, "keterangan": f"Foto {nama}",
                          "sumber": "Instagram @akun" if i % 2 else "", "lembar_baru": False})
        return hasil

    def test_word_valid_f4_gaya_dan_media(self):
        foto = self.foto_siap(fl.tujuh_foto())
        tujuan = self.folder / "hasil.docx"
        info = ekspor.buat_dokumen({"judul": "Judul Berita", "isi": fl.ISI_CONTOH, "foto_per_lembar": 3}, foto, tujuan)
        self.assertEqual(info["lembar"], 3)
        doc = Document(str(tujuan))
        sect = doc.element.body.find(f"{W}sectPr")
        pgsz, pgmar = sect.find(f"{W}pgSz"), sect.find(f"{W}pgMar")
        self.assertEqual((pgsz.get(f"{W}w"), pgsz.get(f"{W}h")), ("11907", "18711"))
        self.assertTrue(all(pgmar.get(f"{W}{s}") == "1440" for s in ("top", "bottom", "left", "right")))
        self.assertEqual(doc.paragraphs[0].style.name, "Title")
        self.assertEqual(doc.paragraphs[0].text, "Judul Berita")
        self.assertEqual(doc.paragraphs[1].text, "")   # satu "enter" antara judul dan isi
        self.assertEqual([p.text for p in doc.paragraphs[2:5]], paragraf_berita(fl.ISI_CONTOH))
        self.assertTrue(all(p.style.name == "Normal" for p in doc.paragraphs[1:5]))
        self.assertEqual(len(doc.tables), 3)
        with zipfile.ZipFile(tujuan) as z:
            media = [n for n in z.namelist() if n.startswith("word/media/")]
        self.assertEqual(len(media), 7)
        # Kotak bergaris putus-putus & baris tak terbelah
        self.assertTrue(any(b.get(f"{W}val") == "dashed" for b in doc.element.body.iter(f"{W}top")))
        self.assertTrue(all(tr.find(f"{W}trPr/{W}cantSplit") is not None for tr in doc.element.body.iter(f"{W}tr")))

    def test_lembar_baru_tanpa_page_break_manual(self):
        """Regresi halaman kosong di Microsoft Word: tiap lembar mulai di halaman baru lewat
        'Page break before' di baris pertama tabel, bukan page break manual di paragraf terpisah."""
        foto = self.foto_siap(fl.tujuh_foto()[:3])
        tujuan = self.folder / "tiga.docx"
        ekspor.buat_dokumen({"judul": "J", "isi": "Isi", "foto_per_lembar": 2}, foto, tujuan)
        body = Document(str(tujuan)).element.body
        self.assertFalse(any(b.get(f"{W}type") == "page" for b in body.iter(f"{W}br")))
        tabel = body.findall(f"{W}tbl")
        self.assertEqual(len(tabel), 2)
        for t in tabel:
            p_pertama = t.find(f"{W}tr/{W}tc/{W}p")
            self.assertIsNotNone(p_pertama.find(f"{W}pPr/{W}pageBreakBefore"))
        # Tinggi tabel per halaman menyisakan cadangan yang cukup untuk paragraf penutup
        area = 33.0 - 2 * 2.54
        for t in tabel:
            tinggi = sum(int(h.get(f"{W}val")) for h in t.iter(f"{W}trHeight")) / 567
            self.assertLessEqual(tinggi, area - 1.4)

    def test_dua_garis_potong_tanpa_mengubah_ukuran_kotak(self):
        """Kotak luar (garis lurus) tetap; di dalamnya garis potong putus-putus 0,4 cm dari tepi foto."""
        emu_cm, twip_cm = 360000, 567
        for per in (1, 2, 3):
            foto = self.foto_siap(fl.tujuh_foto()[:per])
            tujuan = self.folder / f"garis-{per}.docx"
            ekspor.buat_dokumen({"judul": "J", "isi": "Isi", "foto_per_lembar": per}, foto, tujuan)
            body = Document(str(tujuan)).element.body
            tabel = body.find(f"{W}tbl")
            baris = [tr for tr in tabel.findall(f"{W}tr") if tr.find(f".//{W}drawing") is not None]
            self.assertEqual(len(baris), per)
            area_cm = (18711 - 2 * 1440) / twip_cm   # 33,0 - 2 x 2,54 = 27,92 cm
            kotak_cm = (area_cm - ekspor.CADANGAN_CM - (per - 1) * ekspor.JEDA_CM) / per
            for tr in baris:
                # tinggi kotak luar tidak berubah oleh garis potong kedua
                tinggi = int(tr.find(f"{W}trPr/{W}trHeight").get(f"{W}val")) / twip_cm
                self.assertAlmostEqual(tinggi, kotak_cm, delta=0.01)
                sel = tr.find(f"{W}tc")
                # kotak luar = garis lurus; garis potong (putus-putus) hanya di sekeliling foto
                self.assertTrue(all(b.get(f"{W}val") == "single" for b in sel.find(f"{W}tcPr/{W}tcBorders")))
                dalam = sel.find(f"{W}tbl")
                self.assertIsNotNone(dalam, "kotak dalam di sekeliling foto")
                tc_dalam = dalam.find(f".//{W}tc")
                self.assertTrue(all(b.get(f"{W}val") == "dashed" for b in tc_dalam.find(f"{W}tcPr/{W}tcBorders")))
                self.assertTrue(all(int(m.get(f"{W}w")) == round(0.4 * twip_cm)
                                    for m in tc_dalam.find(f"{W}tcPr/{W}tcMar")))
                ext = tc_dalam.find(".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent")
                lebar_cm, tinggi_cm = int(ext.get("cx")) / emu_cm, int(ext.get("cy")) / emu_cm
                self.assertLessEqual(tinggi_cm + 2 * 0.4 + 2 * ekspor.MARGIN_SEL_CM, kotak_cm)
                self.assertLessEqual(lebar_cm + 2 * 0.4 + 2 * ekspor.MARGIN_SEL_CM, 15.92)

    def test_tanpa_foto_hanya_berita(self):
        tujuan = self.folder / "berita.docx"
        info = ekspor.buat_dokumen({"judul": "J", "isi": "Satu\nDua"}, [], tujuan)
        doc = Document(str(tujuan))
        self.assertEqual((info["lembar"], len(doc.tables), [p.text for p in doc.paragraphs]), (0, 0, ["J", "", "Satu", "Dua"]))

    def test_gambar_contoh_templat_tidak_ikut(self):
        # Templat dengan gambar contoh: gambar & relasinya harus dibuang
        templat = self.folder / "berita.docx"
        doc = ekspor.templat_sementara()
        doc.add_paragraph("Judul contoh", style="Title")
        gambar = self.folder / "contoh.png"
        gambar.write_bytes(fl.foto(1500, 1000, "PNG"))
        doc.add_picture(str(gambar))
        doc.save(str(templat))
        asli = ekspor.JALUR_TEMPLAT
        ekspor.JALUR_TEMPLAT = templat
        try:
            tujuan = self.folder / "hasil.docx"
            info = ekspor.buat_dokumen({"judul": "Baru", "isi": "Isi"}, [], tujuan)
        finally:
            ekspor.JALUR_TEMPLAT = asli
        self.assertFalse(info["templat_sementara"])
        with zipfile.ZipFile(tujuan) as z:
            self.assertEqual([n for n in z.namelist() if n.startswith("word/media/")], [])
            self.assertNotIn(b"image", z.read("word/_rels/document.xml.rels"))
        self.assertEqual([p.text for p in Document(str(tujuan)).paragraphs], ["Baru", "", "Isi"])


# ---------- Alur web ----------
class UjiWeb(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.app = create_app({"TESTING": True}, instance_path=str(self.folder / "instance"))
        self.klien = self.app.test_client()
        self.klien.post("/siapkan", data={"csrf_token": self.token("/siapkan"), "nama_lengkap": "Budi Santoso",
                                          "nama_pengguna": "budi", "sandi": "rahasia123", "konfirmasi": "rahasia123"})

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def token(self, url, klien=None):
        html = (klien or self.klien).get(url).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def db(self):
        if not hasattr(self, "_db"):
            self._db = sqlite3.connect(self.folder / "instance" / "superapp.db")
            self.addCleanup(self._db.close)
        return self._db

    def buat(self, **ubah):
        data = {"csrf_token": self.token("/liputan/baru"), "tanggal": "2026-10-13", "tokoh": "Wali",
                "kegiatan": "Zoom Meeting", "judul": "Wali Kota Ikuti Zoom Meeting", "isi": fl.ISI_CONTOH,
                "foto_per_lembar": "3", "status": "draf", "spt_id": ""}
        data.update(ubah)
        r = self.klien.post("/liputan/baru", data=data)
        return r, int(r.location.split("/liputan/")[1].split("#")[0]) if r.status_code == 302 else None

    def unggah(self, lid, daftar):
        # Request dibangun manual agar berkas sementara milik alat uji Werkzeug (badan > 500 KB) ikut ditutup
        pembangun = EnvironBuilder(path=f"/liputan/{lid}/foto", method="POST", data={
            "csrf_token": self.token(f"/liputan/{lid}"),
            "foto": [(io.BytesIO(data), nama) for nama, data in daftar]})
        environ = pembangun.get_environ()
        try:
            r = self.klien.open(environ)
            r.close()
        finally:
            environ["wsgi.input"].close()
            pembangun.close()
        return r

    def folder_kegiatan(self, lid):
        """Folder berkas kegiatan: instance/data/liputan/<tahun>/<bulan>/<id> (dari tanggal kegiatan)."""
        tanggal = self.db().execute("SELECT tanggal FROM liputan WHERE id=?", (lid,)).fetchone()[0]
        tahun, bulan = int(tanggal[:4]), int(tanggal[5:7])
        nama_bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
                      "September", "Oktober", "November", "Desember"][bulan - 1]
        return self.folder / "instance" / "data" / "liputan" / str(tahun) / f"{bulan:02d}-{nama_bulan}" / str(lid)

    def ekspor(self, lid, siapkan_foto=True):
        if siapkan_foto and not self.db().execute("SELECT COUNT(*) FROM liputan_foto WHERE liputan_id=?", (lid,)).fetchone()[0]:
            self.unggah(lid, [("a.png", fl.foto(300, 200, "PNG"))])
        return self.klien.post(f"/liputan/{lid}/ekspor", data={"csrf_token": self.token(f"/liputan/{lid}")})

    def test_word_ditolak_bila_wajib_belum_lengkap(self):
        _, lid = self.buat(kegiatan="")
        html = self.klien.get(f"/liputan/{lid}").get_data(as_text=True)
        self.assertRegex(html, r"data-butuh-wajib[^>]*disabled")
        self.assertRegex(html, r'id="syarat-word"[^>]*data-syarat-word\s*>')   # pesan syarat terlihat
        r = self.ekspor(lid, siapkan_foto=False)
        self.assertIn("#panel-laporan", r.location)
        html = self.klien.get(f"/liputan/{lid}").get_data(as_text=True)
        self.assertIn("Word belum dapat dibuat. Lengkapi dulu: nama kegiatan, foto dokumentasi.", html)
        self.assertIsNone(self.db().execute("SELECT berkas_ekspor FROM liputan").fetchone()[0])
        self.assertFalse((self.folder_kegiatan(lid) / "ekspor").exists())
        # Isian yang dikirim bersama tombol tetap tersimpan walau Word ditolak
        data = {"csrf_token": self.token(f"/liputan/{lid}"), "tanggal": "2026-10-13", "tokoh": "Wali", "kegiatan": "Rapat",
                "judul": "Judul Baru", "isi": "Isi", "foto_per_lembar": "2", "status": "draf", "spt_id": ""}
        self.klien.post(f"/liputan/{lid}/ekspor", data=data)
        self.assertEqual(self.db().execute("SELECT judul, kegiatan FROM liputan").fetchone(), ("Judul Baru", "Rapat"))
        self.assertIsNone(self.db().execute("SELECT berkas_ekspor FROM liputan").fetchone()[0])   # foto masih kurang
        # Setelah lengkap, Word dibuat dan tombol aktif
        self.ekspor(lid)
        self.assertIsNotNone(self.db().execute("SELECT berkas_ekspor FROM liputan").fetchone()[0])
        html = self.klien.get(f"/liputan/{lid}").get_data(as_text=True)
        self.assertNotRegex(html, r"data-butuh-wajib[^>]*disabled")

    def test_alur_lengkap(self):
        r, lid = self.buat()
        self.assertEqual(r.status_code, 302)
        self.unggah(lid, fl.tujuh_foto())
        foto = self.db().execute("SELECT nama_berkas, nama_asli, diolah, urutan FROM liputan_foto ORDER BY urutan").fetchall()
        self.assertEqual(len(foto), 7)
        # Diolah: > 800 KB, WebP (tidak didukung Word), EXIF orientasi. PNG/GIF/JPG kecil tidak disentuh.
        self.assertEqual({f[1] for f in foto if f[2]}, {"besar.jpg", "medsos.webp", "kamera.jpg"})
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{24}\.(jpg|png|gif)", f[0]) for f in foto))
        html = self.klien.get(f"/liputan/{lid}").get_data(as_text=True)
        self.assertIn("Lembar 3", html)
        r = self.ekspor(lid)
        self.assertEqual(r.status_code, 302)
        unduh = self.klien.get(f"/liputan/{lid}/unduh")
        self.addCleanup(unduh.close)
        self.assertIn("13 Oktober Wali - Zoom Meeting.docx", unduh.headers["Content-Disposition"])
        doc = Document(io.BytesIO(unduh.data))
        self.assertEqual(len(doc.tables), 3)
        log = [b[0] for b in self.db().execute("SELECT aksi FROM log_proses WHERE modul='arsip_liputan'")]
        self.assertEqual(log, ["Simpan kegiatan", "Unggah foto", "Ekspor Word"])
        self.assertIn("Arsip Liputan", self.klien.get("/log").get_data(as_text=True))

    def test_tanggal_baru_kosong(self):
        html = self.klien.get("/liputan/baru").get_data(as_text=True)
        self.assertRegex(html, r'id="f-tanggal" name="tanggal" type="date" class="input"\s*value=""')
        self.assertRegex(html, r'data-wadah-spt\s+hidden')            # bawaan: Tanpa SPT, daftar tersembunyi

    def test_pilihan_tanpa_dan_dengan_spt(self):
        sumber = fx.batch_contoh(self.folder / "batch.docx")
        r = self.klien.post("/spt/analisis", content_type="multipart/form-data", data={
            "csrf_token": self.token("/spt"), "format": "word", "berkas": (io.BytesIO(sumber.read_bytes()), "b.docx")})
        r = self.klien.post("/spt/proses", data={"csrf_token": self.token(r.location),
                                                 "token": r.location.rsplit("/", 1)[1], "pilih": ["1"]})
        for _ in range(200):
            if self.klien.get(f"{r.location}/status").get_json()["selesai"]:
                break
        spt_id = self.db().execute("SELECT id FROM spt").fetchone()[0]
        # Tanpa SPT: spt_id yang ikut terkirim diabaikan
        _, lid = self.buat(pakai_spt="tidak", spt_id=str(spt_id))
        self.assertIsNone(self.db().execute("SELECT spt_id FROM liputan WHERE id=?", (lid,)).fetchone()[0])
        # Dengan SPT tetapi belum memilih: ditolak dengan pesan
        r, lid2 = self.buat(pakai_spt="ya", spt_id="")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Pilih SPT dari daftar, atau pilih Tanpa SPT.", r.get_data(as_text=True))
        self.assertRegex(r.get_data(as_text=True), r'data-wadah-spt\s+>')     # daftar tetap terbuka
        # Dengan SPT + pilih: tersimpan, dan halaman membuka daftar SPT
        _, lid3 = self.buat(pakai_spt="ya", spt_id=str(spt_id))
        self.assertEqual(self.db().execute("SELECT spt_id FROM liputan WHERE id=?", (lid3,)).fetchone()[0], spt_id)
        html = self.klien.get(f"/liputan/{lid3}").get_data(as_text=True)
        self.assertRegex(html, r'name="pakai_spt" value="ya"[^>]*checked')

    def test_validasi_form(self):
        r, lid = self.buat(tanggal="", judul="")
        self.assertEqual(r.status_code, 400)
        self.assertIsNone(lid)
        html = r.get_data(as_text=True)
        self.assertIn("Isi tanggal kegiatan", html)
        self.assertIn("Isi judul berita", html)

    def test_unggahan_bukan_gambar_ditolak(self):
        _, lid = self.buat()
        self.unggah(lid, [("palsu.jpg", b"bukan gambar"), ("asli.png", fl.foto(300, 200, "PNG"))])
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM liputan_foto").fetchone()[0], 1)
        html = self.klien.get(f"/liputan/{lid}").get_data(as_text=True)
        self.assertIn("palsu.jpg", html)

    def test_geser_simpan_hapus_foto(self):
        _, lid = self.buat()
        self.unggah(lid, [("a.png", fl.foto(300, 200, "PNG")), ("b.png", fl.foto(200, 300, "PNG"))])
        ids = [b[0] for b in self.db().execute("SELECT id FROM liputan_foto ORDER BY urutan")]
        tok = self.token(f"/liputan/{lid}")
        self.klien.post(f"/liputan/{lid}/foto/{ids[1]}/geser", data={"csrf_token": tok, "arah": "naik",
                                                                     f"keterangan_{ids[0]}": "Ket A", f"sumber_{ids[0]}": "IG"})
        urut = [b[0] for b in self.db().execute("SELECT id FROM liputan_foto ORDER BY urutan")]
        self.assertEqual(urut, [ids[1], ids[0]])
        self.assertEqual(self.db().execute("SELECT keterangan, sumber FROM liputan_foto WHERE id=?", (ids[0],)).fetchone(), ("Ket A", "IG"))
        nama = self.db().execute("SELECT nama_berkas FROM liputan_foto WHERE id=?", (ids[0],)).fetchone()[0]
        berkas = self.folder_kegiatan(lid) / "foto" / nama
        self.assertTrue(berkas.exists())
        self.klien.post(f"/liputan/{lid}/foto/{ids[0]}/hapus", data={"csrf_token": tok})
        self.assertFalse(berkas.exists())
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM liputan_foto").fetchone()[0], 1)

    def test_tampil_foto_wajib_login_dan_jalur_aman(self):
        _, lid = self.buat()
        self.unggah(lid, [("a.png", fl.foto(300, 200, "PNG"))])
        fid = self.db().execute("SELECT id FROM liputan_foto").fetchone()[0]
        r = self.klien.get(f"/liputan/{lid}/foto/{fid}")
        self.addCleanup(r.close)
        self.assertEqual(r.status_code, 200)
        self.assertIn("/masuk", self.app.test_client().get(f"/liputan/{lid}/foto/{fid}").location)
        db = self.db()
        db.execute("UPDATE liputan_foto SET nama_berkas = '../../../secret_key'")
        db.commit()
        self.assertEqual(self.klien.get(f"/liputan/{lid}/foto/{fid}").status_code, 404)

    def test_unduhan_di_luar_folder_ditolak(self):
        _, lid = self.buat()
        self.ekspor(lid)
        db = self.db()
        for nama in ("../../../secret_key", "../foto/../../../superapp.db"):
            db.execute("UPDATE liputan SET berkas_ekspor = ?", (nama,))
            db.commit()
            self.assertEqual(self.klien.get(f"/liputan/{lid}/unduh").status_code, 404)
        self.assertEqual(self.klien.get(f"/liputan/{lid}/paket").status_code, 302)

    def test_pencarian_dan_filter(self):
        self.buat(judul="Rapat Posyandu", tanggal="2026-10-04")
        self.buat(judul="Upacara Hari Pahlawan", tokoh="Wakil", tanggal="2025-11-10", status="final")
        self.buat(judul="Zoom Kemendagri", isi="Membahas tata kelola posyandu", tanggal="2026-03-01")
        def judul(url):
            html = self.klien.get(url).get_data(as_text=True)
            return sorted(j for j in ("Rapat Posyandu", "Upacara Hari Pahlawan", "Zoom Kemendagri") if j in html)
        self.assertEqual(judul("/liputan?q=posyandu"), ["Rapat Posyandu", "Zoom Kemendagri"])
        self.assertEqual(judul("/liputan?q=Wakil"), ["Upacara Hari Pahlawan"])
        self.assertEqual(judul("/liputan?tahun=2026"), ["Rapat Posyandu", "Zoom Kemendagri"])
        self.assertEqual(judul("/liputan?tahun=2026&bulan=3"), ["Zoom Kemendagri"])
        self.assertEqual(judul("/liputan?status=final"), ["Upacara Hari Pahlawan"])

    def test_spt_terhubung_dan_paket(self):
        # Buat SPT lewat Pemecah SPT
        sumber = fx.batch_contoh(self.folder / "batch.docx")
        r = self.klien.post("/spt/analisis", content_type="multipart/form-data", data={
            "csrf_token": self.token("/spt"), "format": "word", "berkas": (io.BytesIO(sumber.read_bytes()), "b.docx")})
        lokasi = r.location
        r = self.klien.post("/spt/proses", data={"csrf_token": self.token(lokasi), "token": lokasi.rsplit("/", 1)[1], "pilih": ["1"]})
        for _ in range(200):
            if self.klien.get(f"{r.location}/status").get_json()["selesai"]:
                break
        spt_id, nomor = self.db().execute("SELECT id, nomor FROM spt").fetchone()
        r, lid = self.buat(spt_id=str(spt_id), q=nomor)
        self.assertIn(nomor, self.klien.get(f"/liputan?q={nomor}").get_data(as_text=True))
        self.ekspor(lid)
        paket = self.klien.get(f"/liputan/{lid}/paket")
        nama = zipfile.ZipFile(io.BytesIO(paket.data)).namelist()
        self.assertEqual(len(nama), 2)
        self.assertTrue(any(n.startswith("SPT/") and n.endswith(".docx") for n in nama))
        unduh = self.klien.get(f"/liputan/spt/{spt_id}/docx")
        self.addCleanup(unduh.close)
        self.assertEqual(unduh.status_code, 200)
        # Menghapus batch SPT melepas tautan (ON DELETE SET NULL), arsip tetap ada
        self.klien.post("/spt/hapus", data={"csrf_token": self.token("/spt"), "batch": ["1"]})
        self.assertEqual(self.db().execute("SELECT spt_id FROM liputan").fetchone()[0], None)

    def test_hapus_kegiatan_menghapus_berkas(self):
        _, lid = self.buat()
        self.unggah(lid, [("a.png", fl.foto(300, 200, "PNG"))])
        self.ekspor(lid)
        folder = self.folder_kegiatan(lid)
        self.assertTrue((folder / "ekspor").is_dir() and (folder / "foto").is_dir())
        r = self.klien.post(f"/liputan/{lid}/hapus", data={"csrf_token": self.token(f"/liputan/{lid}")})
        self.assertTrue(r.location.endswith("/liputan"))
        self.assertFalse(folder.exists())
        self.assertFalse(folder.parent.exists(), "folder bulan yang kosong ikut dibersihkan")
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM liputan_foto").fetchone()[0], 0)
        self.assertEqual(self.klien.get(f"/liputan/{lid}").status_code, 404)

    @staticmethod
    def potong_panel(html):
        awal = html.index('id="panel-laporan"')
        return html[awal:html.index("</aside>", awal)]

    def test_panel_kelengkapan_dan_ekspor(self):
        html = self.klien.get("/liputan/baru").get_data(as_text=True)
        self.assertIn('id="panel-laporan"', html)
        self.assertIn("Word dapat dibuat setelah kegiatan disimpan", html)
        self.assertNotIn("Buat Word", html)
        _, lid = self.buat()
        html = self.klien.get(f"/liputan/{lid}").get_data(as_text=True)
        panel = self.potong_panel(html)
        for teks in ("Kelengkapan", "Buat Word", "Hapus kegiatan"):
            self.assertIn(teks, panel)
        self.assertRegex(panel, r">4</span> dari 5 wajib")   # tanggal, judul, isi, kegiatan; foto belum
        self.assertNotIn("Unduh Word", panel)
        # butir pelengkap yang belum diisi bertanda netral (opsional), bukan silang merah seperti butir wajib
        self.assertIn(": belum diisi (opsional)", panel)
        pelengkap = panel[panel.index('data-kelengkapan="spt"'):]
        pelengkap = pelengkap[:pelengkap.index("</li>")]
        self.assertIn("text-redup", pelengkap.split("data-tanda-belum")[0].rsplit("<span", 1)[1])
        self.unggah(lid, [("a.png", fl.foto(300, 200, "PNG"))])
        self.ekspor(lid)
        html = self.klien.get(f"/liputan/{lid}").get_data(as_text=True)
        panel = self.potong_panel(html)
        for teks in ("Buat ulang Word", "Unduh Word", "Unduh paket ZIP"):
            self.assertIn(teks, panel)
        self.assertRegex(panel, r">5</span> dari 5 wajib")   # foto ada (keterangan hanya pelengkap)
        self.assertRegex(panel, r'data-kelengkapan="word"\s+data-lengkap="1"')

    # ---------- Susunan per bulan kegiatan ----------
    def test_berkas_disimpan_per_bulan_kegiatan(self):
        _, lid = self.buat(tanggal="2026-10-13")
        self.unggah(lid, [("a.png", fl.foto(300, 200, "PNG"))])
        self.ekspor(lid)
        folder = self.folder / "instance" / "data" / "liputan" / "2026" / "10-Oktober" / str(lid)
        self.assertTrue((folder / "foto").is_dir() and (folder / "ekspor").is_dir())
        log = self.db().execute("SELECT lokasi FROM log_proses WHERE aksi='Ekspor Word'").fetchone()[0]
        self.assertIn("10-Oktober", log)

    def test_ganti_bulan_memindahkan_folder(self):
        _, lid = self.buat(tanggal="2026-10-13")
        self.unggah(lid, [("a.png", fl.foto(300, 200, "PNG"))])
        lama = self.folder_kegiatan(lid)
        data = {"csrf_token": self.token(f"/liputan/{lid}"), "tanggal": "2026-11-02", "tokoh": "Wali",
                "kegiatan": "Rapat", "judul": "Judul", "isi": "Isi", "foto_per_lembar": "2", "status": "draf", "spt_id": ""}
        self.klien.post(f"/liputan/{lid}/simpan", data=data)
        baru = self.folder_kegiatan(lid)
        self.assertIn("11-November", str(baru))
        self.assertTrue((baru / "foto").is_dir())
        self.assertFalse(lama.exists())
        self.assertFalse(lama.parent.exists(), "folder Oktober yang kosong dibersihkan")
        fid = self.db().execute("SELECT id FROM liputan_foto").fetchone()[0]
        r = self.klien.get(f"/liputan/{lid}/foto/{fid}")
        self.addCleanup(r.close)
        self.assertEqual(r.status_code, 200)

    def test_gagal_pindah_folder_tanggal_tidak_berubah(self):
        _, lid = self.buat(tanggal="2026-10-13")
        self.unggah(lid, [("a.png", fl.foto(300, 200, "PNG"))])
        data = {"csrf_token": self.token(f"/liputan/{lid}"), "tanggal": "2026-12-01", "tokoh": "Wali",
                "kegiatan": "Rapat", "judul": "Judul", "isi": "Isi", "foto_per_lembar": "2", "status": "draf", "spt_id": ""}
        with mock.patch("app.modul.arsip_liputan.layanan.shutil.move", side_effect=PermissionError("terkunci")):
            r = self.klien.post(f"/liputan/{lid}/simpan", data=data)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.db().execute("SELECT tanggal FROM liputan").fetchone()[0], "2026-10-13")
        self.assertTrue((self.folder_kegiatan(lid) / "foto").is_dir())

    def test_folder_versi_lama_dipindah_saat_aplikasi_dinyalakan(self):
        _, lid = self.buat(tanggal="2025-03-05")
        self.unggah(lid, [("a.png", fl.foto(300, 200, "PNG"))])
        baru = self.folder_kegiatan(lid)
        lama = self.folder / "instance" / "data" / "liputan" / str(lid)
        shutil.move(str(baru), str(lama))                      # tiru susunan versi lama
        create_app({"TESTING": True}, instance_path=str(self.folder / "instance"))
        self.assertTrue((baru / "foto").is_dir())
        self.assertFalse(lama.exists())

    def test_arsip_dikelompokkan_per_bulan(self):
        self.buat(judul="Rapat A", tanggal="2026-10-04")
        self.buat(judul="Rapat B", tanggal="2026-10-20")
        self.buat(judul="Upacara", tanggal="2026-11-10")
        self.buat(judul="Zoom Lama", tanggal="2025-03-01")
        html = self.klien.get("/liputan").get_data(as_text=True)
        posisi = [html.index(t) for t in ("November 2026", "Oktober 2026", "Maret 2025")]
        self.assertEqual(posisi, sorted(posisi), "bulan terbaru di atas")
        self.assertRegex(html, r"Oktober 2026</h2>\s*<p[^>]*>2 kegiatan")
        self.assertLess(html.index("Rapat B"), html.index("Rapat A"))   # dalam bulan: tanggal terbaru dulu
        html = self.klien.get("/liputan?q=Upacara").get_data(as_text=True)
        self.assertIn("November 2026", html)
        self.assertNotIn("Oktober 2026", html)   # bulan tanpa hasil pencarian tidak ditampilkan

    def test_tanda_perlu_ekspor_ulang(self):
        _, lid = self.buat()
        self.ekspor(lid)
        self.assertNotIn("Ada perubahan setelah Word", self.klien.get(f"/liputan/{lid}").get_data(as_text=True))
        db = self.db()
        db.execute("UPDATE liputan SET diekspor = '2000-01-01 00:00:00'")
        db.commit()
        self.assertIn("Ada perubahan setelah Word", self.klien.get(f"/liputan/{lid}").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
