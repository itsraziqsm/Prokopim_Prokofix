# CLAUDE.md — Super App Prokopim

Konteks untuk asisten AI yang bekerja di repo ini. Baca seluruhnya sebelum mengubah kode.

## Tentang proyek
"Super App Prokopim": kumpulan tools kerja pribadi untuk pegawai instansi pemerintah (Bagian Prokopim),
berjalan **lokal** di komputer pengguna (Windows), dibuka lewat browser di `http://127.0.0.1:<port>`.
Rencana: aplikasi akan dipindah ke **server Ubuntu** — lihat "Catatan pindah ke server".
Setiap fitur = satu **modul** yang terdaftar di registry dan tampil sebagai kartu di halaman Alat.

## Pengguna & gaya kerja
- Berpengalaman membuat website, **belum pernah memakai Python** → beri komentar kode berbahasa Indonesia,
  jelaskan konsep Python/Flask bila perlu.
- Antarmuka & teks UI **sepenuhnya Bahasa Indonesia**. Nama variabel/fungsi juga Bahasa Indonesia
  (`ambil_db`, `catat`, `tombol`, `lencana`, ...).
- Bekerja **langsung di branch `main`** (sudah diizinkan). Branch `claude/happy-pascal-l5d8dh` = arsip
  placeholder lama, jangan disentuh.
- Komunikasi dengan pengguna dalam Bahasa Indonesia, ringkas. Perintah terminal dalam blok `bash` terpisah.
- Pengguna sering mengirim daftar perubahan bernomor; kerjakan semua, laporkan per nomor.
  Bila ada poin kosong/terpotong, kerjakan sisanya lalu tanyakan.

## Stack & batasan
- Python 3.10+, Jinja2, SQLite (`sqlite3` bawaan). Dependensi Python yang **disetujui**: `flask`,
  `python-docx` (membawa `lxml`), `Pillow`, `pypdf` (Python murni; HANYA untuk membaca/menggabung PDF di
  Gabungkan PDF — tanpa paket tambahan seperti `cryptography`, jadi PDF terenkripsi AES/bersandi ditolak sebagai
  "terkunci kata sandi"). Tidak ada yang lain (lihat `requirements.txt`).
- PDF dibuat **tanpa paket Python**: Windows → Microsoft Word lewat PowerShell/COM; Linux/Windows tanpa Word →
  LibreOffice `soffice --headless`. Bila keduanya tidak ada, hasil tetap Word dan batch berstatus "sebagian".
- **Tailwind CSS v4 lewat paket npm** (`@tailwindcss/cli` 4.3.2) — BUKAN CDN.
  Hasil build `app/static/css/app.css` **di-commit** agar aplikasi jalan tanpa Node & tanpa internet.
- JS biasa (tanpa framework), satu file `app/static/js/app.js`.
- Tanpa CDN / font / skrip eksternal. System font stack. Ikon & ilustrasi = SVG inline.
- Jangan menambah dependensi Python lain tanpa persetujuan pengguna.
- `subprocess` selalu dengan daftar argumen, tanpa `shell=True`; jalur lewat `pathlib`.
- Jangan mengubah/menghapus file di luar folder proyek.

## Menjalankan
```bash
pip install -r requirements.txt
python run.py            # pilih port otomatis (5000, 8000, 8080, ...); atau: python run.py 8080
npm install              # sekali, hanya bila mengubah tampilan
npm run watch:css        # build CSS otomatis saat mengedit template / input.css
npm run build:css        # build minify — WAJIB dijalankan sebelum commit bila kelas Tailwind berubah
flask --app run auth reset-sandi <nama_pengguna>   # lupa kata sandi
python -m unittest -v    # uji otomatis (wajib lulus sebelum commit)

# Cadangan (lihat bagian "Cadangan & pemulihan")
flask --app run cadangan buat [--jenis lengkap|database] [--ke FOLDER]   # tanpa batas 300 MB
flask --app run cadangan periksa <berkas.zip>     # validasi penuh (tanda, struktur, hash, database), tidak mengubah apa pun
flask --app run cadangan pulihkan <berkas.zip>    # HANYA saat aplikasi mati; ketik PULIHKAN untuk lanjut
flask --app run cadangan reset-sandi              # lupa kata sandi cadangan
```
Sandi cadangan dibaca dengan `getpass`, atau dari variabel lingkungan `SUPERAPP_SANDI_CADANGAN` (untuk penjadwalan
buat/periksa/pulihkan; tidak dipakai reset-sandi). Jangan menaruh variabel itu di berkas yang ikut git.
`run.py` menangani error Windows 10013 (port dicadangkan Hyper-V/WSL) dengan mencoba port lain.

