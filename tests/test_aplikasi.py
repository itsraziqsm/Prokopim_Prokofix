"""Uji otomatis aplikasi (memakai unittest bawaan Python, tanpa paket tambahan).

Jalankan dari folder proyek:
    python -m unittest -v

Setiap uji memakai folder data sementara, jadi database asli di instance/ tidak tersentuh.
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import create_app
from app import log_proses
from app.db import ambil_db

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
        for url in ("/", "/alat", "/log", "/spt"):
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
        for url in ("/", "/alat", "/log", "/pengaturan", "/akun", "/spt", "/liputan", "/liputan/baru"):
            self.assertEqual(self.klien.get(url).status_code, 200, url)

    def test_modul_siap_dialihkan_ke_halamannya(self):
        r = self.klien.get("/modul/pemecah_spt")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.location.endswith("/spt"))

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
        html = self.klien.get("/alat").get_data(as_text=True)
        self.assertNotIn("lencana-pengembangan", html)
        self.assertIn("Pemecah SPT", html)

    def test_logo_ke_dashboard_dan_menu_alat(self):
        html = self.klien.get("/").get_data(as_text=True)
        self.assertIn('aria-label="Dashboard', html)
        self.assertIn('href="/alat"', html)
        self.assertNotIn('aria-current="page" class="sidebar-item flex min-h-11', html)  # menu Alat tidak aktif
        html = self.klien.get("/liputan").get_data(as_text=True)
        self.assertIn('href="/alat"', html)                                            # breadcrumb "Alat"

    def test_dashboard_ringkasan_dari_database(self):
        from datetime import date
        hari_ini = date.today().isoformat()
        with self.app.app_context():
            db = ambil_db()
            db.execute("INSERT INTO liputan (tanggal, judul, status) VALUES (?, 'Rapat Koordinasi Uji', 'draf')", (hari_ini,))
            db.execute("INSERT INTO liputan (tanggal, judul, status) VALUES ('2000-01-05', 'Liputan Lama', 'final')")
            db.commit()
        with self.app.test_request_context():
            log_proses.catat("sistem", "Proses ringkasan uji", pengguna_id=1)
        html = self.klien.get("/").get_data(as_text=True)
        self.assertIn("Rapat Koordinasi Uji", html)
        self.assertIn("Proses ringkasan uji", html)
        self.assertRegex(html, r'tabular-nums">1</span>\s*<span class="text-redup">Liputan ')   # hanya bulan ini


class UjiTombolProgres(unittest.TestCase):
    """Setiap tombol ekspor/proses (sekarang & yang akan datang) wajib data-tombol-progres:
    tombol berubah menjadi bilah progres dan kiriman ganda ditolak (app.js bagian 5)."""
    # Dicocokkan pada NAMA FUNGSI rute (setelah titik), mis. 'materi_podcast.ekspor', 'gabung_dokumen.gabungkan'
    POLA_RUTE = r"url_for\('(?:\w+\.)?\w*(ekspor|proses|analisis|gabungkan)\w*'"

    def test_semua_tombol_ekspor_memakai_tombol_progres(self):
        from pathlib import Path
        diperiksa = 0
        for berkas in Path("app/templates").rglob("*.html"):
            html = berkas.read_text(encoding="utf-8")
            # a) formulir yang mengirim ke rute ekspor/proses: tombol kirimnya wajib bertombol progres
            for m in re.finditer(r'<form[^>]*action="\{\{ ' + self.POLA_RUTE + r'.*?</form>', html, re.S):
                diperiksa += 1
                self.assertIn("data-tombol-progres", m.group(0), f"{berkas}: {m.group(0)[:120]}")
            # b) tombol dengan formaction ke rute ekspor/proses
            for m in re.finditer(r'<button[^>]*formaction="\{\{ ' + self.POLA_RUTE + r'[^>]*>', html, re.S):
                diperiksa += 1
                self.assertIn("data-tombol-progres", m.group(0), f"{berkas}: {m.group(0)[:120]}")
        self.assertGreaterEqual(diperiksa, 5)   # SPT analisis & proses, Word liputan, Word materi, Gabungkan PDF


class UjiFilter(DasarUji):
    def test_jalur_aman_dan_bisa_dipatah(self):
        f = self.app.jinja_env.filters["jalur"]
        self.assertEqual(str(f(r"D:\Arsip\a.docx")), r"D:\<wbr>Arsip\<wbr>a.docx")
        self.assertIn("&lt;script&gt;", str(f("<script>")))


if __name__ == "__main__":
    unittest.main()


class UjiModeServer(unittest.TestCase):
    """SUPERAPP_SERVER / SUPERAPP_HTTPS (deploy/superapp.service) dan konsistensi berkas deploy/."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.lama = {k: os.environ.pop(k, None) for k in ("SUPERAPP_SERVER", "SUPERAPP_HTTPS")}

    def tearDown(self):
        for k, v in self.lama.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        shutil.rmtree(self.folder, ignore_errors=True)

    def _app_masuk(self):
        app = create_app({"TESTING": True}, instance_path=self.folder)
        klien = app.test_client()
        html = klien.get("/siapkan").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        klien.post("/siapkan", data={"csrf_token": token, "nama_lengkap": "Budi", "nama_pengguna": "budi",
                                     "sandi": SANDI, "konfirmasi": SANDI})
        with app.test_request_context():
            log_proses.catat("pemecah_spt", "Memecah 3 SPT", lokasi=self.folder, pengguna_id=1)
        return app, klien

    def test_bawaan_lokal_tidak_berubah(self):
        app, klien = self._app_masuk()
        self.assertFalse(app.config["MODE_SERVER"])
        self.assertTrue(app.config["IZINKAN_BUKA_FOLDER"])
        self.assertFalse(app.config.get("SESSION_COOKIE_SECURE"))
        self.assertRegex(klien.get("/log").get_data(as_text=True), r'action="/log/\d+/buka"')

    def test_mode_server_menyembunyikan_buka_folder(self):
        os.environ["SUPERAPP_SERVER"] = "1"
        app, klien = self._app_masuk()
        self.assertFalse(app.config["IZINKAN_BUKA_FOLDER"])
        self.assertNotRegex(klien.get("/log").get_data(as_text=True), r'/log/\d+/buka')
        token = re.search(r'name="csrf_token" value="([^"]+)"', klien.get("/akun").get_data(as_text=True)).group(1)
        with closing(sqlite3.connect(f"{self.folder}/superapp.db")) as db:
            log_id = db.execute("SELECT MAX(id) FROM log_proses WHERE lokasi IS NOT NULL").fetchone()[0]
        self.assertEqual(klien.post(f"/log/{log_id}/buka", data={"csrf_token": token}).status_code, 404)

    def test_mode_server_membaca_header_proxy(self):
        os.environ["SUPERAPP_SERVER"] = "1"
        app = create_app({"TESTING": True}, instance_path=self.folder)
        terlihat = {}

        @app.before_request
        def rekam():
            from flask import request
            terlihat.update(url=request.url, alamat=request.remote_addr)

        app.test_client().get("/masuk", headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "contoh.go.id",
                                                 "X-Forwarded-For": "10.1.2.3"})
        self.assertEqual(terlihat["url"], "https://contoh.go.id/masuk")
        self.assertEqual(terlihat["alamat"], "10.1.2.3")

    def test_https_mengamankan_cookie(self):
        os.environ["SUPERAPP_HTTPS"] = "1"
        app = create_app({"TESTING": True}, instance_path=self.folder)
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])

    def test_berkas_deploy_konsisten(self):
        akar = Path(__file__).resolve().parent.parent
        ruang = {}
        exec((akar / "deploy" / "gunicorn.conf.py").read_text(encoding="utf-8"), ruang)
        # thread latar Pemecah SPT hidup di dalam proses web -> wajib satu worker
        self.assertEqual(ruang["workers"], 1)
        self.assertTrue(ruang["bind"].startswith("127.0.0.1:"))
        nginx = (akar / "deploy" / "nginx-superapp.conf").read_text(encoding="utf-8")
        self.assertIn(f"server {ruang['bind']};", nginx)   # upstream nginx = alamat gunicorn
        mb = int(re.search(r"client_max_body_size\s+(\d+)m;", nginx).group(1))
        from app.modul import arsip_liputan, utilitas
        terbesar = max(arsip_liputan.routes.BATAS_UNGGAH_FOTO, utilitas.gabung_dokumen.routes.BATAS_UNGGAH,
                       create_app({"TESTING": True}, instance_path=self.folder).config["MAX_CONTENT_LENGTH"])
        self.assertGreaterEqual(mb * 1024 * 1024, terbesar)
        layanan = (akar / "deploy" / "superapp.service").read_text(encoding="utf-8")
        self.assertIn("SUPERAPP_SERVER=1", layanan)
        self.assertIn("--config deploy/gunicorn.conf.py run:app", layanan)
        self.assertIn("gunicorn", (akar / "requirements-server.txt").read_text(encoding="utf-8"))
