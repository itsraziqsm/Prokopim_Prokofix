"""Uji Cadangan: kata sandi & pembatas, gerbang web, pembuatan ZIP, serangan pada pemulihan, pemulihan end-to-end,
unduh/hapus, peringatan Dashboard, dan perintah terminal."""
import base64
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import time
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from app import create_app
from app.cadangan import arsip, audit, basisdata, pulihkan, routes as rute_cadangan, sandi as sandi_mod

SANDI_MASUK = "rahasia123"
SANDI = "sandi-cadangan-panjang"


def isi_berkas(folder, kecuali=("cadangan/audit.log",)):
    """{jalur relatif: sha256} semua berkas di folder (untuk memastikan tidak ada yang berubah).
    audit.log dikecualikan: setiap penolakan MEMANG dicatat di sana."""
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file() and p.relative_to(folder).as_posix() not in kecuali}


# ====================== Kata sandi (tanpa Flask) ======================
class UjiSandi(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_syarat_dan_hash_di_luar_database(self):
        with self.assertRaisesRegex(sandi_mod.GalatSandi, "minimal 12"):
            sandi_mod.periksa_syarat("pendek", "pendek")
        with self.assertRaisesRegex(sandi_mod.GalatSandi, "tidak sama"):
            sandi_mod.periksa_syarat("a" * 12, "b" * 12)
        sandi_mod.atur_sandi(self.folder, SANDI)
        isi = (self.folder / "kunci.json").read_text()
        self.assertNotIn(SANDI, isi)
        data = json.loads(isi)
        self.assertEqual((data["algoritma"], data["n"], data["r"], data["p"]), ("scrypt", 2 ** 14, 8, 1))
        self.assertTrue(sandi_mod.cocok(self.folder, SANDI))
        self.assertFalse(sandi_mod.cocok(self.folder, SANDI + "x"))
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE((self.folder / "kunci.json").stat().st_mode), 0o600)

    def test_pembatas_lima_kali_dan_bertahan(self):
        sandi_mod.atur_sandi(self.folder, SANDI)
        t = 1_000_000.0
        for _ in range(4):
            self.assertFalse(sandi_mod.verifikasi(self.folder, "salah-salah-salah", t))
        self.assertTrue(sandi_mod.verifikasi(self.folder, SANDI, t))        # benar sebelum batas: hitungan direset
        for _ in range(5):
            sandi_mod.verifikasi(self.folder, "salah-salah-salah", t)
        self.assertFalse(sandi_mod.verifikasi(self.folder, SANDI, t + 10))   # terkunci walau benar
        # "Mulai ulang": status dibaca lagi dari percobaan.json
        self.assertTrue(json.loads((self.folder / "percobaan.json").read_text())["terkunci_sampai"] > t)
        self.assertFalse(sandi_mod.verifikasi(self.folder, SANDI, t + 299))
        self.assertTrue(sandi_mod.verifikasi(self.folder, SANDI, t + 301))   # setelah 5 menit
        for _ in range(5):
            sandi_mod.verifikasi(self.folder, "salah-salah-salah", t + 400)
        self.assertTrue(sandi_mod.terkunci(self.folder, t + 401))             # berlaku lagi bila terus salah


class UjiJalur(unittest.TestCase):
    def test_relatif_dan_absolut_windows_posix(self):
        r, a = basisdata.ke_relatif, basisdata.ke_absolut
        self.assertEqual(r(r"C:\App\instance\data\spt\3", [r"c:/app/instance"]), "{instance}/data/spt/3")
        self.assertEqual(r("C:/App/instance", [r"C:\App\instance\\"]), "{instance}")
        self.assertEqual(r("/srv/app/instance/data/x", ["/srv/app/instance"]), "{instance}/data/x")
        self.assertEqual(r("/srv/app/instance2/data", ["/srv/app/instance"]), "/srv/app/instance2/data")
        self.assertEqual(r("/Srv/App/instance/data", ["/srv/app/instance"]), "/Srv/App/instance/data")  # POSIX peka huruf
        self.assertEqual(r(r"D:\Lain\data", [r"C:\App\instance"]), r"D:\Lain\data")
        self.assertIsNone(r(None, ["/x"]))
        self.assertEqual(a("{instance}/data/spt/3", r"D:\Baru\instance"), r"D:\Baru\instance\data\spt\3")
        self.assertEqual(a("{instance}/data/spt/3", "/srv/baru/instance/"), "/srv/baru/instance/data/spt/3")
        self.assertEqual(a("{instance}", "/srv/b"), "/srv/b")
        self.assertEqual(a("/lain/{instance}/x", "/srv/b"), "/lain/{instance}/x")
        # dua arah: Windows -> relatif -> POSIX
        self.assertEqual(a(r(r"C:\A\instance\data\gabung_dokumen\7", [r"C:\A\instance"]), "/srv/x/instance"),
                         "/srv/x/instance/data/gabung_dokumen/7")


