"""Uji modul Pemecah SPT. Jalankan: python -m unittest -v"""
import io
import re
import shutil
import sqlite3
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from docx import Document

from app import create_app
from app.modul.pemecah_spt import pdf
from app.modul.pemecah_spt.pemecah import GalatBerkas, analisis, pecah_satu, validasi_berkas
from app.modul.pemecah_spt.penamaan import beri_nama, bersihkan
from tests import fixture_spt as fx

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DasarBerkas(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def simpan(self, doc, nama="uji.docx"):
        jalur = self.folder / nama
        doc.save(str(jalur))
        return jalur


class UjiDeteksi(DasarBerkas):
    def test_beberapa_spt_beruntun(self):
        doc = fx.dokumen_f4()
        for n in ("A/1", "A/2", "A/3"):
            fx.judul(doc)
            fx.isi(doc, n)
            fx.ganti_halaman(doc)
        hasil = analisis(self.simpan(doc))
        self.assertEqual([i.nomor for i in hasil.daftar], ["A/1", "A/2", "A/3"])
        self.assertEqual(hasil.peringatan, [])

    def test_batch_contoh_lengkap(self):
        hasil = analisis(fx.batch_contoh(self.folder / "batch.docx"))
        self.assertEqual(len(hasil.daftar), 6)   # pengecoh tidak terhitung
        nomor = [i.nomor for i in hasil.daftar]
        self.assertEqual(nomor[1], "800.1.11.1/102/Prokopim/2026")   # judul terpecah
        self.assertEqual(nomor[3], "800.1.11.1/103/Prokopim/2026")   # judul dari gaya (basedOn)
        self.assertEqual(nomor[4], "800.1.11.1/104/Prokopim/2026")   # nomor di sel tabel
        self.assertEqual(nomor[5], "SPT_urut-6")                     # nomor tidak terbaca
        self.assertFalse(hasil.daftar[5].nomor_terbaca)
        self.assertEqual([i.kembar for i in hasil.daftar], [True, False, True, False, False, False])
        self.assertTrue(any("sebelum SPT pertama" in p for p in hasil.peringatan))

    def test_frasa_dalam_kalimat_tidak_terdeteksi(self):
        doc = fx.dokumen_f4()
        p = doc.add_paragraph()
        r = p.add_run("Berdasarkan Surat Perintah Tugas Nomor 5")
        r.bold = r.underline = True
        fx.judul(doc)
        fx.isi(doc, "B/1")
        self.assertEqual(len(analisis(self.simpan(doc)).daftar), 1)

    def test_judul_tanpa_underline_tidak_terdeteksi(self):
        doc = fx.dokumen_f4()
        fx.judul(doc, underline=False)
        fx.isi(doc, "C/1")
        with self.assertRaises(GalatBerkas):
            analisis(self.simpan(doc))

    def test_underline_none_dan_bold_false_dihormati(self):
        doc = fx.dokumen_f4()
        gaya = fx.gaya_judul(doc)
        p = fx.judul(doc, gaya=gaya)
        p.runs[0].font.underline = False   # menulis <w:u w:val="none"/> di atas gaya
        fx.isi(doc, "C/2")
        with self.assertRaises(GalatBerkas):
            analisis(self.simpan(doc))

    def test_tanpa_judul_galat_jelas(self):
        doc = fx.dokumen_f4()
        doc.add_paragraph("Hanya surat biasa.")
        with self.assertRaisesRegex(GalatBerkas, "Tidak ditemukan judul SPT"):
            analisis(self.simpan(doc))

    def test_peringatan_multi_seksi(self):
        doc = fx.dokumen_f4()
        fx.judul(doc)
        fx.isi(doc, "D/1")
        doc.add_section()
        fx.judul(doc)
        fx.isi(doc, "D/2")
        hasil = analisis(self.simpan(doc))
        self.assertTrue(any("seksi" in p for p in hasil.peringatan))


class UjiPemecahan(DasarBerkas):
    def test_hasil_valid_f4_kop_dan_isi_terpisah(self):
        sumber = fx.batch_contoh(self.folder / "batch.docx")
        hasil = analisis(sumber)
        for info in hasil.daftar:
            tujuan = self.folder / f"hasil-{info.urutan}.docx"
            pecah_satu(sumber, info, tujuan)
            doc = Document(str(tujuan))   # harus bisa dibuka ulang
            seksi = doc.sections[0]
            self.assertAlmostEqual(seksi.page_width.mm, 215, places=0)
            self.assertAlmostEqual(seksi.page_height.mm, 330, places=0)
            self.assertIn(fx.KOP, seksi.header.paragraphs[0].text)
            teks = "\n".join(p.text for p in doc.paragraphs)
            self.assertTrue(teks.startswith("SURAT PERINTAH TUGAS"))
            # SPT 2 sengaja memuat pengecoh (judul tanpa garis bawah) yang memang bagian isinya
            self.assertEqual(teks.count("SURAT PERINTAH TUGAS"), 2 if info.urutan == 2 else 1)
            self.assertNotIn("Catatan pengantar", teks)
            body = doc.element.body
            self.assertEqual(len(body.findall(f".//{W}pPr/{W}sectPr")), 0)   # tanpa section break liar
            self.assertFalse(any(b.get(f"{W}type") == "page" for b in body.iter(f"{W}br")))
        # Nomor di tabel ikut terbawa
        doc5 = Document(str(self.folder / "hasil-5.docx"))
        self.assertEqual(doc5.tables[0].rows[0].cells[2].text, "800.1.11.1/104/Prokopim/2026")

    def test_kop_seksi_kedua_mewarisi_dari_seksi_pertama(self):
        doc = fx.dokumen_f4()
        fx.judul(doc)
        fx.isi(doc, "E/1")
        doc.add_section()   # seksi baru tanpa header sendiri (mewarisi)
        fx.judul(doc)
        fx.isi(doc, "E/2")
        sumber = self.simpan(doc)
        info = analisis(sumber).daftar[1]
        tujuan = self.folder / "e2.docx"
        pecah_satu(sumber, info, tujuan)
        hasil = Document(str(tujuan))
        self.assertIn(fx.KOP, hasil.sections[0].header.paragraphs[0].text)
        self.assertEqual(len(hasil.sections), 1)


class UjiMigrasi(DasarBerkas):
    def test_kolom_progres_ditambahkan_ke_database_lama(self):
        instance = self.folder / "lama"
        instance.mkdir()
        db = sqlite3.connect(instance / "superapp.db")
        db.execute("CREATE TABLE spt_batch (id INTEGER PRIMARY KEY, pengguna_id INTEGER, nama_berkas_asli TEXT, "
                   "format_keluaran TEXT, jumlah INTEGER, folder TEXT, status TEXT, catatan TEXT, dibuat TEXT)")
        db.commit()
        db.close()
        create_app({"TESTING": True}, instance_path=str(instance))
        db = sqlite3.connect(instance / "superapp.db")
        kolom = {b[1] for b in db.execute("PRAGMA table_info(spt_batch)")}
        db.close()
        self.assertTrue({"progres", "total_langkah", "tahap"} <= kolom)


class UjiPdfProgres(DasarBerkas):
    @unittest.skipUnless(pdf.pengonversi_tersedia(), "Microsoft Word / LibreOffice tidak tersedia")
    def test_progres_dilaporkan(self):
        sumber = fx.batch_contoh(self.folder / "batch.docx")
        daftar = []
        for info in analisis(sumber).daftar[:3]:
            tujuan = self.folder / f"{info.urutan}.docx"
            pecah_satu(sumber, info, tujuan)
            daftar.append(tujuan)
        laporan = []
        hasil = pdf.konversi_ke_pdf(daftar, self.folder, lambda jadi, nama: laporan.append(jadi))
        self.assertIsNone(hasil.galat)
        self.assertTrue(laporan)
        self.assertEqual(laporan[-1], 3)
        self.assertEqual(laporan, sorted(laporan))


class UjiPenamaan(unittest.TestCase):
    def test_sanitasi(self):
        self.assertEqual(bersihkan("800 / 12 \\ Prokopim/2026"), "800-12-Prokopim-2026")
        self.assertEqual(bersihkan('A:B*C?"D<E>F|G'), "ABCDEFG")
        self.assertEqual(bersihkan("  nama.  "), "nama")
        self.assertEqual(bersihkan("CON"), "_CON")
        self.assertEqual(bersihkan("com1.txt"), "_com1.txt")
        self.assertEqual(bersihkan("a\x00b\x1fc"), "abc")
        self.assertEqual(len(bersihkan("x" * 300)), 100)
        self.assertEqual(bersihkan("///", "SPT_urut-3"), "---")
        self.assertEqual(bersihkan("::", "SPT_urut-3"), "SPT_urut-3")

    def test_duplikat_semua_anggota_diberi_akhiran(self):
        nama = beri_nama(["A/1", "B/2", "a/1", "C/3", "A/1"])
        self.assertEqual(nama, ["A-1 (1)", "B-2", "a-1 (2)", "C-3", "A-1 (3)"])

    def test_tetap_unik_bila_bentrok(self):
        nama = beri_nama(["X (1)", "X", "X"])
        self.assertEqual(len({n.casefold() for n in nama}), 3)


class UjiValidasi(DasarBerkas):
    def test_bukan_docx_ditolak(self):
        palsu = self.folder / "palsu.docx"
        palsu.write_text("bukan zip")
        with self.assertRaisesRegex(GalatBerkas, "bukan dokumen"):
            validasi_berkas(palsu, "palsu.docx")

    def test_doc_dan_docm_ditolak(self):
        jalur = self.simpan(fx.dokumen_f4())
        with self.assertRaisesRegex(GalatBerkas, r"\.doc"):
            validasi_berkas(jalur, "lama.doc")
        with self.assertRaisesRegex(GalatBerkas, "makro"):
            validasi_berkas(jalur, "makro.docm")

    def test_zip_tanpa_document_xml_ditolak(self):
        jalur = self.folder / "zip.docx"
        with zipfile.ZipFile(jalur, "w") as z:
            z.writestr("isi.txt", "halo")
        with self.assertRaisesRegex(GalatBerkas, "bukan dokumen Word"):
            validasi_berkas(jalur, "zip.docx")

    def test_docx_valid_lolos(self):
        validasi_berkas(self.simpan(fx.dokumen_f4()), "baik.docx")


# ---------- Alur web ----------
class UjiAlurWeb(DasarBerkas):
    def setUp(self):
        super().setUp()
        self.app = create_app({"TESTING": True}, instance_path=str(self.folder / "instance"))
        self.klien = self.app.test_client()
        tok = self.token("/siapkan")
        self.klien.post("/siapkan", data={"csrf_token": tok, "nama_lengkap": "Budi Santoso",
                                          "nama_pengguna": "budi", "sandi": "rahasia123", "konfirmasi": "rahasia123"})
        self.sumber = fx.batch_contoh(self.folder / "batch.docx")

    def token(self, url, klien=None):
        html = (klien or self.klien).get(url).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def unggah(self, format_keluaran="word", jalur=None, nama="Batch SPT November.docx"):
        data = {"csrf_token": self.token("/spt"), "format": format_keluaran,
                "berkas": (io.BytesIO(Path(jalur or self.sumber).read_bytes()), nama)}
        return self.klien.post("/spt/analisis", data=data, content_type="multipart/form-data")

    def proses(self, lokasi_pratinjau, pilih, tunggu=True):
        token = lokasi_pratinjau.rsplit("/", 1)[1]
        r = self.klien.post("/spt/proses", data={"csrf_token": self.token(lokasi_pratinjau),
                                                 "token": token, "pilih": [str(p) for p in pilih]})
        if tunggu and "/spt/batch/" in (r.location or ""):
            self.tunggu_selesai(r.location)
        return r

    def tunggu_selesai(self, lokasi_batch, batas=120):
        """Proses berjalan di thread latar; tanya status seperti yang dilakukan halaman hasil."""
        url = f"{lokasi_batch}/status"
        mulai = time.monotonic()
        while time.monotonic() - mulai < batas:
            data = self.klien.get(url).get_json()
            if data["selesai"]:
                return data
            time.sleep(0.1)
        self.fail("Proses latar tidak selesai")

    def db(self):
        if not hasattr(self, "_db"):
            self._db = sqlite3.connect(self.folder / "instance" / "superapp.db")
            self.addCleanup(self._db.close)
        return self._db

    def test_alur_lengkap_word(self):
        r = self.unggah()
        self.assertIn("/spt/pratinjau/", r.location)
        html = self.klien.get(r.location).get_data(as_text=True)
        for teks in ("6 SPT ditemukan", "Nomor kembar", "Nomor tidak terbaca",
                     "800.1.11.1-101-Prokopim-2026 (1)", "800.1.11.1-101-Prokopim-2026 (2)"):
            self.assertIn(teks, html)

        r = self.proses(r.location, [1, 2, 3, 6])          # SPT 4 & 5 tidak dicentang
        self.assertRegex(r.location, r"/spt/batch/\d+$")
        html = self.klien.get(r.location).get_data(as_text=True)
        self.assertIn("Unduh semua (ZIP)", html)
        self.assertEqual(len(list((self.folder / "instance" / "tmp").glob("*"))), 0)   # unggahan sementara dihapus

        baris = self.db().execute("SELECT id, nama_docx, status FROM spt ORDER BY urutan").fetchall()
        self.assertEqual([b[1] for b in baris], ["800.1.11.1-101-Prokopim-2026 (1).docx",
                                                 "800.1.11.1-102-Prokopim-2026.docx",
                                                 "800.1.11.1-101-Prokopim-2026 (2).docx", "SPT_urut-6.docx"])
        unduh = self.klien.get(f"/spt/unduh/{baris[0][0]}/docx")
        self.addCleanup(unduh.close)
        self.assertEqual(unduh.status_code, 200)
        Document(io.BytesIO(unduh.data))   # berkas unduhan valid
        self.assertEqual(self.klien.get(f"/spt/unduh/{baris[0][0]}/pdf").status_code, 404)

        batch_id = r.location.rsplit("/", 1)[1]
        z = zipfile.ZipFile(io.BytesIO(self.klien.get(f"/spt/batch/{batch_id}/zip").data))
        self.assertEqual(len(z.namelist()), 4)

        log = self.db().execute("SELECT modul, aksi, status, lokasi FROM log_proses WHERE modul='pemecah_spt'").fetchall()
        self.assertEqual([l[1] for l in log], ["Analisis batch", "Pecah batch"])
        self.assertTrue(log[1][3].endswith(f"spt{Path('/').as_posix()}{batch_id}") or log[1][3].endswith(batch_id))
        self.assertIn("Pemecah SPT", self.klien.get("/log").get_data(as_text=True))

    def test_tanpa_pengonversi_tetap_word_status_sebagian(self):
        r = self.unggah("keduanya")
        with mock.patch.object(pdf, "word_tersedia", return_value=False), \
                mock.patch.object(pdf, "cari_soffice", return_value=None):
            r = self.proses(r.location, [1, 2])
        html = self.klien.get(r.location).get_data(as_text=True)
        self.assertIn("LibreOffice", html)
        status = self.db().execute("SELECT status, nama_docx, nama_pdf FROM spt").fetchall()
        self.assertTrue(all(s[0] == "sebagian" and s[1] and s[2] is None for s in status))
        self.assertEqual(self.db().execute("SELECT status FROM spt_batch").fetchone()[0], "sebagian")

    @unittest.skipUnless(pdf.pengonversi_tersedia(), "Microsoft Word / LibreOffice tidak tersedia")
    def test_pdf_dibuat(self):
        r = self.proses(self.unggah("pdf").location, [1, 2])
        baris = self.db().execute("SELECT id, nama_docx, nama_pdf, status FROM spt").fetchall()
        self.assertTrue(all(b[1] is None and b[2].endswith(".pdf") and b[3] == "sukses" for b in baris))
        unduh = self.klien.get(f"/spt/unduh/{baris[0][0]}/pdf")
        self.addCleanup(unduh.close)
        self.assertTrue(unduh.data.startswith(b"%PDF"))
        self.assertIn("/batch/", r.location)

    def test_unggahan_bukan_docx_ditolak(self):
        palsu = self.folder / "palsu.docx"
        palsu.write_bytes(b"MZ bukan word")
        r = self.unggah(jalur=palsu, nama="palsu.docx")
        self.assertTrue(r.location.endswith("/spt"))
        self.assertIn("bukan dokumen .docx", self.klien.get("/spt").get_data(as_text=True))
        self.assertEqual(self.db().execute("SELECT status FROM log_proses WHERE modul='pemecah_spt'").fetchone()[0], "gagal")

    def test_jalur_unduhan_di_luar_folder_ditolak(self):
        self.proses(self.unggah().location, [1])
        db = self.db()
        db.execute("UPDATE spt SET nama_docx = '../../secret_key'")
        db.commit()
        spt_id = db.execute("SELECT id FROM spt").fetchone()[0]
        self.assertEqual(self.klien.get(f"/spt/unduh/{spt_id}/docx").status_code, 404)
        db.execute("UPDATE spt_batch SET folder = ?", (str(self.folder / "instance"),))
        db.execute("UPDATE spt SET nama_docx = 'secret_key'")
        db.commit()
        self.assertEqual(self.klien.get(f"/spt/unduh/{spt_id}/docx").status_code, 404)
        self.assertEqual(self.klien.get(f"/spt/unduh/{spt_id}/exe").status_code, 404)

    def test_pratinjau_terikat_ke_pengguna(self):
        lokasi = self.unggah().location
        db = self.db()
        db.execute("INSERT INTO pengguna (nama_lengkap, nama_pengguna, sandi_hash, sesi_token) "
                   "VALUES ('Lain', 'lain', (SELECT sandi_hash FROM pengguna WHERE id = 1), 'x')")
        db.commit()
        lain = self.app.test_client()
        lain.post("/masuk", data={"csrf_token": self.token("/masuk", lain), "nama_pengguna": "lain", "sandi": "rahasia123"})
        r = lain.get(lokasi)
        self.assertTrue(r.location.endswith("/spt"))
        self.assertEqual(lain.get("/spt/batch/1").status_code, 404)

    def test_progres_dan_status(self):
        r = self.proses(self.unggah("keduanya").location, [1, 2, 3], tunggu=False)
        html = self.klien.get(r.location).get_data(as_text=True)
        # Halaman hasil langsung terbuka: masih memproses (progress bar) atau sudah selesai
        self.assertTrue("data-pantau-progres" in html or "Hasil pemecahan" in html)
        data = self.tunggu_selesai(r.location)
        self.assertEqual(data["status"], "sukses" if pdf.pengonversi_tersedia() else "sebagian")
        self.assertEqual((data["progres"], data["total"], data["persen"]), (6, 6, 100))
        self.assertTrue(data["pesan"])
        self.assertNotIn("data-pantau-progres", self.klien.get(r.location).get_data(as_text=True))
        self.assertEqual(self.klien.get("/spt/batch/999/status").status_code, 404)

    def test_halaman_proses_menampilkan_progress_bar(self):
        db = self.db()
        db.execute("INSERT INTO spt_batch (pengguna_id, nama_berkas_asli, format_keluaran, status, "
                   "progres, total_langkah, tahap) VALUES (1, 'x.docx', 'word', 'proses', 2, 4, 'Memecah SPT 3 dari 4')")
        db.commit()
        html = self.klien.get("/spt/batch/1").get_data(as_text=True)
        self.assertIn('role="progressbar"', html)
        self.assertIn('aria-valuenow="50"', html)
        self.assertIn("Memecah SPT 3 dari 4", html)
        self.assertIn("Diproses", self.klien.get("/spt").get_data(as_text=True))
        status = self.klien.get("/spt/batch/1/status").get_json()
        self.assertEqual((status["selesai"], status["persen"]), (False, 50))

    def test_token_hanya_bisa_diproses_sekali(self):
        lokasi = self.unggah().location
        token = lokasi.rsplit("/", 1)[1]
        csrf = self.token(lokasi)
        self.proses(lokasi, [1])
        r = self.klien.post("/spt/proses", data={"csrf_token": csrf, "token": token, "pilih": ["1"]})
        self.assertTrue(r.location.endswith("/spt"))
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM spt_batch").fetchone()[0], 1)

    def test_batch_tertinggal_ditandai_gagal_saat_aplikasi_dinyalakan(self):
        db = self.db()
        db.execute("INSERT INTO spt_batch (pengguna_id, nama_berkas_asli, format_keluaran, status) "
                   "VALUES (1, 'x.docx', 'word', 'proses')")
        db.commit()
        create_app({"TESTING": True}, instance_path=str(self.folder / "instance"))
        self.assertEqual(self.db().execute("SELECT status FROM spt_batch").fetchone()[0], "gagal")

    def test_tanpa_centang_ditolak(self):
        lokasi = self.unggah().location
        r = self.proses(lokasi, [])
        self.assertEqual(r.location, lokasi)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM spt_batch").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
