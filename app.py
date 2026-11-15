"""Arsip Berita + SPT — aplikasi lokal (placeholder).

Jalankan:  python app.py   lalu buka http://127.0.0.1:5000
"""
import threading
import webbrowser

from flask import Flask, render_template, send_file

import docx_export

app = Flask(__name__)

MENU = [
    ("beranda", "Beranda"),
    ("berita", "Arsip Berita"),
    ("spt", "SPT"),
    ("pegawai", "Pegawai"),
    ("pengaturan", "Pengaturan"),
]


@app.context_processor
def inject_menu():
    return {"menu": MENU}


@app.route("/")
def beranda():
    return render_template("beranda.html")


@app.route("/berita")
def berita():
    return render_template(
        "placeholder.html",
        judul="Arsip Berita",
        rencana=[
            "Input berita: tanggal, judul, kategori, lokasi, penulis, isi, tautan",
            "Unggah foto dokumentasi + keterangan",
            "Pencarian & filter periode/kategori",
            "Ekspor satu berita / rekap periode ke Word F4",
        ],
    )


@app.route("/spt")
def spt():
    return render_template(
        "placeholder.html",
        judul="Surat Perintah Tugas (SPT)",
        rencana=[
            "Nomor surat otomatis sesuai format",
            "Dasar, daftar pegawai yang ditugaskan, untuk, waktu & tempat",
            "Penandatangan (jabatan, nama, pangkat, NIP)",
            "Ekspor SPT ber-kop surat ke Word F4",
            "Tautkan SPT dengan berita liputan",
        ],
    )


@app.route("/pegawai")
def pegawai():
    return render_template(
        "placeholder.html",
        judul="Data Pegawai",
        rencana=["Master data nama, NIP, pangkat/golongan, jabatan"],
    )


@app.route("/pengaturan")
def pengaturan():
    return render_template(
        "placeholder.html",
        judul="Pengaturan",
        rencana=[
            "Kop surat: nama instansi, alamat, logo",
            "Penandatangan default, format nomor SPT, font",
            "Backup data (database + foto)",
        ],
    )


@app.route("/contoh-word")
def contoh_word():
    buf = docx_export.contoh_f4()
    return send_file(
        buf,
        as_attachment=True,
        download_name="contoh_F4.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


if __name__ == "__main__":
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
