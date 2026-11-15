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
        "id": "arsip-liputan",
        "nama": "Arsip Liputan",
        "deskripsi": "Menyimpan liputan kegiatan resmi lalu mengekspor laporan Word ukuran F4.",
        "tujuan": (
            "Menyimpan liputan berita kegiatan resmi secara rapi di komputer sendiri: "
            "data kegiatan, foto dokumentasi, dan isi berita. Laporan dapat diekspor "
            "menjadi dokumen Word ukuran F4 yang siap dicetak."
        ),
        "ikon": "kamera",
        "status": "pengembangan",
        "url": None,
        "urutan": 2,
        "rencana": [
            "Pencatatan data kegiatan (tanggal, tempat, pimpinan yang hadir)",
            "Unggah foto dokumentasi beserta keterangannya",
            "Penulisan dan penyuntingan isi berita",
            "Ekspor laporan ke Word ukuran F4",
        ],
    },
]


def semua_modul():
    """Mengembalikan semua modul, diurutkan berdasarkan kolom 'urutan'."""
    return sorted(MODUL, key=lambda m: m["urutan"])


def cari_modul(modul_id):
    """Mencari modul berdasarkan id. Mengembalikan None jika tidak ada."""
    return next((m for m in MODUL if m["id"] == modul_id), None)