# ====================== Dasar web ======================
class DasarCadangan(unittest.TestCase):
    def setUp(self):
        self.akar = Path(tempfile.mkdtemp())
        self.instance = self.akar / "instance-a"
        self.templat = self.akar / "templat-a"
        self.templat.mkdir()
        (self.templat / "berita.docx").write_bytes(b"PK\x03\x04templat-a")
        self.app = create_app({"TESTING": True, "FOLDER_TEMPLAT": str(self.templat)}, instance_path=str(self.instance))
        self.klien = self.app.test_client()
        self.klien.post("/siapkan", data={"csrf_token": self.token("/siapkan"), "nama_lengkap": "Budi",
                                          "nama_pengguna": "budi", "sandi": SANDI_MASUK, "konfirmasi": SANDI_MASUK})

    def tearDown(self):
        shutil.rmtree(self.akar, ignore_errors=True)

    def token(self, url="/akun", klien=None):
        html = (klien or self.klien).get(url).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def post(self, url, klien=None, **data):
        return (klien or self.klien).post(url, data={"csrf_token": self.token(klien=klien), **data})

    @property
    def folder_cadangan(self):
        return self.instance / "cadangan"

    def siapkan_sandi(self):
        r = self.post("/cadangan/sandi-baru", sandi=SANDI, konfirmasi=SANDI)
        self.assertEqual(r.location, "/cadangan")

    def isi_data_contoh(self):
        """Data di instance A: materi podcast, batch SPT + berkas, hasil gabung + berkas, log berlokasi."""
        with self.app.app_context():
            from app.modul.data_podcast.materi import layanan as lm
            from app import log_proses
            from app.db import ambil_db
            lm.buat_contoh()
            db = ambil_db()
            folder_spt = self.instance / "data" / "spt" / "1"
            folder_spt.mkdir(parents=True)
            (folder_spt / "SPT-1.docx").write_bytes(b"PK\x03\x04spt")
            db.execute("INSERT INTO spt_batch (id, pengguna_id, nama_berkas_asli, format_keluaran, jumlah, folder) "
                       "VALUES (1, 1, 'a.docx', 'word', 1, ?)", (str(folder_spt),))
            db.execute("INSERT INTO spt (batch_id, urutan, nomor, nama_docx) VALUES (1, 1, '800/1', 'SPT-1.docx')")
            folder_gabung = self.instance / "data" / "gabung_dokumen" / "1"
            folder_gabung.mkdir(parents=True)
            (folder_gabung / "Gabungan.pdf").write_bytes(b"%PDF-1.4 hasil")
            db.execute("INSERT INTO gabung_hasil (id, pengguna_id, nama_berkas, folder) VALUES (1, 1, 'Gabungan.pdf', ?)",
                       (str(folder_gabung),))
            db.commit()
            log_proses.catat("sistem", "Ekspor", lokasi=str(folder_spt), pengguna_id=1)
        (self.instance / "data" / "spt" / "1" / "skrip.py").write_text("print('x')")           # tidak didukung
        (self.instance / "data" / "spt" / "1" / "lama.docx.lama-1").write_bytes(b"x")         # .lama*
        (self.instance / "tmp").mkdir(exist_ok=True)
        (self.instance / "tmp" / "sementara.docx").write_bytes(b"x")

    def buat_cadangan(self, jenis="lengkap"):
        with self.app.app_context():
            return arsip.buat_cadangan(instance=self.instance, folder_templat=self.templat,
                                       folder_tujuan=self.folder_cadangan / "berkas", folder_kerja=self.folder_cadangan,
                                       jenis=jenis, sandi=SANDI)

    def instance_lain(self, nama="instance-b", data=True):
        """Instance kedua (aplikasi lain) dengan akun & data berbeda."""
        folder = self.akar / nama
        templat = self.akar / f"templat-{nama}"
        templat.mkdir()
        (templat / "berita.docx").write_bytes(b"PK\x03\x04templat-lama-b")
        app = create_app({"TESTING": True, "FOLDER_TEMPLAT": str(templat)}, instance_path=str(folder))
        klien = app.test_client()
        klien.post("/siapkan", data={"csrf_token": self.token("/siapkan", klien), "nama_lengkap": "Citra",
                                     "nama_pengguna": "citra", "sandi": "sandi-citra-1", "konfirmasi": "sandi-citra-1"})
        if data:
            (folder / "data" / "liputan").mkdir(parents=True)
            (folder / "data" / "liputan" / "lama.jpg").write_bytes(b"\xff\xd8 foto lama b")
        return folder, templat, app, klien


