"""Ekspor Materi Podcast ke Word A4 (python-docx) — tampilan mengikuti dokumen rekap acuan.

Susunan dokumen:
    1. Judul (2 baris, tengah, huruf kapital lewat gaya) + subjudul (keterangan)
    2. Kalimat ringkasan + tabel ringkasan (No, Instansi [tautan ke bagiannya], Pertanyaan, Status)
    3. Per instansi: Heading 1 (dengan bookmark), baris status, lalu tiap pertanyaan ("Pertanyaan"),
       label "JAWABAN", dan isi jawaban (paragraf, judul kecil, daftar bernomor/berpoin, tabel)
    4. Footer: "<judul>  ·  Halaman X dari Y" (field PAGE/NUMPAGES asli Word)

Semua tampilan memakai GAYA BERNAMA (Title, Subjudul, Ringkas, Heading 1, Status Instansi, Pertanyaan,
Label Jawaban, Isi Jawaban, Judul Jawaban, Butir Jawaban, Lanjutan Butir, Sel Tabel, Kaki) agar mudah diedit di Word.
Isi teks pertanyaan & jawaban tidak diubah selain perapian spasi.
"""
import re

from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from .pengurai import rapikan, urai

# ---------- Ukuran (twips; 1 cm = 567 twips) ----------
LEBAR_A4, TINGGI_A4 = 11906, 16838
MARGIN = 1134                                  # 2 cm
LEBAR_TEKS = LEBAR_A4 - 2 * MARGIN             # 9638
IND_JAWABAN = 340                              # 0,6 cm
IND_BUTIR = 360                                # langkah indentasi per tingkat daftar
LEBAR_KOLOM_RINGKASAN = (650, 4700, 1500, 2788)

# ---------- Warna (hex tanpa #) ----------
AKSEN = "1F3A5F"
ABU = "55606E"
ABU_KAKI = "6B7684"
GARIS = "C5CDD6"
LATAR_PERTANYAAN = "EDF1F6"
TAUTAN = "0B4F9C"
# status: (latar, teks)
WARNA_STATUS = {"selesai": ("E3F3E7", "1B5E32"), "proses": ("FFF1CF", "7A4A00"), "belum": ("E9ECF0", "3A4350")}

def _x(xml):
    """Parse potongan XML WordprocessingML; deklarasi namespace w: disisipkan otomatis ke elemen akarnya."""
    if "xmlns:w=" not in xml:
        xml = re.sub(r"^<(w:[A-Za-z]+)", lambda m: f"<{m.group(1)} {nsdecls('w')}", xml, count=1)
    return parse_xml(xml)


_FONT = '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Calibri" w:cs="Calibri"/>'


# ---------- Gaya ----------
def _gaya(doc, style_id, nama, ppr="", rpr="", dasar="Normal", berikut=None, kustom=True):
    """Ganti/buat satu gaya paragraf. ppr/rpr = isi XML <w:pPr>/<w:rPr> (urutan elemen sesuai standar)."""
    styles = doc.styles.element
    for lama in styles.findall(qn("w:style")):
        if lama.get(qn("w:styleId")) == style_id:
            styles.remove(lama)
    atribut_kustom = ' w:customStyle="1"' if kustom else ""
    xml = (f'<w:style w:type="paragraph"{atribut_kustom} '
           f'w:styleId="{style_id}"><w:name w:val="{nama}"/>'
           + (f'<w:basedOn w:val="{dasar}"/>' if dasar else "")
           + (f'<w:next w:val="{berikut}"/>' if berikut else "")
           + "<w:qFormat/>"
           + (f"<w:pPr>{ppr}</w:pPr>" if ppr else "")
           + f"<w:rPr>{_FONT}{rpr}</w:rPr></w:style>")
    styles.append(_x(xml))


