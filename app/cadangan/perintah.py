"""Perintah terminal cadangan (cli_group "cadangan"). Dijalankan dari folder proyek, mis.:

    flask --app run cadangan buat [--jenis lengkap|database] [--ke FOLDER]
    flask --app run cadangan periksa <berkas.zip>
    flask --app run cadangan pulihkan <berkas.zip>
    flask --app run cadangan reset-sandi

Sandi cadangan dibaca dengan getpass (tidak tampil di layar), atau dari variabel lingkungan
SUPERAPP_SANDI_CADANGAN bila ada (untuk penjadwalan buat/periksa/pulihkan; TIDAK dipakai reset-sandi).
"""
import getpass
import os
from pathlib import Path

import click
from flask import current_app
from werkzeug.security import check_password_hash

from .. import log_proses
from ..db import ambil_db
from . import arsip, audit, basisdata, bp, pulihkan as pulihkan_mod, sandi as sandi_mod

VARIABEL_SANDI = "SUPERAPP_SANDI_CADANGAN"


def _folder():
    return Path(current_app.instance_path) / "cadangan"


def _baca_sandi(pesan="Kata sandi cadangan: "):
    return os.environ.get(VARIABEL_SANDI) or getpass.getpass(pesan)


def _gagal(pesan, aksi=None):
    if aksi:
        audit.tulis(_folder(), aksi, "terminal", "gagal", pesan)
    raise click.ClickException(pesan)


@bp.cli.command("buat")
@click.option("--jenis", type=click.Choice(["lengkap", "database"]), default="lengkap", show_default=True,
              help="lengkap = database + data/ + templat; database = database saja")
@click.option("--ke", "ke", type=click.Path(file_okay=False, path_type=Path), default=None,
              help="Folder tujuan (bawaan: instance/cadangan/berkas)")
def buat(jenis, ke):
    """Buat cadangan (tanpa batas 300 MB seperti di browser)."""
    if not sandi_mod.ada_sandi(_folder()):
        _gagal("Kata sandi cadangan belum dibuat. Buat lewat halaman Cadangan atau: flask --app run cadangan reset-sandi")
    sandi = _baca_sandi()
    if not sandi_mod.verifikasi(_folder(), sandi):
        _gagal("Kata sandi cadangan salah, atau akses sedang dikunci sementara.", "Buat cadangan")
    if ambil_db().execute("SELECT 1 FROM spt_batch WHERE status = 'proses' LIMIT 1").fetchone():
        _gagal("Ada batch Pemecah SPT yang masih diproses. Tunggu sampai selesai.", "Buat cadangan")
    try:
        hasil = arsip.buat_cadangan(instance=current_app.instance_path,
                                    folder_templat=current_app.config["FOLDER_TEMPLAT"],
                                    folder_tujuan=ke or (_folder() / "berkas"), folder_kerja=_folder(), jenis=jenis,
                                    sandi=sandi)
    except arsip.GalatCadangan as e:
        _gagal(str(e), "Buat cadangan")
    audit.tulis(_folder(), "Buat cadangan", "terminal", "sukses", hasil["nama"])
    log_proses.catat("cadangan", "Buat cadangan", detail=f"{hasil['nama']} (terminal)", lokasi=str(hasil["jalur"].parent))
    click.echo(f"Cadangan dibuat: {hasil['jalur']}")
    click.echo(f"Ukuran {hasil['ukuran'] / (1024 * 1024):.1f} MB, {hasil['jumlah_berkas']} berkas data.".replace(".", ",", 1))
    if hasil["dilewati"]:
        click.echo(f"Dilewati (jenis berkas tidak didukung/tautan): {len(hasil['dilewati'])} berkas.")


def _ringkas_manifest(manifest):
    click.echo(f"Dibuat  : {manifest.get('dibuat')}")
    click.echo(f"Jenis   : {arsip.JENIS.get(manifest['jenis'], manifest['jenis'])}")
    click.echo(f"Berkas  : {len(manifest['berkas']) - 1} berkas data + database")
    for tabel, jumlah in (manifest.get("hitungan") or {}).items():
        click.echo(f"  {tabel:<20}{jumlah:>8}")