# ====================== Gerbang web ======================
class UjiGerbang(DasarCadangan):
    RUTE_GET = ("/cadangan", "/cadangan/unduh/cadangan-lengkap-2026-01-01-0000.zip")
    RUTE_POST = ("/cadangan/buat", "/cadangan/uji/cadangan-lengkap-2026-01-01-0000.zip",
                 "/cadangan/hapus/cadangan-lengkap-2026-01-01-0000.zip", "/cadangan/ganti-sandi")

    def test_belum_login_diarahkan_ke_masuk(self):
        tamu = self.app.test_client()
        for url in self.RUTE_GET + ("/cadangan/kunci", "/cadangan/sandi-baru"):
            self.assertIn("/masuk", tamu.get(url).location, url)

    def test_sandi_cadangan_pertama(self):
        for url in self.RUTE_GET + ("/cadangan/kunci",):
            self.assertEqual(self.klien.get(url).location, "/cadangan/sandi-baru", url)
        self.assertEqual(self.post("/cadangan/sandi-baru", sandi="pendek", konfirmasi="pendek").status_code, 400)
        r = self.post("/cadangan/sandi-baru", sandi=SANDI_MASUK + "abcd", konfirmasi=SANDI_MASUK + "abcd")
        self.assertEqual(r.status_code, 302)                                  # beda dari sandi masuk: boleh
        shutil.rmtree(self.folder_cadangan)
        with mock.patch.object(sandi_mod, "PANJANG_MIN", 8):
            r = self.post("/cadangan/sandi-baru", sandi=SANDI_MASUK, konfirmasi=SANDI_MASUK)
        self.assertEqual(r.status_code, 400)                                  # sama dengan sandi masuk: ditolak
        self.assertIn("berbeda dari kata sandi masuk", r.get_data(as_text=True))
        self.assertFalse(sandi_mod.ada_sandi(self.folder_cadangan))
        with sqlite3.connect(self.instance / "superapp.db") as d:            # hash tidak pernah masuk database
            for (sql,) in d.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"):
                self.assertNotIn("kunci", sql.lower())

    def test_sesi_cadangan_sepuluh_menit_dan_kunci_kembali(self):
        t = time.time()
        with mock.patch.object(rute_cadangan, "sekarang", return_value=t):
            self.siapkan_sandi()
            self.assertEqual(self.klien.get("/cadangan").status_code, 200)
            with self.klien.session_transaction() as s:
                self.assertEqual(set(s) - {"uid", "token", "_csrf", "_permanent", "_flashes"}, {"cadangan_sampai"})
                self.assertNotIn(SANDI, json.dumps(dict(s)))
        with mock.patch.object(rute_cadangan, "sekarang", return_value=t + 601):
            for url in self.RUTE_GET:
                self.assertEqual(self.klien.get(url).location, "/cadangan/kunci", url)
            for url in self.RUTE_POST:
                self.assertEqual(self.post(url, sandi=SANDI).location, "/cadangan/kunci", url)
            r = self.post("/cadangan/kunci", sandi=SANDI)
            self.assertEqual(r.location, "/cadangan")
            self.assertEqual(self.klien.get("/cadangan").status_code, 200)
            self.post("/cadangan/kunci-kembali")
            self.assertEqual(self.klien.get("/cadangan").location, "/cadangan/kunci")

    def test_pembatas_web_bertahan_antar_restart(self):
        self.siapkan_sandi()
        self.post("/cadangan/kunci-kembali")
        for _ in range(5):
            self.assertEqual(self.post("/cadangan/kunci", sandi="salah-sekali-ini").status_code, 401)
        app_baru = create_app({"TESTING": True, "FOLDER_TEMPLAT": str(self.templat)}, instance_path=str(self.instance))
        klien = app_baru.test_client()
        klien.post("/masuk", data={"csrf_token": self.token("/masuk", klien), "nama_pengguna": "budi", "sandi": SANDI_MASUK})
        r = klien.post("/cadangan/kunci", data={"csrf_token": self.token(klien=klien), "sandi": SANDI})
        self.assertEqual(r.status_code, 401)
        self.assertIn("Kata sandi cadangan salah, atau akses sedang dikunci", r.get_data(as_text=True))

    def test_csrf_ditolak(self):
        self.siapkan_sandi()
        for url in self.RUTE_POST + ("/cadangan/kunci", "/cadangan/kunci-kembali"):
            self.assertEqual(self.klien.post(url, data={"sandi": SANDI, "jenis": "lengkap"}).status_code, 400, url)

    def test_ganti_sandi(self):
        self.siapkan_sandi()
        lama = self.buat_cadangan("database")
        r = self.post("/cadangan/ganti-sandi", sandi_lama="salah-sama-sekali", sandi_baru="sandi-baru-panjang",
                      konfirmasi="sandi-baru-panjang")
        self.assertTrue(sandi_mod.cocok(self.folder_cadangan, SANDI))
        self.post("/cadangan/ganti-sandi", sandi_lama=SANDI, sandi_baru="pendek", konfirmasi="pendek")
        self.assertTrue(sandi_mod.cocok(self.folder_cadangan, SANDI))
        self.post("/cadangan/ganti-sandi", sandi_lama=SANDI, sandi_baru="sandi-baru-panjang",
                  konfirmasi="sandi-baru-panjang")
        self.assertTrue(sandi_mod.cocok(self.folder_cadangan, "sandi-baru-panjang"))
        # cadangan lama tetap diverifikasi dengan sandi lama
        self.assertEqual(pulihkan.periksa(lama["jalur"], SANDI, self.akar / "x")["jenis"], "database")
        with self.assertRaises(arsip.GalatArsip):
            pulihkan.periksa(lama["jalur"], "sandi-baru-panjang", self.akar / "x")