def _siapkan_gaya(doc):
    styles = doc.styles.element
    # Bawaan dokumen: Calibri 12 pt, jarak baris 1,2 (288/240), jarak setelah paragraf 6 pt
    lama = styles.find(qn("w:docDefaults"))
    if lama is not None:
        styles.remove(lama)
    styles.insert(0, parse_xml(
        f'<w:docDefaults {nsdecls("w")}><w:rPrDefault><w:rPr>{_FONT}<w:sz w:val="24"/><w:szCs w:val="24"/>'
        '<w:lang w:val="id-ID"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
        '<w:spacing w:after="120" w:line="288" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'))
    _gaya(doc, "Normal", "Normal", dasar=None, kustom=False)
    _gaya(doc, "Title", "Title", kustom=False, berikut="Subjudul",
          ppr='<w:spacing w:before="0" w:after="0" w:line="276" w:lineRule="auto"/><w:jc w:val="center"/>',
          rpr=f'<w:b/><w:bCs/><w:caps/><w:color w:val="{AKSEN}"/><w:sz w:val="38"/><w:szCs w:val="38"/>')
    _gaya(doc, "Subjudul", "Subjudul",
          ppr='<w:spacing w:before="40" w:after="280"/><w:jc w:val="center"/>',
          rpr=f'<w:color w:val="{ABU}"/><w:sz w:val="24"/><w:szCs w:val="24"/>')
    _gaya(doc, "Ringkas", "Ringkas", ppr='<w:keepNext/><w:spacing w:before="120" w:after="160"/>')
    _gaya(doc, "Heading1", "heading 1", kustom=False, berikut="StatusInstansi",
          ppr=f'<w:keepNext/><w:keepLines/><w:pBdr><w:bottom w:val="single" w:sz="8" w:space="3" w:color="{AKSEN}"/>'
              '</w:pBdr><w:spacing w:before="520" w:after="100"/><w:outlineLvl w:val="0"/>',
          rpr=f'<w:b/><w:bCs/><w:color w:val="{AKSEN}"/><w:sz w:val="32"/><w:szCs w:val="32"/>')
    _gaya(doc, "StatusInstansi", "Status Instansi", ppr='<w:keepNext/><w:spacing w:before="60" w:after="120"/>',
          rpr='<w:sz w:val="21"/><w:szCs w:val="21"/>')
    # keepNext TIDAK di gaya: dipasang per paragraf hanya bila pertanyaan punya jawaban
    _gaya(doc, "Pertanyaan", "Pertanyaan", berikut="LabelJawaban",
          ppr=f'<w:keepLines/><w:pBdr><w:left w:val="single" w:sz="24" w:space="8" w:color="{AKSEN}"/></w:pBdr>'
              f'<w:shd w:val="clear" w:color="auto" w:fill="{LATAR_PERTANYAAN}"/>'
              '<w:tabs><w:tab w:val="left" w:pos="680"/></w:tabs>'
              '<w:spacing w:before="260" w:after="100"/><w:ind w:left="680" w:hanging="680"/>',
          rpr="<w:b/><w:bCs/>")
    _gaya(doc, "LabelJawaban", "Label Jawaban", berikut="IsiJawaban",
          ppr=f'<w:keepNext/><w:spacing w:before="60" w:after="40"/><w:ind w:left="{IND_JAWABAN}"/>',
          rpr=f'<w:b/><w:bCs/><w:color w:val="{ABU}"/><w:spacing w:val="30"/><w:sz w:val="19"/><w:szCs w:val="19"/>')
    _gaya(doc, "IsiJawaban", "Isi Jawaban", ppr=f'<w:ind w:left="{IND_JAWABAN}"/>')
    _gaya(doc, "JudulJawaban", "Judul Jawaban", berikut="IsiJawaban",
          ppr=f'<w:keepNext/><w:spacing w:before="160" w:after="60"/><w:ind w:left="{IND_JAWABAN}"/>',
          rpr="<w:b/><w:bCs/>")
    _gaya(doc, "ButirJawaban", "Butir Jawaban", ppr='<w:spacing w:after="80"/>')
    _gaya(doc, "LanjutanButir", "Lanjutan Butir", ppr='<w:spacing w:after="80"/>')
    _gaya(doc, "SelTabel", "Sel Tabel", ppr='<w:spacing w:before="0" w:after="0" w:line="264" w:lineRule="auto"/>')
    _gaya(doc, "SelTabelJawaban", "Sel Tabel Jawaban", dasar="SelTabel", rpr='<w:sz w:val="22"/><w:szCs w:val="22"/>')
    _gaya(doc, "Kaki", "Kaki", ppr='<w:spacing w:before="0" w:after="0"/><w:jc w:val="center"/>',
          rpr=f'<w:color w:val="{ABU_KAKI}"/><w:sz w:val="18"/><w:szCs w:val="18"/>')