## Struktur
```
run.py                         titik masuk; pemilihan port
package.json                   skrip build Tailwind
app/__init__.py                create_app(): config, secret key di instance/, blueprint, halaman galat
app/modules_registry.py        DAFTAR MODUL (sumber tunggal) + STATUS_LABEL; field `induk` (None = tingkat atas). Modul yang
                               punya anak = JUDUL KELOMPOK di halaman Alat (bukan kartu, tanpa halaman sendiri), kartu
                               anaknya tampil di bawah judul itu. Kelompok saat ini: "Berita" (id berita: Pemecah SPT, Arsip
                               Liputan), "Podcast" (id data_podcast: Materi Podcast), dan "Utilitas" (id utilitas:
                               Gabungkan PDF); kelompok_alat(), modul_utama(), anak_dari()
app/routes.py                  blueprint "utama": / (Dashboard), /alat (kartu modul), /log, /log/<id>/buka, /modul/<id>,
                               /pengaturan
app/ringkasan.py               data Dashboard: angka liputan bulan ini/draf, SPT bulan ini, 5 liputan & 5 log terakhir
app/auth.py                    blueprint "auth": /siapkan, /masuk, /keluar, /akun, CLI reset-sandi, penjaga login
app/keamanan.py                CSRF (csrf_field)
app/db.py                      koneksi SQLite per request + SKEMA (pengguna, log_proses, spt_batch, spt,
                               liputan, liputan_foto, materi_podcast, materi_instansi, materi_pertanyaan); PRAGMA foreign_keys=ON di setiap koneksi
app/log_proses.py              catat(), per_halaman(), lokasi_terakhir(), buka_di_penjelajah()
app/waktu.py                   sapaan, tanggal_indonesia, waktu_singkat
app/modul/pemecah_spt/         Fitur 1 — blueprint "pemecah_spt" di /spt:
  pemecah.py                     logika murni tanpa Flask: validasi .docx, deteksi judul, nomor, pecah_satu().
                                 Rentang SPT dimulai di AWAL HALAMAN judulnya agar kop yang diketik di badan
                                 dokumen ikut ke SPT-nya (awal_halaman): 1) page break / section break /
                                 pageBreakBefore (paragraf & baris pertama tabel), 2) kop yang isinya mirip kop
                                 SPT pertama (kop diketik ulang, halaman didorong Enter; KEMIRIPAN_KOP_MIN),
                                 3) lastRenderedPageBreak; maks. KOP_MAKS elemen berisi di atas judul
  penamaan.py                    nama berkas dari nomor (sanitasi, duplikat → (1),(2) untuk SEMUA anggota)
  pdf.py                         konversi PDF (Word COM / LibreOffice), deteksi otomatis
  layanan.py                     DB & berkas; daftar_spt(), ambil_spt(id) untuk modul lain (Arsip Liputan)
  pekerja.py                     pemrosesan batch di thread latar + laporan progres ke DB
  routes.py                      /spt, /spt/analisis, /spt/pratinjau/<token>, /spt/proses, /spt/batch/<id>,
                                 /spt/batch/<id>/status (JSON progres), /spt/batch/<id>/zip,
                                 /spt/batch/<id>/buka, /spt/unduh/<spt_id>/<docx|pdf>,
                                 POST /spt/hapus (satu/banyak batch + berkas hasilnya)
app/templates/pemecah_spt/     index (unggah + riwayat), pratinjau, batch (hasil)
app/modul/arsip_liputan/       Fitur 2 — blueprint "arsip_liputan" di /liputan (semua pengguna melihat seluruh arsip):
  teks.py                        paragraf_berita() (normalisasi saat ekspor; DB tetap apa adanya), nama_ekspor()
                                 "13 Oktober Wali - Zoom Meeting" (tokoh kosong: "13 Oktober - Zoom Meeting")
  foto.py                        olah_foto(): validasi Pillow; DIOLAH hanya bila > 800 KB, format bukan
                                 JPG/PNG/GIF/BMP, atau EXIF orientasi ≠ normal → JPEG q85 (turun s.d. 60),
                                 sisi maks. 1920 (turun s.d. 1200) sampai ≤ 800 KB; selain itu byte tidak disentuh
  ekspor.py                      Word dari app/templat_docx/berita.docx (isi & gambar contoh + relasinya dibuang,
                                 sectPr F4 11907x18711 margin 1440 dipertahankan; templat_sementara() bila berkas
                                 belum ada). BERITA (Title, satu paragraf kosong, lalu Normal) lalu LEMBAR FOTO: tiap
                                 lembar = tabel 1 kolom, kotak luar garis LURUS tipis (tinggi baris exact + cantSplit), jeda
                                 0,6 cm, maks. 3 foto; garis POTONG putus-putus = tabel dalam 0,4 cm dari tepi foto
                                 (ruangnya diambil dari ukuran foto, tinggi kotak luar tidak berubah);
                                 bagi_lembar() menghormati "Mulai lembar baru". Lembar baru = "Page break before"
                                 di baris pertama tabel, JANGAN page break manual (di Word memicu halaman kosong);
                                 CADANGAN_CM 1,5 di bawah tabel; paragraf pemisah/penutup 1 pt
  kelengkapan.py                 daftar_kelengkapan(): butir URUT SESUAI FORMULIR — wajib (tanggal, nama kegiatan, judul,
                                 isi, foto) & pelengkap (status final, SPT, keterangan foto, sumber foto, Word terbaru);
                                 wajib_belum() = PENGAMAN: rute /ekspor menolak membuat Word bila ada butir wajib kurang
                                 (isian tetap disimpan); tombol [data-butuh-wajib] nonaktif langsung via app.js
  layanan.py                     DB, folder PER BULAN KEGIATAN instance/data/liputan/<tahun>/<MM-Bulan>/<id>/{foto,ekspor}
                                 (folder_liputan(id) dihitung dari tanggal di DB; tanggal pindah bulan → folder ikut
                                 dipindah SEBELUM DB diubah, gagal → simpan ditolak; folder versi lama <id>/ dipindah
                                 otomatis saat aplikasi dinyalakan; folder bulan/tahun kosong dibersihkan),
                                 cari() → (daftar, total, jumlah_per_bulan), jalur_aman()
  routes.py                      /liputan (cari & filter), /liputan/baru, /liputan/<id> (+ /simpan, /ekspor,
                                 /unduh, /paket, /hapus), /liputan/<id>/foto (+ /<fid>, /simpan, /<fid>/simpan|
                                 geser|hapus), /liputan/spt/<spt_id>/<docx|pdf>
app/modul/data_podcast/        Fitur 3 — INDUK "Podcast" (id data_podcast) = judul kelompok di halaman Alat (#data-podcast); blueprint
                               "data_podcast" hanya mengalihkan /podcast ke /alat#data-podcast, cli_group "podcast"
                               (flask --app run podcast contoh = materi contoh FIKTIF), SEMUA_BLUEPRINT didaftarkan di create_app.
                               Fitur anak baru = sub-paket baru di sini + modul registry dengan "induk": "data_podcast".
  materi/                        Fitur anak "Materi Podcast" — blueprint "materi_podcast" di /podcast/materi (semua pengguna
                                 melihat semua materi). Tabel materi_podcast → materi_instansi → materi_pertanyaan (CASCADE).
    pengurai.py                    logika murni: urai(teks) → blok (paragraf/judul/daftar{bernomor,butir[{isi,anak}]}/tabel),
                                   html(teks) → HTML AMAN (semua teks di-escape, HTML dibangun sendiri), teks_polos(),
                                   rapikan()/ada_isi(). Dipakai BERSAMA oleh web (filter jawaban_html, /pratinjau) & Word.
    layanan.py                     DB (query tanpa N+1; fungsi SQL ada_isi() didaftarkan per koneksi), status_instansi()
                                   (selesai | proses | belum), simpan_instansi() menyinkronkan SELURUH daftar pertanyaan dalam
                                   satu transaksi (pid milik instansi lain diabaikan), duplikat_materi(), ekspor(), jalur_ekspor()
    ekspor.py                      Word A4 (lihat "Ekspor Word Materi Podcast" di bawah)
    contoh.py                      data contoh fiktif (3 instansi: selesai + daftar bersarang & tabel, dalam proses, belum)
    routes.py                      /podcast/materi (+ ?q=), /baru, /<id> (+ /simpan, /hapus, /duplikat, /ekspor, /unduh,
                                   /baca), /<id>/instansi (POST tambah), /<id>/instansi/<iid> (GET/POST simpan, /geser,
                                   /hapus), POST /pratinjau (fragmen HTML untuk pratinjau langsung)
app/modul/utilitas/            Fitur 4 — INDUK "Utilitas" (id utilitas) = judul kelompok di halaman Alat (#utilitas); blueprint
                               "utilitas" hanya mengalihkan /utilitas ke /alat#utilitas; SEMUA_BLUEPRINT didaftarkan di create_app.
  gabung_dokumen/                Fitur anak "Gabungkan PDF" (id gabung_dokumen) — blueprint "gabung_dokumen" di /utilitas/gabung;
                                 sesi & hasil HANYA milik pengguna yang masuk (milik orang lain → 404).
    penggabung.py                  logika murni (pypdf): urai_rentang("1-3,5,8-", n) → indeks (urut sesuai tulisan; kosong/"semua"
                                   = semua; tolak 0, terbalik, di luar halaman, teks lain → GalatRentang), tanda_pdf(), periksa_pdf()
                                   (rusak/terkunci/kosong → GalatBerkas), siapkan_sumber() = TITIK PERLUASAN WORD (sekarang hanya
                                   PDF; nanti .docx dikonversi lewat app/modul/pemecah_spt/pdf.py + tambah ".docx" ke
                                   EKSTENSI_DIDUKUNG), gabungkan() (hanya halaman terpilih; OpenAction/JavaScript dokumen & /AA
                                   halaman tidak ikut; bookmark per file = nama file tanpa ekstensi; Title = nama hasil; ditulis
                                   langsung ke berkas), nama_berkas_hasil() (karakter terlarang Windows → "-", maks. 100, bukan
                                   CON/PRN/COMn/LPTn, berakhiran .pdf, unik " (1)")
    layanan.py                     sesi penyusunan instance/tmp/gabung_dokumen/<token>/ (<id acak>.pdf + sesi.json; token
                                   secrets.token_urlsafe terikat pengguna; folder > 24 jam dihapus saat halaman awal dibuka —
                                   pembersih sendiri karena pembersih tmp SPT hanya untuk berkas), unggahan per file (ekstensi
                                   .pdf + "%PDF-" di 1 KB pertama, ditulis bertahap; maks. 50 MB/file, 200 MB/penyusunan, 30 file,
                                   2000 halaman; penolakan per file tidak membatalkan file lain), gabungkan() (rekaman gabung_hasil
                                   + folder instance/data/gabung_dokumen/<id>/; gagal → folder & rekaman dibersihkan; sesi dihapus
                                   setelah berhasil), jalur_hasil_aman()/folder_hasil_aman() (pola jalur_berkas_aman/folder_batch_aman)
    routes.py                      /utilitas/gabung (unggah + riwayat), POST /unggah, /<token> (susun), POST /<token>/tambah,
                                   POST /<token>/aksi (aksi="naik|turun|hapus:<id>" atau "periksa"; simpan isian dulu; naik/turun
                                   → ?fokus=), POST /<token>/gabung (fungsi gabungkan), /hasil/<id>, /hasil/<id>/unduh,
                                   POST /hapus. Batas kiriman unggah & tambah di create_app (batas_khusus). Filter |ukuran_berkas.
app/templates/utilitas/gabung/ index (zona seret [data-seret-berkas] + riwayat dengan pilih-semua & hapus), susun (SATU form
                               multipart, banyak tombol formaction; tombol sr-only pertama = Periksa rentang untuk Enter; rentang
                               per baris lewat field(label_tersembunyi=true) dengan galat inline), hasil (Unduh, Gabungkan lagi)
app/cadangan/                  Fitur 5 — CADANGAN (halaman SISTEM di sidebar, bukan modul registry): blueprint "cadangan" di
                               /cadangan + cli_group "cadangan"; didaftarkan di create_app. Logika murni dipakai web & terminal:
  sandi.py                       kunci.json (hash scrypt n=2**14 r=8 p=1 + salt; tulis atomik, izin 0600), cocok(),
                                 verifikasi() dengan pembatas 5x salah -> kunci 5 menit (percobaan.json, bertahan antar-restart)
  basisdata.py                   salin_snapshot() (sqlite3 backup API) + jalur absolut -> "{instance}/..." HANYA di salinan;
                                 KOLOM_JALUR = log_proses.lokasi, spt_batch.folder, gabung_hasil.folder (cek ulang dengan grep
                                 bila menambah kolom jalur!); ke_relatif/ke_absolut (Windows & POSIX); validasi_db();
                                 siapkan_untuk_pasang() (jalur absolut sesuai instance tujuan + putar ulang sesi_token)
  arsip.py                       buat_cadangan() (ZIP bertahap -> .sementara -> os.replace; kunci buat.kunci; cek ruang disk
                                 >= 1,2x; batas_byte), manifest + tanda HMAC, POLA_NAMA, daftar putih entri, periksa_struktur()/
                                 periksa_isi() (tanpa extractall), uji_keutuhan() (tombol Uji, tanpa sandi), daftar_cadangan()
  pulihkan.py                    prosedur 10 langkah dengan rollback; periksa() untuk perintah periksa
  audit.py                       instance/cadangan/audit.log (JSON per baris, append-only)
  routes.py                      /cadangan (buat + daftar + ganti sandi), /sandi-baru, /kunci, /kunci-kembali, POST /buat,
                                 /unduh/<nama>, POST /uji/<nama>, POST /hapus/<nama>, POST /ganti-sandi
  perintah.py                    flask --app run cadangan buat|periksa|pulihkan|reset-sandi
app/templates/cadangan/        kunci, sandi_baru, index
app/templates/data_podcast/    materi/ index, baru, detail (tabel instansi + naik/turun, Word, judul, duplikat,
                               hapus), instansi (editor pertanyaan + pratinjau + "Tandai selesai"), baca (mode baca)
app/templates/arsip_liputan/   index (arsip dikelompokkan per bulan kegiatan, terbaru di atas, satu tabel per bulan), form
                               (tanggal kegiatan baru kosong; SPT terkait: radio pakai_spt Tanpa/Dengan — daftar &
                               pencarian [data-wadah-spt] hanya tampil bila "Dengan SPT"; server: "tidak" → spt_id NULL,
                               "ya" tanpa pilihan → galat) (konten kiri: Data kegiatan, Isi berita, Foto; panel kanan
                               #panel-laporan: Word/ekspor di atas + Kelengkapan ✓/✗; sticky setinggi layar)
app/templat_docx/berita.docx   TEMPLAT berita (taruh berkas asli di sini; lihat README di folder itu)
app/templates/base.html        kerangka: sidebar + konten; wadah notifikasi; skrip tema/sidebar di <head>
app/templates/komponen/        sidebar.html, ui.html (makro), ikon.html (SVG)
app/templates/auth/            _kartu.html (tata letak 60/40), masuk, siapkan, akun
app/templates/                 dashboard (ringkasan), alat (kartu modul), log, modul_dev, pengaturan, galat
app/static/src/input.css       SUMBER CSS (edit ini)
app/static/css/app.css         HASIL BUILD (jangan diedit manual)
app/static/img/                logo.png (logo Prokopim polos, latar transparan; sidebar & halaman masuk), logo-teks.png
                               (logo + tulisan PROKOPIM; panel kanan halaman masuk di atas alas --latar-logo karena
                               tulisannya hitam), favicon.png (64 px), gambar halaman masuk opsional: masuk.jpg/.png/.webp
instance/                      superapp.db + secret_key (tidak ikut git; backup = salin folder ini)
instance/data/spt/<id_batch>/  berkas hasil Pemecah SPT
instance/tmp/                  unggahan sementara selama pratinjau (<token>.docx + .json), dihapus >24 jam
instance/data/liputan/<tahun>/<MM-Bulan>/<id>/  foto/ (nama acak, versi olahan) dan ekspor/ (satu Word terbaru)
instance/data/podcast/<id>/ekspor/             satu Word terbaru Materi Podcast (nama dari judul + keterangan)
instance/tmp/gabung_dokumen/<token>/           sesi penyusunan Gabungkan PDF (PDF sumber bernama acak + sesi.json), > 24 jam dihapus
instance/data/gabung_dokumen/<id>/             PDF hasil Gabungkan PDF (satu berkas, nama tersanitasi dari pengguna)
instance/cadangan/kunci.json                   hash scrypt kata sandi cadangan (DI LUAR database; tidak ikut cadangan)
instance/cadangan/percobaan.json               pembatas percobaan sandi cadangan
instance/cadangan/audit.log                    catatan audit cadangan (append-only; tidak tertimpa saat pemulihan)
instance/cadangan/berkas/                      cadangan-<lengkap|database|sebelum-pulihkan>-YYYY-MM-DD-HHMM[-n].zip + .json pendamping
instance/pulihkan_tmp/<stempel>/               staging pemulihan (dihapus setelah selesai/gagal)
tests/test_aplikasi.py         uji inti (create_app(instance_path=folder_sementara))
tests/test_pemecah_spt.py      uji Pemecah SPT; tests/fixture_spt.py membangun .docx contoh (batch_contoh())
tests/test_arsip_liputan.py    uji Arsip Liputan; tests/fixture_liputan.py membuat foto contoh (tujuh_foto())
tests/test_materi_podcast.py   uji Materi Podcast (pengurai + XSS, status, CRUD, N+1, ekspor Word, keamanan, CLI)
tests/test_cadangan.py         uji Cadangan (sandi & pembatas, gerbang, pembuatan, SERANGAN pada pemulihan, pemulihan
                               end-to-end ke instance lain, rollback, terminal, Dashboard)
tests/test_gabung_dokumen.py   uji Gabungkan PDF (rentang, nama, pypdf, alur web, batas, keamanan, kelompok Utilitas);
                               tests/fixture_pdf.py membuat PDF contoh (lebar halaman = "sidik" urutan, terkunci, rusak)
```