# ====================== Pembuatan ======================
class UjiPembuatan(DasarCadangan):
    def setUp(self):
        super().setUp()
        self.isi_data_contoh()
        self.siapkan_sandi()

    def test_isi_zip_lengkap_dan_manifest(self):
        r = self.post("/cadangan/buat", jenis="lengkap", sandi=SANDI)
        self.assertEqual(r.status_code, 302)
        nama = arsip.daftar_cadangan(self.folder_cadangan / "berkas")[0]["nama"]
        self.assertRegex(nama, r"^cadangan-lengkap-\d{4}-\d{2}-\d{2}-\d{4}\.zip$")
        jalur = self.folder_cadangan / "berkas" / nama
        with zipfile.ZipFile(jalur) as zf:
            nama_entri = sorted(zf.namelist())
            self.assertEqual(nama_entri, ["data/gabung_dokumen/1/Gabungan.pdf", "data/spt/1/SPT-1.docx",
                                          "database/superapp.db", "manifest.json", "templat_docx/berita.docx"])
            for terlarang in ("secret_key", "tmp/", "cadangan/", "skrip.py", ".lama"):
                self.assertFalse(any(terlarang in n for n in nama_entri), terlarang)
            manifest = json.loads(zf.read("manifest.json"))
            for b in manifest["berkas"]:
                self.assertEqual(hashlib.sha256(zf.read(b["jalur"])).hexdigest(), b["sha256"])
                self.assertEqual(len(zf.read(b["jalur"])), b["ukuran"])
            db = self.akar / "snap.db"
            db.write_bytes(zf.read("database/superapp.db"))
        arsip.verifikasi_tanda(manifest, SANDI)
        self.assertEqual(manifest["versi_format"], 1)
        self.assertIn("+", manifest["dibuat"][19:] + "+")                       # zona waktu ikut
        self.assertIn("materi_pertanyaan", manifest["skema"])
        self.assertTrue(basisdata.integritas_ok(db))
        with sqlite3.connect(db) as snap, sqlite3.connect(self.instance / "superapp.db") as hidup:
            self.assertEqual(basisdata.hitung_baris(snap), manifest["hitungan"])
            for tabel in ("pengguna", "materi_pertanyaan", "spt", "gabung_hasil"):
                self.assertEqual(snap.execute(f"SELECT COUNT(*) FROM {tabel}").fetchone(),
                                 hidup.execute(f"SELECT COUNT(*) FROM {tabel}").fetchone())
            self.assertEqual(snap.execute("SELECT folder FROM spt_batch").fetchone()[0], "{instance}/data/spt/1")
            self.assertEqual(snap.execute("SELECT folder FROM gabung_hasil").fetchone()[0], "{instance}/data/gabung_dokumen/1")
            self.assertIn(("{instance}/data/spt/1",), snap.execute("SELECT lokasi FROM log_proses").fetchall())
            self.assertEqual(hidup.execute("SELECT folder FROM spt_batch").fetchone()[0],
                             str(self.instance / "data" / "spt" / "1"))       # database hidup tidak diubah
        pendamping = json.loads(jalur.with_suffix(".json").read_text())
        self.assertEqual((pendamping["jenis"], pendamping["hitungan"]["spt"]), ("lengkap", 1))
        catatan = audit.baca(self.folder_cadangan)
        self.assertIn(("Buat cadangan", "web:budi", "sukses"), [(c["aksi"], c["pelaku"], c["hasil"]) for c in catatan])

    @unittest.skipIf(os.name == "nt", "pemeriksaan mode berkas memakai fcntl (POSIX)")
    def test_fsync_selalu_pada_berkas_yang_dibuka_untuk_ditulis(self):
        """Regresi: di Windows os.fsync pada berkas yang dibuka "rb" gagal dengan Errno 9 (Bad file descriptor)."""
        import fcntl
        asli = os.fsync

        def fsync_ketat(fd):
            if fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY:
                raise OSError(9, "Bad file descriptor (berkas baca-saja, seperti di Windows)")
            return asli(fd)
        with mock.patch("os.fsync", side_effect=fsync_ketat):
            hasil = self.buat_cadangan()
            tujuan, templat_b, _, _ = self.instance_lain()
            pulihkan.pulihkan(jalur_zip=hasil["jalur"], instance=tujuan, folder_templat=templat_b, sandi=SANDI,
                              konfirmasi=lambda: "PULIHKAN", tampil=lambda b: None)

    def test_jenis_database_saja(self):
        hasil = self.buat_cadangan("database")
        with zipfile.ZipFile(hasil["jalur"]) as zf:
            self.assertEqual(sorted(zf.namelist()), ["database/superapp.db", "manifest.json"])

    def test_tolak_proses_berjalan_ruang_kurang_batas_web_dan_kunci(self):
        with sqlite3.connect(self.instance / "superapp.db") as d:
            d.execute("UPDATE spt_batch SET status = 'proses' WHERE id = 1")
        r = self.post("/cadangan/buat", jenis="lengkap", sandi=SANDI)
        self.assertEqual(arsip.daftar_cadangan(self.folder_cadangan / "berkas"), [])
        with sqlite3.connect(self.instance / "superapp.db") as d:
            d.execute("UPDATE spt_batch SET status = 'sukses' WHERE id = 1")
        with mock.patch.object(arsip.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(10, 9, 1)):
            with self.assertRaisesRegex(arsip.GalatCadangan, "Ruang disk"):
                self.buat_cadangan()
        with mock.patch.object(rute_cadangan, "BATAS_WEB_BYTE", 10):
            self.post("/cadangan/buat", jenis="lengkap", sandi=SANDI)
            with self.klien.session_transaction() as s:
                pesan = " ".join(p for _, p in s.get("_flashes", []))
        self.assertIn("flask --app run cadangan buat", pesan)
        (self.folder_cadangan / "buat.kunci").write_text("123")
        with self.assertRaisesRegex(arsip.GalatCadangan, "sedang berjalan"):
            self.buat_cadangan()
        self.assertEqual(arsip.daftar_cadangan(self.folder_cadangan / "berkas"), [])

    def test_sandi_salah_saat_buat(self):
        self.post("/cadangan/buat", jenis="lengkap", sandi="salah-salah-salah")
        self.assertEqual(arsip.daftar_cadangan(self.folder_cadangan / "berkas"), [])

    def test_uji_unduh_hapus(self):
        hasil = self.buat_cadangan()
        nama = hasil["nama"]
        self.post(f"/cadangan/uji/{nama}")
        self.assertTrue(arsip.baca_pendamping(hasil["jalur"])["uji"]["berhasil"])
        r = self.klien.get(f"/cadangan/unduh/{nama}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        r.close()
        for buruk in ("..%2Fsecret_key", "secret_key", "x.zip", nama.replace(".zip", ".json"),
                      "cadangan-lengkap-2026-01-01-0000.zip", nama + "%00", "..%2F..%2Finstance-a%2Fsuperapp.db"):
            self.assertEqual(self.klien.get(f"/cadangan/unduh/{buruk}").status_code, 404, buruk)
            self.assertEqual(self.post(f"/cadangan/hapus/{buruk}").status_code, 404, buruk)
        # berkas rusak -> uji gagal tercatat
        rusak = self.folder_cadangan / "berkas" / "cadangan-database-2026-01-01-0000.zip"
        rusak.write_bytes(b"bukan zip")
        self.post(f"/cadangan/uji/{rusak.name}")
        self.assertFalse(arsip.baca_pendamping(rusak)["uji"]["berhasil"])
        self.post(f"/cadangan/hapus/{nama}")
        self.assertFalse(hasil["jalur"].exists())
        self.assertFalse(hasil["jalur"].with_suffix(".json").exists())
        self.assertIn("Hapus cadangan", [c["aksi"] for c in audit.baca(self.folder_cadangan)])


# ====================== Serangan pada pemulihan ======================
class UjiSerangan(DasarCadangan):
    def setUp(self):
        super().setUp()
        self.isi_data_contoh()
        self.siapkan_sandi()
        self.asli = self.buat_cadangan()["jalur"]
        self.tujuan, self.templat_b, _, _ = self.instance_lain()
        self.sebelum = isi_berkas(self.tujuan)

    def baca_entri(self):
        with zipfile.ZipFile(self.asli) as zf:
            return {n: zf.read(n) for n in zf.namelist() if n != "manifest.json"}, json.loads(zf.read("manifest.json"))

    def rakit(self, entri, manifest=None, tanda_ulang=True, tambahan=(), terdaftar=None, info_khusus=None):
        """ZIP baru dari entri {nama: bytes}; manifest disusun ulang & ditandatangani (seolah penyerang tahu sandi)
        agar pemeriksaan struktur/isi/database diuji sendiri-sendiri. tambahan = entri yang TIDAK di manifest."""
        _, dasar = self.baca_entri()
        manifest = dict(manifest or dasar)
        daftar = terdaftar if terdaftar is not None else entri
        manifest["berkas"] = [{"jalur": n, "ukuran": len(d), "sha256": hashlib.sha256(d).hexdigest()}
                              for n, d in daftar.items()]
        if tanda_ulang:
            manifest.pop("tanda", None)
            manifest["tanda"] = arsip.hitung_tanda(manifest, SANDI)
        jalur = self.akar / f"serangan-{len(list(self.akar.glob('serangan-*')))}.zip"
        with zipfile.ZipFile(jalur, "w", zipfile.ZIP_DEFLATED) as zf:
            for nama, data in list(entri.items()) + list(tambahan):
                info = (info_khusus or {}).get(nama) or zipfile.ZipInfo(nama)
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, data)
            zf.writestr("manifest.json", json.dumps(manifest))
        return jalur

    def harus_ditolak(self, jalur, sandi=SANDI, pola=None):
        with self.assertRaises((arsip.GalatArsip, pulihkan.GalatPulihkan)) as k:
            pulihkan.pulihkan(jalur_zip=jalur, instance=self.tujuan, folder_templat=self.templat_b, sandi=sandi,
                              konfirmasi=lambda: "PULIHKAN", tampil=lambda b: None)
        if pola:
            self.assertRegex(str(k.exception), pola)
        self.assertEqual(isi_berkas(self.tujuan), self.sebelum)          # tidak ada yang berubah
        self.assertFalse((self.tujuan / "pulihkan_tmp").exists())
        return str(k.exception)

    def test_sandi_salah_dan_manifest_diubah(self):
        pesan = self.harus_ditolak(self.asli, sandi="bukan-sandinya-ya")
        entri, manifest = self.baca_entri()
        manifest["hitungan"]["pengguna"] = 99
        self.assertEqual(self.harus_ditolak(self.rakit(entri, manifest, tanda_ulang=False)), pesan)   # pesan sama
        # manifest diubah: daftar berkas dibuang, tanda lama tetap
        _, manifest = self.baca_entri()
        manifest["skema"] = {}
        self.harus_ditolak(self.rakit(entri, manifest, tanda_ulang=False), pola="sandi cadangan salah")

    def test_satu_byte_diubah(self):
        entri, manifest = self.baca_entri()
        asli = dict(entri)
        data = bytearray(entri["data/spt/1/SPT-1.docx"])
        data[-1] ^= 1
        entri["data/spt/1/SPT-1.docx"] = bytes(data)
        self.harus_ditolak(self.rakit(entri, terdaftar=asli), pola="tidak cocok")

    def test_berkas_tidak_terdaftar_dan_hilang(self):
        entri, _ = self.baca_entri()
        self.harus_ditolak(self.rakit(entri, tambahan=[("data/spt/1/selundup.pdf", b"%PDF")]), pola="tidak terdaftar")
        daftar = dict(entri, **{"data/spt/1/hilang.pdf": b"%PDF"})
        self.harus_ditolak(self.rakit(entri, terdaftar=daftar), pola="tidak ada di cadangan")

    def test_jalur_berbahaya(self):
        entri, _ = self.baca_entri()
        for nama in ("../x.pdf", "data/../../x.pdf", "/etc/x.pdf", "C:\\x.pdf", "C:/x.pdf", "data\\spt\\x.pdf",
                     "data/spt/x\x00.pdf", "data//x.pdf", "lain/x.pdf", "secret_key", "templat_docx/a/b.docx"):
            with self.subTest(nama=nama):
                self.harus_ditolak(self.rakit(entri, tambahan=[(nama, b"%PDF")]))

    def test_symlink_nama_ganda_dan_ekstensi_terlarang(self):
        entri, _ = self.baca_entri()
        tautan = zipfile.ZipInfo("data/spt/1/tautan.pdf")
        tautan.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.harus_ditolak(self.rakit(dict(entri, **{"data/spt/1/tautan.pdf": b"/etc/passwd"}),
                                      info_khusus={"data/spt/1/tautan.pdf": tautan}), pola="tautan")
        ganda = dict(entri, **{"data/spt/1/spt-1.DOCX": entri["data/spt/1/SPT-1.docx"]})
        self.harus_ditolak(self.rakit(ganda), pola="ganda")
        for akhiran in (".py", ".exe", ".bat", ".html", ".js", ".db"):
            with self.subTest(akhiran=akhiran):
                self.harus_ditolak(self.rakit(dict(entri, **{f"data/spt/1/x{akhiran}": b"isi"})))

    def test_zip_bomb(self):
        entri, _ = self.baca_entri()
        self.harus_ditolak(self.rakit(dict(entri, **{"data/spt/1/nol.pdf": b"\0" * (4 * 1024 * 1024)})), pola="Rasio")
        with mock.patch.object(arsip, "MAKS_TOTAL_BYTE", 10_000):
            self.harus_ditolak(self.asli, pola="melebihi batas")
        with mock.patch.object(arsip, "MAKS_ENTRI", 3):
            self.harus_ditolak(self.asli, pola="terlalu banyak")

    def ubah_db(self, sql, pola):
        entri, _ = self.baca_entri()
        db = self.akar / "ubah.db"
        db.write_bytes(entri["database/superapp.db"])
        with sqlite3.connect(db) as d:
            d.executescript(sql)
        entri["database/superapp.db"] = db.read_bytes()
        db.unlink()
        self.harus_ditolak(self.rakit(entri), pola=pola)

    def test_database_berbahaya(self):
        self.ubah_db("CREATE TRIGGER jahat AFTER INSERT ON log_proses BEGIN DELETE FROM pengguna; END;", "trigger")
        self.ubah_db("CREATE TABLE asing (x);", "tidak dikenal")
        self.ubah_db("CREATE VIEW v AS SELECT 1;", "view")
        self.ubah_db("ALTER TABLE pengguna ADD COLUMN kolom_masa_depan TEXT;", "lebih baru")
        self.ubah_db("PRAGMA foreign_keys=OFF; INSERT INTO spt (batch_id, urutan, nomor) VALUES (999, 1, 'x');", "rujukan")

    def test_database_rusak_dan_versi_baru(self):
        entri, manifest = self.baca_entri()
        data = bytearray(entri["database/superapp.db"])
        data[100:] = b"\xa5" * (len(data) - 100)              # semua halaman setelah header dirusak
        self.harus_ditolak(self.rakit(dict(entri, **{"database/superapp.db": bytes(data)})), pola="rusak")
        self.assertIn(("Pulihkan", "terminal", "gagal"),
                      [(c["aksi"], c["pelaku"], c["hasil"]) for c in audit.baca(self.tujuan / "cadangan")])
        manifest["versi_format"] = 99
        self.harus_ditolak(self.rakit(entri, manifest), pola="lebih baru")

    def test_tidak_ada_rute_web_unggah_zip(self):
        for aturan in self.app.url_map.iter_rules():
            if aturan.rule.startswith("/cadangan"):
                self.assertNotIn("pulih", aturan.rule)
        r = self.post("/cadangan/pulihkan")
        self.assertEqual(r.status_code, 404)


