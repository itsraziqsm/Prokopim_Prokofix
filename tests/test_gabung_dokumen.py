"""Uji Utilitas > Gabungkan PDF: rentang halaman, penamaan, penggabungan (pypdf), alur web, keamanan."""
import io
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from pypdf import PdfReader
from werkzeug.test import EnvironBuilder

from app import create_app
from app.modul.utilitas.gabung_dokumen import layanan, penggabung
from app.modules_registry import kelompok_alat
from app.waktu import tanggal_tanpa_hari
from tests import fixture_pdf as fp

SANDI = "rahasia123"


def lebar_halaman(jalur_atau_bytes):
    sumber = io.BytesIO(jalur_atau_bytes) if isinstance(jalur_atau_bytes, bytes) else str(jalur_atau_bytes)
    return [int(h.mediabox.width) for h in PdfReader(sumber).pages]


# ====================== Rentang halaman ======================
class UjiRentang(unittest.TestCase):
    def test_rentang_valid(self):
        u = penggabung.urai_rentang
        self.assertEqual(u("1-3,5,8-", 9), [0, 1, 2, 4, 7, 8])
        self.assertEqual(u("", 3), [0, 1, 2])
        self.assertEqual(u("  Semua ", 2), [0, 1])
        self.assertEqual(u(" 3 , 1 - 2 ", 5), [2, 0, 1])      # spasi diabaikan, urutan mengikuti penulisan
        self.assertEqual(u("2-", 4), [1, 2, 3])
        self.assertEqual(u("4", 4), [3])
        self.assertEqual(u("1–2", 3), [0, 1])                   # tanda pisah panjang diterima
        self.assertEqual(u("1,,2,", 3), [0, 1])                 # koma berlebih diabaikan

    def test_rentang_tidak_valid(self):
        kasus = {
            "0": "dimulai dari 1", "0-2": "dimulai dari 1", "2-0": "dimulai dari 1",
            "5-3": "terbalik", "6": "melebihi", "2-9": "melebihi", "7-": "melebihi",
            "abc": "bukan nomor", "1-2-3": "bukan nomor", "-3": "bukan nomor", "1.5": "bukan nomor", ",": "tidak ada halaman",
        }
        for teks, pesan in kasus.items():
            with self.subTest(teks=teks), self.assertRaises(penggabung.GalatRentang) as k:
                penggabung.urai_rentang(teks, 5)
            self.assertIn(pesan, str(k.exception))


class UjiNamaBerkas(unittest.TestCase):
    def test_sanitasi_dan_unik(self):
        n = penggabung.nama_berkas_hasil
        self.assertEqual(n('Laporan: "akhir"/2026?'), "Laporan- -akhir--2026-.pdf")
        self.assertEqual(n("rekap.PDF"), "rekap.pdf")
        self.assertEqual(n("CON"), "CON (berkas).pdf")
        self.assertEqual(n("lpt1.pdf"), "lpt1 (berkas).pdf")
        self.assertEqual(n("  ..  ", bawaan="Gabungan 1 Mei 2026.pdf"), "Gabungan 1 Mei 2026.pdf")
        self.assertEqual(len(n("x" * 300)), 100)
        self.assertTrue(n("x" * 300).endswith(".pdf"))
        self.assertEqual(n("a.pdf", ["a.pdf", "A (1).pdf"]), "a (2).pdf")
        self.assertEqual(len(n("y" * 300, ["y" * 96 + ".pdf"])), 100)


