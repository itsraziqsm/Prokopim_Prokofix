"""Pembuat berkas .docx contoh untuk uji Pemecah SPT (dibangun dengan python-docx)."""
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Mm

KOP = "PEMERINTAH KABUPATEN CONTOH — SEKRETARIAT DAERAH"


def dokumen_f4():
    doc = Document()
    seksi = doc.sections[0]
    seksi.page_width, seksi.page_height = Mm(215), Mm(330)
    seksi.left_margin, seksi.right_margin = Mm(30), Mm(20)
    seksi.header.paragraphs[0].text = KOP
    return doc


def judul(doc, pecah=False, bold=True, underline=True, gaya=None, teks="SURAT PERINTAH TUGAS"):
    p = doc.add_paragraph(style=gaya)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for bagian in (["SURAT ", "PERINTAH", " TUGAS"] if pecah else [teks]):
        r = p.add_run(bagian)
        if gaya is None:
            r.bold, r.underline = bold, underline
    return p


def gaya_judul(doc):
    """Gaya paragraf 'Judul SPT' yang mewarisi bold+underline dari gaya dasarnya (basedOn)."""
    dasar = doc.styles.add_style("Judul Dasar", WD_STYLE_TYPE.PARAGRAPH)
    dasar.font.bold, dasar.font.underline = True, True
    gaya = doc.styles.add_style("Judul SPT", WD_STYLE_TYPE.PARAGRAPH)
    gaya.base_style = dasar
    return gaya


def isi(doc, nomor, nama="Budi Santoso", nomor_di_tabel=False):
    if nomor is not None:
        if nomor_di_tabel:
            sel = doc.add_table(rows=1, cols=3).rows[0].cells
            sel[0].text, sel[1].text, sel[2].text = "Nomor", ":", nomor
        else:
            doc.add_paragraph(f"Nomor\t: {nomor}").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("Dasar\t: Peraturan Bupati Contoh Nomor 12 Tahun 2024.")
    doc.add_paragraph("MEMERINTAHKAN:")
    tabel = doc.add_table(rows=1, cols=2).rows[0].cells
    tabel[0].text, tabel[1].text = "Kepada", nama
    doc.add_paragraph(f"Untuk\t: Meliput kegiatan bersama {nama}.")
    doc.add_paragraph("")


def ganti_halaman(doc):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def batch_contoh(jalur):
    """6 SPT: nomor kembar (2x), judul terpecah, judul dari gaya, nomor di tabel, nomor tidak terbaca.
    Ditambah pengecoh: kalimat biasa berisi frasa judul, dan judul tanpa garis bawah."""
    doc = dokumen_f4()
    gaya = gaya_judul(doc)
    doc.add_paragraph("Catatan pengantar sebelum SPT pertama.")
    ganti_halaman(doc)   # catatan ada di halaman sendiri, jadi tidak termasuk SPT pertama
    data = [
        dict(nomor="800.1.11.1/101/Prokopim/2026", nama="Budi Santoso"),
        dict(nomor="800.1.11.1/102/Prokopim/2026", nama="Siti Aminah", pecah=True),
        dict(nomor="800.1.11.1/101/Prokopim/2026", nama="Andi Wijaya"),           # kembar dengan SPT 1
        dict(nomor="800.1.11.1/103/Prokopim/2026", nama="Rina Lestari", gaya=gaya),
        dict(nomor="800.1.11.1/104/Prokopim/2026", nama="Dewi Kartika", di_tabel=True),
        dict(nomor=None, nama="Joko Susilo"),                                       # nomor tidak terbaca
    ]
    for i, d in enumerate(data):
        if i:
            ganti_halaman(doc)
        judul(doc, pecah=d.get("pecah", False), gaya=d.get("gaya"))
        isi(doc, d["nomor"], d["nama"], nomor_di_tabel=d.get("di_tabel", False))
        if i == 1:
            p = doc.add_paragraph()
            r = p.add_run("Berdasarkan Surat Perintah Tugas Nomor 5 Tahun 2026 yang lalu.")
            r.bold = r.underline = True
            judul(doc, underline=False)   # judul tanpa garis bawah: bukan awal SPT
    doc.save(str(jalur))
    return jalur


KOP_BADAN = ["PEMERINTAH KOTA CONTOH", "SEKRETARIAT DAERAH", "BAGIAN PROTOKOL DAN KOMUNIKASI PIMPINAN"]


def kop_di_badan(doc, sebagai_tabel=False):
    """Kop surat yang diketik di BADAN dokumen (bukan di Header), tepat di atas judul."""
    if sebagai_tabel:
        sel = doc.add_table(rows=1, cols=2).rows[0].cells
        sel[0].text = "[logo]"
        sel[1].text = "\n".join(KOP_BADAN)
    else:
        for baris in KOP_BADAN:
            doc.add_paragraph(baris).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("")


def batch_kop_di_badan(jalur, pemisah="page_break", jumlah=3):
    """Beberapa SPT yang masing-masing diawali kop di badan dokumen.
    pemisah: 'page_break' (Ctrl+Enter di paragraf sendiri), 'akhir_paragraf' (page break di akhir paragraf
    terakhir SPT), 'page_break_before' (opsi paragraf kop), 'seksi' (section break halaman baru)."""
    doc = Document()
    seksi = doc.sections[0]
    seksi.page_width, seksi.page_height = Mm(215), Mm(330)
    for i in range(1, jumlah + 1):
        if i > 1:
            if pemisah == "page_break":
                ganti_halaman(doc)
            elif pemisah == "akhir_paragraf":
                doc.paragraphs[-1].add_run().add_break(WD_BREAK.PAGE)
            elif pemisah == "seksi":
                doc.add_section()
        awal = len(doc.paragraphs)
        kop_di_badan(doc, sebagai_tabel=(i == 2 and pemisah != "page_break_before"))
        if pemisah == "page_break_before" and i > 1:
            doc.paragraphs[awal].paragraph_format.page_break_before = True
        judul(doc)
        isi(doc, f"0059/{i}/SPT-UL/2026", f"Pegawai {i}")
        doc.add_paragraph(f"Penandatangan SPT {i}")
    doc.save(str(jalur))
    return jalur