## Pola & konvensi penting
- **Id modul**: huruf kecil dengan tanda hubung/garis bawah (mis. `pemecah_spt`); id yang sama dipakai di `catat()`
  agar nama modul tampil di tabel Log. Modul siap: `status="siap"`, `url` diisi (mis. `/spt`).
- **Menambah modul**: tambah satu dict di `MODUL` (`app/modules_registry.py`): id, nama, deskripsi,
  tujuan, ikon, status (`"siap"`/`"pengembangan"`), url (None → `/modul/<id>`), urutan, rencana.
  Modul "pengembangan" tetap bisa diklik → template tunggal `modul_dev.html`; `/modul/<id>` untuk modul "siap" dialihkan ke `url`-nya.
  Lencana status di halaman Alat hanya muncul bila status modul berbeda-beda, dan hanya pada modul yang belum siap.
  Logika modul nyata: buat blueprint sendiri (mis. `app/modul/pemecah_spt/`), daftarkan di `create_app`,
  isi `url` di registry, ubah status jadi `"siap"`. Logika berat ditaruh di modul murni tanpa Flask agar mudah diuji.
  Sidebar menandai "Alat" aktif untuk semua blueprint modul; breadcrumb modul diawali ("Alat", /alat).
- **Materi Podcast — format jawaban** (kolom teks biasa, BUKAN HTML; DB menyimpan apa adanya, maks. 20.000 karakter):
  satu baris = satu paragraf (baris kosong diabaikan); `1. ` bernomor (di dalam satu daftar tak terputus nomor ketikan
  diabaikan; bila daftar tingkat teratas diselingi paragraf/judul/tabel: ketik `1.` = daftar baru mulai 1, ketik `2.`+ =
  MELANJUTKAN daftar bernomor sebelumnya — blok berbagi `rantai`, HTML `<ol start>`, Word memakai w:num yang sama per
  rantai dalam satu jawaban); `- ` poin; indentasi ≥2 spasi/tab di bawah butir = butir bersarang, baris tanpa penanda yang lebih menjorok
  = paragraf lanjutan butir; `**tebal**`, `*miring*`; baris yang seluruhnya `**teks**` = judul kecil; baris diawali `|` =
  tabel (`|---|` menandai baris sebelumnya header, `\|` = garis tegak di dalam sel); spasi ganda/NBSP/tepi dirapikan
  saat tampil & ekspor; tanda tak berpasangan tampil apa adanya, pengurai tidak pernah melempar galat.