# ====================== Penggabung (tanpa Flask) ======================
class UjiPenggabung(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def tulis(self, nama, data):
        (self.folder / nama).write_bytes(data)
        return self.folder / nama

    def test_gabung_urutan_rentang_bookmark_metadata(self):
        a = self.tulis("a.pdf", fp.pdf(3, dasar=100))
        b = self.tulis("b.pdf", fp.pdf(4, dasar=200, aksi_buka=True))
        c = self.tulis("c.pdf", fp.pdf(2, dasar=300))
        sumber = [{"jalur": b, "halaman": [3, 0], "judul": "Berkas B"},
                  {"jalur": a, "halaman": [0, 1, 2], "judul": "Berkas A"},
                  {"jalur": c, "halaman": [1], "judul": "Berkas C"}]
        tujuan = self.folder / "hasil.pdf"
        self.assertEqual(penggabung.gabungkan(sumber, tujuan, "Gabungan Uji", daftar_isi=True), 6)
        self.assertEqual(lebar_halaman(tujuan), [203, 200, 100, 101, 102, 301])
        pembaca = PdfReader(str(tujuan))
        self.assertEqual([(o.title, pembaca.get_destination_page_number(o)) for o in pembaca.outline],
                         [("Berkas B", 0), ("Berkas A", 2), ("Berkas C", 5)])
        self.assertEqual(pembaca.metadata.title, "Gabungan Uji")
        akar = pembaca.trailer["/Root"]
        self.assertNotIn("/OpenAction", akar)                   # tindakan otomatis dokumen tidak ikut
        self.assertNotIn("/JavaScript", akar.get("/Names", {}))

    def test_tanpa_daftar_isi(self):
        a = self.tulis("a.pdf", fp.pdf(2))
        tujuan = self.folder / "hasil.pdf"
        penggabung.gabungkan([{"jalur": a, "halaman": [0, 1], "judul": "A"}], tujuan, "T", daftar_isi=False)
        self.assertEqual(PdfReader(str(tujuan)).outline, [])

    def test_pemeriksaan_berkas(self):
        self.assertEqual(penggabung.periksa_pdf(self.tulis("a.pdf", fp.pdf(5))), 5)
        with self.assertRaisesRegex(penggabung.GalatBerkas, "terkunci kata sandi"):
            penggabung.periksa_pdf(self.tulis("k.pdf", fp.pdf(1, sandi="rahasia")))
        with self.assertRaisesRegex(penggabung.GalatBerkas, "rusak"):
            penggabung.periksa_pdf(self.tulis("r.pdf", fp.pdf_rusak()))
        self.assertTrue(penggabung.tanda_pdf(fp.pdf(1)[:1024]))
        self.assertFalse(penggabung.tanda_pdf(fp.bukan_pdf()))

    def test_sumber_selain_pdf_belum_didukung(self):
        self.assertEqual(penggabung.siapkan_sumber(self.folder / "x.pdf"), self.folder / "x.pdf")
        with self.assertRaisesRegex(penggabung.GalatBerkas, "belum didukung"):
            penggabung.siapkan_sumber(self.folder / "x.docx")


# ====================== Web ======================
class DasarWeb(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.app = create_app({"TESTING": True}, instance_path=str(self.folder))
        self.klien = self.app.test_client()
        self.klien.post("/siapkan", data={"csrf_token": self.token("/siapkan"), "nama_lengkap": "Budi",
                                          "nama_pengguna": "budi", "sandi": SANDI, "konfirmasi": SANDI})

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def token(self, url="/akun", klien=None):
        html = (klien or self.klien).get(url).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def db(self):
        koneksi = sqlite3.connect(self.folder / "superapp.db")
        koneksi.row_factory = sqlite3.Row
        return closing(koneksi)

    def kirim(self, url, berkas=(), **data):
        """POST multipart; berkas sementara alat uji Werkzeug ikut ditutup."""
        isian = {"csrf_token": self.token(), **data}
        if berkas:
            isian["berkas"] = [(io.BytesIO(isi), nama) for nama, isi in berkas]
        pembangun = EnvironBuilder(path=url, method="POST", data=isian)
        environ = pembangun.get_environ()
        try:
            r = self.klien.open(environ)
            r.close()
        finally:
            environ["wsgi.input"].close()
            pembangun.close()
        return r

    def unggah(self, berkas):
        r = self.kirim("/utilitas/gabung/unggah", berkas)
        token = r.location.rstrip("/").split("/")[-1] if r.status_code == 302 and "/gabung/" in r.location else None
        return r, token

    def sesi(self, token):
        return json.loads((self.folder / "tmp" / "gabung_dokumen" / token / "sesi.json").read_text(encoding="utf-8"))

    def nama_urut(self, token):
        return [b["nama"] for b in self.sesi(token)["berkas"]]

    def pesan_flash(self):
        with self.klien.session_transaction() as s:
            return " ".join(p for _, p in s.get("_flashes", []))


class UjiAlurWeb(DasarWeb):
    def test_alur_penuh_unggah_susun_gabung_unduh(self):
        r, token = self.unggah([("a.pdf", fp.pdf(3, 100)), ("b.pdf", fp.pdf(2, 200)), ("c.pdf", fp.pdf(4, 300))])
        self.assertIsNotNone(token, r.location)
        html = self.klien.get(f"/utilitas/gabung/{token}").get_data(as_text=True)
        for teks in ("a.pdf", "b.pdf", "c.pdf", 'placeholder="1-3,5,8-"', "data-tombol-progres", f"Gabungan {tanggal_tanpa_hari()}.pdf"):
            self.assertIn(teks, html)
        b_id = self.sesi(token)["berkas"][1]["id"]
        # Naik b: rentang yang diketik ikut tersimpan oleh rute aksi
        isian = {f"rentang_{x['id']}": r for x, r in zip(self.sesi(token)["berkas"], ("3,1", "", "2-"))}
        r = self.kirim(f"/utilitas/gabung/{token}/aksi", aksi=f"naik:{b_id}", nama_hasil="Rekap: Mei",
                       daftar_isi_dikirim="1", daftar_isi="1", **isian)
        self.assertIn(f"fokus=naik-{b_id}", r.location)
        self.assertEqual(self.nama_urut(token), ["b.pdf", "a.pdf", "c.pdf"])
        self.assertEqual([b["rentang"] for b in self.sesi(token)["berkas"]], ["", "3,1", "2-"])
        r = self.kirim(f"/utilitas/gabung/{token}/gabung", nama_hasil="Rekap: Mei", daftar_isi_dikirim="1", daftar_isi="1")
        self.assertEqual(r.status_code, 302, self.pesan_flash())
        hasil_id = int(r.location.rstrip("/").split("/")[-1])
        self.assertFalse((self.folder / "tmp" / "gabung_dokumen" / token).exists())   # sesi habis terpakai
        with self.db() as d:
            baris = d.execute("SELECT * FROM gabung_hasil WHERE id = ?", (hasil_id,)).fetchone()
            log = d.execute("SELECT aksi, status, detail, lokasi FROM log_proses WHERE modul = 'gabung_dokumen'").fetchone()
        self.assertEqual((baris["nama_berkas"], baris["jumlah_berkas"], baris["jumlah_halaman"]), ("Rekap- Mei.pdf", 3, 7))
        self.assertEqual(tuple(log[:3]), ("Gabungkan PDF", "sukses", "3 file → 7 halaman"))
        self.assertEqual(log["lokasi"], str((self.folder / "data" / "gabung_dokumen" / str(hasil_id)).resolve()))
        self.assertIn("Rekap- Mei.pdf", self.klien.get(f"/utilitas/gabung/hasil/{hasil_id}").get_data(as_text=True))
        r = self.klien.get(f"/utilitas/gabung/hasil/{hasil_id}/unduh")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        isi = r.get_data()
        r.close()
        self.assertEqual(lebar_halaman(isi), [200, 201, 102, 100, 301, 302, 303])
        self.assertEqual([o.title for o in PdfReader(io.BytesIO(isi)).outline], ["b", "a", "c"])
        self.assertIn("Rekap- Mei.pdf", self.klien.get("/utilitas/gabung").get_data(as_text=True))   # riwayat

    def test_turun_hapus_dan_tambah(self):
        _, token = self.unggah([("a.pdf", fp.pdf(1, 100)), ("b.pdf", fp.pdf(1, 200))])
        a_id = self.sesi(token)["berkas"][0]["id"]
        self.kirim(f"/utilitas/gabung/{token}/aksi", aksi=f"turun:{a_id}")
        self.assertEqual(self.nama_urut(token), ["b.pdf", "a.pdf"])
        self.kirim(f"/utilitas/gabung/{token}/aksi", aksi=f"turun:{a_id}")     # sudah paling bawah
        self.assertEqual(self.nama_urut(token), ["b.pdf", "a.pdf"])
        self.kirim(f"/utilitas/gabung/{token}/aksi", aksi=f"hapus:{a_id}")
        self.assertEqual(self.nama_urut(token), ["b.pdf"])
        self.assertFalse((self.folder / "tmp" / "gabung_dokumen" / token / f"{a_id}.pdf").exists())
        r = self.kirim(f"/utilitas/gabung/{token}/tambah", [("c.pdf", fp.pdf(2, 300))],
                       **{f"rentang_{self.sesi(token)['berkas'][0]['id']}": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.nama_urut(token), ["b.pdf", "c.pdf"])
        self.assertEqual(self.sesi(token)["berkas"][0]["rentang"], "1")        # isian disimpan sebelum menambah

    def test_rentang_salah_ditolak_inline_per_baris(self):
        _, token = self.unggah([("laporan.pdf", fp.pdf(3)), ("lampiran.pdf", fp.pdf(2))])
        ids = [b["id"] for b in self.sesi(token)["berkas"]]
        for url, data in ((f"/utilitas/gabung/{token}/aksi", {"aksi": "periksa"}), (f"/utilitas/gabung/{token}/gabung", {})):
            pembangun = EnvironBuilder(path=url, method="POST", data={
                "csrf_token": self.token(), f"rentang_{ids[0]}": "2-9", f"rentang_{ids[1]}": "abc", **data})
            r = self.klien.open(pembangun.get_environ())
            html = r.get_data(as_text=True)
            self.assertEqual(r.status_code, 400, url)
            self.assertIn("laporan.pdf: halaman 9 melebihi jumlah halaman (3).", html)
            self.assertIn("lampiran.pdf: “abc” bukan nomor atau rentang halaman.", html)
            self.assertIn(f'id="g-rentang_{ids[0]}"', html)               # galat inline lewat makro field
        with self.db() as d:
            self.assertEqual(d.execute("SELECT COUNT(*) FROM gabung_hasil").fetchone()[0], 0)

    def test_berkas_bermasalah_ditolak_per_file(self):
        r, token = self.unggah([("baik.pdf", fp.pdf(2)), ("catatan.txt", fp.bukan_pdf()), ("palsu.pdf", fp.bukan_pdf()),
                                ("rusak.pdf", fp.pdf_rusak()), ("kunci.pdf", fp.pdf(1, sandi="x"))])
        self.assertIsNotNone(token)
        self.assertEqual(self.nama_urut(token), ["baik.pdf"])
        pesan = self.pesan_flash() or ""
        r2 = self.klien.get(f"/utilitas/gabung/{token}")
        html = r2.get_data(as_text=True)
        for teks in ("catatan.txt: bukan berkas PDF", "palsu.pdf: bukan berkas PDF", "rusak.pdf: PDF rusak",
                     "kunci.pdf: PDF ini terkunci kata sandi"):
            self.assertIn(teks, html + pesan)
        self.assertEqual(len(list((self.folder / "tmp" / "gabung_dokumen" / token).glob("*.pdf"))), 1)

    def test_semua_ditolak_tidak_membuat_sesi(self):
        r, token = self.unggah([("x.txt", fp.bukan_pdf())])
        self.assertIsNone(token)
        self.assertEqual(list((self.folder / "tmp" / "gabung_dokumen").iterdir()), [])

    def test_batas_jumlah_ukuran_halaman(self):
        with mock.patch.object(layanan, "MAKS_BERKAS", 2):
            _, token = self.unggah([("a.pdf", fp.pdf(1)), ("b.pdf", fp.pdf(1)), ("c.pdf", fp.pdf(1))])
            self.assertEqual(self.nama_urut(token), ["a.pdf", "b.pdf"])
        with mock.patch.object(layanan, "MAKS_BYTE_BERKAS", 1200):
            _, token = self.unggah([("kecil.pdf", fp.pdf(1)), ("besar.pdf", fp.pdf(40))])
            self.assertEqual(self.nama_urut(token), ["kecil.pdf"])
        with mock.patch.object(layanan, "MAKS_HALAMAN", 5):
            _, token = self.unggah([("a.pdf", fp.pdf(3)), ("b.pdf", fp.pdf(3))])
            self.assertEqual(self.nama_urut(token), ["a.pdf"])
        with mock.patch.object(layanan, "MAKS_BYTE_SESI", len(fp.pdf(1)) + 10):
            _, token = self.unggah([("a.pdf", fp.pdf(1)), ("b.pdf", fp.pdf(1))])
            self.assertEqual(self.nama_urut(token), ["a.pdf"])

    def test_batas_kiriman_dipasang_sebelum_penjaga_login(self):
        self.app.config["MAX_CONTENT_LENGTH"] = 10            # batas umum sangat kecil
        r, token = self.unggah([("a.pdf", fp.pdf(1))])        # rute unggah memakai batas khususnya sendiri
        self.assertIsNotNone(token)

    def test_sesi_lama_dibersihkan(self):
        _, token = self.unggah([("a.pdf", fp.pdf(1))])
        folder = self.folder / "tmp" / "gabung_dokumen" / token
        lama = time.time() - layanan.UMUR_SESI_DETIK - 60
        os.utime(folder, (lama, lama))
        self.klien.get("/utilitas/gabung")
        self.assertFalse(folder.exists())

    def test_hapus_hasil_menghapus_berkas_dan_rekaman(self):
        _, token = self.unggah([("a.pdf", fp.pdf(1))])
        hasil_id = int(self.kirim(f"/utilitas/gabung/{token}/gabung").location.rstrip("/").split("/")[-1])
        folder = self.folder / "data" / "gabung_dokumen" / str(hasil_id)
        self.assertTrue(folder.is_dir())
        r = self.kirim("/utilitas/gabung/hapus", hasil=str(hasil_id))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(folder.exists())
        with self.db() as d:
            self.assertEqual(d.execute("SELECT COUNT(*) FROM gabung_hasil").fetchone()[0], 0)
            self.assertEqual(d.execute("SELECT status FROM log_proses WHERE aksi = 'Hapus hasil'").fetchone()[0], "sukses")


class UjiKeamanan(DasarWeb):
    def hasil_orang_lain(self):
        with self.db() as d:
            d.execute("INSERT INTO pengguna (id, nama_lengkap, nama_pengguna, sandi_hash, sesi_token) "
                      "VALUES (2, 'Lain', 'lain', 'x', 'y')")
            d.execute("INSERT INTO gabung_hasil (id, pengguna_id, nama_berkas, folder) VALUES (50, 2, 'x.pdf', '')")
            d.commit()
        folder = self.folder / "data" / "gabung_dokumen" / "50"
        folder.mkdir(parents=True)
        (folder / "x.pdf").write_bytes(fp.pdf(1))
        with self.db() as d:
            d.execute("UPDATE gabung_hasil SET folder = ? WHERE id = 50", (str(folder.resolve()),))
            d.commit()
        return folder

    def test_sesi_dan_hasil_pengguna_lain_ditolak(self):
        _, token = self.unggah([("a.pdf", fp.pdf(1))])
        jalur = self.folder / "tmp" / "gabung_dokumen" / token / "sesi.json"
        sesi = json.loads(jalur.read_text(encoding="utf-8"))
        sesi["pengguna_id"] = 2
        jalur.write_text(json.dumps(sesi), encoding="utf-8")
        self.assertEqual(self.klien.get(f"/utilitas/gabung/{token}").status_code, 404)
        self.assertEqual(self.kirim(f"/utilitas/gabung/{token}/gabung").status_code, 404)
        folder = self.hasil_orang_lain()
        self.assertEqual(self.klien.get("/utilitas/gabung/hasil/50").status_code, 404)
        self.assertEqual(self.klien.get("/utilitas/gabung/hasil/50/unduh").status_code, 404)
        self.kirim("/utilitas/gabung/hapus", hasil="50")
        self.assertTrue(folder.exists())
        self.assertEqual(self.klien.get("/utilitas/gabung/" + "x" * 30).status_code, 404)
        self.assertEqual(self.klien.get("/utilitas/gabung/..%2F..%2Fsecret_key").status_code, 404)

    def test_path_traversal_unduhan_ditolak(self):
        _, token = self.unggah([("a.pdf", fp.pdf(1))])
        hasil_id = int(self.kirim(f"/utilitas/gabung/{token}/gabung").location.rstrip("/").split("/")[-1])
        for nama, folder in (("../../../secret_key", None), ("..\\..\\secret_key", None),
                             ("superapp.db", str(self.folder.resolve())), ("secret_key", str(self.folder.resolve()))):
            with self.db() as d:
                if folder:
                    d.execute("UPDATE gabung_hasil SET nama_berkas = ?, folder = ? WHERE id = ?", (nama, folder, hasil_id))
                else:
                    d.execute("UPDATE gabung_hasil SET nama_berkas = ? WHERE id = ?", (nama, hasil_id))
                d.commit()
            self.assertEqual(self.klien.get(f"/utilitas/gabung/hasil/{hasil_id}/unduh").status_code, 404, nama)
        # folder palsu di luar instance/data/gabung_dokumen/<id> tidak ikut terhapus
        self.kirim("/utilitas/gabung/hapus", hasil=str(hasil_id))
        self.assertTrue((self.folder / "superapp.db").exists())

    def test_wajib_login_dan_csrf(self):
        _, token = self.unggah([("a.pdf", fp.pdf(1))])
        tamu = self.app.test_client()
        for url in ("/utilitas", "/utilitas/gabung", f"/utilitas/gabung/{token}", "/utilitas/gabung/hasil/1",
                    "/utilitas/gabung/hasil/1/unduh"):
            r = tamu.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/masuk", r.location)
        token_tamu = self.token("/masuk", klien=tamu)
        for url in ("/utilitas/gabung/unggah", f"/utilitas/gabung/{token}/gabung", "/utilitas/gabung/hapus"):
            r = tamu.post(url, data={"csrf_token": token_tamu})
            self.assertIn("/masuk", r.location, url)
        for url in ("/utilitas/gabung/unggah", f"/utilitas/gabung/{token}/aksi", f"/utilitas/gabung/{token}/gabung",
                    "/utilitas/gabung/hapus"):
            self.assertEqual(self.klien.post(url, data={"aksi": "periksa"}).status_code, 400, url)


class UjiKelompok(DasarWeb):
    def test_kelompok_utilitas_dan_kelompok_lain_tetap(self):
        with self.app.app_context():
            kelompok = kelompok_alat()
        self.assertEqual([(k["induk"]["id"], [m["id"] for m in k["modul"]]) for k in kelompok],
                         [("berita", ["pemecah_spt", "arsip_liputan"]), ("data_podcast", ["materi_podcast"]),
                          ("utilitas", ["gabung_dokumen"])])
        alat = self.klien.get("/alat").get_data(as_text=True)
        self.assertIn('id="utilitas"', alat)
        self.assertIn('href="/utilitas/gabung"', alat)
        self.assertIn("Gabungkan beberapa file PDF menjadi satu.", alat)
        self.assertNotIn('href="/utilitas"', alat)
        r = self.klien.get("/utilitas")
        self.assertTrue(r.location.endswith("/alat#utilitas"))
        self.assertEqual(self.klien.get("/modul/gabung_dokumen").location, "/utilitas/gabung")


if __name__ == "__main__":
    unittest.main()
