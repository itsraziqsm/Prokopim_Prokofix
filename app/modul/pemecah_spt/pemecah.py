"""Logika inti Pemecah SPT — murni Python + python-docx, tanpa Flask (mudah diuji).

Istilah:
    body      = isi utama dokumen Word (<w:body>), berisi paragraf (<w:p>), tabel (<w:tbl>), dst.
    run       = potongan teks dengan format yang sama di dalam paragraf (<w:r>)
    sectPr    = pengaturan seksi: ukuran kertas, margin, header/footer
"""
import copy
import re
import unicodedata
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from docx import Document

# ---------- Konstanta ----------
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
JUDUL_NORMAL = "surat perintah tugas"
UKURAN_MAKS = 25 * 1024 * 1024          # 25 MB berkas unggahan
ENTRI_ZIP_MAKS = 5000                   # batas jumlah isi arsip .docx
UKURAN_TERDEKOMPRESI_MAKS = 300 * 1024 * 1024   # cegah "zip bomb"
ELEMEN_CARI_NOMOR = 12                  # nomor dicari di 12 potong teks pertama setelah judul
PANJANG_CUPLIKAN = 180

TIPE_MAKRO = "application/vnd.ms-word.document.macroEnabled.main+xml"


def q(tag):
    """Nama tag lengkap dengan namespace Word, mis. q('p') -> '{...}p'."""
    return f"{{{W}}}{tag}"


class GalatBerkas(Exception):
    """Galat yang pesannya aman & layak ditampilkan ke pengguna."""


# ---------- Hasil analisis ----------
@dataclass
class InfoSPT:
    urutan: int              # 1, 2, 3, ... sesuai kemunculan di batch
    mulai: int               # indeks elemen body (inklusif)
    akhir: int               # indeks elemen body (eksklusif)
    nomor: str
    nomor_terbaca: bool
    cuplikan: str
    kembar: bool = False
    nama: str = ""           # nama berkas tanpa ekstensi (diisi penamaan.py)


@dataclass
class HasilAnalisis:
    daftar: list
    peringatan: list = field(default_factory=list)

    def ke_dict(self):
        return {"daftar": [asdict(i) for i in self.daftar], "peringatan": list(self.peringatan)}

    @classmethod
    def dari_dict(cls, data):
        return cls([InfoSPT(**i) for i in data["daftar"]], list(data["peringatan"]))


# ---------- 1. Validasi unggahan ----------
def validasi_berkas(jalur: Path, nama_asli: str):
    """Memastikan berkas benar-benar .docx yang aman dibuka. Melempar GalatBerkas bila tidak."""
    akhiran = Path(nama_asli or "").suffix.lower()
    if akhiran == ".doc":
        raise GalatBerkas("Format .doc (Word 97-2003) belum didukung. Buka di Word, lalu Simpan Sebagai .docx.")
    if akhiran == ".docm":
        raise GalatBerkas("Berkas .docm berisi makro dan tidak diterima. Simpan Sebagai .docx biasa.")
    if akhiran != ".docx":
        raise GalatBerkas("Hanya berkas Word .docx yang diterima.")

    ukuran = jalur.stat().st_size
    if ukuran == 0:
        raise GalatBerkas("Berkas kosong.")
    if ukuran > UKURAN_MAKS:
        raise GalatBerkas("Berkas lebih dari 25 MB.")

    with open(jalur, "rb") as f:
        if f.read(4) != b"PK\x03\x04":  # semua .docx adalah arsip ZIP
            raise GalatBerkas("Berkas bukan dokumen .docx yang valid (mungkin rusak atau hanya diganti namanya).")

    try:
        with zipfile.ZipFile(jalur) as arsip:
            isi = arsip.infolist()
            if len(isi) > ENTRI_ZIP_MAKS:
                raise GalatBerkas("Struktur berkas tidak wajar (terlalu banyak bagian).")
            if sum(i.file_size for i in isi) > UKURAN_TERDEKOMPRESI_MAKS:
                raise GalatBerkas("Struktur berkas tidak wajar (isi terlalu besar).")
            nama_isi = {i.filename for i in isi}
            if "word/document.xml" not in nama_isi:
                raise GalatBerkas("Berkas bukan dokumen Word (.docx).")
            if "word/vbaProject.bin" in nama_isi or (
                    "[Content_Types].xml" in nama_isi
                    and TIPE_MAKRO.encode() in arsip.read("[Content_Types].xml")):
                raise GalatBerkas("Berkas berisi makro (.docm) dan tidak diterima. Simpan Sebagai .docx biasa.")
    except zipfile.BadZipFile:
        raise GalatBerkas("Berkas .docx rusak dan tidak dapat dibuka.")

    try:
        Document(str(jalur))
    except Exception:  # python-docx melempar beragam jenis galat untuk berkas rusak
        raise GalatBerkas("Berkas .docx rusak atau tidak dapat dibaca.")


