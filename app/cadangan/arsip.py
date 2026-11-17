"""Berkas ZIP cadangan — logika murni tanpa Flask (dipakai web & terminal).

Struktur ZIP (daftar putih):
    manifest.json                ringkasan + daftar berkas (ukuran, SHA-256) + parameter KDF + tanda HMAC
    database/superapp.db         salinan konsisten database (jalur absolut sudah dibuat relatif)
    data/...                     isi instance/data/ (hanya jenis "lengkap" dan "sebelum-pulihkan")
    templat_docx/<nama>.docx     templat Word (hanya jenis "lengkap" dan "sebelum-pulihkan")
TIDAK PERNAH disertakan: instance/secret_key, instance/tmp/, instance/cadangan/, instance/pulihkan_tmp/, berkas .lama*.

Tanda = HMAC-SHA256(manifest kanonik tanpa field "tanda"), kunci = scrypt(sandi cadangan, salt di manifest).
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import stat
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import basisdata
from .sandi import PARAMETER_KDF, tulis_atomik, turunkan_kunci

VERSI_FORMAT = 1
JENIS = {"lengkap": "Semua data dan hasil", "database": "Database saja", "sebelum-pulihkan": "Sebelum pemulihan"}
JENIS_DENGAN_DATA = {"lengkap", "sebelum-pulihkan"}
EKSTENSI_DATA = {".pdf", ".docx", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".json"}
POLA_NAMA = re.compile(r"cadangan-(lengkap|database|sebelum-pulihkan)-\d{4}-\d{2}-\d{2}-\d{4}(-\d{1,3})?\.zip")
JALUR_DB = "database/superapp.db"

# Batas saat MEMERIKSA/membongkar (cegah zip bomb)
MAKS_ENTRI = 50_000
MAKS_TOTAL_BYTE = 20 * 1024 ** 3          # total setelah dibongkar
MAKS_RASIO = 200                          # ukuran asli / ukuran terkompresi, untuk entri > 1 MB
MAKS_MANIFEST_BYTE = 20 * 1024 * 1024
POTONGAN = 1024 * 1024


class GalatCadangan(Exception):
    """Cadangan tidak bisa dibuat; pesan aman untuk pengguna."""


class GalatArsip(Exception):
    """ZIP cadangan ditolak saat diperiksa; pesan aman untuk pengguna (tanpa membocorkan detail rahasia)."""


# ---------- Nama & pendamping ----------
def nama_sah(nama):
    return bool(POLA_NAMA.fullmatch(nama or ""))


def nama_baru(folder, jenis, sekarang=None):
    """cadangan-<jenis>-YYYY-MM-DD-HHMM[-n].zip yang belum ada di folder (nama dibuat sistem, bukan dari pengguna)."""
    sekarang = sekarang or datetime.now()
    dasar = f"cadangan-{jenis}-{sekarang:%Y-%m-%d-%H%M}"
    nama, n = f"{dasar}.zip", 2
    while (Path(folder) / nama).exists() or (Path(folder) / nama).with_suffix(".json").exists():
        nama, n = f"{dasar}-{n}.zip", n + 1
    return nama


def jalur_pendamping(jalur_zip):
    return Path(jalur_zip).with_suffix(".json")


def baca_pendamping(jalur_zip):
    try:
        return json.loads(jalur_pendamping(jalur_zip).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def daftar_cadangan(folder):
    """Semua ZIP bernama sah di folder, terbaru di atas, beserta ringkasan dari berkas pendampingnya."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    hasil = []
    for jalur in folder.iterdir():
        if not nama_sah(jalur.name) or not jalur.is_file() or jalur.is_symlink():
            continue
        info = baca_pendamping(jalur)
        info.update(nama=jalur.name, ukuran=jalur.stat().st_size,
                    jenis=info.get("jenis") or POLA_NAMA.fullmatch(jalur.name).group(1))
        info.setdefault("dibuat_lokal", datetime.fromtimestamp(jalur.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"))
        hasil.append(info)
    return sorted(hasil, key=lambda i: (i["dibuat_lokal"], i["nama"]), reverse=True)


def cadangan_terakhir(folder):
    """Waktu (datetime) cadangan terbaru di folder, atau None."""
    daftar = daftar_cadangan(folder)
    if not daftar:
        return None
    try:
        return datetime.strptime(daftar[0]["dibuat_lokal"], "%Y-%m-%d %H:%M:%S")
    except (KeyError, ValueError):
        return None


# ---------- Validasi nama entri ----------
def jalur_entri_aman(nama):
    """True bila nama entri ZIP aman dan termasuk daftar putih struktur cadangan."""
    if not isinstance(nama, str) or not nama or "\x00" in nama or "\\" in nama:
        return False
    if nama.startswith("/") or re.match(r"^[A-Za-z]:", nama) or any(ord(h) < 32 for h in nama):
        return False
    bagian = nama.split("/")
    if any(b in ("", ".", "..") for b in bagian):
        return False
    if nama in ("manifest.json", JALUR_DB):
        return True
    akhiran = Path(bagian[-1]).suffix.lower()
    if bagian[0] == "data" and len(bagian) >= 2:
        return akhiran in EKSTENSI_DATA
    if bagian[0] == "templat_docx" and len(bagian) == 2:
        return akhiran == ".docx"
    return False


# ---------- Pengumpulan berkas ----------
def _dikecualikan(nama):
    return ".lama" in nama


def daftar_berkas(instance, folder_templat, jenis):
    """([(jalur_dalam_zip, Path)], [jalur dilewati]) sesuai jenis. Symlink, berkas .lama*, dan ekstensi di luar
    daftar putih dilewati (agar cadangan sendiri selalu lolos pemeriksaan saat dipulihkan)."""
    berkas, dilewati = [], []
    if jenis not in JENIS_DENGAN_DATA:
        return berkas, dilewati
    akar_data = Path(instance) / "data"
    if akar_data.is_dir() and not akar_data.is_symlink():
        for akar, folder_anak, nama_berkas in os.walk(akar_data, followlinks=False):
            folder_anak[:] = sorted(f for f in folder_anak if not _dikecualikan(f)
                                    and not (Path(akar) / f).is_symlink())
            for nama in sorted(nama_berkas):
                jalur = Path(akar) / nama
                relatif = "data/" + jalur.relative_to(akar_data).as_posix()
                if _dikecualikan(nama) or jalur.is_symlink() or not jalur.is_file() or not jalur_entri_aman(relatif):
                    dilewati.append(relatif)
                    continue
                berkas.append((relatif, jalur))
    templat = Path(folder_templat)
    if templat.is_dir():
        for jalur in sorted(templat.glob("*.docx")):
            relatif = f"templat_docx/{jalur.name}"
            if _dikecualikan(jalur.name) or jalur.is_symlink() or not jalur.is_file() or not jalur_entri_aman(relatif):
                dilewati.append(relatif)
                continue
            berkas.append((relatif, jalur))
    return berkas, dilewati


def perkiraan_ukuran(instance, folder_templat, jenis):
    berkas, _ = daftar_berkas(instance, folder_templat, jenis)
    db = Path(instance) / "superapp.db"
    return (db.stat().st_size if db.is_file() else 0) + sum(j.stat().st_size for _, j in berkas)


# ---------- Manifest & tanda ----------
def manifest_kanonik(manifest):
    isi = {k: v for k, v in manifest.items() if k != "tanda"}
    return json.dumps(isi, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _parameter_kdf_aman(kdf):
    """Parameter KDF dari manifest dibatasi agar ZIP palsu tidak bisa membuat scrypt memakan memori/CPU besar."""
    try:
        n, r, p, dklen = int(kdf["n"]), int(kdf["r"]), int(kdf["p"]), int(kdf["dklen"])
        salt = base64.b64decode(kdf["salt"].encode("ascii"), validate=True)
    except (KeyError, ValueError, TypeError, AttributeError):
        raise GalatArsip("Manifest cadangan tidak sah.")
    if kdf.get("algoritma") != "scrypt" or not (2 ** 10 <= n <= 2 ** 16 and n & (n - 1) == 0) \
            or not (1 <= r <= 16) or not (1 <= p <= 4) or dklen != 32 or not (16 <= len(salt) <= 64):
        raise GalatArsip("Manifest cadangan tidak sah.")
    return salt, n, r, p, dklen


def hitung_tanda(manifest, sandi):
    salt, n, r, p, dklen = _parameter_kdf_aman(manifest.get("kdf") or {})
    kunci = turunkan_kunci(sandi, salt, n, r, p, dklen)
    return hmac.new(kunci, manifest_kanonik(manifest), hashlib.sha256).hexdigest()


def verifikasi_tanda(manifest, sandi):
    """Melempar GalatArsip bila tanda tidak cocok (sandi salah ATAU isi manifest diubah; tidak dibedakan)."""
    tanda = manifest.get("tanda")
    if not isinstance(tanda, str) or not hmac.compare_digest(hitung_tanda(manifest, sandi), tanda):
        raise GalatArsip("Kata sandi cadangan salah atau berkas cadangan telah diubah.")


# ---------- Kunci proses ----------
@contextmanager
def kunci_berkas(jalur, pesan, kedaluwarsa=3 * 3600):
    """Kunci sederhana berbasis berkas (O_EXCL) agar hanya satu proses berjalan. Kunci basi (> 3 jam) dilepas."""
    jalur = Path(jalur)
    jalur.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(jalur, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            try:
                basi = time.time() - jalur.stat().st_mtime > kedaluwarsa
            except OSError:
                basi = True
            if not basi:
                raise GalatCadangan(pesan)
            jalur.unlink(missing_ok=True)
    else:
        raise GalatCadangan(pesan)
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        jalur.unlink(missing_ok=True)


# ---------- Pembuatan ----------
def fsync_berkas(jalur):
    """Paksa isi berkas benar-benar tertulis ke disk sebelum dipindah/dipasang.
    Berkas WAJIB dibuka dengan izin tulis: di Windows os.fsync pada berkas baca-saja gagal (Errno 9)."""
    with open(jalur, "r+b") as f:
        os.fsync(f.fileno())



def _tulis_entri(zf, nama, sumber, kompres=True):
    """Salin berkas ke ZIP sedikit demi sedikit sambil menghitung SHA-256 & ukuran.
    Database disimpan TANPA kompresi: database SQLite yang hampir kosong bisa terkompresi ratusan kali dan
    akan ditolak pemeriksaan rasio (anti zip bomb) saat dipulihkan."""
    h, ukuran = hashlib.sha256(), 0
    besar = Path(sumber).stat().st_size > 2 ** 31
    info = zipfile.ZipInfo(nama, date_time=time.localtime()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED if kompres else zipfile.ZIP_STORED
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    with open(sumber, "rb") as masuk, zf.open(info, "w", force_zip64=besar) as keluar:
        while True:
            potongan = masuk.read(POTONGAN)
            if not potongan:
                break
            h.update(potongan)
            ukuran += len(potongan)
            keluar.write(potongan)
    return {"jalur": nama, "ukuran": ukuran, "sha256": h.hexdigest()}


def buat_cadangan(*, instance, folder_templat, folder_tujuan, folder_kerja, jenis, sandi, batas_byte=None,
                  sekarang=None):
    """Buat ZIP cadangan bertanda tangan. Mengembalikan dict ringkasan (nama, jalur, ukuran, hitungan, ...).

    ZIP ditulis bertahap ke berkas .sementara lalu dipindah (atomik). Satu pembuatan dalam satu waktu (kunci berkas).
    Melempar GalatCadangan bila melebihi batas_byte, ruang disk kurang, atau pembuatan lain sedang berjalan."""
    if jenis not in JENIS:
        raise GalatCadangan("Jenis cadangan tidak dikenal.")
    instance, folder_tujuan, folder_kerja = Path(instance), Path(folder_tujuan), Path(folder_kerja)
    db_hidup = instance / "superapp.db"
    if not db_hidup.is_file():
        raise GalatCadangan("Database aplikasi belum ada.")
    folder_tujuan.mkdir(parents=True, exist_ok=True)
    berkas, dilewati = daftar_berkas(instance, folder_templat, jenis)
    perkiraan = db_hidup.stat().st_size + sum(j.stat().st_size for _, j in berkas)
    if batas_byte is not None and perkiraan > batas_byte:
        raise GalatCadangan(f"Perkiraan ukuran cadangan ({perkiraan // (1024 * 1024)} MB) melebihi batas "
                            f"{batas_byte // (1024 * 1024)} MB untuk pembuatan lewat browser. Buat lewat terminal: "
                            f"flask --app run cadangan buat")
    if shutil.disk_usage(folder_tujuan).free < perkiraan * 1.2:
        raise GalatCadangan("Ruang disk tidak cukup untuk membuat cadangan.")

    with kunci_berkas(folder_kerja / "buat.kunci", "Pembuatan cadangan lain sedang berjalan. Tunggu sampai selesai."):
        sekarang = sekarang or datetime.now()
        kerja = folder_kerja / f"buat-{secrets.token_hex(6)}"
        kerja.mkdir(parents=True)
        nama = nama_baru(folder_tujuan, jenis, sekarang)
        sementara = folder_tujuan / f".{nama}.sementara"
        try:
            snapshot = kerja / "superapp.db"
            basisdata.salin_snapshot(db_hidup, snapshot, [str(instance), str(instance.resolve())])
            koneksi = basisdata.buka_baca_saja(snapshot)
            try:
                hitungan, skema = basisdata.hitung_baris(koneksi), basisdata.ringkas_skema(koneksi)
            finally:
                koneksi.close()
            salt = secrets.token_bytes(16)
            daftar = []
            with zipfile.ZipFile(sementara, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                daftar.append(_tulis_entri(zf, JALUR_DB, snapshot, kompres=False))
                for relatif, jalur in berkas:
                    try:
                        daftar.append(_tulis_entri(zf, relatif, jalur))
                    except FileNotFoundError:        # terhapus saat cadangan dibuat
                        dilewati.append(relatif)
                manifest = {
                    "versi_format": VERSI_FORMAT, "aplikasi": "Super App Prokopim",
                    "dibuat": sekarang.astimezone().isoformat(timespec="seconds"), "jenis": jenis,
                    "skema": skema, "hitungan": hitungan, "berkas": daftar,
                    "kdf": {"algoritma": "scrypt", "salt": base64.b64encode(salt).decode("ascii"), **PARAMETER_KDF},
                }
                manifest["tanda"] = hitung_tanda(manifest, sandi)
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
            fsync_berkas(sementara)
            jalur_zip = folder_tujuan / nama
            os.replace(sementara, jalur_zip)
        except BaseException:
            sementara.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(kerja, ignore_errors=True)
    ringkas = {"nama": nama, "jenis": jenis, "dibuat": manifest["dibuat"],
               "dibuat_lokal": sekarang.strftime("%Y-%m-%d %H:%M:%S"), "ukuran": jalur_zip.stat().st_size,
               "hitungan": hitungan, "jumlah_berkas": len(daftar) - 1, "dilewati": dilewati[:50], "uji": None}
    tulis_atomik(jalur_pendamping(jalur_zip), ringkas)
    return {**ringkas, "jalur": jalur_zip}


# ---------- Pemeriksaan ----------
def baca_manifest(zf):
    """Manifest dari ZIP yang sudah dibuka. Melempar GalatArsip bila tidak ada, terlalu besar, atau bentuknya salah."""
    entri = [i for i in zf.infolist() if i.filename == "manifest.json"]
    if len(entri) != 1 or entri[0].file_size > MAKS_MANIFEST_BYTE:
        raise GalatArsip("Berkas ini bukan cadangan Super App Prokopim yang sah.")
    try:
        with zf.open(entri[0]) as f:
            manifest = json.loads(f.read(MAKS_MANIFEST_BYTE + 1).decode("utf-8"))
    except (ValueError, zipfile.BadZipFile, OSError, EOFError):
        raise GalatArsip("Manifest cadangan tidak dapat dibaca.")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("berkas"), list) \
            or not isinstance(manifest.get("versi_format"), int) or manifest.get("jenis") not in JENIS:
        raise GalatArsip("Manifest cadangan tidak sah.")
    if manifest["versi_format"] > VERSI_FORMAT:
        raise GalatArsip("Cadangan ini dibuat oleh versi aplikasi yang lebih baru. Perbarui aplikasi dulu.")
    return manifest


def periksa_struktur(zf, manifest):
    """Cek setiap entri ZIP terhadap daftar putih & manifest TANPA membongkar. Mengembalikan {nama: ZipInfo}."""
    entri = zf.infolist()
    if len(entri) > MAKS_ENTRI:
        raise GalatArsip("Cadangan berisi terlalu banyak berkas.")
    terdaftar = {}
    for b in manifest["berkas"]:
        if not isinstance(b, dict) or not jalur_entri_aman(b.get("jalur")) or b.get("jalur") == "manifest.json" \
                or not isinstance(b.get("ukuran"), int) or b["ukuran"] < 0 \
                or not re.fullmatch(r"[0-9a-f]{64}", str(b.get("sha256", ""))):
            raise GalatArsip("Manifest cadangan berisi daftar berkas yang tidak sah.")
        if b["jalur"].casefold() in terdaftar:
            raise GalatArsip("Manifest cadangan berisi nama berkas ganda.")
        terdaftar[b["jalur"].casefold()] = b
    if JALUR_DB.casefold() not in terdaftar:
        raise GalatArsip("Cadangan tidak berisi database.")
    if manifest["jenis"] not in JENIS_DENGAN_DATA and any(k != JALUR_DB for k in terdaftar):
        raise GalatArsip("Cadangan jenis \"Database saja\" tidak boleh berisi berkas data.")

    dilihat, peta, total = set(), {}, 0
    for info in entri:
        nama = info.filename
        if not jalur_entri_aman(nama) or info.is_dir():
            raise GalatArsip(f"Cadangan berisi berkas dengan jalur yang tidak diizinkan ({nama[:80]!r}).")
        kunci = nama.casefold()
        if kunci in dilihat:
            raise GalatArsip(f"Cadangan berisi nama berkas ganda ({nama[:80]}).")
        dilihat.add(kunci)
        jenis_berkas = stat.S_IFMT(info.external_attr >> 16)    # 0 = tidak dicatat (mis. dibuat di Windows)
        if jenis_berkas and jenis_berkas != stat.S_IFREG:
            raise GalatArsip(f"Cadangan berisi tautan atau berkas khusus ({nama[:80]}).")
        if info.flag_bits & 0x1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise GalatArsip(f"Cadangan berisi berkas terenkripsi atau berformat tidak dikenal ({nama[:80]}).")
        if info.file_size > 1024 * 1024 and info.file_size > MAKS_RASIO * max(info.compress_size, 1):
            raise GalatArsip(f"Rasio kompresi berkas tidak wajar ({nama[:80]}).")
        total += info.file_size
        if total > MAKS_TOTAL_BYTE:
            raise GalatArsip("Ukuran isi cadangan setelah dibongkar melebihi batas.")
        if nama == "manifest.json":
            continue
        b = terdaftar.get(kunci)
        if b is None or b["jalur"] != nama:
            raise GalatArsip(f"Cadangan berisi berkas yang tidak terdaftar di manifest ({nama[:80]}).")
        if info.file_size != b["ukuran"]:
            raise GalatArsip(f"Ukuran berkas tidak cocok dengan manifest ({nama[:80]}).")
        peta[nama] = info
    hilang = [b["jalur"] for b in manifest["berkas"] if b["jalur"] not in peta]
    if hilang:
        raise GalatArsip(f"Berkas yang terdaftar di manifest tidak ada di cadangan ({hilang[0][:80]}).")
    return peta


def periksa_isi(zf, manifest, peta, folder_bongkar=None, hanya_db=False):
    """Baca tiap entri bertahap, cocokkan ukuran & SHA-256 dengan manifest. Bila folder_bongkar diberikan, isi ditulis
    ke jalur yang DIHITUNG SENDIRI di dalam folder itu (bukan extractall). hanya_db=True: hanya database ditulis."""
    if folder_bongkar is not None:
        folder_bongkar = Path(folder_bongkar).resolve()
    for b in manifest["berkas"]:
        info = peta[b["jalur"]]
        tujuan = None
        if folder_bongkar is not None and (not hanya_db or b["jalur"] == JALUR_DB):
            tujuan = (folder_bongkar / Path(*b["jalur"].split("/"))).resolve()
            if not tujuan.is_relative_to(folder_bongkar) or tujuan == folder_bongkar:
                raise GalatArsip("Jalur berkas cadangan keluar dari folder pembongkaran.")
            tujuan.parent.mkdir(parents=True, exist_ok=True)
        h, ukuran = hashlib.sha256(), 0
        try:
            keluar = open(tujuan, "xb") if tujuan else None
            try:
                with zf.open(info) as masuk:
                    while True:
                        potongan = masuk.read(POTONGAN)
                        if not potongan:
                            break
                        ukuran += len(potongan)
                        if ukuran > b["ukuran"]:
                            raise GalatArsip(f"Isi berkas lebih besar dari yang tercatat ({b['jalur'][:80]}).")
                        h.update(potongan)
                        if keluar:
                            keluar.write(potongan)
            finally:
                if keluar:
                    keluar.close()
        except GalatArsip:
            raise
        except FileExistsError:
            raise GalatArsip(f"Cadangan berisi nama berkas ganda ({b['jalur'][:80]}).")
        except (zipfile.BadZipFile, OSError, EOFError, ValueError) as e:
            raise GalatArsip(f"Berkas cadangan rusak ({b['jalur'][:80]}).") from e
        if ukuran != b["ukuran"] or not hmac.compare_digest(h.hexdigest(), b["sha256"]):
            raise GalatArsip(f"Isi berkas tidak cocok dengan manifest ({b['jalur'][:80]}).")


def buka_zip(jalur):
    try:
        return zipfile.ZipFile(jalur)
    except (zipfile.BadZipFile, OSError, EOFError):
        raise GalatArsip("Berkas bukan ZIP yang sah atau rusak.")


def uji_keutuhan(jalur_zip, folder_kerja):
    """Uji keutuhan TANPA sandi (untuk tombol "Uji" di web): ZIP terbaca, struktur sesuai daftar putih, ukuran &
    SHA-256 cocok dengan manifest, database lolos integrity_check. Keaslian (tanda) diperiksa saat pemulihan.
    Mengembalikan manifest; melempar GalatArsip bila gagal."""
    kerja = Path(folder_kerja) / f"uji-{secrets.token_hex(6)}"
    kerja.mkdir(parents=True)
    try:
        with buka_zip(jalur_zip) as zf:
            manifest = baca_manifest(zf)
            peta = periksa_struktur(zf, manifest)
            periksa_isi(zf, manifest, peta, folder_bongkar=kerja, hanya_db=True)
        try:
            utuh = basisdata.integritas_ok(kerja / "database" / "superapp.db")
        except Exception:
            utuh = False
        if not utuh:
            raise GalatArsip("Database di dalam cadangan rusak (integrity_check gagal).")
        return manifest
    finally:
        shutil.rmtree(kerja, ignore_errors=True)


def simpan_hasil_uji(jalur_zip, berhasil, pesan):
    info = baca_pendamping(jalur_zip)
    info["uji"] = {"waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "berhasil": bool(berhasil),
                   "pesan": str(pesan)[:300]}
    tulis_atomik(jalur_pendamping(jalur_zip), info)