- **Materi Podcast — status instansi**: "Belum ada jawaban" (tak satu pun terjawab), "Dalam proses", "Selesai" (kolom
  `selesai`, hanya berlaku bila SEMUA pertanyaan berjawaban; server menolak tanda selesai bila ada yang kosong, isian lain
  tetap disimpan). Lencana: selesai = `lencana-siap`, proses = `lencana-peringatan`, belum = `lencana-netral`.
- **Ekspor Word Materi Podcast** (ekspor.py, python-docx, dibangun dari nol): A4 11906x16838, margin 2 cm, Calibri 12,
  baris 1,2, setelah 6 pt; GAYA BERNAMA (Title [caps, 19 pt, 1F3A5F, 2 baris lewat bagi_judul()], Subjudul, Ringkas,
  Heading 1 [bookmark instansi_<n>, garis bawah, keepNext], Status Instansi, Pertanyaan [latar EDF1F6, garis kiri aksen,
  nomor i.k + tab, keepNext hanya bila berjawaban], Label Jawaban "JAWABAN", Isi Jawaban [indentasi 0,6 cm], Judul
  Jawaban, Butir Jawaban, Lanjutan Butir, Sel Tabel, Kaki). Tabel ringkasan No/Instansi(tautan internal)/Pertanyaan/Status
  (warna latar + teks status tertulis). Daftar = numbering asli Word: tiap daftar/rantai w:num baru + startOverride=1 (lanjutan = w:num sama). Tabel
  jawaban: header biru tua, border C5CDD6, cantSplit, lebar ≤ area cetak. Footer "<judul>  ·  Halaman PAGE dari NUMPAGES".
  Isi teks tidak boleh berubah selain perapian spasi (diuji: urutan kata dokumen = urutan kata DB).
  Acuan tampilan: dokumen "REKAP_JAWABAN_UNTUK_PODCAST_PER_11_NOVEMBER_RAPI.docx" (berisi data asli; tidak di-commit).
