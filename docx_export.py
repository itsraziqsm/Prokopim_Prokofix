"""Pembuatan dokumen Word ukuran F4 (215 x 330 mm)."""
import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Mm, Pt

F4_LEBAR, F4_TINGGI = Mm(215), Mm(330)


def dokumen_f4(font="Arial", ukuran=12):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = F4_LEBAR, F4_TINGGI
    sec.left_margin, sec.right_margin = Cm(3), Cm(2)
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
    normal = doc.styles["Normal"]
    normal.font.name = font
    normal.font.size = Pt(ukuran)
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia", font
    )
    pf = normal.paragraph_format
    pf.space_before = pf.space_after = Pt(0)
    pf.line_spacing = 1.0
    return doc


def contoh_f4():
    doc = dokumen_f4()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("CONTOH DOKUMEN F4")
    r.bold = True
    doc.add_paragraph()
    doc.add_paragraph(
        "Dokumen ini adalah placeholder untuk memastikan ukuran kertas F4 "
        "(215 x 330 mm). Format SPT dan arsip berita akan dibuat di tahap berikutnya."
    )
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
