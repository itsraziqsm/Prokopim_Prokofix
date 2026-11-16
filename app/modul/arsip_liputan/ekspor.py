"""Pembuatan Word liputan: BERITA lalu LEMBAR FOTO (murni Python + python-docx, tanpa Flask).

Templat: app/templat_docx/berita.docx (dari dokumen kantor "13 Oktober Wali - Zoom Meeting.docx").
Isi templat dihapus kecuali sectPr akhir (ukuran F4 & margin tetap), gambar contohnya dibuang beserta
relasinya, lalu diisi ulang memakai gaya "Title" dan "Normal" milik templat.

>>> TEMPLAT SEMENTARA <<<
Bila berkas templat belum ada di repo, templat_sementara() membuat dokumen dengan spesifikasi yang sama
(F4 11907x18711 twip, margin 1440, Title Segoe UI 18 pt tebal rata tengah, Normal Calibri 16 pt warna
0C1014, jarak setelah 8 pt, spasi 1,08). Ganti dengan berkas asli begitu tersedia.
"""
import math
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Emu, Pt, RGBColor, Twips

from .teks import paragraf_berita

JALUR_TEMPLAT = Path(__file__).resolve().parents[2] / "templat_docx" / "berita.docx"

FOTO_PER_LEMBAR_MAKS = 3
JEDA_CM = 0.6               # baris kosong antar kotak (untuk gunting)
CADANGAN_CM = 1.5           # ruang cadangan per halaman: Word menghitung tinggi tabel sedikit lebih besar
                            # daripada LibreOffice (garis tepi, pembulatan); tanpa cadangan cukup, paragraf
                            # setelah tabel terdorong ke halaman baru dan muncul halaman kosong
MARGIN_SEL_CM = 0.25        # jarak isi kotak ke garis putus-putus
UKURAN_KETERANGAN, UKURAN_SUMBER = 11, 10   # pt
GARIS_POTONG = {"val": "dashed", "sz": "8", "space": "0", "color": "7F7F7F"}


# ---------- Templat ----------
def _set_font(gaya, nama):
    """Atur font gaya secara eksplisit (hapus rujukan font tema yang akan menimpanya)."""
    gaya.font.name = nama
    rfonts = gaya.element.get_or_add_rPr().get_or_add_rFonts()
    for atribut in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        rfonts.attrib.pop(qn(atribut), None)
    rfonts.set(qn("w:cs"), nama)


def templat_sementara():
    """TEMPLAT SEMENTARA — dibuat terprogram karena app/templat_docx/berita.docx belum ada."""
    doc = Document()
    seksi = doc.sections[0]
    seksi.page_width, seksi.page_height = Twips(11907), Twips(18711)
    for sisi in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(seksi, sisi, Twips(1440))
    seksi.header_distance = seksi.footer_distance = Twips(708)

    normal = doc.styles["Normal"]
    _set_font(normal, "Calibri")
    normal.font.size = Pt(16)
    normal.font.color.rgb = RGBColor(0x0C, 0x10, 0x14)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.08

    judul = doc.styles["Title"]
    _set_font(judul, "Segoe UI")
    judul.font.size = Pt(18)
    judul.font.bold = True
    judul.font.color.rgb = RGBColor(0x0C, 0x10, 0x14)
    judul.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    judul.paragraph_format.space_after = Pt(8)
    ppr = judul.element.find(qn("w:pPr"))
    if ppr is not None and ppr.find(qn("w:pBdr")) is not None:   # templat bawaan python-docx bergaris bawah
        ppr.remove(ppr.find(qn("w:pBdr")))
    return doc


def buka_templat():
    """(dokumen kosong siap diisi, apakah_templat_sementara)."""
    if JALUR_TEMPLAT.is_file():
        doc, sementara = Document(str(JALUR_TEMPLAT)), False
    else:
        doc, sementara = templat_sementara(), True
    body = doc.element.body
    for el in list(body.iterchildren()):
        if el.tag != qn("w:sectPr"):
            body.remove(el)
    # Gambar contoh di templat (±770 KB) dibuang beserta relasinya agar tidak ikut ke hasil
    for rid, rel in list(doc.part.rels.items()):
        if rel.reltype == RT.IMAGE:
            doc.part.drop_rel(rid)
    return doc, sementara


