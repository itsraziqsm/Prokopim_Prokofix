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
    induk      : id modul induk, atau None untuk modul tingkat atas. Modul yang PUNYA anak (mis. "Data Podcast")
                 tidak tampil sebagai kartu, melainkan sebagai JUDUL KELOMPOK di halaman Alat; kartu anak-anaknya
                 (mis. "Materi Podcast") tampil di bawah judul itu. Fitur anak baru cukup diberi induk yang sama.
"""

NAMA_APLIKASI = "Super App Prokopim"

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
        "induk": None,
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
        "induk": None,
        "rencana": [
            "Data kegiatan, isi berita, dan SPT terkait",
            "Foto dengan keterangan & sumber; unggah, seret, atau tempel",
            "Ekspor Word F4: berita lalu lembar foto untuk digunting",
            "Paket ZIP berisi Word dan SPT",
        ],
    },
    {
        "id": "data_podcast",
        "nama": "Data Podcast",
        "deskripsi": "Kumpulan alat persiapan podcast: materi pertanyaan dan jawaban per instansi.",
        "tujuan": "Induk untuk fitur-fitur persiapan podcast. Setiap fitur anak tampil sebagai kartu di halamannya.",
        "ikon": "mikrofon",
        "status": "siap",
        "url": "/podcast",
        "urutan": 3,
        "induk": None,
        "rencana": [
            "Materi Podcast: pertanyaan & jawaban per instansi",
            "Fitur persiapan podcast lainnya menyusul",
        ],
    },
    {
        "id": "materi_podcast",
        "nama": "Materi Podcast",
        "deskripsi": "Pertanyaan untuk tiap instansi beserta jawabannya per tema podcast; mode baca dan ekspor Word.",
        "tujuan": (
            "Menyimpan pertanyaan yang diajukan ke tiap instansi (OPD) beserta jawabannya, memantau instansi "
            "yang sudah atau belum menjawab, membacanya dengan nyaman, dan mengekspornya sebagai dokumen Word A4."
        ),
        "ikon": "tanya-jawab",
        "status": "siap",
        "url": "/podcast/materi",
        "urutan": 1,
        "induk": "data_podcast",
        "rencana": [
            "Pertanyaan & jawaban per instansi dengan format ringan (daftar, tebal, tabel)",
            "Status instansi: belum ada jawaban, dalam proses, selesai",
            "Mode baca dengan pencarian, filter status, dan cetak",
            "Ekspor Word A4 dengan ringkasan dan tautan ke tiap instansi",
        ],
    },
]


def semua_modul():
    """Mengembalikan semua modul, diurutkan berdasarkan kolom 'urutan'."""
    return sorted(MODUL, key=lambda m: m["urutan"])


def modul_utama():
    """Modul tingkat atas (tanpa induk) untuk halaman Alat."""
    return [m for m in semua_modul() if not m.get("induk")]


def anak_dari(induk_id):
    """Fitur anak dari sebuah modul induk, urut sesuai 'urutan'."""
    return [m for m in semua_modul() if m.get("induk") == induk_id]


def kelompok_alat():
    """Susunan halaman Alat: [{"induk": None | modul induk, "modul": [kartu...]}, ...].
    Kelompok pertama = modul tingkat atas tanpa anak (tanpa judul); lalu satu kelompok per modul induk."""
    tanpa_anak, kelompok = [], []
    for m in modul_utama():
        anak = anak_dari(m["id"])
        if anak:
            kelompok.append({"induk": m, "modul": anak})
        else:
            tanpa_anak.append(m)
    return ([{"induk": None, "modul": tanpa_anak}] if tanpa_anak else []) + kelompok


def cari_modul(modul_id):
    """Mencari modul berdasarkan id. Mengembalikan None jika tidak ada."""
    return next((m for m in MODUL if m["id"] == modul_id), None)
