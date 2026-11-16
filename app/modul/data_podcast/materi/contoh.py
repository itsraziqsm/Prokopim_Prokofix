"""Materi contoh FIKTIF untuk mencoba tampilan (perintah: flask --app run podcast contoh).

Tiga instansi: satu selesai (daftar bersarang + tabel), satu dalam proses, satu belum ada jawaban.
Semua nama, angka, dan isi di bawah ini karangan, bukan data rekap asli.
"""

JUDUL = "Rekap Jawaban Podcast Kota Hijau 2030 (Contoh)"
KETERANGAN = "Per 1 Januari"

INSTANSI = [
    {
        "nama": "Dinas Taman Kota Contoh",
        "selesai": True,
        "pertanyaan": [
            (
                "Apa program utama dinas untuk menambah ruang terbuka hijau tahun ini?",
                "Program utama tahun ini ada tiga, yaitu:\n"
                "1. **Taman lingkungan** di setiap kelurahan\n"
                "   Dimulai dari kelurahan yang belum memiliki taman sama sekali.\n"
                "   - Tahap pertama: 12 kelurahan\n"
                "   - Tahap kedua: 18 kelurahan\n"
                "2. Penanaman *pohon peneduh* di jalan protokol\n"
                "3. Kebun warga di lahan tidur milik pemerintah\n"
                "Seluruh program dibiayai bersama dengan kecamatan.",
            ),
            (
                "Berapa target luas ruang terbuka hijau per kecamatan?",
                "**Target per kecamatan**\n"
                "Target disusun berdasarkan luas wilayah dan kepadatan penduduk.\n"
                "| Kecamatan | Luas saat ini | Target |\n"
                "|---|---|---|\n"
                "| Kecamatan Satu | 12 ha | 15 ha |\n"
                "| Kecamatan Dua | 8 ha | 11 ha |\n"
                "| Kecamatan Tiga | 20 ha | 22 ha |\n"
                "Angka di atas masih dapat berubah setelah evaluasi tengah tahun.",
            ),
        ],
    },
    {
        "nama": "Dinas Kebersihan Contoh",
        "selesai": False,
        "pertanyaan": [
            (
                "Bagaimana jadwal pengangkutan sampah di kawasan taman?",
                "Sampah di kawasan taman diangkut dua kali sehari, pagi dan sore.\n"
                "- Pagi: pukul 06.00\n"
                "- Sore: pukul 16.00",
            ),
            ("Apa langkah dinas untuk mengurangi sampah plastik di taman?", ""),
        ],
    },
    {
        "nama": "Bagian Kerja Sama Contoh",
        "selesai": False,
        "pertanyaan": [
            ("Apakah ada mitra swasta yang terlibat dalam pembangunan taman?", ""),
            ("Bagaimana bentuk pelaporan dana kerja sama kepada masyarakat?", ""),
        ],
    },
]