- **Semua halaman wajib login** (penjaga `before_app_request` di `auth.py`); pengecualian di `ENDPOINT_PUBLIK`.
- **Setiap `<form method="post">` wajib `{{ csrf_field() }}`.**
- **Pencatatan proses**: modul memanggil `catat(modul_id, aksi, status="sukses"|"gagal", detail=..., lokasi=...)`.
  Lokasi tampil di tabel Log; buka folder hanya dari lokasi di DB milik pengguna (bukan input bebas).
- **Berkas hasil & unduhan**: simpan di `instance/data/<modul>/<id>/` dengan nama dari data tepercaya
  (nama berkas dari klien hanya untuk tampilan). Unduh HANYA dari rekaman database, lalu resolve dan pastikan
  jalurnya di dalam folder data modul (lihat `layanan.jalur_berkas_aman`) → `send_file(as_attachment=True)`.
  ZIP dibuat di memori. "Buka folder" hanya dari lokasi yang tercatat. Unggahan: validasi ekstensi, signature,
  isi ZIP & batas ukuran; simpan dengan nama acak; token sementara terikat ke pengguna.
- **Hapus data + berkas**: selalu lewat `<form data-konfirmasi="... {n} ..." data-konfirmasi-judul="..."
  data-konfirmasi-tombol="Hapus">` (dialog `#dialog-konfirmasi` di base.html; `{n}` = jumlah `data-pilih-item` tercentang),
  tombol `.tombol-bahaya` di dialog. Server: hanya milik pengguna, tolak yang masih "proses", hapus folder HANYA
  bila jalurnya persis `instance/data/<modul>/<id>` (lihat `layanan.folder_batch_aman`), hapus berkas dulu baru
  rekaman DB (bila berkas terkunci, rekaman dipertahankan), lalu `catat(..., "Hapus batch", ...)`.
  Catatan: SPT yang dihapus juga hilang dari `daftar_spt()`; `liputan.spt_id` otomatis jadi NULL (ON DELETE SET NULL).