# ====================== Pemulihan end-to-end ======================
class UjiPemulihan(DasarCadangan):
    def setUp(self):
        super().setUp()
        self.isi_data_contoh()
        self.siapkan_sandi()

    def pulihkan_ke(self, tujuan, templat, zip_, konfirmasi="PULIHKAN"):
        keluaran = []
        laporan = pulihkan.pulihkan(jalur_zip=zip_, instance=tujuan, folder_templat=templat, sandi=SANDI,
                                    konfirmasi=lambda: konfirmasi, tampil=keluaran.append)
        return laporan, "\n".join(keluaran)

    def test_pulihkan_lengkap_ke_instance_lain(self):
        cadangan = self.buat_cadangan()["jalur"]
        tujuan, templat_b, app_b, klien_b = self.instance_lain()
        with sqlite3.connect(tujuan / "superapp.db") as d:     # data b lebih banyak -> pratinjau menunjukkan selisih
            for i in range(7):
                d.execute("INSERT INTO log_proses (pengguna_id, modul, aksi) VALUES (1, 'sistem', ?)", (f"b{i}",))
        kunci_b = (tujuan / "secret_key").read_bytes()
        self.assertEqual(klien_b.get("/").status_code, 200)                  # sesi b masih berlaku
        with self.assertRaises(pulihkan.GalatPulihkan):                      # konfirmasi salah -> batal
            self.pulihkan_ke(tujuan, templat_b, cadangan, konfirmasi="ya")
        laporan, keluaran = self.pulihkan_ke(tujuan, templat_b, cadangan)
        self.assertIn("akan hilang", keluaran)
        self.assertTrue(laporan["cocok"])
        self.assertEqual(laporan["hilang"], {})
        self.assertEqual((tujuan / "secret_key").read_bytes(), kunci_b)
        with sqlite3.connect(tujuan / "superapp.db") as d:
            self.assertEqual(d.execute("SELECT nama_pengguna FROM pengguna").fetchall(), [("budi",)])
            self.assertEqual(d.execute("SELECT folder FROM spt_batch").fetchone()[0],
                             str(tujuan.resolve() / "data" / "spt" / "1"))
            self.assertIn((str(tujuan.resolve() / "data" / "spt" / "1"),),
                          d.execute("SELECT lokasi FROM log_proses").fetchall())
            token_baru = d.execute("SELECT sesi_token FROM pengguna").fetchone()[0]
        with sqlite3.connect(self.instance / "superapp.db") as d:
            self.assertNotEqual(d.execute("SELECT sesi_token FROM pengguna").fetchone()[0], token_baru)
        self.assertEqual((tujuan / "data" / "spt" / "1" / "SPT-1.docx").read_bytes(), b"PK\x03\x04spt")
        self.assertEqual((templat_b / "berita.docx").read_bytes(), b"PK\x03\x04templat-a")
        self.assertEqual(len(list(templat_b.glob("berita.docx.lama-*"))), 1)
        self.assertEqual(len(list(tujuan.glob("superapp.db.lama-*"))), 1)
        self.assertTrue((next(tujuan.glob("data.lama-*")) / "liputan" / "lama.jpg").is_file())
        sebelum = arsip.daftar_cadangan(tujuan / "cadangan" / "berkas")
        self.assertEqual([c["jenis"] for c in sebelum], ["sebelum-pulihkan"])
        self.assertEqual(pulihkan.periksa(tujuan / "cadangan" / "berkas" / sebelum[0]["nama"], SANDI, self.akar / "p")
                         ["hitungan"]["log_proses"], 8)
        self.assertIn("/masuk", klien_b.get("/").location)                   # cookie sesi lama tidak valid
        self.assertIn(("Pulihkan", "terminal", "sukses"),
                      [(c["aksi"], c["pelaku"], c["hasil"]) for c in audit.baca(tujuan / "cadangan")])
        self.assertTrue(laporan["sandi_baru_diatur"] is False or sandi_mod.cocok(tujuan / "cadangan", SANDI))

    def test_pulihkan_database_saja_tidak_menyentuh_data(self):
        cadangan = self.buat_cadangan("database")["jalur"]
        tujuan, templat_b, _, _ = self.instance_lain()
        data_sebelum = isi_berkas(tujuan / "data")
        templat_sebelum = isi_berkas(templat_b)
        laporan, keluaran = self.pulihkan_ke(tujuan, templat_b, cadangan)
        self.assertIn("TIDAK diubah", keluaran)
        self.assertEqual(isi_berkas(tujuan / "data"), data_sebelum)
        self.assertEqual(isi_berkas(templat_b), templat_sebelum)
        self.assertEqual(laporan["hilang"], {"berkas SPT": 1, "hasil gabung PDF": 1})
        self.assertFalse(list(tujuan.glob("data.lama-*")))

    def test_pulihkan_ke_server_baru_tanpa_database(self):
        cadangan = self.buat_cadangan()["jalur"]
        baru = self.akar / "server-baru"
        laporan, _ = self.pulihkan_ke(baru, self.akar / "templat-baru", cadangan)
        self.assertIsNone(laporan["sebelum_pulihkan"])
        self.assertTrue(laporan["sandi_baru_diatur"])
        self.assertTrue(sandi_mod.cocok(baru / "cadangan", SANDI))
        self.assertTrue((baru / "data" / "gabung_dokumen" / "1" / "Gabungan.pdf").is_file())

    def test_rollback_saat_gagal_di_tengah(self):
        cadangan = self.buat_cadangan()["jalur"]
        tujuan, templat_b, _, _ = self.instance_lain()
        sebelum_db = (tujuan / "superapp.db").read_bytes()
        sebelum_data, sebelum_templat = isi_berkas(tujuan / "data"), isi_berkas(templat_b)
        with mock.patch.object(pulihkan, "_pasang_templat", side_effect=OSError("disk penuh")):
            with self.assertRaisesRegex(pulihkan.GalatPulihkan, "dikembalikan"):
                self.pulihkan_ke(tujuan, templat_b, cadangan)
        self.assertEqual((tujuan / "superapp.db").read_bytes(), sebelum_db)
        self.assertEqual(isi_berkas(tujuan / "data"), sebelum_data)
        self.assertEqual(isi_berkas(templat_b), sebelum_templat)
        self.assertFalse(list(tujuan.glob("superapp.db.lama-*")) + list(tujuan.glob("data.lama-*")))

    def test_tolak_saat_aplikasi_berjalan(self):
        cadangan = self.buat_cadangan()["jalur"]
        tujuan, templat_b, _, _ = self.instance_lain()
        kunci = sqlite3.connect(tujuan / "superapp.db")
        kunci.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaisesRegex(pulihkan.GalatPulihkan, "Matikan aplikasi"):
                self.pulihkan_ke(tujuan, templat_b, cadangan)
        finally:
            kunci.rollback()
            kunci.close()