# ---------- Pembagian lembar ----------
def bagi_lembar(foto, per_lembar):
    """Bagi foto (urut) per lembar: maks. `per_lembar` (1-3) foto; foto bertanda lembar_baru memulai lembar baru."""
    per_lembar = min(max(int(per_lembar or 2), 1), FOTO_PER_LEMBAR_MAKS)
    lembar, kini = [], []
    for f in foto:
        if kini and (len(kini) >= per_lembar or f["lembar_baru"]):
            lembar.append(kini)
            kini = []
        kini.append(f)
    if kini:
        lembar.append(kini)
    return lembar


# ---------- Bantuan XML ----------
_URUTAN_TCPR = ["cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd", "noWrap",
                "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark"]


def _sisipkan_tcpr(tcpr, anak):
    """Sisipkan anak tcPr pada urutan yang benar menurut skema Word (urutan salah = berkas 'rusak')."""
    posisi = _URUTAN_TCPR.index(anak.tag.split("}")[1])
    for i, el in enumerate(tcpr):
        nama = el.tag.split("}")[1]
        if nama in _URUTAN_TCPR and _URUTAN_TCPR.index(nama) > posisi:
            tcpr.insert(i, anak)
            return
    tcpr.append(anak)


def _batas_sel(sel, gaya):
    batas = OxmlElement("w:tcBorders")
    for sisi in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{sisi}")
        for k, v in (gaya or {"val": "nil"}).items():
            el.set(qn(f"w:{k}"), v)
        batas.append(el)
    _sisipkan_tcpr(sel._tc.get_or_add_tcPr(), batas)


def _margin_sel(sel, cm):
    mar = OxmlElement("w:tcMar")
    for sisi in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{sisi}")
        el.set(qn("w:w"), str(int(Cm(cm).twips)))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    _sisipkan_tcpr(sel._tc.get_or_add_tcPr(), mar)


def _baris_tetap(baris, tinggi_cm):
    """Tinggi baris PASTI dan baris tidak boleh terbelah ke halaman berikutnya."""
    baris.height = Cm(tinggi_cm)
    baris.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    trpr = baris._tr.get_or_add_trPr()
    trpr.insert(0, OxmlElement("w:cantSplit"))


def _rapat(paragraf, ukuran_pt=None, rata=WD_ALIGN_PARAGRAPH.CENTER):
    """Paragraf tanpa jarak & spasi tunggal (di dalam kotak, gaya Normal 16 pt/1,08 tidak cocok)."""
    pf = paragraf.paragraph_format
    pf.space_before = pf.space_after = Pt(0)
    pf.line_spacing = 1.0
    pf.alignment = rata
    if ukuran_pt:   # ukuran tanda paragraf ikut menentukan tinggi baris di Word
        ppr = paragraf._p.get_or_add_pPr()
        rpr = OxmlElement("w:rPr")
        for tag in ("w:sz", "w:szCs"):
            el = OxmlElement(tag)
            el.set(qn("w:val"), str(int(ukuran_pt * 2)))
            rpr.append(el)
        ppr.append(rpr)
    return paragraf


def _paragraf_kecil(wadah):
    """Paragraf setinggi 1 pt (pemisah/penutup tabel) agar tidak memakan tempat dan memicu halaman kosong."""
    p = wadah.add_paragraph()
    _rapat(p, 1)
    p.paragraph_format.line_spacing = Pt(1)
    return p


# ---------- Lembar foto ----------
def _baris_teks(teks, lebar_cm, ukuran_pt):
    """Perkiraan jumlah baris teks (rata-rata lebar huruf ~0,5 x ukuran font)."""
    huruf_per_cm = 1 / (ukuran_pt * 0.5 * 0.0353)
    return max(1, math.ceil(len(teks) / max(1, lebar_cm * huruf_per_cm)))


def ukuran_foto(lebar_px, tinggi_px, kotak_tinggi_cm, isi_lebar_cm, keterangan, sumber):
    """(lebar_cm, tinggi_cm) foto agar muat di kotak tanpa gepeng (proporsi tetap)."""
    ruang_teks = 0.0
    if keterangan:
        ruang_teks += _baris_teks(keterangan, isi_lebar_cm, UKURAN_KETERANGAN) * UKURAN_KETERANGAN * 0.0353 * 1.25 + 0.15
    if sumber:
        ruang_teks += _baris_teks(f"Sumber: {sumber}", isi_lebar_cm, UKURAN_SUMBER) * UKURAN_SUMBER * 0.0353 * 1.25
    tinggi_maks = kotak_tinggi_cm - 2 * MARGIN_SEL_CM - ruang_teks - 0.3
    rasio = tinggi_px / lebar_px
    lebar = min(isi_lebar_cm, tinggi_maks / rasio)
    return lebar, lebar * rasio


