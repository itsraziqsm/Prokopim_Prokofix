"""Titik masuk aplikasi.

Cara menjalankan (dari folder proyek):
    python run.py            -> otomatis memilih port yang bisa dipakai
    python run.py 8080       -> memakai port tertentu
Alamat yang dipakai akan dicetak di terminal, buka alamat itu di browser.
"""
import os
import socket
import sys

from app import create_app

HOST = "127.0.0.1"  # hanya bisa diakses dari komputer ini (aman, lokal)

# Port yang dicoba berurutan. Di Windows, port tertentu (sering 5000) bisa
# dicadangkan oleh Hyper-V/WSL/Docker sehingga muncul error
# "An attempt was made to access a socket in a way forbidden by its access permissions".
PORT_CADANGAN = [5000, 8000, 8080, 8765, 5050, 3000]


def port_bisa_dipakai(port):
    """Coba 'pinjam' port sebentar. True jika berhasil (port bebas & diizinkan)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Samakan dengan server Flask: di Linux/macOS port yang baru saja ditutup (TIME_WAIT)
        # tetap boleh dipakai. Tidak dipasang di Windows karena artinya berbeda di sana.
        if os.name != "nt":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, port))
            return True
        except OSError:
            return False


def pilih_port():
    # Mode debug menjalankan ulang skrip ini di proses kedua; proses itu
    # memakai port yang sudah dipilih proses pertama (disimpan di variabel lingkungan).
    if os.environ.get("SUPERAPP_PORT"):
        return int(os.environ["SUPERAPP_PORT"])

    # Port yang diminta pengguna: python run.py 8080
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
        if not port_bisa_dipakai(port):
            sys.exit(f"Port {port} tidak bisa dipakai. Coba port lain, misalnya: python run.py 8080")
        return port

    for port in PORT_CADANGAN:
        if port_bisa_dipakai(port):
            return port

    # Semua gagal: biarkan sistem operasi memilih port kosong apa saja
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


# Membuat objek aplikasi Flask lewat "app factory" (lihat app/__init__.py)
app = create_app()

if __name__ == "__main__":
    port = pilih_port()
    os.environ["SUPERAPP_PORT"] = str(port)

    # Cetak alamat sekali saja (bukan di proses kedua mode debug)
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        print(f"\n  Super App Prokopim berjalan di:  http://{HOST}:{port}\n  Tekan Ctrl+C untuk berhenti.\n")

    # debug=True = server otomatis memuat ulang saat kode diubah (khusus pengembangan)
    app.run(host=HOST, port=port, debug=True)