- **SPT lintas modul**: `layanan_spt.daftar_spt(semua_pengguna=True, cari=...)` dan `ambil_spt(id, semua_pengguna=True)`
  untuk modul yang dilihat semua pengguna; default tetap hanya milik pengguna yang masuk.
- **Foto pengguna**: tampilkan lewat rute yang wajib login (`send_file`), BUKAN folder static. Simpan dengan nama acak.
  Unggah: pilih/seret/tempel (Ctrl+V) via `[data-zona-unggah]` (DataTransfer → input file). Batas ukuran khusus
  per rute dipasang di `create_app` (`batas_khusus`) SEBELUM penjaga login, karena CSRF membaca formulir lebih dulu.
- **Konfirmasi di tombol**: `data-konfirmasi` juga boleh di tombol pengirim (mis. Hapus di dalam form besar).
- **Satu form, banyak aksi**: tombol dengan `formaction` (mis. Naik/Turun/Hapus foto, "Buat Word" dengan
  `form="form-kegiatan"`) — rute aksi menyimpan isian form dulu agar ketikan tidak hilang.
- **Proses lama + progres**: kerjakan di thread latar (`threading.Thread(daemon=True)` dengan
  `app.app_context()`, kirim `current_app._get_current_object()`), simpan progres di DB (kolom `status="proses"`,
  `progres`, `total_langkah`, `tahap`), sediakan endpoint JSON `{selesai, progres, total, persen, tahap, pesan, jenis}`,
  lalu tampilkan makro `progres(url_status, ...)` dari `ui.html`. app.js menanyakan status tiap detik, lalu memuat
  ulang halaman dengan notifikasi. Di thread tidak ada `g.pengguna`: panggil `catat(..., pengguna_id=...)`.
  Batch yang tertinggal berstatus "proses" ditandai gagal saat aplikasi dinyalakan (`db.siapkan_db`).
  Kolom baru pada tabel lama: tambahkan ke `KOLOM_SUSULAN` di `db.py` (ALTER TABLE otomatis).
- **Notifikasi**: server `flash(pesan, "sukses"|"info"|"galat")`; JS `window.notifikasi(pesan, jenis)`.
  Tampil pop-up kanan atas (fixed), jangan pakai alert inline untuk pesan umum. Galat per-field tetap inline (makro `field`).
- **Komponen ulang-pakai** di `komponen/ui.html`: `lencana`, `kartu_modul`, `breadcrumb`, `kembali(label, url)` (satu tautan
  kembali untuk halaman yang lebih dalam dari tingkat kedua, mis. halaman materi/instansi), `tombol`, `toast`, `field` (+ `placeholder`,
  `label_tersembunyi` untuk isian di dalam tabel yang sudah punya judul kolom),
  `alert` (peringatan inline yang menetap, jenis info|peringatan|galat). Kelas komponen CSS: `.tombol(-primer|-sekunder|-teks|-bahaya)`,
  `.lencana(-siap|-pengembangan|-peringatan|-gagal)`,
  `.panel`, `.input`, `.label`, `.petunjuk`, `.galat-field`, `.ikon`.
- **Warna**: hanya lewat CSS variable di `input.css` (`--warna-aksen`, `--latar`, `--permukaan`, `--teks`, `--teks-redup`,
  `--garis`, ...) yang dipetakan ke kelas Tailwind (`bg-aksen`, `text-redup`, `border-garis`, `bg-siap-latar`, ...).
  Jangan menulis warna hex langsung di template.
- **Tema**: `<html data-theme="light|dark">`, dipilih di halaman Pengaturan (Terang/Gelap/Ikuti sistem),
  disimpan di `localStorage["tema"]`. **Sidebar**: `<html data-sidebar="lebar|ringkas">` (bawaan ringkas), `localStorage["sidebar"]`.
- Tanggal/waktu tampil format Indonesia (`waktu.py`, filter Jinja `waktu_singkat`, `jalur` untuk path panjang).
  Sapaan & tanggal dihitung di server saja (server = komputer pengguna); jangan duplikasi di JS.
- **Ukuran**: pakai skala bawaan Tailwind (`text-sm`, `size-4`, `min-h-10`, ...). Hindari nilai sembarang `[...]`.
- Ikon baru: tambahkan cabang di `komponen/ikon.html`, warna `currentColor`.
- **Cetak**: `@media print` di input.css memaksa warna tema terang, menyembunyikan sidebar/notifikasi/`[data-tidak-dicetak]`.
  Isi jawaban bergaya lewat `.isi-jawaban` (daftar bertingkat via `data-tingkat`, tabel); ukuran huruf mode baca dalam `em`.
- **Tabel lebar**: bungkus dengan `<div class="relative overflow-x-auto" tabindex="0" role="region" aria-label="...">`.
  `relative` WAJIB: tanpa itu teks `sr-only` (absolute) di dalam tabel lolos dan melebarkan halaman di ponsel.
  Teks panjang berisi garis miring (nomor surat, jalur) pakai filter `|jalur` + `wrap-break-word`.
  Tabel di dalam `grid`: pakai `grid-cols-1` (atau `min-w-0` pada item) agar lebar minimum tabel tidak melebarkan halaman.
- **Tombol ekspor/proses WAJIB `data-tombol-progres="Membuat Word…"`** (pada `<button type="submit">`, juga yang memakai
  `formaction`): saat diklik tombol itu sendiri berubah menjadi bilah progres berjalan (`.tombol-progres`, tak tentu karena
  server memproses dalam satu permintaan; ukuran tombol tetap; tanpa animasi bila reduced-motion) dan formulirnya
  terkunci — kiriman berikutnya (klik ganda, Enter, tombol lain) ditolak sampai halaman berganti. Berlaku untuk Word
  liputan, Word materi, Analisis & Proses SPT, dan SEMUA ekspor baru; dijaga uji `UjiTombolProgres` (memindai templat:
  form/formaction ke rute berisi "ekspor", "proses", "analisis"). Proses yang punya progres nyata (thread latar) tetap
  memakai makro `progres` di halaman berikutnya.