def _tabel_lembar(doc, isi_lembar, area_lebar, area_tinggi_cm):
    n = len(isi_lembar)
    kotak_cm = (area_tinggi_cm - CADANGAN_CM - (n - 1) * JEDA_CM) / n
    isi_lebar_cm = Emu(area_lebar).cm - 2 * MARGIN_SEL_CM - 0.2

    tabel = doc.add_table(rows=0, cols=1)
    tabel.alignment = WD_TABLE_ALIGNMENT.CENTER
    tabel.autofit = False
    tabel.columns[0].width = area_lebar
    for k, foto in enumerate(isi_lembar):
        if k:   # jeda antar kotak, tanpa garis
            jeda = tabel.add_row()
            _baris_tetap(jeda, JEDA_CM)
            sel = jeda.cells[0]
            sel.width = area_lebar
            _batas_sel(sel, None)
            _rapat(sel.paragraphs[0], 1).paragraph_format.line_spacing = Pt(1)

        baris = tabel.add_row()
        _baris_tetap(baris, kotak_cm)
        sel = baris.cells[0]
        sel.width = area_lebar
        sel.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        _batas_sel(sel, GARIS_POTONG)
        _margin_sel(sel, MARGIN_SEL_CM)

        keterangan, sumber = (foto.get("keterangan") or "").strip(), (foto.get("sumber") or "").strip()
        lebar, tinggi = ukuran_foto(foto["lebar"], foto["tinggi"], kotak_cm, isi_lebar_cm, keterangan, sumber)
        p_foto = _rapat(sel.paragraphs[0])
        if k == 0:
            # Lembar selalu mulai di halaman baru lewat "Page break before" pada baris pertama tabel,
            # BUKAN page break manual di paragraf terpisah (di Word, paragraf itu bisa terdorong ke
            # halaman berikutnya lalu page break-nya menghasilkan halaman kosong).
            p_foto.paragraph_format.page_break_before = True
        p_foto.add_run().add_picture(str(foto["jalur"]), width=Cm(lebar), height=Cm(tinggi))
        if keterangan:
            p = _rapat(sel.add_paragraph(), UKURAN_KETERANGAN)
            p.paragraph_format.space_before = Pt(4)
            p.add_run(keterangan).font.size = Pt(UKURAN_KETERANGAN)
        if sumber:
            p = _rapat(sel.add_paragraph(), UKURAN_SUMBER)
            p.add_run(f"Sumber: {sumber}").font.size = Pt(UKURAN_SUMBER)
    return tabel


# ---------- Dokumen ----------
def buat_dokumen(liputan, foto, tujuan):
    """Tulis Word ke `tujuan`. liputan: dict (judul, isi, foto_per_lembar); foto: list dict
    (jalur, lebar, tinggi, keterangan, sumber, lembar_baru) urut. Mengembalikan info ringkas."""
    doc, sementara = buka_templat()
    seksi = doc.sections[0]
    area_lebar = seksi.page_width - seksi.left_margin - seksi.right_margin
    area_tinggi_cm = Emu(seksi.page_height - seksi.top_margin - seksi.bottom_margin).cm

    doc.add_paragraph(liputan["judul"], style="Title")
    for teks in paragraf_berita(liputan.get("isi", "")):
        doc.add_paragraph(teks, style="Normal")

    lembar = bagi_lembar(foto, liputan.get("foto_per_lembar", 2))
    for ke, isi_lembar in enumerate(lembar):
        if ke:
            _paragraf_kecil(doc)   # pemisah 1 pt agar dua tabel tidak menyatu (tanpa page break)
        _tabel_lembar(doc, isi_lembar, area_lebar, area_tinggi_cm)
    if lembar:
        _paragraf_kecil(doc)   # Word mewajibkan paragraf setelah tabel terakhir

    Path(tujuan).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(tujuan))
    return {"lembar": len(lembar), "templat_sementara": sementara}
