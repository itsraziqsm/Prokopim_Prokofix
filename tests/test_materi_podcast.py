"""Uji Data Podcast > Materi Podcast: penguraian jawaban, status instansi, CRUD, ekspor Word, keamanan."""
import random
import re
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from docx import Document
from docx.oxml.ns import qn

from app import create_app
from app.modul.data_podcast.materi import contoh, layanan, pengurai
from app.modul.data_podcast.materi.ekspor import LEBAR_TEKS, MARGIN, bagi_judul

SANDI = "rahasia123"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# ====================== Penguraian ======================
class UjiPengurai(unittest.TestCase):
    def jenis(self, teks):
        return [b["jenis"] for b in pengurai.urai(teks)]

    def test_paragraf_per_baris_dan_baris_kosong_diabaikan(self):
        blok = pengurai.urai("Satu\n\n\n  \nDua\r\nTiga")
        self.assertEqual(self.jenis("Satu\n\n\n  \nDua\r\nTiga"), ["paragraf"] * 3)
        self.assertEqual([b["isi"][0][0] for b in blok], ["Satu", "Dua", "Tiga"])

    def test_spasi_dirapikan(self):
        blok = pengurai.urai("  Ada  spasi   ganda\tdan tab  ")
        self.assertEqual(blok[0]["isi"], [("Ada spasi ganda dan tab", False, False)])
        self.assertFalse(pengurai.ada_isi("  \t\n"))

    def test_daftar_bernomor_selalu_mulai_dari_satu(self):
        blok = pengurai.urai("7. tujuh\n3. tiga\n10. sepuluh")
        self.assertEqual(len(blok), 1)
        self.assertTrue(blok[0]["bernomor"])
        self.assertEqual([b["isi"][0][0] for b in blok[0]["butir"]], ["tujuh", "tiga", "sepuluh"])
        html = str(pengurai.html("7. tujuh\n3. tiga"))
        self.assertIn("<ol", html)
        self.assertNotIn("start=", html)          # nomor ketikan tidak dipakai
        # paragraf di antara dua daftar -> dua blok daftar
        self.assertEqual(self.jenis("1. a\nSela\n5. b"), ["daftar", "paragraf", "daftar"])

    def test_daftar_diselingi_paragraf_bisa_lanjut_atau_mulai_baru(self):
        teks = ("1. Deteksi\nPenjelasan\n2. Verifikasi\nPenjelasan\n3. Mobilisasi\nPenjelasan\n"
                "1. Baru satu\n2. Baru dua\nSela\n1. Baru lagi")
        daftar = [b for b in pengurai.urai(teks) if b["jenis"] == "daftar"]
        self.assertEqual([d["mulai"] for d in daftar], [1, 2, 3, 1, 1])
        rantai = [d["rantai"] for d in daftar]
        self.assertEqual(rantai[0], rantai[1])
        self.assertEqual(rantai[1], rantai[2])                  # "2." dan "3." melanjutkan
        self.assertEqual(len({rantai[2], rantai[3], rantai[4]}), 3)   # "1." selalu daftar baru
        html = str(pengurai.html(teks))
        self.assertIn('<ol start="2"', html)
        self.assertIn('<ol start="3"', html)
        self.assertEqual(html.count("<ol "), 5)
        # di dalam satu daftar yang tidak terputus, angka ketikan tetap diabaikan
        self.assertEqual(pengurai.urai("1. a\n1. b\n1. c")[0]["mulai"], 1)
        self.assertEqual(len(pengurai.urai("1. a\n1. b\n1. c")[0]["butir"]), 3)
        # tanpa daftar sebelumnya, "3." tetap mulai dari 1
        self.assertEqual(pengurai.urai("Sela\n3. x")[1]["mulai"], 1)

    def test_daftar_berpoin_dan_ganti_jenis(self):
        blok = pengurai.urai("- a\n- b\n1. c")
        self.assertEqual([(b["jenis"], b["bernomor"]) for b in blok], [("daftar", False), ("daftar", True)])

    def test_daftar_bersarang_dan_paragraf_lanjutan(self):
        teks = "1. Induk\n   Lanjutan induk\n   - Anak 1\n     Lanjutan anak\n   - Anak 2\n       1. Cucu\n2. Induk dua"
        blok = pengurai.urai(teks)
        self.assertEqual(len(blok), 1)
        induk = blok[0]["butir"]
        self.assertEqual(len(induk), 2)
        anak = induk[0]["anak"]
        self.assertEqual([a["jenis"] for a in anak], ["paragraf", "daftar"])
        self.assertEqual(anak[0]["isi"][0][0], "Lanjutan induk")
        sub = anak[1]["butir"]
        self.assertEqual([s["isi"][0][0] for s in sub], ["Anak 1", "Anak 2"])
        self.assertEqual(sub[0]["anak"][0]["isi"][0][0], "Lanjutan anak")
        self.assertEqual(sub[1]["anak"][0]["jenis"], "daftar")
        self.assertEqual(induk[1]["isi"][0][0], "Induk dua")
        # tab di awal baris = indentasi lebih dalam
        tab = pengurai.urai("1. a\n\t- b\n\t\t- c")[0]["butir"][0]["anak"][0]
        self.assertEqual(tab["butir"][0]["isi"][0][0], "b")
        self.assertEqual(tab["butir"][0]["anak"][0]["butir"][0]["isi"][0][0], "c")

    def test_baris_tanpa_indentasi_menutup_daftar(self):
        self.assertEqual(self.jenis("- a\nParagraf"), ["daftar", "paragraf"])

    def test_tebal_miring_dan_judul_kecil(self):
        isi = pengurai.urai("Ini **tebal** dan *miring* serta ***dua***")[0]["isi"]
        self.assertIn(("tebal", True, False), isi)
        self.assertIn(("miring", False, True), isi)
        self.assertEqual(pengurai.urai("**Judul Kecil**")[0], {"jenis": "judul", "isi": [("Judul Kecil", False, False)]})
        self.assertEqual(self.jenis("**a** dan **b**"), ["paragraf"])
        self.assertEqual(pengurai.urai("2*3*4")[0]["isi"], [("2*3*4", False, False)])

    def test_tanda_tidak_berpasangan_tampil_apa_adanya(self):
        for teks in ("**tebal tanpa tutup", "*miring", "a ** b", "| sel tanpa tutup", "**", "*", "-", "1.", "|---|"):
            blok = pengurai.urai(teks)            # tidak boleh melempar galat
            self.assertIsInstance(blok, list)
        self.assertEqual(pengurai.teks_polos("**tebal tanpa tutup"), "**tebal tanpa tutup")
        self.assertEqual(pengurai.teks_polos("*miring"), "*miring")

    def test_tabel_dengan_dan_tanpa_header(self):
        t = pengurai.urai("| A | B |\n|---|:---:|\n| 1 | 2 |\n| 3 |")[0]
        self.assertEqual(t["jenis"], "tabel")
        self.assertEqual([s[0][0] for s in t["header"]], ["A", "B"])
        self.assertEqual(len(t["baris"]), 2)
        self.assertEqual(len(t["baris"][1]), 2)    # kolom kurang dilengkapi
        tanpa = pengurai.urai("| x | y |\n| z | w |")[0]
        self.assertIsNone(tanpa["header"])
        self.assertEqual(len(tanpa["baris"]), 2)
        self.assertEqual(pengurai.urai("| a \\| b |")[0]["baris"][0][0][0][0], "a | b")
        html = str(pengurai.html("| A |\n|---|\n| 1 |"))
        self.assertIn('<th scope="col">A</th>', html)
        self.assertIn('class="relative overflow-x-auto"', html)

    def test_xss_selalu_di_escape(self):
        muatan = ['<script>alert(1)</script>', '"><img src=x onerror=alert(1)>', "<b onclick='x'>a</b>",
                  "javascript:alert(1)", "<iframe srcdoc='x'></iframe>"]
        for m in muatan:
            for teks in (m, f"**{m}**", f"1. {m}", f"| {m} |", f"- *{m}*"):
                html = str(pengurai.html(teks))
                self.assertNotIn("<script", html)
                self.assertNotIn("<img", html)
                self.assertNotIn("<iframe", html)
                self.assertNotIn("<b ", html)
                self.assertNotRegex(html, r"<[^>]*\son\w+=")

    def test_masukan_acak_tidak_menimbulkan_galat(self):
        acak = random.Random(7)
        huruf = "ab *|-1.\t \n **#<>&"
        for _ in range(500):
            teks = "".join(acak.choice(huruf) for _ in range(acak.randint(0, 80)))
            pengurai.urai(teks)
            pengurai.html(teks)

    def test_bagi_judul_dua_baris_tanpa_mengubah_kata(self):
        judul = "Rekap Jawaban Podcast Mitigasi Bencana 2026"
        baris = bagi_judul(judul)
        self.assertEqual(len(baris), 2)
        self.assertEqual(" ".join(baris), judul)
        self.assertEqual(bagi_judul("Rekap Singkat"), ["Rekap Singkat"])


