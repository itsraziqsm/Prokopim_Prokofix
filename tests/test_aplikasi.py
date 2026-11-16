"""Uji otomatis aplikasi (memakai unittest bawaan Python, tanpa paket tambahan).

Jalankan dari folder proyek:
    python -m unittest -v

Setiap uji memakai folder data sementara, jadi database asli di instance/ tidak tersentuh.
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing

from app import create_app
from app import log_proses

SANDI = "rahasia123"


class DasarUji(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.app = create_app({"TESTING": True}, instance_path=self.folder)
        self.klien = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    # ---- bantuan ----
    def token(self, klien, url):
        html = klien.get(url).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def buat_akun(self):
        return self.klien.post("/siapkan", data={
            "csrf_token": self.token(self.klien, "/siapkan"), "nama_lengkap": "Budi Santoso",
            "nama_pengguna": "budi", "sandi": SANDI, "konfirmasi": SANDI})

    def masuk(self, klien, sandi=SANDI, nama="budi", **lain):
        return klien.post("/masuk", data={"csrf_token": self.token(klien, "/masuk"),
                                          "nama_pengguna": nama, "sandi": sandi, **lain})

    def keluar(self, klien):
        return klien.post("/keluar", data={"csrf_token": self.token(klien, "/akun")})

    def log_db(self):
        with closing(sqlite3.connect(f"{self.folder}/superapp.db")) as db:
            return db.execute("SELECT aksi, status FROM log_proses ORDER BY id").fetchall()


class UjiPenyiapan(DasarUji):
    def test_tanpa_akun_diarahkan_ke_siapkan(self):
        for url in ("/", "/log", "/spt"):
            self.assertIn("/siapkan", self.klien.get(url).location)

    def test_csrf_salah_ditolak(self):
        r = self.klien.post("/siapkan", data={"csrf_token": "salah", "nama_lengkap": "A",
                                              "nama_pengguna": "a", "sandi": SANDI, "konfirmasi": SANDI})
        self.assertEqual(r.status_code, 400)

    def test_sandi_pendek_ditolak(self):
        r = self.klien.post("/siapkan", data={"csrf_token": self.token(self.klien, "/siapkan"),
                                              "nama_lengkap": "A", "nama_pengguna": "a",
                                              "sandi": "pendek", "konfirmasi": "pendek"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("minimal 8", r.get_data(as_text=True))

    def test_buat_akun_langsung_masuk_dan_siapkan_tertutup(self):
        self.assertTrue(self.buat_akun().location.endswith("/"))
        self.assertIn("Budi", self.klien.get("/").get_data(as_text=True))
        self.assertIn("/masuk", self.klien.get("/siapkan").location)

    def test_sandi_tersimpan_sebagai_hash(self):
        self.buat_akun()
        with closing(sqlite3.connect(f"{self.folder}/superapp.db")) as db:
            h = db.execute("SELECT sandi_hash FROM pengguna").fetchone()[0]
        self.assertTrue(h.startswith("scrypt:"))
        self.assertNotIn(SANDI, h)


class UjiMasuk(DasarUji):
    def setUp(self):
        super().setUp()
        self.buat_akun()
        self.keluar(self.klien)

    def test_halaman_dilindungi_dengan_next(self):
        self.assertIn("/masuk?next=/log", self.klien.get("/log").location)

    def test_sandi_salah(self):
        r = self.masuk(self.klien, sandi="salahsalah")
        self.assertEqual(r.status_code, 401)
        self.assertIn("Nama pengguna atau kata sandi salah", r.get_data(as_text=True))
        self.assertIn(("Percobaan masuk gagal (kata sandi salah)", "gagal"), self.log_db())

    def test_masuk_tidak_peka_huruf_besar_dan_kembali_ke_next(self):
        r = self.masuk(self.klien, nama="BUDI", next="/log")
        self.assertTrue(r.location.endswith("/log"))

    def test_open_redirect_diblokir(self):
        r = self.masuk(self.klien, next="//contoh-jahat.com")
        self.assertNotIn("contoh-jahat", r.location)

    def test_ganti_sandi_mengeluarkan_sesi_lain(self):
        self.masuk(self.klien)
        lain = self.app.test_client()
        self.masuk(lain)
        r = self.klien.post("/akun", data={"csrf_token": self.token(self.klien, "/akun"),
                                           "sandi_lama": SANDI, "sandi_baru": "barubaru1", "konfirmasi": "barubaru1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.klien.get("/").status_code, 200)   # sesi ini tetap masuk
        self.assertEqual(lain.get("/").status_code, 302)         # sesi lain keluar
        self.assertIn(("Kata sandi diganti", "sukses"), self.log_db())

    def test_ganti_sandi_dengan_sandi_lama_salah(self):
        self.masuk(self.klien)
        r = self.klien.post("/akun", data={"csrf_token": self.token(self.klien, "/akun"),
                                           "sandi_lama": "keliru", "sandi_baru": "barubaru1", "konfirmasi": "barubaru1"})
        self.assertEqual(r.status_code, 400)


class UjiHalaman(DasarUji):
    def setUp(self):
        super().setUp()
        self.buat_akun()

    def test_halaman_utama_terbuka(self):
        for url in ("/", "/log", "/pengaturan", "/akun", "/spt", "/liputan", "/liputan/baru"):
            self.assertEqual(self.klien.get(url).status_code, 200, url)

    def test_modul_tidak_ada_404(self):
        r = self.klien.get("/modul/tidak-ada")
        self.assertEqual(r.status_code, 404)
        self.assertIn("Halaman tidak ditemukan", r.get_data(as_text=True))

    def test_log_tabel_dan_lokasi_terakhir(self):
        with self.app.test_request_context():
            log_proses.catat("pemecah_spt", "Memecah 3 SPT", lokasi=self.folder, pengguna_id=1)
        html = self.klien.get("/log").get_data(as_text=True)
        self.assertIn("<table", html)
        self.assertIn("Memecah 3 SPT", html)
        self.assertIn("Terakhir", html)

    def test_buka_lokasi_log_tidak_ada_404(self):
        r = self.klien.post("/log/99999/buka", data={"csrf_token": self.token(self.klien, "/akun")})
        self.assertEqual(r.status_code, 404)

    def test_paginasi_log(self):
        with self.app.test_request_context():
            for i in range(30):
                log_proses.catat("sistem", f"Proses uji {i}", pengguna_id=1)
        self.assertIn("Halaman 2 dari", self.klien.get("/log?hal=2").get_data(as_text=True))

    def test_status_tidak_sah_ditolak(self):
        with self.app.test_request_context(), self.assertRaises(ValueError):
            log_proses.catat("sistem", "x", status="proses", pengguna_id=1)

    def test_menu_bawaan_tertutup_dan_tombol_di_atas_pemisah(self):
        html = self.klien.get("/").get_data(as_text=True)
        self.assertIn('sb === "lebar" ? "lebar" : "ringkas"', html)
        tombol = html.index('id="tombol-sidebar"')
        self.assertLess(html.index('aria-label="Navigasi utama"'), tombol)       # di dalam nav samping
        self.assertLess(tombol, html.index('href="/pengaturan"'))               # tepat sebelum bagian bawah

    def test_lencana_disembunyikan_bila_semua_modul_siap(self):
        html = self.klien.get("/").get_data(as_text=True)
        self.assertNotIn("lencana-pengembangan", html)


class UjiFilter(DasarUji):
    def test_jalur_aman_dan_bisa_dipatah(self):
        f = self.app.jinja_env.filters["jalur"]
        self.assertEqual(str(f(r"D:\Arsip\a.docx")), r"D:\<wbr>Arsip\<wbr>a.docx")
        self.assertIn("&lt;script&gt;", str(f("<script>")))


if __name__ == "__main__":
    unittest.main()