@bp.cli.command("periksa")
@click.argument("berkas", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def periksa(berkas):
    """Periksa keutuhan & keaslian cadangan (tanda, struktur, hash, database) TANPA mengubah apa pun."""
    try:
        manifest = pulihkan_mod.periksa(berkas, _baca_sandi(), current_app.instance_path)
    except arsip.GalatArsip as e:
        _gagal(f"Cadangan TIDAK lolos pemeriksaan: {e}", "Periksa cadangan")
    audit.tulis(_folder(), "Periksa cadangan", "terminal", "sukses", berkas.name)
    click.echo("Cadangan lolos pemeriksaan (keaslian, keutuhan, dan database).")
    _ringkas_manifest(manifest)


@bp.cli.command("pulihkan")
@click.argument("berkas", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def pulihkan(berkas):
    """Pulihkan cadangan. Aplikasi WAJIB dimatikan dulu. Data sekarang dicadangkan otomatis lebih dulu."""
    try:
        laporan = pulihkan_mod.pulihkan(
            jalur_zip=berkas, instance=current_app.instance_path, folder_templat=current_app.config["FOLDER_TEMPLAT"],
            sandi=_baca_sandi(), tampil=click.echo,
            konfirmasi=lambda: click.prompt(f"\nKetik {pulihkan_mod.KATA_KONFIRMASI} untuk melanjutkan", default="",
                                            show_default=False))
    except (pulihkan_mod.GalatPulihkan, arsip.GalatArsip, arsip.GalatCadangan) as e:
        raise click.ClickException(str(e))
    log_proses.catat("cadangan", "Pulihkan", detail=f"{berkas.name} (terminal)")
    click.echo("\nPemulihan selesai.")
    click.echo("Jumlah data: " + ", ".join(f"{v} {basisdata.LABEL_TABEL.get(k, k)}"
                                           for k, v in laporan["hitungan"].items()))
    if laporan["sebelum_pulihkan"]:
        click.echo(f"Cadangan kondisi sebelumnya: instance/cadangan/berkas/{laporan['sebelum_pulihkan']}")
    if laporan["hilang"]:
        click.echo("Rekaman yang berkasnya tidak ada: " + ", ".join(f"{v} {k}" for k, v in laporan["hilang"].items()))
    for jalur in laporan["disimpan"]:
        click.echo(f"Disimpan (tidak dihapus otomatis): {jalur}")
    if laporan["sandi_baru_diatur"]:
        click.echo("Kata sandi cadangan di komputer ini diatur sama dengan kata sandi cadangan yang dipulihkan.")
    click.echo("Semua pengguna perlu masuk ulang. Nyalakan aplikasi seperti biasa.")


@bp.cli.command("reset-sandi")
def reset_sandi():
    """Atur ulang kata sandi cadangan (lupa sandi). Cadangan lama tetap memakai sandi lamanya."""
    baru = getpass.getpass("Kata sandi cadangan baru: ")
    konfirmasi = getpass.getpass("Ulangi kata sandi cadangan baru: ")
    try:
        sandi_mod.periksa_syarat(baru, konfirmasi)
    except sandi_mod.GalatSandi as e:
        _gagal(str(e))
    try:
        hash_masuk = [b[0] for b in ambil_db().execute("SELECT sandi_hash FROM pengguna")]
    except Exception:
        hash_masuk = []
    if any(check_password_hash(h, baru) for h in hash_masuk):
        _gagal("Gunakan kata sandi yang berbeda dari kata sandi masuk.")
    sandi_mod.atur_sandi(_folder(), baru)
    audit.tulis(_folder(), "Reset kata sandi cadangan", "terminal", "sukses")
    click.echo("Kata sandi cadangan diatur ulang. Cadangan lama tetap dipulihkan dengan kata sandi lamanya.")