# ====================== Status ======================
class UjiStatus(unittest.TestCase):
    def test_status_instansi(self):
        self.assertEqual(layanan.status_instansi(3, 0, False), "belum")
        self.assertEqual(layanan.status_instansi(0, 0, True), "belum")
        self.assertEqual(layanan.status_instansi(3, 1, False), "proses")
        self.assertEqual(layanan.status_instansi(3, 3, False), "proses")
        self.assertEqual(layanan.status_instansi(3, 3, True), "selesai")
        self.assertEqual(layanan.status_instansi(3, 2, True), "proses")   # tanda lama tidak berlaku lagi


# ====================== Web ======================
class DasarWeb(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.app = create_app({"TESTING": True}, instance_path=self.folder)
        self.klien = self.app.test_client()
        self.klien.post("/siapkan", data={"csrf_token": self.token("/siapkan"), "nama_lengkap": "Budi",
                                          "nama_pengguna": "budi", "sandi": SANDI, "konfirmasi": SANDI})

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def token(self, url="/akun", klien=None):
        html = (klien or self.klien).get(url).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def post(self, url, **data):
        return self.klien.post(url, data={"csrf_token": self.token(), **data})

    def db(self):
        koneksi = sqlite3.connect(f"{self.folder}/superapp.db")
        koneksi.row_factory = sqlite3.Row
        return closing(koneksi)

    def satu(self, sql, *param):
        with self.db() as d:
            return d.execute(sql, param).fetchone()

    def contoh(self):
        with self.app.app_context():
            return layanan.buat_contoh()

    def buat_materi(self, judul="Materi Uji", keterangan="Per 1 Mei"):
        r = self.post("/podcast/materi/baru", judul=judul, keterangan=keterangan)
        self.assertEqual(r.status_code, 302)
        return int(r.location.rstrip("/").split("/")[-1])

    def tambah_instansi(self, mid, nama):
        r = self.post(f"/podcast/materi/{mid}/instansi", nama=nama)
        self.assertEqual(r.status_code, 302)
        return int(r.location.split("/instansi/")[1])

    def simpan_instansi(self, mid, iid, pertanyaan, nama="Dinas Uji", selesai=False):
        data = {"nama": nama, "pid": [str(p[0] or "") for p in pertanyaan],
                "teks": [p[1] for p in pertanyaan], "jawaban": [p[2] for p in pertanyaan]}
        if selesai:
            data["selesai"] = "1"
        return self.post(f"/podcast/materi/{mid}/instansi/{iid}", **data)

    def pertanyaan(self, iid):
        with self.db() as d:
            return d.execute("SELECT id, teks, jawaban FROM materi_pertanyaan WHERE instansi_id = ? ORDER BY urutan",
                             (iid,)).fetchall()


class UjiHalaman(DasarWeb):
    def test_semua_halaman_terbuka_dan_kartu_induk(self):
        mid = self.contoh()
        for url in ("/podcast", "/podcast/materi", "/podcast/materi?q=Hijau", "/podcast/materi/baru",
                    f"/podcast/materi/{mid}", f"/podcast/materi/{mid}/instansi/1", f"/podcast/materi/{mid}/baca"):
            self.assertEqual(self.klien.get(url).status_code, 200, url)
        alat = self.klien.get("/alat").get_data(as_text=True)
        self.assertIn('href="/podcast"', alat)
        self.assertNotIn('href="/podcast/materi"', alat)          # anak tampil di halaman induk saja
        self.assertIn("Pemecah SPT", alat)
        self.assertIn("Arsip Liputan", alat)
        induk = self.klien.get("/podcast").get_data(as_text=True)
        self.assertIn('href="/podcast/materi"', induk)
        self.assertIn("Fitur baru akan hadir di sini", induk)

    def test_pencarian_judul(self):
        self.contoh()
        self.buat_materi("Podcast Lain")
        html = self.klien.get("/podcast/materi?q=Hijau").get_data(as_text=True)
        self.assertIn("Kota Hijau", html)
        self.assertNotIn("Podcast Lain", html)
        self.assertIn("Tidak ada materi", self.klien.get("/podcast/materi?q=%25_tidak").get_data(as_text=True))

    def test_mode_baca_berisi_nomor_status_dan_jawaban_aman(self):
        mid = self.contoh()
        html = self.klien.get(f"/podcast/materi/{mid}/baca").get_data(as_text=True)
        for teks in ("1.1", "2.2", "3.1", 'data-status="selesai"', 'data-status="proses"', 'data-status="belum"',
                     "<strong>Taman lingkungan</strong>", "Belum dijawab.", "data-cetak", "data-ukuran-baca"):
            self.assertIn(teks, html)

    def test_pratinjau_memakai_pengurai_dan_escape(self):
        r = self.post("/podcast/materi/pratinjau", teks="1. <script>x</script>\n- **b**")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<strong>b</strong>", html)

    def test_tanpa_query_berlebihan(self):
        """Jumlah query halaman materi & mode baca tidak bertambah seiring jumlah instansi (tanpa N+1)."""
        def hitung(url):
            jumlah = [0]
            asli = sqlite3.connect

            def sambung(*a, **k):
                koneksi = asli(*a, **k)
                koneksi.set_trace_callback(lambda sql: jumlah.__setitem__(0, jumlah[0] + sql.lstrip().upper().startswith("SELECT")))
                return koneksi
            with mock.patch("app.db.sqlite3.connect", side_effect=sambung):
                self.assertEqual(self.klien.get(url).status_code, 200)
            return jumlah[0]

        mid = self.contoh()
        awal = {u: hitung(u) for u in (f"/podcast/materi/{mid}", f"/podcast/materi/{mid}/baca")}
        for n in range(6):
            iid = self.tambah_instansi(mid, f"Instansi {n}")
            self.simpan_instansi(mid, iid, [(None, "Tanya?", "Jawab.")], nama=f"Instansi {n}")
        for url, jumlah in awal.items():
            self.assertEqual(hitung(url), jumlah, url)


class UjiCrud(DasarWeb):
    def test_buat_ubah_materi_dan_validasi(self):
        r = self.post("/podcast/materi/baru", judul="  ", keterangan="")
        self.assertEqual(r.status_code, 400)
        mid = self.buat_materi()
        self.assertEqual(self.post(f"/podcast/materi/{mid}/simpan", judul="Judul Baru", keterangan="Per 2 Mei").status_code, 302)
        self.assertEqual(tuple(self.satu("SELECT judul, keterangan FROM materi_podcast WHERE id = ?", mid)),
                         ("Judul Baru", "Per 2 Mei"))
        self.assertEqual(self.post(f"/podcast/materi/{mid}/simpan", judul="x" * 300).status_code, 400)
        self.assertEqual(self.post(f"/podcast/materi/{mid}/instansi", nama="").status_code, 400)

    def test_simpan_pertanyaan_tambah_ubah_hapus_urut_ulang(self):
        mid = self.buat_materi()
        iid = self.tambah_instansi(mid, "Dinas A")
        self.simpan_instansi(mid, iid, [(None, "P1", "J1"), (None, "P2", ""), (None, "P3", "J3")])
        p1, p2, p3 = [b["id"] for b in self.pertanyaan(iid)]
        # urut ulang (P3 ke atas), ubah P1, hapus P2, tambah P4, baris kosong diabaikan
        self.simpan_instansi(mid, iid, [(p3, "P3", "J3"), (p1, "P1 diubah", "J1 baru"), (None, "", "  "), (None, "P4", "")])
        hasil = [(b["id"], b["teks"], b["jawaban"]) for b in self.pertanyaan(iid)]
        self.assertEqual([h[1] for h in hasil], ["P3", "P1 diubah", "P4"])
        self.assertEqual(hasil[0][0], p3)
        self.assertEqual(hasil[1][0], p1)
        self.assertNotIn(p2, [h[0] for h in hasil])
        self.assertEqual(hasil[1][2], "J1 baru")

    def test_pertanyaan_kosong_berjawaban_dan_jawaban_terlalu_panjang_ditolak(self):
        mid = self.buat_materi()
        iid = self.tambah_instansi(mid, "Dinas A")
        self.assertEqual(self.simpan_instansi(mid, iid, [(None, "", "Ada jawaban")]).status_code, 400)
        r = self.simpan_instansi(mid, iid, [(None, "P", "x" * (pengurai.PANJANG_MAKS + 1))])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.pertanyaan(iid), [])
        # pid milik instansi lain tidak bisa dipakai untuk mengubah pertanyaannya
        iid2 = self.tambah_instansi(mid, "Dinas B")
        self.simpan_instansi(mid, iid2, [(None, "Milik B", "")])
        pid_b = self.pertanyaan(iid2)[0]["id"]
        self.simpan_instansi(mid, iid, [(pid_b, "Disusupkan", "")])
        self.assertEqual(self.pertanyaan(iid2)[0]["teks"], "Milik B")

    def test_tandai_selesai_ditolak_bila_ada_pertanyaan_tanpa_jawaban(self):
        mid = self.buat_materi()
        iid = self.tambah_instansi(mid, "Dinas A")
        r = self.simpan_instansi(mid, iid, [(None, "P1", "J1"), (None, "P2", "")], selesai=True)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.satu("SELECT selesai FROM materi_instansi WHERE id = ?", iid)[0], 0)
        self.assertEqual(len(self.pertanyaan(iid)), 2)                     # isian lain tetap tersimpan
        with self.app.app_context():
            self.assertEqual(layanan.ambil_instansi(mid, iid)["status"], "proses")
        self.simpan_instansi(mid, iid, [(None, "P1", "J1"), (None, "P2", "J2")], selesai=True)
        self.assertEqual(self.satu("SELECT selesai FROM materi_instansi WHERE id = ?", iid)[0], 1)
        with self.app.app_context():
            self.assertEqual(layanan.ambil_instansi(mid, iid)["status"], "selesai")
        aksi = [b[0] for b in self.satu_semua("SELECT aksi FROM log_proses WHERE modul = 'materi_podcast'")]
        self.assertIn("Tandai selesai", aksi)

    def satu_semua(self, sql):
        with self.db() as d:
            return d.execute(sql).fetchall()

    def test_geser_instansi(self):
        mid = self.buat_materi()
        a, b, c = (self.tambah_instansi(mid, n) for n in ("A", "B", "C"))
        r = self.post(f"/podcast/materi/{mid}/instansi/{c}/geser", arah="naik")
        self.assertIn(f"fokus=geser-naik-{c}", r.location)
        self.post(f"/podcast/materi/{mid}/instansi/{a}/geser", arah="naik")      # sudah paling atas: tetap
        urut = [r[0] for r in self.satu_semua(f"SELECT nama FROM materi_instansi WHERE materi_id = {mid} ORDER BY urutan")]
        self.assertEqual(urut, ["A", "C", "B"])

    def test_hapus_materi_menghapus_anak_dan_berkas(self):
        mid = self.contoh()
        self.post(f"/podcast/materi/{mid}/ekspor")
        folder = Path(self.folder) / "data" / "podcast" / str(mid)
        self.assertTrue(folder.is_dir())
        r = self.post(f"/podcast/materi/{mid}/hapus")
        self.assertEqual(r.status_code, 302)
        self.assertFalse(folder.exists())
        for tabel in ("materi_podcast", "materi_instansi", "materi_pertanyaan"):
            self.assertEqual(self.satu(f"SELECT COUNT(*) FROM {tabel}")[0], 0, tabel)

    def test_hapus_instansi(self):
        mid = self.contoh()
        self.post(f"/podcast/materi/{mid}/instansi/1/hapus")
        self.assertEqual(self.satu("SELECT COUNT(*) FROM materi_instansi")[0], 2)
        self.assertEqual(self.satu("SELECT COUNT(*) FROM materi_pertanyaan WHERE instansi_id = 1")[0], 0)

    def test_duplikat_menyalin_semuanya(self):
        mid = self.contoh()
        r = self.post(f"/podcast/materi/{mid}/duplikat")
        baru = int(r.location.rstrip("/").split("/")[-1])
        self.assertNotEqual(baru, mid)

        def isi(m):
            with self.db() as d:
                return d.execute("""SELECT i.urutan, i.nama, i.selesai, p.urutan, p.teks, p.jawaban
                                    FROM materi_instansi i JOIN materi_pertanyaan p ON p.instansi_id = i.id
                                    WHERE i.materi_id = ? ORDER BY i.urutan, p.urutan""", (m,)).fetchall()
        self.assertEqual([tuple(b) for b in isi(baru)], [tuple(b) for b in isi(mid)])
        self.assertTrue(self.satu("SELECT judul FROM materi_podcast WHERE id = ?", baru)[0].endswith("(salinan)"))

    def test_perintah_contoh(self):
        hasil = self.app.test_cli_runner().invoke(args=["podcast", "contoh"])
        self.assertEqual(hasil.exit_code, 0, hasil.output)
        with self.app.app_context():
            mid = layanan.daftar_materi()[0]["id"]
            self.assertEqual([i["status"] for i in layanan.daftar_instansi(mid)], ["selesai", "proses", "belum"])