# ---------- Penomoran daftar (numbering asli Word) ----------
class Penomoran:
    """Dua definisi daftar (bernomor & berpoin). Setiap daftar di jawaban mendapat w:num baru
    dengan startOverride=1, sehingga penomoran mulai dari 1 per daftar. Daftar LANJUTAN (rantai sama,
    lihat pengurai.urai) memakai w:num yang sama sehingga Word melanjutkan nomornya."""
    ID_BERNOMOR, ID_POIN = 9001, 9002

    def __init__(self, doc):
        self.el = doc.part.numbering_part.element
        format_nomor = ("decimal", "lowerLetter", "lowerRoman")
        poin = ("•", "◦", "▪")
        for abs_id, bernomor in ((self.ID_BERNOMOR, True), (self.ID_POIN, False)):
            tingkat = ""
            for i in range(9):
                kiri = IND_JAWABAN + IND_BUTIR * (i + 1)
                if bernomor:
                    fmt, teks = format_nomor[i % 3], f"%{i + 1}."
                else:
                    fmt, teks = "bullet", poin[i % 3]
                tingkat += (f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/>'
                            f'<w:lvlText w:val="{teks}"/><w:lvlJc w:val="left"/>'
                            f'<w:pPr><w:ind w:left="{kiri}" w:hanging="{IND_BUTIR}"/></w:pPr>'
                            f'<w:rPr>{_FONT}</w:rPr></w:lvl>')
            abstrak = parse_xml(f'<w:abstractNum {nsdecls("w")} w:abstractNumId="{abs_id}">'
                                f'<w:multiLevelType w:val="hybridMultilevel"/>{tingkat}</w:abstractNum>')
            # abstractNum wajib berada sebelum semua w:num
            pertama_num = self.el.find(qn("w:num"))
            if pertama_num is not None:
                pertama_num.addprevious(abstrak)
            else:
                self.el.append(abstrak)
        ada = [int(n.get(qn("w:numId"))) for n in self.el.findall(qn("w:num"))]
        self.berikut = max(ada, default=0) + 1
        self.per_rantai = {}

    def untuk_daftar(self, blok, tingkat, kunci):
        """numId untuk satu blok daftar; kunci = (id pertanyaan, rantai) agar rantai tidak bocor antarjawaban."""
        if blok["bernomor"] and kunci in self.per_rantai:
            return self.per_rantai[kunci]
        nid = self.baru(blok["bernomor"], tingkat)
        if blok["bernomor"]:
            self.per_rantai[kunci] = nid
        return nid

    def baru(self, bernomor, tingkat):
        nid = self.berikut
        self.berikut += 1
        abs_id = self.ID_BERNOMOR if bernomor else self.ID_POIN
        self.el.append(parse_xml(
            f'<w:num {nsdecls("w")} w:numId="{nid}"><w:abstractNumId w:val="{abs_id}"/>'
            f'<w:lvlOverride w:ilvl="{tingkat}"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'))
        return nid


# ---------- Bantuan paragraf & run ----------
def _ppr_tambah(paragraf, xml):
    """Tambahkan elemen ke <w:pPr> pada posisi yang benar (setelah pStyle)."""
    ppr = paragraf._p.get_or_add_pPr()
    el = _x(xml)
    gaya = ppr.find(qn("w:pStyle"))
    if gaya is not None:
        gaya.addnext(el)
    else:
        ppr.insert(0, el)
    return el


def _run(paragraf, teks, tebal=False, miring=False, warna=None, latar=None):
    r = paragraf.add_run(teks)
    if tebal:
        r.bold = True
    if miring:
        r.italic = True
    if warna:
        rpr = r._r.get_or_add_rPr()
        rpr.append(parse_xml(f'<w:color {nsdecls("w")} w:val="{warna}"/>'))
    if latar:
        r._r.get_or_add_rPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{latar}"/>'))
    return r


def _segmen(paragraf, segmen):
    for teks, tebal, miring in segmen:
        _run(paragraf, teks, tebal, miring)


