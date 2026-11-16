"""Konversi .docx -> .pdf TANPA paket Python tambahan.

Urutan pengonversi:
    1. Windows dengan Microsoft Word terpasang -> PowerShell + COM (Word dibuka SEKALI untuk semua berkas)
    2. LibreOffice (`soffice --headless`) -> Linux/Ubuntu, atau Windows tanpa Word
Bila tidak ada keduanya, konversi dilewati dan pemanggil tetap memakai hasil Word.
"""
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

PESAN_TIDAK_ADA = ("PDF tidak dibuat karena Microsoft Word maupun LibreOffice tidak ditemukan. "
                   "Pasang LibreOffice (Ubuntu: sudo apt install libreoffice-writer) atau Microsoft Word, "
                   "lalu proses ulang berkas ini.")

# Skrip PowerShell: buka Word sekali, konversi semua berkas dalam daftar, lalu tutup di blok finally.
# Daftar berkas dikirim lewat file teks UTF-8 (satu baris: jalur_docx<TAB>jalur_pdf) agar aman
# terhadap spasi, tanda kutip, dan huruf non-ASCII.
SKRIP_WORD = r"""
param([Parameter(Mandatory=$true)][string]$Daftar)
$ErrorActionPreference = 'Stop'
$word = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    foreach ($baris in [System.IO.File]::ReadAllLines($Daftar, [System.Text.Encoding]::UTF8)) {
        if (-not $baris) { continue }
        $bagian = $baris -split "`t"
        $doc = $null
        try {
            $doc = $word.Documents.Open($bagian[0], $false, $true)
            $doc.ExportAsFixedFormat($bagian[1], 17)
        } catch {
            Write-Output ("GAGAL`t" + $bagian[0] + "`t" + $_.Exception.Message)
        } finally {
            if ($doc -ne $null) {
                $doc.Close(0) | Out-Null
                [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc)
            }
        }
    }
} finally {
    if ($word -ne $null) {
        $word.Quit(0) | Out-Null
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
"""

LOKASI_SOFFICE = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
    "/opt/libreoffice/program/soffice",
    "/snap/bin/libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


@dataclass
class HasilKonversi:
    pengonversi: str | None   # "Microsoft Word" | "LibreOffice" | None
    galat: str | None         # pesan untuk pengguna bila ada masalah


def _batas_waktu(jumlah):
    return 90 + 30 * jumlah


def word_tersedia():
    """True bila Windows dan Microsoft Word terdaftar sebagai objek COM."""
    if os.name != "nt" or not shutil.which("powershell"):
        return False
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"))
        return True
    except OSError:
        return False


def cari_soffice():
    for nama in ("soffice", "libreoffice"):
        jalur = shutil.which(nama)
        if jalur:
            return Path(jalur)
    for jalur in LOKASI_SOFFICE:
        if Path(jalur).is_file():
            return Path(jalur)
    return None


def pengonversi_tersedia():
    if word_tersedia():
        return "Microsoft Word"
    if cari_soffice():
        return "LibreOffice"
    return None


def _jalankan(argumen, batas_waktu, pantau=None):
    """Jalankan program luar dan tunggu selesai. Selama menunggu, `pantau()` dipanggil tiap 0,5 detik
    (dipakai untuk melaporkan progres). Melempar subprocess.TimeoutExpired bila melewati batas waktu."""
    proses = subprocess.Popen(argumen, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mulai = time.monotonic()
    while True:
        try:
            proses.wait(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            if pantau:
                pantau()
            if time.monotonic() - mulai > batas_waktu:
                proses.kill()
                proses.wait()
                raise
    if pantau:
        pantau()


def _konversi_word(daftar, folder_kerja, pantau):
    berkas_daftar = folder_kerja / "daftar.txt"
    berkas_daftar.write_text(
        "\n".join(f"{d.resolve()}\t{d.with_suffix('.pdf').resolve()}" for d in daftar), encoding="utf-8")
    berkas_skrip = folder_kerja / "konversi.ps1"
    berkas_skrip.write_text(SKRIP_WORD, encoding="utf-8-sig")
    _jalankan(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-File", str(berkas_skrip), "-Daftar", str(berkas_daftar)],
              _batas_waktu(len(daftar)), pantau)


def _konversi_soffice(soffice, daftar, folder_keluar, folder_kerja, pantau):
    profil = folder_kerja / "profil"  # profil terpisah agar tidak bentrok dengan LibreOffice yang sedang dibuka
    _jalankan([str(soffice), f"-env:UserInstallation={profil.resolve().as_uri()}",
               "--headless", "--norestore", "--convert-to", "pdf", "--outdir", str(folder_keluar),
               *[str(d) for d in daftar]],
              _batas_waktu(len(daftar)), pantau)


def konversi_ke_pdf(daftar_docx, folder_keluar, saat_progres=None):
    """Konversi semua berkas sekaligus. PDF ditulis di folder_keluar dengan nama yang sama.
    Keberhasilan per berkas diperiksa pemanggil lewat keberadaan berkas .pdf.
    saat_progres(jumlah_pdf_jadi, nama_pengonversi) dipanggil berkala selama konversi berjalan."""
    daftar = [Path(d) for d in daftar_docx]
    if not daftar:
        return HasilKonversi(None, None)
    folder_keluar = Path(folder_keluar)

    def belum():
        return [d for d in daftar if not (folder_keluar / f"{d.stem}.pdf").exists()]

    def pantau_dengan(nama):
        if saat_progres is None:
            return None
        return lambda: saat_progres(len(daftar) - len(belum()), nama)

    dipakai, galat = None, None
    with tempfile.TemporaryDirectory(prefix="superapp-pdf-") as tmp:
        kerja = Path(tmp)
        if word_tersedia():
            dipakai = "Microsoft Word"
            try:
                _konversi_word(daftar, kerja, pantau_dengan("Microsoft Word"))
            except subprocess.TimeoutExpired:
                galat = "Waktu konversi PDF lewat Microsoft Word habis."
            except OSError as e:
                galat = f"Microsoft Word tidak dapat dijalankan ({e})."
        soffice = cari_soffice()
        if belum() and soffice:   # tanpa Word, atau Word gagal untuk sebagian berkas
            dipakai = "LibreOffice" if dipakai is None else f"{dipakai} + LibreOffice"
            try:
                _konversi_soffice(soffice, belum(), folder_keluar, kerja, pantau_dengan("LibreOffice"))
                galat = None
            except subprocess.TimeoutExpired:
                galat = "Waktu konversi PDF lewat LibreOffice habis."
            except OSError as e:
                galat = f"LibreOffice tidak dapat dijalankan ({e})."

    if dipakai is None:
        return HasilKonversi(None, PESAN_TIDAK_ADA)
    if belum() and not galat:
        galat = f"Sebagian PDF gagal dibuat oleh {dipakai}."
    return HasilKonversi(dipakai, galat)