class UjiKeamanan(DasarWeb):
    def test_rute_wajib_login(self):
        mid = self.contoh()
        tamu = self.app.test_client()
        for url in ("/podcast", "/podcast/materi", "/podcast/materi/baru", f"/podcast/materi/{mid}",
                    f"/podcast/materi/{mid}/instansi/1", f"/podcast/materi/{mid}/baca", f"/podcast/materi/{mid}/unduh"):
            r = tamu.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/masuk", r.location)
        token = self.token("/masuk", klien=tamu)
        for url in (f"/podcast/materi/{mid}/hapus", f"/podcast/materi/{mid}/ekspor", "/podcast/materi/pratinjau"):
            r = tamu.post(url, data={"csrf_token": token})
            self.assertEqual(r.status_code, 302, url)
        self.assertEqual(self.satu("SELECT COUNT(*) FROM materi_podcast")[0], 1)

    def test_csrf_ditolak(self):
        mid = self.contoh()
        for url in (f"/podcast/materi/{mid}/hapus", f"/podcast/materi/{mid}/duplikat", "/podcast/materi/baru",
                    f"/podcast/materi/{mid}/instansi/1", "/podcast/materi/pratinjau"):
            self.assertEqual(self.klien.post(url, data={"judul": "x"}).status_code, 400, url)
        self.assertEqual(self.satu("SELECT COUNT(*) FROM materi_podcast")[0], 1)

    def test_unduh_hanya_dari_folder_ekspor(self):
        mid = self.contoh()
        self.assertEqual(self.klien.get(f"/podcast/materi/{mid}/unduh").status_code, 404)   # belum diekspor
        self.post(f"/podcast/materi/{mid}/ekspor")
        r = self.klien.get(f"/podcast/materi/{mid}/unduh")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        r.close()
        for nama in ("../../../secret_key", "../../../superapp.db", "/etc/passwd", "..\\..\\secret_key"):
            with self.db() as d:
                d.execute("UPDATE materi_podcast SET berkas_ekspor = ? WHERE id = ?", (nama, mid))
                d.commit()
            self.assertEqual(self.klien.get(f"/podcast/materi/{mid}/unduh").status_code, 404, nama)
        self.assertEqual(self.klien.get("/podcast/materi/999/unduh").status_code, 404)


