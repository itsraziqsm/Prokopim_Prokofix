"""Pemulihan cadangan (HANYA lewat terminal) — logika murni tanpa Flask.

Urutan WAJIB (gagal di langkah mana pun = berhenti; tidak ada yang berubah sebelum langkah 8, dan langkah 8
dikembalikan seperti semula bila gagal di tengah):
    1. pastikan aplikasi tidak berjalan (BEGIN EXCLUSIVE pada database hidup) + kunci pemulihan
    2. verifikasi tanda HMAC manifest dengan sandi cadangan
    3. periksa struktur ZIP (daftar putih, jalur, ukuran, rasio, nama ganda) TANPA extractall
    4. bongkar ke instance/pulihkan_tmp/<stempel>/ sambil mencocokkan ukuran & SHA-256
    5. validasi database staging (integrity, foreign key, skema dikenal, tanpa trigger/view/tabel virtual)
    6. pratinjau + konfirmasi (pengguna mengetik PULIHKAN)
    7. cadangan otomatis kondisi sekarang ("sebelum-pulihkan")
    8. pasang database / data / templat (yang lama disimpan sebagai *.lama-<stempel>)
    9. token sesi semua pengguna diputar ulang (cookie sesi lama tidak lagi valid)
   10. pemeriksaan akhir + laporan berkas yang hilang
"""
import os
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

from ..waktu import BULAN
from . import arsip, audit, basisdata, sandi as sandi_mod

KATA_KONFIRMASI = "PULIHKAN"


class GalatPulihkan(Exception):
    """Pemulihan dihentikan; pesan aman untuk pengguna. Tidak ada yang diubah (atau sudah dikembalikan)."""


# ---------- Langkah 1 ----------
def pastikan_tidak_berjalan(db_hidup):
    """Gagal bila database sedang dipakai (aplikasi berjalan / ada transaksi). Database belum ada = boleh."""
    if not Path(db_hidup).exists():
        return
    try:
        koneksi = sqlite3.connect(str(db_hidup), timeout=0.5)
        try:
            koneksi.execute("BEGIN EXCLUSIVE")
            koneksi.rollback()
        finally:
            koneksi.close()
    except sqlite3.OperationalError:
        raise GalatPulihkan("Database sedang dipakai. Matikan aplikasi dulu, lalu jalankan pemulihan lagi.")


# ---------- Pratinjau ----------
def hitungan_sekarang(db_hidup):
    if not Path(db_hidup).exists():
        return {}
    koneksi = basisdata.buka_baca_saja(db_hidup)
    try:
        return basisdata.hitung_baris(koneksi)
    finally:
        koneksi.close()


def baris_pratinjau(manifest, ukuran_zip, sekarang_hitung):
    """Teks pratinjau: waktu & jenis cadangan, ukuran, hitungan per tabel, dan selisih dengan data sekarang."""
    baris = [f"Cadangan dibuat : {manifest.get('dibuat')}",
             f"Jenis           : {arsip.JENIS.get(manifest['jenis'], manifest['jenis'])}",
             f"Ukuran berkas   : {ukuran_zip / (1024 * 1024):.1f} MB".replace(".", ","),
             f"Berkas data     : {len(manifest['berkas']) - 1}", "",
             f"{'Tabel':<22}{'Sekarang':>10}{'Cadangan':>10}"]
    cadangan_hitung = manifest.get("hitungan") or {}
    for tabel in basisdata.TABEL_UTAMA:
        if tabel not in cadangan_hitung and tabel not in sekarang_hitung:
            continue
        lama, baru = sekarang_hitung.get(tabel, 0), cadangan_hitung.get(tabel, 0)
        catatan = f"   ({lama - baru} {basisdata.LABEL_TABEL[tabel]} di data sekarang akan hilang)" if lama > baru else ""
        baris.append(f"{basisdata.LABEL_TABEL[tabel]:<22}{lama:>10}{baru:>10}{catatan}")
    if manifest["jenis"] == "database":
        baris += ["", "Jenis \"Database saja\": folder data/ (berkas hasil & foto) TIDAK diubah."]
    return baris


