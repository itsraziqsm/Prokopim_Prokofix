"""PDF contoh untuk uji Gabungkan PDF, dibuat dengan pypdf (halaman kosong berukuran berbeda).

Ukuran halaman dipakai sebagai "sidik" urutan: lebar halaman ke-i dari PDF "a" = 100 + i, dari "b" = 200 + i, dst.,
sehingga urutan halaman hasil penggabungan bisa diperiksa dari lebar halamannya.
"""
import io

from pypdf import PdfWriter


def pdf(jumlah_halaman=3, dasar=100, sandi=None, metadata=None, aksi_buka=False):
    """Bytes PDF dengan `jumlah_halaman` halaman; halaman ke-i berukuran (dasar + i) x (dasar + i + 50)."""
    penulis = PdfWriter()
    for i in range(jumlah_halaman):
        penulis.add_blank_page(width=dasar + i, height=dasar + i + 50)
    if metadata:
        penulis.add_metadata(metadata)
    if aksi_buka:
        # Tindakan otomatis tingkat dokumen yang TIDAK boleh ikut ke hasil penggabungan
        from pypdf.generic import DictionaryObject, NameObject, TextStringObject
        penulis._root_object[NameObject("/OpenAction")] = DictionaryObject({
            NameObject("/S"): NameObject("/JavaScript"), NameObject("/JS"): TextStringObject("app.alert('x')")})
    if sandi:
        penulis.encrypt(sandi, algorithm="RC4-128")   # RC4 tidak butuh paket tambahan
    hasil = io.BytesIO()
    penulis.write(hasil)
    return hasil.getvalue()


def pdf_rusak():
    """Diawali tanda %PDF- tetapi isinya bukan PDF yang sah."""
    return b"%PDF-1.7\n" + b"ini bukan isi pdf yang benar\n" * 20


def bukan_pdf():
    return b"Ini berkas teks biasa, bukan PDF.\n" * 10