# ====================== Ekspor Word ======================
def _kata(teks):
    return re.findall(r"\S+", teks)


def _kata_jawaban_db(jawaban):
    """Kata isi jawaban dari teks database, dihitung TERPISAH dari pengurai (buang tanda format saja)."""
    kata = []
    for baris in jawaban.splitlines():
        s = baris.strip()
        if re.fullmatch(r"\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?", s) and "-" in s:
            continue                                         # baris pemisah header tabel
        if s.startswith("|"):
            s = " ".join(sel.strip() for sel in s.strip("|").split("|"))
        s = re.sub(r"^(\d+\.|-)\s+", "", s)                  # penanda daftar
        s = s.replace("**", "").replace("*", "")
        kata += _kata(s)
    return kata


class UjiEkspor(DasarWeb):
    def setUp(self):
        super().setUp()
        self.mid = self.contoh()
        self.assertEqual(self.post(f"/podcast/materi/{self.mid}/ekspor").status_code, 302)
        with self.app.app_context():
            materi = layanan.ambil_materi(self.mid)
            self.jalur = layanan.jalur_ekspor(materi)
            self.instansi = layanan.muat_lengkap(self.mid)
        self.doc = Document(self.jalur)

    def test_berkas_dan_log(self):
        self.assertEqual(self.jalur.parent, Path(self.folder) / "data" / "podcast" / str(self.mid) / "ekspor")
        baris = self.satu("SELECT aksi, status, lokasi FROM log_proses WHERE aksi = 'Ekspor Word'")
        self.assertEqual((baris["status"], baris["lokasi"]), ("sukses", str(self.jalur.parent)))

    def test_a4_margin_dan_font(self):
        sec = self.doc.sections[0]
        self.assertEqual((sec.page_width.twips, sec.page_height.twips), (11906, 16838))
        for m in (sec.left_margin, sec.right_margin, sec.top_margin, sec.bottom_margin):
            self.assertEqual(m.twips, MARGIN)
        self.assertEqual(round(sec.left_margin.cm, 2), 2.0)
        bawaan = self.doc.styles.element.find(qn("w:docDefaults"))
        self.assertEqual(bawaan.find(f".//{W}sz").get(qn("w:val")), "24")
        self.assertEqual(bawaan.find(f".//{W}spacing").get(qn("w:line")), "288")
        self.assertEqual(bawaan.find(f".//{W}rFonts").get(qn("w:ascii")), "Calibri")

    def test_gaya_bernama(self):
        nama = {s.name for s in self.doc.styles}
        for g in ("Title", "Subjudul", "Ringkas", "Heading 1", "Status Instansi", "Pertanyaan",
                  "Label Jawaban", "Isi Jawaban", "Butir Jawaban", "Kaki"):
            self.assertIn(g, nama)
        dipakai = {p.style.name for p in self.doc.paragraphs}
        self.assertTrue({"Title", "Heading 1", "Pertanyaan", "Label Jawaban", "Isi Jawaban", "Butir Jawaban"} <= dipakai)

    def test_bookmark_dan_tautan_internal_sejumlah_instansi(self):
        tubuh = self.doc.element.body
        bookmark = [b.get(qn("w:name")) for b in tubuh.iter(qn("w:bookmarkStart"))]
        tautan = [h.get(qn("w:anchor")) for h in tubuh.iter(qn("w:hyperlink"))]
        self.assertEqual(len(bookmark), len(self.instansi))
        self.assertEqual(sorted(tautan), sorted(bookmark))
        # tabel ringkasan: header + satu baris per instansi, status tertulis
        ringkasan = self.doc.tables[0]
        self.assertEqual(len(ringkasan.rows), len(self.instansi) + 1)
        self.assertEqual([r.cells[3].text for r in ringkasan.rows[1:]], ["Selesai", "Dalam proses", "Belum ada jawaban"])
        self.assertLessEqual(sum(int(g.get(qn("w:w"))) for g in ringkasan._tbl.tblGrid.iter(qn("w:gridCol"))), LEBAR_TEKS)

    def test_footer_berisi_field_halaman(self):
        kaki = self.doc.sections[0].footer._element
        perintah = "".join(t.text for t in kaki.iter(qn("w:instrText")))
        self.assertIn("PAGE", perintah)
        self.assertIn("NUMPAGES", perintah)
        self.assertIn(contoh.JUDUL, "".join(t.text or "" for t in kaki.iter(qn("w:t"))))

    def test_daftar_bernomor_memakai_numbering_word_mulai_dari_satu(self):
        tubuh = self.doc.element.body
        dipakai = {n.get(qn("w:val")) for n in tubuh.iter(qn("w:numId"))}
        self.assertGreaterEqual(len(dipakai), 3)            # tiap daftar punya w:num sendiri
        penomoran = self.doc.part.numbering_part.element
        for num in penomoran.findall(qn("w:num")):
            if num.get(qn("w:numId")) in dipakai:
                self.assertEqual(num.find(f".//{W}startOverride").get(qn("w:val")), "1")

    def test_daftar_lanjutan_memakai_num_yang_sama_di_word(self):
        from app.modul.data_podcast.materi.ekspor import buat_dokumen
        jawab = "1. a\nSela\n2. b\nSela\n1. baru"
        ins = [{"nama": "X", "status": "proses", "label_status": "Dalam proses", "jumlah": 2, "terjawab": 2,
                "pertanyaan": [{"teks": "T1", "jawaban": jawab, "terjawab": True},
                               {"teks": "T2", "jawaban": "2. lanjut?", "terjawab": True}]}]
        tujuan = Path(self.folder) / "nomor.docx"
        buat_dokumen({"judul": "Uji", "keterangan": ""}, ins, tujuan)
        doc = Document(tujuan)
        num = [p._p.pPr.numPr.numId.val for p in doc.paragraphs if p.style.name == "Butir Jawaban"]
        self.assertEqual(num[0], num[1])            # "2." melanjutkan daftar "1."
        self.assertNotEqual(num[1], num[2])         # "1." memulai daftar baru
        self.assertNotIn(num[3], num[:3])           # jawaban lain tidak melanjutkan nomor jawaban sebelumnya

    def test_tabel_jawaban_tidak_melebihi_area_cetak(self):
        for t in self.doc.tables[1:]:
            grid = sum(int(g.get(qn("w:w"))) for g in t._tbl.tblGrid.iter(qn("w:gridCol")))
            ind = t._tbl.tblPr.find(qn("w:tblInd"))
            self.assertLessEqual(grid + (int(ind.get(qn("w:w"))) if ind is not None else 0), LEBAR_TEKS)
            for baris in t.rows:
                self.assertIsNotNone(baris._tr.trPr.find(qn("w:cantSplit")))

    def test_label_jawaban_hanya_untuk_pertanyaan_berjawaban(self):
        label = [p for p in self.doc.paragraphs if p.style.name == "Label Jawaban"]
        terjawab = sum(1 for i in self.instansi for p in i["pertanyaan"] if p["terjawab"])
        self.assertEqual(len(label), terjawab)

    def test_urutan_kata_isi_sama_dengan_database(self):
        """Kata isi dokumen (pertanyaan & jawaban, tanpa nomor/label/status) persis sama urutannya dengan DB."""
        harapan = []
        for ins in self.instansi:
            for p in ins["pertanyaan"]:
                harapan += _kata(p["teks"])
                if p["terjawab"]:
                    harapan += _kata_jawaban_db(p["jawaban"])
        lewati = {"Heading 1", "Status Instansi", "Label Jawaban"}
        nama_gaya = {s.style_id: s.name for s in self.doc.styles}
        hasil, mulai = [], False
        for el in self.doc.element.body.iterchildren():
            if el.tag == qn("w:p"):
                gaya = el.find(f"{W}pPr/{W}pStyle")
                gaya = nama_gaya.get(gaya.get(qn("w:val"))) if gaya is not None else "Normal"
                teks = "".join(t.text or "" for t in el.iter(qn("w:t")))
                if gaya == "Heading 1":
                    mulai = True
                if not mulai or gaya in lewati:
                    continue
                if gaya == "Pertanyaan":
                    teks = re.sub(r"^\d+\.\d+", "", teks)    # nomor i.k
                hasil += _kata(teks)
            elif el.tag == qn("w:tbl") and mulai:
                for t in el.iter(qn("w:p")):
                    hasil += _kata("".join(x.text or "" for x in t.iter(qn("w:t"))))
        self.assertEqual(hasil, harapan)


if __name__ == "__main__":
    unittest.main()