- **Perilaku JS siap pakai** (app.js): `<form data-kirim-sekali data-teks-proses="Memproses...">` (cegah kirim ganda untuk
  formulir biasa; tombol dinonaktifkan SETELAH formulir mulai terkirim agar name/value tombol pengirim — mis.
  aksi="naik:<id>" — tetap ikut; untuk ekspor pakai `data-tombol-progres`),
  `data-pilih-semua` + `data-pilih-item` + `data-jumlah-dipilih` (centang semua), `data-pilih-berkas` +
  `data-nama-berkas` (input berkas bergaya tombol; input multiple → "3 berkas: a.pdf, ..."), tombol
  `data-butuh-berkas="<id input>"` (aktif hanya bila input berisi berkas), `<div data-seret-berkas>` (zona seret-lepas
  umum untuk input file di dalamnya, menyaring sesuai `accept`; berbeda dari `data-zona-unggah` yang khusus foto), `data-salin="teks"` (salin ke clipboard),
  `data-pantau-progres="url"` (dipasang makro `progres`), `data-konfirmasi` (dialog konfirmasi),
  `data-perlu-pilihan` (tombol nonaktif bila belum ada `data-pilih-item` tercentang),
  `data-zona-unggah` + `data-pratinjau-unggah` + `data-tombol-unggah` (unggah foto), `window.konfirmasi(pesan,
  {judul, tombol}, lanjut)` (dialog konfirmasi dari JS), `?fokus=<id>` (fokus kembali ke tombol setelah dialihkan, mis.
  naik/turun; dipasang setelah event load agar tidak ditimpa jangkar #... di alamat), `<form data-jaga-perubahan>` + `[data-tanda-berubah]` (peringatan beforeunload; event "ubah-daftar"),
  `[data-editor-pertanyaan]` (tambah/naik/turun/hapus pertanyaan di browser, pratinjau langsung lewat POST /pratinjau,
  `[data-tanda-selesai]` aktif hanya bila semua berjawaban), `[data-buka-editor="<id textarea>"]` + `<dialog data-editor-fokus>`
  (editor fokus layar penuh untuk satu jawaban: bilah format tebal/miring/judul/daftar/tabel/indentasi, Ctrl+B/I,
  Enter melanjutkan daftar, Tab/Shift+Tab menjorok; teks disalin langsung ke kolom asli; pratinjau kanan bisa
  disembunyikan dan lebarnya diseret 20–50% — `--lebar-pratinjau`, localStorage "editor-pratinjau" &
  "editor-lebar-pratinjau"; di ponsel pratinjau di bawah), `[data-alat-baca]` (mode baca: filter status, cari + sorot
  `<mark>`, ukuran huruf `localStorage["ukuran-baca"]`, cetak), `data-saring="#wadah"` +
  `data-saring-teks` + `data-saring-kosong` (saring daftar di sisi klien), `data-kelengkapan` + `data-cek=
  "isi:ID | pilih:NAMA | nilai:NAMA=NILAI"` (centang/silang panel diperbarui langsung dari isian formulir;
  klik butir = gulir halus ke isian + fokus + sorotan sesaat `[data-sorot]`, tanpa animasi bila reduced-motion), notifikasi titipan lewat
  `sessionStorage["notifikasi-tertunda"]` agar tetap tampil setelah halaman dimuat ulang.

## Standar UI/UX
- Rapi, tenang, profesional (kantor pemerintahan); satu warna aksen biru tua + netral; tanpa gradasi mencolok.
- Kontras WCAG AA, fokus keyboard terlihat, elemen HTML semantik + ARIA seperlunya, hormati `prefers-reduced-motion`.
- Responsif 1366×768 sampai monitor lebar; tetap rapi di tablet/ponsel (sidebar jadi ikon saja).
- Navigasi **hanya sidebar**: logo di puncak = tautan ke Dashboard (disorot saat aktif); atas = Alat (ikon empat kotak), Log; tombol "Lebarkan/Ciutkan menu" (ikon caret, `#tombol-sidebar`,
  hanya md ke atas) tepat di atas garis pemisah; bawah = Cadangan (aktif untuk semua rute /cadangan), Pengaturan, Akun. Bawaan menu **tertutup** (ringkas)
  kecuali `localStorage["sidebar"] == "lebar"`.
- Tanpa footer. Halaman auth: formulir 60% kiri, gambar 40% kanan, satu layar tanpa scroll.
- Jangan membuat form/tombol palsu yang seolah berfungsi.
- **Hindari AI-slop**: tanpa ilustrasi/kartu pengisi, tanpa teks pengisi, tanpa instruksi developer di UI,
  tanpa ikon centang untuk hal yang belum selesai, tanpa lencana yang nilainya sama di semua item,
  tanpa judul kecil huruf kapital berjarak, tanpa kalimat penjelas di bawah tombol, contoh pengisian ditaruh di
  placeholder (bukan petunjuk), petunjuk syarat hanya tampil selama syaratnya belum terpenuhi, butir opsional yang belum
  diisi bertanda netral (bukan silang merah). Breadcrumb maks. 3 tingkat; halaman lebih dalam memakai `kembali()`;
  satu jalan kembali saja.
- Keamanan secukupnya untuk aplikasi lokal satu pengguna: hash sandi, CSRF, wajib login, rotasi token sesi
  saat ganti sandi. Tanpa pembatas percobaan login.

## Cadangan & pemulihan (keamanan WAJIB dijaga)
- Pembuatan: web (/cadangan) + terminal. PEMULIHAN HANYA TERMINAL — jangan pernah menambah rute web yang menerima
  unggahan ZIP cadangan.
- Halaman /cadangan butuh KATA SANDI CADANGAN terpisah (min. 12, bukan sandi masuk), disimpan sebagai hash scrypt di
  instance/cadangan/kunci.json. Berhasil -> `session["cadangan_sampai"]` (10 menit). JANGAN menyimpan sandi/kunci HMAC
  di session (cookie Flask hanya ditandatangani). Pesan galat sandi tidak membedakan "salah" dan "terkunci".
  "Buat cadangan" & "Ganti sandi" meminta sandi diketik ulang (lewat pembatas yang sama).
- Isi ZIP: manifest.json, database/superapp.db (snapshot konsisten, TANPA kompresi agar tidak tertolak cek rasio),
  data/** (hanya ekstensi pdf/docx/jpg/jpeg/png/gif/bmp/webp/json; lain-lain, symlink & .lama* dilewati),
  templat_docx/*.docx. TIDAK PERNAH: secret_key, tmp/, cadangan/, pulihkan_tmp/, .lama*.
- Manifest: versi_format, dibuat (ISO+zona), jenis, skema, hitungan, berkas (jalur/ukuran/SHA-256), kdf (scrypt + salt),
  tanda = HMAC-SHA256(JSON kanonik terurut tanpa "tanda"), kunci = scrypt(sandi, salt). Parameter KDF dari manifest
  dibatasi (cegah DoS). Bandingkan dengan hmac.compare_digest.
- Pemulihan (pulihkan.py) berurutan: aplikasi mati (BEGIN EXCLUSIVE) + kunci -> tanda -> struktur (daftar putih, tolak
  jalur absolut/../huruf drive/backslash/NUL/symlink/terenkripsi/nama ganda case-insensitive/tidak di manifest/hilang;
  batas MAKS_ENTRI, MAKS_TOTAL_BYTE, MAKS_RASIO) -> bongkar ke staging (jalur dihitung sendiri) sambil cek SHA-256 ->
  validasi DB (trusted_schema=OFF, integrity, foreign_key_check, skema ⊆ SKEMA+KOLOM_SUSULAN, tanpa trigger/view/
  virtual) -> pratinjau + ketik PULIHKAN -> cadangan otomatis "sebelum-pulihkan" -> pasang (db/data/templat; yang lama
  jadi *.lama-<stempel>, rollback bila gagal) -> sesi_token semua pengguna diputar -> cek akhir + laporan berkas hilang.
  secret_key tidak pernah diubah. Bila kunci.json belum ada (server baru), sandi cadangan yang dipakai memulihkan
  dijadikan sandi cadangan di sana.
- Aksi dicatat ke tabel Log (catat("cadangan", ...)) DAN audit.log. Unduh hanya nama yang cocok POLA_NAMA dan berada di
  instance/cadangan/berkas/ (Cache-Control: no-store). Dashboard memberi peringatan bila cadangan terakhir > 7 hari.
- **ZIP cadangan berisi data rahasia** (hash kata sandi pengguna, data kegiatan, foto). Simpan di tempat aman (bukan
  folder bersama/publik); sandi cadangan tanpa catatan = cadangan tidak bisa dipulihkan.
- **Pindah ke server Ubuntu**:
  1. Di Windows: halaman Cadangan -> Buat cadangan "Semua data dan hasil" (atau `flask --app run cadangan buat` bila
     > 300 MB), lalu Uji dan Unduh ZIP-nya.
  2. Di server: clone repo, buat virtual environment (Ubuntu 23.04+ menolak `pip install` ke Python sistem —
     "externally-managed-environment", PEP 668; JANGAN pakai --break-system-packages):
     `sudo apt install python3-venv python3-full`, lalu di folder proyek `python3 -m venv .venv`,
     `source .venv/bin/activate`, `pip install -r requirements.txt`. Semua perintah `flask --app run ...` dan
     `python run.py` dijalankan SETELAH `source .venv/bin/activate` (atau pakai `.venv/bin/flask`, `.venv/bin/python`).
     Salin ZIP cadangan lewat jalur aman (mis. scp).
  3. Pastikan aplikasi belum/tidak berjalan, lalu `flask --app run cadangan periksa <zip>` dan
     `flask --app run cadangan pulihkan <zip>` (jalur Windows di database otomatis diubah ke jalur server).
  4. Jalankan aplikasi (lihat catatan di bawah); semua pengguna masuk ulang. Berkas *.lama-* bisa dihapus setelah yakin.

## Catatan pindah ke server (perlu ditinjau)
Keputusan "hanya 127.0.0.1, satu pengguna" belum cocok untuk server Ubuntu. Sebelum pindah, tinjau:
host/port & reverse proxy (nginx) + HTTPS, server WSGI (mis. gunicorn) menggantikan `python run.py` (debug=True),
`SESSION_COOKIE_SECURE`, multi-pengguna (saat ini hanya /siapkan untuk akun pertama), pembatas percobaan login,
tombol "Buka folder" (membuka folder di mesin SERVER, bukan di komputer pengguna — sembunyikan atau ganti dengan unduhan),
proses latar memakai thread di dalam proses web (dengan gunicorn: worker harus tetap hidup selama proses,
pertimbangkan antrean bila batch besar/banyak pengguna), dan LibreOffice terpasang di server.

## Verifikasi sebelum selesai
1. `npm run build:css` bila ada kelas Tailwind baru.
2. `python -m unittest -v` harus lulus; tambah uji untuk perilaku baru di `tests/`.
3. Jalankan aplikasi, cek halaman yang diubah di mode terang & gelap, lebar 1366 dan 390 (tanpa scroll horizontal).
4. Commit ke `main` dengan pesan Bahasa Indonesia, lalu push.