def _tautan_internal(paragraf, teks, bookmark):
    """Tautan ke bookmark di dokumen ini (klik nama instansi -> bagiannya)."""
    tautan = parse_xml(f'<w:hyperlink {nsdecls("w")} w:anchor="{bookmark}" w:history="1"/>')
    paragraf._p.append(tautan)
    r = Run(parse_xml(f'<w:r {nsdecls("w")}><w:rPr><w:color w:val="{TAUTAN}"/><w:u w:val="single"/></w:rPr></w:r>'),
            paragraf)
    r.text = teks
    tautan.append(r._r)


def _bookmark(paragraf, nomor, nama):
    paragraf._p.insert(1 if paragraf._p.pPr is not None else 0,
                       parse_xml(f'<w:bookmarkStart {nsdecls("w")} w:id="{nomor}" w:name="{nama}"/>'))
    paragraf._p.append(parse_xml(f'<w:bookmarkEnd {nsdecls("w")} w:id="{nomor}"/>'))


def _field(paragraf, perintah):
    """Field asli Word (PAGE / NUMPAGES): begin, instrText, separate, nilai sementara, end."""
    for xml in (f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>',
                f'<w:instrText {nsdecls("w")} xml:space="preserve"> {perintah} </w:instrText>',
                f'<w:fldChar {nsdecls("w")} w:fldCharType="separate"/>',
                f'<w:t {nsdecls("w")}>1</w:t>',
                f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>'):
        r = paragraf.add_run()
        r._r.append(parse_xml(xml))


# ---------- Tabel ----------
def _tabel(doc, lebar_kolom, jumlah_baris, ada_header, ind=0):
    """Tabel lebar tetap: border tipis abu-abu, baris tidak terbelah, header berulang di tiap halaman."""
    t = doc.add_table(rows=jumlah_baris, cols=len(lebar_kolom))
    tbl = t._tbl
    tblpr = tbl.tblPr
    for anak in list(tblpr):
        tblpr.remove(anak)
    garis = "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="{GARIS}"/>'
                    for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    for xml in (f'<w:tblW w:w="{sum(lebar_kolom)}" w:type="dxa"/>',
                f'<w:tblInd w:w="{ind}" w:type="dxa"/>' if ind else "",
                f"<w:tblBorders>{garis}</w:tblBorders>",
                '<w:tblLayout w:type="fixed"/>',
                '<w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="110" w:type="dxa"/>'
                '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="110" w:type="dxa"/></w:tblCellMar>',
                '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" '
                'w:noHBand="1" w:noVBand="1"/>'):
        if xml:
            tblpr.append(_x(xml))
    for kolom, lebar in zip(tbl.tblGrid.findall(qn("w:gridCol")), lebar_kolom):
        kolom.set(qn("w:w"), str(lebar))
    for i, baris in enumerate(t.rows):
        trpr = baris._tr.get_or_add_trPr()
        trpr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
        if i == 0 and ada_header:
            trpr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
        for sel, lebar in zip(baris.cells, lebar_kolom):
            tcpr = sel._tc.get_or_add_tcPr()
            for anak in list(tcpr):
                tcpr.remove(anak)
            tcpr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{lebar}" w:type="dxa"/>'))
            tcpr.append(parse_xml(f'<w:vAlign {nsdecls("w")} w:val="center"/>'))
    return t


def _latar_sel(sel, warna):
    """Latar sel (w:shd harus sebelum w:vAlign di dalam tcPr)."""
    sel._tc.tcPr.find(qn("w:vAlign")).addprevious(
        parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{warna}"/>'))


def _paragraf_sel(sel, gaya, rata=None):
    p = sel.paragraphs[0]
    p.style = gaya
    if rata:
        _ppr_tambah(p, f'<w:jc {nsdecls("w")} w:val="{rata}"/>')
    return p


def _sel_header(sel, teks, gaya, rata=None):
    _latar_sel(sel, AKSEN)
    _run(_paragraf_sel(sel, gaya, rata), teks, tebal=True, warna="FFFFFF")


# ---------- Isi jawaban ----------
def _tulis_blok(doc, daftar_blok, penomoran, tingkat=0, dalam_butir=False, kunci_jawaban=0):
    for b in daftar_blok:
        if b["jenis"] == "paragraf":
            setelah_tabel = doc.element.body[-2].tag == qn("w:tbl")
            if dalam_butir:
                # Paragraf lanjutan butir: sejajar dengan teks butir di atasnya
                p = doc.add_paragraph(style="Lanjutan Butir")
                _ppr_tambah(p, f'<w:ind {nsdecls("w")} w:left="{IND_JAWABAN + IND_BUTIR * tingkat}"/>')
            else:
                p = doc.add_paragraph(style="Isi Jawaban")
            if setelah_tabel:   # beri jarak agar teks tidak menempel ke tabel di atasnya
                _ppr_tambah(p, f'<w:spacing {nsdecls("w")} w:before="120"/>')
            _segmen(p, b["isi"])
        elif b["jenis"] == "judul":
            _segmen(doc.add_paragraph(style="Judul Jawaban"), b["isi"])
        elif b["jenis"] == "daftar":
            tingkat_ini = min(tingkat, 8)
            nid = penomoran.untuk_daftar(b, tingkat_ini, (kunci_jawaban, b.get("rantai")))
            for butir in b["butir"]:
                p = doc.add_paragraph(style="Butir Jawaban")
                _ppr_tambah(p, f'<w:numPr {nsdecls("w")}><w:ilvl w:val="{tingkat_ini}"/>'
                               f'<w:numId w:val="{nid}"/></w:numPr>')
                _segmen(p, butir["isi"])
                _tulis_blok(doc, butir["anak"], penomoran, tingkat + 1, dalam_butir=True, kunci_jawaban=kunci_jawaban)
        elif b["jenis"] == "tabel":
            _tabel_jawaban(doc, b, IND_JAWABAN + (IND_BUTIR * tingkat if dalam_butir else 0))


def _tabel_jawaban(doc, b, ind):
    semua = ([b["header"]] if b["header"] else []) + b["baris"]
    kolom = max((len(r) for r in semua), default=0)
    if not kolom:
        return
    lebar_total = LEBAR_TEKS - ind               # tidak melebihi area cetak
    lebar = [lebar_total // kolom] * kolom
    lebar[-1] += lebar_total - sum(lebar)
    t = _tabel(doc, lebar, len(semua), bool(b["header"]), ind=ind)
    for i, isi_baris in enumerate(semua):
        for sel, segmen in zip(t.rows[i].cells, isi_baris):
            if i == 0 and b["header"]:
                _latar_sel(sel, AKSEN)
                p = _paragraf_sel(sel, "Sel Tabel Jawaban")
                for teks, _tebal, miring in segmen:
                    _run(p, teks, True, miring, warna="FFFFFF")
            else:
                _segmen(_paragraf_sel(sel, "Sel Tabel Jawaban"), segmen)


# ---------- Bagian dokumen ----------
def bagi_judul(judul):
    """Bagi judul menjadi dua baris yang panjangnya seimbang (di batas kata). Judul pendek tetap satu baris."""
    kata = rapikan(judul).split(" ")
    if len(kata) < 3 or len(" ".join(kata)) <= 28:
        return [" ".join(kata)]
    terbaik = min(range(1, len(kata)),
                  key=lambda i: abs(len(" ".join(kata[:i])) - len(" ".join(kata[i:]))))
    return [" ".join(kata[:terbaik]), " ".join(kata[terbaik:])]


def nama_bookmark(nomor):
    return f"instansi_{nomor}"


def _status_teks(ins):
    if ins["status"] == "proses":
        return f"   {ins['terjawab']} dari {ins['jumlah']} pertanyaan terjawab"
    return f"   {ins['jumlah']} pertanyaan"


def buat_dokumen(materi, instansi, tujuan):
    """materi: dict (judul, keterangan); instansi: hasil layanan.muat_lengkap(). Menyimpan ke `tujuan`."""
    doc = Document()
    _siapkan_gaya(doc)

    sec = doc.sections[0]
    sec_pr = sec._sectPr
    for anak in sec_pr.findall(qn("w:pgSz")) + sec_pr.findall(qn("w:pgMar")):
        sec_pr.remove(anak)
    sec_pr.insert(0, parse_xml(f'<w:pgMar {nsdecls("w")} w:top="{MARGIN}" w:right="{MARGIN}" w:bottom="{MARGIN}" '
                               f'w:left="{MARGIN}" w:header="708" w:footer="560" w:gutter="0"/>'))
    sec_pr.insert(0, parse_xml(f'<w:pgSz {nsdecls("w")} w:w="{LEBAR_A4}" w:h="{TINGGI_A4}"/>'))

    judul = rapikan(materi["judul"])
    doc.core_properties.title = judul
    doc.core_properties.author = "Super App Prokopim"

    # --- Judul & subjudul ---
    p = doc.add_paragraph(style="Title")
    for i, baris in enumerate(bagi_judul(judul)):
        if i:
            p.add_run().add_break()
        p.add_run(baris)
    if rapikan(materi.get("keterangan")):
        doc.add_paragraph(rapikan(materi["keterangan"]), style="Subjudul")
    else:
        _ppr_tambah(p, f'<w:spacing {nsdecls("w")} w:after="280"/>')

    # --- Ringkasan ---
    jumlah = sum(i["jumlah"] for i in instansi)
    terjawab = sum(i["terjawab"] for i in instansi)
    selesai = sum(1 for i in instansi if i["status"] == "selesai")
    p = doc.add_paragraph(style="Ringkas")
    _run(p, f"{terjawab} dari {jumlah} pertanyaan sudah ada jawabannya", tebal=True)
    _run(p, f" ({selesai} dari {len(instansi)} instansi selesai)."
            + (" Klik nama instansi untuk langsung menuju bagiannya." if instansi else ""))
    if instansi:
        t = _tabel(doc, LEBAR_KOLOM_RINGKASAN, len(instansi) + 1, True)
        for sel, teks, rata in zip(t.rows[0].cells, ("No", "Instansi", "Pertanyaan", "Status"),
                                   ("left", "left", "center", "left")):
            _sel_header(sel, teks, "Sel Tabel", rata)
        for n, ins in enumerate(instansi, start=1):
            sel = t.rows[n].cells
            _run(_paragraf_sel(sel[0], "Sel Tabel"), str(n))
            _tautan_internal(_paragraf_sel(sel[1], "Sel Tabel"), rapikan(ins["nama"]), nama_bookmark(n))
            _run(_paragraf_sel(sel[2], "Sel Tabel", "center"), str(ins["jumlah"]))
            latar, warna = WARNA_STATUS[ins["status"]]
            _latar_sel(sel[3], latar)
            _run(_paragraf_sel(sel[3], "Sel Tabel"), ins["label_status"], tebal=True, warna=warna)

    # --- Per instansi ---
    penomoran = Penomoran(doc)
    for n, ins in enumerate(instansi, start=1):
        h = doc.add_paragraph(style="Heading 1")
        h.add_run(f"{n}.  {rapikan(ins['nama'])}")
        _bookmark(h, n, nama_bookmark(n))

        p = doc.add_paragraph(style="Status Instansi")
        latar, warna = WARNA_STATUS[ins["status"]]
        _run(p, f" {ins['label_status']} ", tebal=True, warna=warna, latar=latar)
        _run(p, _status_teks(ins), warna=ABU)
        if not ins["pertanyaan"]:
            _run(doc.add_paragraph(style="Isi Jawaban"), "Belum ada pertanyaan.", miring=True, warna=ABU)

        for k, tanya in enumerate(ins["pertanyaan"], start=1):
            p = doc.add_paragraph(style="Pertanyaan")
            if tanya["terjawab"]:
                _ppr_tambah(p, f'<w:keepNext {nsdecls("w")}/>')   # pertanyaan tidak terpisah dari jawabannya
            _run(p, f"{n}.{k}", warna=AKSEN)
            _run(p, "\t" + rapikan(tanya["teks"]))
            if tanya["terjawab"]:
                doc.add_paragraph("JAWABAN", style="Label Jawaban")
                _tulis_blok(doc, urai(tanya["jawaban"]), penomoran, kunci_jawaban=(n, k))

    # Word mewajibkan paragraf setelah tabel terakhir sebelum akhir dokumen
    tubuh = doc.element.body
    if tubuh[-2].tag == qn("w:tbl"):
        _ppr_tambah(doc.add_paragraph(style="Isi Jawaban"), f'<w:spacing {nsdecls("w")} w:after="0"/>')

    # --- Footer: "<judul>  ·  Halaman X dari Y" ---
    kaki = sec.footer.paragraphs[0]
    kaki.style = "Kaki"
    kaki.add_run(f"{judul}  ·  Halaman ")
    _field(kaki, "PAGE")
    kaki.add_run(" dari ")
    _field(kaki, "NUMPAGES")

    doc.save(tujuan)
    return tujuan