# ---------- Berkas yang hilang ----------
def rekaman_tanpa_berkas(db, instance):
    """Hitung rekaman yang menunjuk ke berkas yang tidak ada (penting setelah pemulihan "Database saja")."""
    instance = Path(instance)
    data = instance / "data"
    koneksi = basisdata.buka_baca_saja(db)
    hasil = {}

    def tambah(label, ada):
        if not ada:
            hasil[label] = hasil.get(label, 0) + 1

    def folder_liputan(liputan_id, tanggal):
        try:
            d = date.fromisoformat(tanggal)
            return data / "liputan" / str(d.year) / f"{d.month:02d}-{BULAN[d.month - 1]}" / str(liputan_id)
        except (TypeError, ValueError):
            return data / "liputan" / "tanpa-tanggal" / str(liputan_id)
    try:
        ada = {b[0] for b in koneksi.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if {"spt", "spt_batch"} <= ada:
            for folder, docx, pdf in koneksi.execute(
                    "SELECT b.folder, s.nama_docx, s.nama_pdf FROM spt s JOIN spt_batch b ON b.id = s.batch_id"):
                for nama in (docx, pdf):
                    if nama:
                        tambah("berkas SPT", folder and (Path(folder) / nama).is_file())
        if "gabung_hasil" in ada:
            for folder, nama in koneksi.execute("SELECT folder, nama_berkas FROM gabung_hasil"):
                tambah("hasil gabung PDF", folder and nama and (Path(folder) / nama).is_file())
        if {"liputan", "liputan_foto"} <= ada:
            for lid, tanggal, nama in koneksi.execute(
                    "SELECT l.id, l.tanggal, f.nama_berkas FROM liputan_foto f JOIN liputan l ON l.id = f.liputan_id"):
                tambah("foto liputan", (folder_liputan(lid, tanggal) / "foto" / nama).is_file())
        if "liputan" in ada:
            for lid, tanggal, nama in koneksi.execute(
                    "SELECT id, tanggal, berkas_ekspor FROM liputan WHERE berkas_ekspor IS NOT NULL"):
                tambah("Word liputan", (folder_liputan(lid, tanggal) / "ekspor" / nama).is_file())
        if "materi_podcast" in ada:
            for mid, nama in koneksi.execute(
                    "SELECT id, berkas_ekspor FROM materi_podcast WHERE berkas_ekspor IS NOT NULL"):
                tambah("Word materi podcast", (data / "podcast" / str(mid) / "ekspor" / nama).is_file())
    finally:
        koneksi.close()
    return hasil


# ---------- Langkah 8: pemasangan (masing-masing mengembalikan fungsi pembatal) ----------
def _pasang_database(staging_db, instance, stempel):
    db_hidup = instance / "superapp.db"
    baru = instance / "superapp.db.baru"
    shutil.copyfile(staging_db, baru)
    basisdata.siapkan_untuk_pasang(baru, str(instance))        # jalur absolut + token sesi baru (langkah 9)
    arsip.fsync_berkas(baru)
    dipindah = []
    for akhiran in ("", "-wal", "-shm", "-journal"):
        lama = Path(f"{db_hidup}{akhiran}")
        if lama.exists():
            simpan = Path(f"{db_hidup}.lama-{stempel}{akhiran}")
            os.replace(lama, simpan)
            dipindah.append((simpan, lama))
    os.replace(baru, db_hidup)

    def batal():
        if db_hidup.exists():
            db_hidup.unlink()
        for simpan, lama in reversed(dipindah):
            os.replace(simpan, lama)
    return batal, [s for s, _ in dipindah[:1]]


def _pasang_data(staging, instance, stempel):
    data = instance / "data"
    sumber = staging / "data"
    sumber.mkdir(exist_ok=True)
    simpan = instance / f"data.lama-{stempel}"
    ada_lama = data.exists()
    if ada_lama:
        os.replace(data, simpan)
    os.replace(sumber, data)

    def batal():
        if data.exists():
            os.replace(data, sumber)
        if ada_lama:
            os.replace(simpan, data)
    return batal, [simpan] if ada_lama else []


def _pasang_templat(staging, folder_templat, stempel):
    sumber = staging / "templat_docx"
    folder_templat = Path(folder_templat)
    terpasang, disimpan = [], []
    try:
        for berkas in sorted(sumber.glob("*.docx")) if sumber.is_dir() else []:
            tujuan = folder_templat / berkas.name
            folder_templat.mkdir(parents=True, exist_ok=True)
            if tujuan.exists():
                simpan = folder_templat / f"{berkas.name}.lama-{stempel}"
                shutil.move(str(tujuan), str(simpan))
                disimpan.append((simpan, tujuan))
            shutil.move(str(berkas), str(tujuan))
            terpasang.append(tujuan)
    except BaseException:
        _batal_templat(terpasang, disimpan)
        raise

    def batal():
        _batal_templat(terpasang, disimpan)
    return batal, [s for s, _ in disimpan]


def _batal_templat(terpasang, disimpan):
    for jalur in terpasang:
        Path(jalur).unlink(missing_ok=True)
    for simpan, tujuan in reversed(disimpan):
        shutil.move(str(simpan), str(tujuan))


# ---------- Prosedur ----------
def validasi_dan_bongkar(jalur_zip, sandi, staging):
    """Langkah 2-5: tanda, struktur, bongkar ke staging, validasi database. Mengembalikan (manifest, hitungan)."""
    with arsip.buka_zip(jalur_zip) as zf:
        manifest = arsip.baca_manifest(zf)
        arsip.verifikasi_tanda(manifest, sandi)                     # 2
        peta = arsip.periksa_struktur(zf, manifest)                 # 3
        staging.mkdir(parents=True)
        arsip.periksa_isi(zf, manifest, peta, folder_bongkar=staging)   # 4
    try:
        hitungan = basisdata.validasi_db(staging / "database" / "superapp.db")   # 5
    except basisdata.GalatBasisData as e:
        raise arsip.GalatArsip(str(e))
    if hitungan != (manifest.get("hitungan") or {}):
        raise arsip.GalatArsip("Isi database tidak cocok dengan ringkasan di manifest.")
    return manifest, hitungan


def periksa(jalur_zip, sandi, instance):
    """Validasi penuh (langkah 2-5) TANPA mengubah data; staging sementara dihapus lagi. Mengembalikan manifest."""
    staging = Path(instance) / "pulihkan_tmp" / f"periksa-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
    try:
        manifest, _ = validasi_dan_bongkar(jalur_zip, sandi, staging)
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def pulihkan(*, jalur_zip, instance, folder_templat, sandi, konfirmasi, tampil, pelaku="terminal"):
    """Jalankan prosedur pemulihan lengkap. konfirmasi() -> teks ketikan pengguna; tampil(baris) untuk keluaran.
    Mengembalikan laporan dict. Melempar GalatPulihkan / arsip.GalatArsip bila dihentikan."""
    instance = Path(instance).resolve()
    folder_cadangan = instance / "cadangan"
    db_hidup = instance / "superapp.db"
    stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    staging = instance / "pulihkan_tmp" / stempel
    nama_zip = Path(jalur_zip).name
    try:
        pastikan_tidak_berjalan(db_hidup)                                        # 1
        with arsip.kunci_berkas(folder_cadangan / "pulihkan.kunci",
                                "Pemulihan lain sedang berjalan. Tunggu sampai selesai."):
            manifest, hitungan = validasi_dan_bongkar(jalur_zip, sandi, staging)    # 2-5
            for baris in baris_pratinjau(manifest, Path(jalur_zip).stat().st_size, hitungan_sekarang(db_hidup)):
                tampil(baris)                                                    # 6
            if (konfirmasi() or "").strip() != KATA_KONFIRMASI:
                raise GalatPulihkan("Pemulihan dibatalkan. Tidak ada yang diubah.")
            pastikan_tidak_berjalan(db_hidup)
            cadangan_sebelum = None
            if db_hidup.exists():                                                # 7
                try:
                    cadangan_sebelum = arsip.buat_cadangan(
                        instance=instance, folder_templat=folder_templat, folder_tujuan=folder_cadangan / "berkas",
                        folder_kerja=folder_cadangan, jenis="sebelum-pulihkan", sandi=sandi)
                except Exception as e:
                    raise GalatPulihkan(f"Cadangan otomatis sebelum pemulihan gagal dibuat ({e}). Tidak ada yang diubah.")
                tampil(f"Cadangan kondisi sekarang dibuat: {cadangan_sebelum['nama']}")

            pembatal, disimpan = [], []                                          # 8
            try:
                batal, lama = _pasang_database(staging / "database" / "superapp.db", instance, stempel)
                pembatal.append(batal); disimpan += lama
                if manifest["jenis"] in arsip.JENIS_DENGAN_DATA:
                    batal, lama = _pasang_data(staging, instance, stempel)
                    pembatal.append(batal); disimpan += lama
                    batal, lama = _pasang_templat(staging, folder_templat, stempel)
                    pembatal.append(batal); disimpan += lama
            except BaseException as e:
                for batal in reversed(pembatal):
                    try:
                        batal()
                    except Exception:
                        pass
                raise GalatPulihkan(f"Pemulihan gagal saat memasang berkas ({e}); kondisi sebelumnya dikembalikan.")

        # 10. Pemeriksaan akhir
        if not basisdata.integritas_ok(db_hidup):
            raise GalatPulihkan("Database hasil pemulihan gagal pemeriksaan integritas. Kembalikan dari "
                                f"{disimpan[0] if disimpan else 'cadangan sebelum-pulihkan'}.")
        koneksi = basisdata.buka_baca_saja(db_hidup)
        try:
            hitungan_akhir = basisdata.hitung_baris(koneksi)
        finally:
            koneksi.close()
        hilang = rekaman_tanpa_berkas(db_hidup, instance)
        sandi_baru_diatur = False
        if not sandi_mod.ada_sandi(folder_cadangan):     # server baru: pakai sandi cadangan ini untuk halaman Cadangan
            sandi_mod.atur_sandi(folder_cadangan, sandi)
            sandi_baru_diatur = True
        laporan = {"stempel": stempel, "jenis": manifest["jenis"], "hitungan": hitungan_akhir,
                   "cocok": hitungan_akhir == hitungan, "hilang": hilang, "disimpan": [str(j) for j in disimpan],
                   "sebelum_pulihkan": cadangan_sebelum["nama"] if cadangan_sebelum else None,
                   "sandi_baru_diatur": sandi_baru_diatur}
        audit.tulis(folder_cadangan, "Pulihkan", pelaku, "sukses",
                    f"{nama_zip}; {sum(hitungan_akhir.values())} baris; berkas hilang: {sum(hilang.values())}")
        return laporan
    except (GalatPulihkan, arsip.GalatArsip, arsip.GalatCadangan) as e:
        audit.tulis(folder_cadangan, "Pulihkan", pelaku, "gagal", f"{nama_zip}: {e}")
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        try:
            (instance / "pulihkan_tmp").rmdir()
        except OSError:
            pass