# ---------- 2. Membaca teks & format ----------
def normalisasi(teks):
    """NFKC (NBSP -> spasi biasa, dsb.), spasi berlebih jadi satu, huruf kecil (casefold)."""
    teks = unicodedata.normalize("NFKC", teks)
    return re.sub(r"\s+", " ", teks).strip().casefold()


def rapikan(teks):
    """Seperti normalisasi, tetapi huruf besar/kecil dipertahankan (untuk ditampilkan)."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", teks)).strip()


def _runs(paragraf):
    """Run teks milik paragraf (tidak termasuk teks terhapus & isi kotak teks)."""
    return paragraf.xpath(".//w:r[not(ancestor::w:del) and not(ancestor::w:txbxContent)]")


def teks_run(run):
    bagian = []
    for anak in run:
        if anak.tag == q("t"):
            bagian.append(anak.text or "")
        elif anak.tag in (q("tab"), q("br"), q("cr")):
            bagian.append(" ")
    return "".join(bagian)


def teks_elemen(el):
    """Semua teks di dalam elemen (paragraf, tabel, sel, ...)."""
    bagian = []
    for node in el.iter(q("t"), q("tab"), q("br"), q("cr"), q("p")):
        if node.tag == q("t"):
            bagian.append(node.text or "")
        else:
            bagian.append(" ")
    return "".join(bagian)


def _bernilai_benar(el):
    """Untuk properti saklar seperti <w:b>: tanpa w:val = aktif; '0'/'false'/'off' = nonaktif."""
    nilai = el.get(q("val"))
    return nilai is None or nilai.lower() not in ("0", "false", "off")


def _dari_rpr(rpr, tag):
    """True/False bila rPr menyatakan properti; None bila tidak menyebut."""
    if rpr is None:
        return None
    el = rpr.find(q(tag))
    if el is None:
        return None
    if tag == "u":
        nilai = el.get(q("val"))
        return nilai is None or nilai.lower() != "none"
    return _bernilai_benar(el)


class GayaDokumen:
    """Menghitung bold/underline EFEKTIF sebuah run:
    format langsung run -> gaya karakter -> gaya paragraf (beserta basedOn) -> docDefaults."""

    def __init__(self, doc):
        gaya_el = doc.styles.element
        self.gaya = {s.get(q("styleId")): s for s in gaya_el.findall(q("style"))}
        self.gaya_paragraf_bawaan = next(
            (s.get(q("styleId")) for s in gaya_el.findall(q("style"))
             if s.get(q("type")) == "paragraph" and _bernilai_benar_default(s)), None)
        self.rpr_bawaan = gaya_el.find(f"{q('docDefaults')}/{q('rPrDefault')}/{q('rPr')}")

    def _dari_gaya(self, id_gaya, tag):
        dikunjungi = set()
        while id_gaya and id_gaya not in dikunjungi:
            dikunjungi.add(id_gaya)
            gaya = self.gaya.get(id_gaya)
            if gaya is None:
                return None
            hasil = _dari_rpr(gaya.find(q("rPr")), tag)
            if hasil is not None:
                return hasil
            dasar = gaya.find(q("basedOn"))
            id_gaya = dasar.get(q("val")) if dasar is not None else None
        return None

    def efektif(self, run, paragraf, tag):
        rpr = run.find(q("rPr"))
        hasil = _dari_rpr(rpr, tag)
        if hasil is not None:
            return hasil
        if rpr is not None and rpr.find(q("rStyle")) is not None:
            hasil = self._dari_gaya(rpr.find(q("rStyle")).get(q("val")), tag)
            if hasil is not None:
                return hasil
        ppr = paragraf.find(q("pPr"))
        pstyle = ppr.find(q("pStyle")) if ppr is not None else None
        id_gaya = pstyle.get(q("val")) if pstyle is not None else self.gaya_paragraf_bawaan
        hasil = self._dari_gaya(id_gaya, tag)
        if hasil is not None:
            return hasil
        return bool(_dari_rpr(self.rpr_bawaan, tag))


def _bernilai_benar_default(gaya):
    nilai = gaya.get(q("default"))
    return nilai is not None and nilai.lower() in ("1", "true", "on")


def adalah_judul_spt(el, gaya: GayaDokumen):
    """Paragraf berisi tepat 'Surat Perintah Tugas' dengan SEMUA run bertext bold DAN underline."""
    if el.tag != q("p"):
        return False
    runs = _runs(el)
    if normalisasi("".join(teks_run(r) for r in runs)) != JUDUL_NORMAL:
        return False
    bertext = [r for r in runs if teks_run(r).strip()]
    return bool(bertext) and all(
        gaya.efektif(r, el, "b") and gaya.efektif(r, el, "u") for r in bertext)


def _punya_isi_visual(el):
    """Gambar, objek, atau tabel di dalam elemen."""
    return any(True for _ in el.iter(q("drawing"), q("pict"), q("object"), q("tbl")))


def adalah_kosong(el):
    """Paragraf tanpa teks, gambar, atau tabel (termasuk paragraf yang hanya berisi page break)."""
    return el.tag == q("p") and not teks_elemen(el).strip() and not _punya_isi_visual(el)


def elemen_body(doc):
    """Daftar elemen body tanpa sectPr penutup body."""
    return [el for el in doc.element.body.iterchildren() if el.tag != q("sectPr")]


def _sectpr_paragraf(el):
    if el.tag != q("p"):
        return None
    ppr = el.find(q("pPr"))
    return ppr.find(q("sectPr")) if ppr is not None else None


# ---------- 3. Analisis ----------
_POLA_NOMOR = re.compile(r"^nomor\b\s*[:：]?\s*(.*)$", re.IGNORECASE)


def _potongan_teks(elemen):
    """Pecah elemen menjadi potongan teks: satu paragraf = satu potongan, satu sel tabel = satu potongan."""
    for el in elemen:
        if el.tag == q("tbl"):
            for sel in el.iter(q("tc")):
                # Abaikan sel yang berisi tabel bertingkat (isinya akan muncul dari sel dalamnya)
                if sel.find(f".//{q('tbl')}") is None:
                    yield rapikan(teks_elemen(sel))
        else:
            yield rapikan(teks_elemen(el))


def cari_nomor(potongan):
    """Mengembalikan (nomor, indeks_potongan_terpakai) atau (None, set())."""
    for i, teks in enumerate(potongan):
        cocok = _POLA_NOMOR.match(teks)
        if not cocok:
            continue
        nilai, terpakai = cocok.group(1).strip(), {i}
        j = i
        # "Nomor" | ":" | "800/..." di sel/paragraf berbeda
        while not nilai.lstrip(":：").strip() and j + 1 < len(potongan):
            j += 1
            terpakai.add(j)
            nilai = potongan[j]
        nilai = nilai.lstrip(":：").strip()
        if any(ch.isalnum() for ch in nilai):
            return nilai[:150], terpakai
        return None, set()
    return None, set()


def analisis(jalur: Path):
    """Mendeteksi semua SPT dalam berkas. Melempar GalatBerkas bila tidak ada judul."""
    doc = Document(str(jalur))
    gaya = GayaDokumen(doc)
    elemen = elemen_body(doc)
    posisi_judul = [i for i, el in enumerate(elemen) if adalah_judul_spt(el, gaya)]
    if not posisi_judul:
        raise GalatBerkas(
            "Tidak ditemukan judul SPT. Judul harus berupa paragraf tersendiri bertuliskan "
            "\"SURAT PERINTAH TUGAS\" yang dicetak tebal dan bergaris bawah.")

    peringatan = []
    sebelum = [el for el in elemen[:posisi_judul[0]] if not adalah_kosong(el)]
    if sebelum:
        peringatan.append(f"Ada {len(sebelum)} paragraf/tabel sebelum SPT pertama. Bagian ini tidak ikut dipecah.")

    semua_sectpr = [s for s in (_sectpr_paragraf(el) for el in elemen) if s is not None]
    semua_sectpr.append(doc.element.body.find(q("sectPr")))
    if len(semua_sectpr) > 1:
        peringatan.append(f"Dokumen memiliki {len(semua_sectpr)} seksi. Tiap SPT memakai pengaturan halaman "
                          "dan kop dari seksi tempat judulnya berada; periksa hasilnya.")
    if any(s is not None and s.find(q("titlePg")) is not None and _bernilai_benar(s.find(q("titlePg")))
           for s in semua_sectpr):
        peringatan.append("Opsi \"Halaman pertama berbeda\" aktif. Kop di halaman pertama tiap SPT "
                          "bisa berbeda dari halaman berikutnya; periksa hasilnya.")

    daftar = []
    batas = posisi_judul[1:] + [len(elemen)]
    for urutan, (mulai, akhir) in enumerate(zip(posisi_judul, batas), start=1):
        while akhir > mulai + 1 and adalah_kosong(elemen[akhir - 1]):
            akhir -= 1
        potongan = [t for t in _potongan_teks(elemen[mulai + 1:akhir]) if t][:ELEMEN_CARI_NOMOR]
        nomor, terpakai = cari_nomor(potongan)
        sisa = " ".join(t for i, t in enumerate(potongan) if i not in terpakai)
        cuplikan = sisa if len(sisa) <= PANJANG_CUPLIKAN else sisa[:PANJANG_CUPLIKAN].rstrip() + "…"
        daftar.append(InfoSPT(
            urutan=urutan, mulai=mulai, akhir=akhir,
            nomor=nomor or f"SPT_urut-{urutan}", nomor_terbaca=nomor is not None, cuplikan=cuplikan))

    # Penanda "Nomor kembar" (tanpa memperhatikan huruf besar/kecil)
    hitung = {}
    for info in daftar:
        if info.nomor_terbaca:
            hitung[info.nomor.casefold()] = hitung.get(info.nomor.casefold(), 0) + 1
    for info in daftar:
        info.kembar = info.nomor_terbaca and hitung[info.nomor.casefold()] > 1

    tak_terbaca = sum(not i.nomor_terbaca for i in daftar)
    if tak_terbaca:
        peringatan.append(f"{tak_terbaca} SPT tanpa nomor yang terbaca; nama berkasnya memakai urutan (SPT_urut-N).")
    return HasilAnalisis(daftar, peringatan)


# ---------- 4. Pemecahan ----------
JENIS_REFERENSI = ("headerReference", "footerReference")


def _lengkapi_referensi(sectpr_terpilih, sectpr_sebelumnya):
    """Seksi Word tanpa header/footer sendiri mewarisi dari seksi sebelumnya.
    Karena hasil pecahan hanya punya satu seksi, salin referensi warisan itu agar kop tetap ada."""
    for jenis in JENIS_REFERENSI:
        for tipe in ("default", "first", "even"):
            if any(r.get(q("type"), "default") == tipe for r in sectpr_terpilih.findall(q(jenis))):
                continue
            for lama in reversed(sectpr_sebelumnya):
                ref = next((r for r in lama.findall(q(jenis)) if r.get(q("type"), "default") == tipe), None)
                if ref is not None:
                    sectpr_terpilih.insert(0, copy.deepcopy(ref))  # referensi wajib di awal sectPr
                    break


def _buang_page_break_tepi(paragraf, di_awal):
    """Hapus page break sebelum teks pertama (di_awal) atau setelah teks terakhir, agar tidak ada halaman kosong."""
    urutan = [n for n in paragraf.iter(q("t"), q("br"))
              if n.tag == q("br") and n.get(q("type")) == "page" or (n.tag == q("t") and (n.text or "").strip())]
    if not di_awal:
        urutan.reverse()
    for n in urutan:
        if n.tag == q("t"):
            break
        n.getparent().remove(n)


def pecah_satu(jalur_asli: Path, info: InfoSPT, tujuan: Path):
    """Membuat satu .docx berisi rentang SPT `info`.
    Dokumen asli dimuat ulang lalu elemen di luar rentang dihapus, sehingga kop (header), gaya,
    ukuran kertas F4, margin, gambar, dan penomoran tetap utuh."""
    doc = Document(str(jalur_asli))
    body = doc.element.body
    elemen = elemen_body(doc)
    sectpr_body = body.find(q("sectPr"))

    # Seksi tempat judul: sectPr paragraf pertama di/atau setelah judul, atau sectPr body
    daftar_sectpr = [(i, s) for i, s in ((i, _sectpr_paragraf(el)) for i, el in enumerate(elemen)) if s is not None]
    terpilih = next((s for i, s in daftar_sectpr if i >= info.mulai), sectpr_body)
    sebelumnya = [s for i, s in daftar_sectpr if s is not terpilih and i < info.mulai]
    sectpr_baru = copy.deepcopy(terpilih) if terpilih is not None else None
    if sectpr_baru is not None:
        _lengkapi_referensi(sectpr_baru, sebelumnya)

    for i, el in enumerate(elemen):
        if not info.mulai <= i < info.akhir:
            body.remove(el)
    for el in elemen[info.mulai:info.akhir]:
        s = _sectpr_paragraf(el)
        if s is not None:
            s.getparent().remove(s)  # cegah section break liar

    if sectpr_baru is not None:
        if sectpr_body is not None:
            body.replace(sectpr_body, sectpr_baru)
        else:
            body.append(sectpr_baru)

    tersisa = elemen_body(doc)
    if tersisa and tersisa[0].tag == q("p"):
        _buang_page_break_tepi(tersisa[0], di_awal=True)
    if tersisa and tersisa[-1].tag == q("p"):
        _buang_page_break_tepi(tersisa[-1], di_awal=False)

    tujuan.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(tujuan))