# ====================== Perintah terminal ======================
class UjiTerminal(DasarCadangan):
    def setUp(self):
        super().setUp()
        self.isi_data_contoh()
        self.siapkan_sandi()

    def jalankan(self, app, argumen, masukan="", sandi=SANDI):
        with mock.patch.dict(os.environ, {"SUPERAPP_SANDI_CADANGAN": sandi}):
            return app.test_cli_runner().invoke(args=argumen, input=masukan)

    def test_buat_periksa_pulihkan_reset(self):
        hasil = self.jalankan(self.app, ["cadangan", "buat", "--jenis", "database"])
        self.assertEqual(hasil.exit_code, 0, hasil.output)
        zip_ = arsip.daftar_cadangan(self.folder_cadangan / "berkas")[0]
        jalur = str(self.folder_cadangan / "berkas" / zip_["nama"])
        hasil = self.jalankan(self.app, ["cadangan", "periksa", jalur])
        self.assertEqual(hasil.exit_code, 0, hasil.output)
        self.assertIn("lolos pemeriksaan", hasil.output)
        hasil = self.jalankan(self.app, ["cadangan", "periksa", jalur], sandi="sandi-yang-salah")
        self.assertNotEqual(hasil.exit_code, 0)
        hasil = self.jalankan(self.app, ["cadangan", "buat"], sandi="sandi-yang-salah")
        self.assertNotEqual(hasil.exit_code, 0)
        ke = self.akar / "tujuan-lain"
        hasil = self.jalankan(self.app, ["cadangan", "buat", "--ke", str(ke)])
        self.assertEqual(hasil.exit_code, 0, hasil.output)
        self.assertEqual(len(list(ke.glob("cadangan-lengkap-*.zip"))), 1)

        tujuan, templat_b, app_b, _ = self.instance_lain()
        hasil = self.jalankan(app_b, ["cadangan", "pulihkan", jalur], masukan="batal\n")
        self.assertNotEqual(hasil.exit_code, 0)
        hasil = self.jalankan(app_b, ["cadangan", "pulihkan", jalur], masukan="PULIHKAN\n")
        self.assertEqual(hasil.exit_code, 0, hasil.output)
        self.assertIn("Pemulihan selesai", hasil.output)
        self.assertIn("1 berkas SPT", hasil.output)
        with sqlite3.connect(tujuan / "superapp.db") as d:
            self.assertIn(("cadangan", "Pulihkan"), d.execute("SELECT modul, aksi FROM log_proses").fetchall())

        with mock.patch("getpass.getpass", side_effect=["sandi-reset-baru-1", "sandi-reset-baru-1"]):
            hasil = self.app.test_cli_runner().invoke(args=["cadangan", "reset-sandi"])
        self.assertEqual(hasil.exit_code, 0, hasil.output)
        self.assertTrue(sandi_mod.cocok(self.folder_cadangan, "sandi-reset-baru-1"))
        self.assertIn(("Reset kata sandi cadangan", "terminal", "sukses"),
                      [(c["aksi"], c["pelaku"], c["hasil"]) for c in audit.baca(self.folder_cadangan)])


# ====================== Sidebar & Dashboard ======================
class UjiTampilan(DasarCadangan):
    def test_sidebar_dan_peringatan_dashboard(self):
        html = self.klien.get("/").get_data(as_text=True)
        self.assertIn('href="/cadangan"', html)
        self.assertIn("Belum ada cadangan dalam 7 hari terakhir", html)
        self.assertLess(html.index('title="Cadangan"'), html.index('title="Pengaturan"'))
        self.siapkan_sandi()
        html = self.klien.get("/cadangan").get_data(as_text=True)
        self.assertRegex(html, r'href="/cadangan" title="Cadangan" aria-current="page"')
        self.assertNotRegex(html, r'href="/alat" title="Alat" aria-current="page"')
        self.assertIn('data-tombol-progres="Membuat cadangan…"', html)
        hasil = self.buat_cadangan("database")
        self.assertNotIn("Belum ada cadangan dalam 7 hari terakhir", self.klien.get("/").get_data(as_text=True))
        info = arsip.baca_pendamping(hasil["jalur"])
        info["dibuat_lokal"] = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")
        hasil["jalur"].with_suffix(".json").write_text(json.dumps(info))
        self.assertIn("Belum ada cadangan dalam 7 hari terakhir", self.klien.get("/").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
