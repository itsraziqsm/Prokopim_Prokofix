"""Daftar modul (fitur) aplikasi — SATU-SATUNYA tempat mendaftarkan modul.

Untuk menambah modul baru, cukup tambahkan satu dict ke dalam list MODUL di bawah.
Dashboard dan halaman "Under Development" akan otomatis menampilkannya.

Keterangan kolom:
    id         : kode unik (huruf kecil, tanda hubung/garis bawah). Juga dipakai di catat(id, ...).
    nama       : nama modul yang tampil di layar.
    deskripsi  : satu kalimat singkat untuk kartu di dashboard.
    tujuan     : paragraf singkat di halaman detail modul.
    ikon       : nama ikon SVG (lihat app/templates/komponen/ikon.html).
    status     : "siap" atau "pengembangan".
    url        : alamat tujuan bila status "siap"; None = pakai halaman /modul/<id>.
    urutan     : urutan pengerjaan (1 = dikerjakan pertama).
    rencana    : daftar rencana fitur (3-5 butir).
"""

NAMA_APLIKASI = "Super App Kerja"

# Label lencana untuk tiap status
STATUS_LABEL = {
    "siap": "Siap",
    "pengembangan": "Dalam pengembangan",
}

MODUL = [
    {
        "id": "pemecah_spt",
        "nama": "Pemecah SPT",
        "deskripsi": "Memecah satu file Word berisi banyak SPT menjadi satu file per SPT.",
        "tujuan": (
            "Satu dokumen Word yang memuat banyak Surat Perintah Tugas dipecah menjadi "
            "satu berkas per SPT, diberi nama sesuai nomor suratnya, dalam format Word, PDF, atau keduanya."
        ),
        "ikon": "dokumen-pecah",
        "status": "siap",
        "url": "/spt",
        "urutan": 1,
        "rencana": [
            "Deteksi judul SPT bercetak tebal dan bergaris bawah",
            "Pratinjau dan pilih SPT sebelum diproses",
            "Penamaan berkas dari nomor SPT",
            "Keluaran Word dan/atau PDF, unduh per berkas atau ZIP",
        ],
    },
    {
        "id": "arsip_liputan",
        "nama": "Arsip Liputan",
        "deskripsi": "Arsip liputan kegiatan resmi: berita dan foto, diekspor ke Word F4 untuk dicetak.",
        "tujuan": (
            "Menyimpan data kegiatan, isi berita, dan foto dokumentasi dari medsos atau web, lalu membuat "
            "satu berkas Word F4 berisi berita diikuti lembar foto bergaris potong."
        ),
        "ikon": "kamera",
        "status": "siap",
        "url": "/liputan",
        "urutan": 2,
        "rencana": [
            "Data kegiatan, isi berita, dan SPT terkait",
            "Foto dengan keterangan & sumber; unggah, seret, atau tempel",
            "Ekspor Word F4: berita lalu lembar foto untuk digunting",
            "Paket ZIP berisi Word dan SPT",
        ],
    },
]


def semua_modul():
    """Mengembalikan semua modul, diurutkan berdasarkan kolom 'urutan'."""
    return sorted(MODUL, key=lambda m: m["urutan"])


def cari_modul(modul_id):
    """Mencari modul berdasarkan id. Mengembalikan None jika tidak ada."""
    return next((m for m in MODUL if m["id"] == modul_id), None)
