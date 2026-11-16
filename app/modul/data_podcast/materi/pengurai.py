"""Penguraian teks jawaban berformat ringan — logika murni tanpa Flask.

Dipakai bersama oleh tampilan web (html()) dan ekspor Word (ekspor.py), sehingga hasil keduanya sama.

Aturan penulisan (lihat juga contoh di halaman instansi):
    - Satu baris tidak kosong = satu paragraf. Baris kosong diabaikan.
    - "1. teks"  = butir daftar bernomor (nomor yang diketik tidak dipakai; selalu mulai dari 1 per daftar).
    - "- teks"   = butir daftar berpoin.
    - Indentasi 2 spasi atau lebih (atau tab) di bawah sebuah butir = butir bersarang; baris TANPA penanda
      dengan indentasi lebih dalam = paragraf lanjutan butir tersebut.
    - **tebal**, *miring*. Baris yang seluruhnya **teks** menjadi judul kecil.
    - Baris diawali "|" = baris tabel, sel dipisah "|". Baris "|---|---|" menandai baris sebelumnya sebagai header.
    - Spasi ganda, NBSP, dan spasi tepi dirapikan (data di database tetap apa adanya).
    - Tanda yang tidak berpasangan ditampilkan apa adanya; penguraian tidak pernah melempar galat.

Hasil urai() = daftar BLOK (dict):
    {"jenis": "paragraf", "isi": [segmen]}
    {"jenis": "judul",    "isi": [segmen]}
    {"jenis": "daftar",   "bernomor": bool, "butir": [{"isi": [segmen], "anak": [blok...]}]}
        anak = paragraf lanjutan dan/atau daftar bersarang, urut sesuai teks
    {"jenis": "tabel",    "header": [[segmen]...] atau None, "baris": [[[segmen]...]...]}
Segmen = (teks, tebal, miring).
"""
import re

from markupsafe import Markup, escape

PANJANG_MAKS = 20_000          # batas panjang satu jawaban (dicek saat menyimpan)
LEBAR_TAB = 4                  # satu tab dihitung 4 spasi indentasi
SELISIH_SARANG = 2             # indentasi minimal (spasi) agar dianggap lebih dalam

# Semua jenis spasi yang dirapikan menjadi spasi biasa (NBSP, spasi sempit, dll.)
_SPASI = re.compile(r"[ \t  -   　]+")
_NOMOR = re.compile(r"^(\d{1,4})[.)]\s+(.*)$")
_POIN = re.compile(r"^[-•]\s+(.*)$")
_PEMISAH_TABEL = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$")
_TEBAL = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_MIRING = re.compile(r"(?<![*\w])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![*\w])")
_JUDUL = re.compile(r"^\*\*(?=\S)(.+?)(?<=\S)\*\*$")


# ---------- Bantuan teks ----------
def rapikan(teks):
    """Rapikan spasi: NBSP/tab/spasi ganda -> satu spasi, buang spasi tepi."""
    return _SPASI.sub(" ", teks or "").strip()


def ada_isi(teks):
    """True bila teks berisi selain spasi (dipakai untuk menentukan pertanyaan sudah dijawab)."""
    return bool(rapikan(teks))


def _lebar_indentasi(baris):
    lebar = 0
    for huruf in baris:
        if huruf == "\t":
            lebar += LEBAR_TAB
        elif huruf in "   ":
            lebar += 1
        else:
            break
    return lebar


def urai_inline(teks):
    """'Ini **tebal** dan *miring*' -> [(teks, tebal, miring), ...]. Tanda tak berpasangan tetap teks biasa."""
    teks = rapikan(teks)
    hasil = []

    def tambah(potongan, tebal):
        # Di dalam setiap potongan, cari *miring*
        posisi = 0
        for m in _MIRING.finditer(potongan):
            if m.start() > posisi:
                hasil.append((potongan[posisi:m.start()], tebal, False))
            hasil.append((m.group(1), tebal, True))
            posisi = m.end()
        if posisi < len(potongan):
            hasil.append((potongan[posisi:], tebal, False))

    posisi = 0
    for m in _TEBAL.finditer(teks):
        if m.start() > posisi:
            tambah(teks[posisi:m.start()], False)
        tambah(m.group(1), True)
        posisi = m.end()
    if posisi < len(teks):
        tambah(teks[posisi:], False)
    # Gabungkan segmen bersebelahan yang gayanya sama
    rapi = []
    for seg in hasil:
        if not seg[0]:
            continue
        if rapi and rapi[-1][1:] == seg[1:]:
            rapi[-1] = (rapi[-1][0] + seg[0], seg[1], seg[2])
        else:
            rapi.append(seg)
    return rapi


def _sel_tabel(baris):
    """'| a | b \\| c |' -> ['a', 'b | c']. Garis tegak bisa ditulis \\| agar menjadi teks biasa."""
    isi = baris.strip().replace("\\|", "\x00")
    if isi.startswith("|"):
        isi = isi[1:]
    if isi.endswith("|"):
        isi = isi[:-1]
    return [s.replace("\x00", "|") for s in isi.split("|")]


def _buat_tabel(baris_tabel):
    """Ubah kumpulan baris berawalan | menjadi blok tabel. Baris pemisah setelah baris pertama = header."""
    baris, header = [], None
    for teks in baris_tabel:
        if _PEMISAH_TABEL.match(teks.strip()) and "-" in teks:
            if len(baris) == 1 and header is None:
                header = baris.pop()
            continue  # pemisah di posisi lain diabaikan
        baris.append(_sel_tabel(teks))
    semua = ([header] if header else []) + baris
    kolom = max((len(b) for b in semua), default=0)

    def lengkapi(b):
        return [urai_inline(s) for s in b] + [[] for _ in range(kolom - len(b))]

    return {"jenis": "tabel", "header": lengkapi(header) if header else None, "baris": [lengkapi(b) for b in baris]}


# ---------- Penguraian blok ----------
def urai(teks):
    """Urai teks jawaban menjadi daftar blok (lihat docstring modul). Tidak pernah melempar galat."""
    blok = []
    # Tumpukan daftar yang sedang terbuka: (indentasi penanda, blok daftar, wadah tempat daftar berada)
    tumpukan = []
    baris_tabel = []

    def tutup_tabel():
        if baris_tabel:
            blok.append(_buat_tabel(baris_tabel))
            baris_tabel.clear()

    for mentah in (teks or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not rapikan(mentah):
            continue                                   # baris kosong diabaikan
        indentasi = _lebar_indentasi(mentah)
        isi = mentah.strip(" \t  ")

        # --- Tabel (selalu di tingkat teratas) ---
        if isi.startswith("|"):
            tumpukan.clear()
            baris_tabel.append(isi)
            continue
        tutup_tabel()

        m_nomor, m_poin = _NOMOR.match(isi), _POIN.match(isi)
        if m_nomor or m_poin:
            bernomor = bool(m_nomor)
            isi_butir = (m_nomor or m_poin).group(m_nomor and 2 or 1)
            # Tutup daftar yang lebih dalam dari baris ini
            while tumpukan and indentasi <= tumpukan[-1][0] - SELISIH_SARANG:
                tumpukan.pop()
            if tumpukan and indentasi >= tumpukan[-1][0] + SELISIH_SARANG:
                # Butir bersarang: daftar baru di dalam butir terakhir
                wadah = tumpukan[-1][1]["butir"][-1]["anak"]
                daftar = {"jenis": "daftar", "bernomor": bernomor, "butir": []}
                wadah.append(daftar)
                tumpukan.append((indentasi, daftar, wadah))
            elif tumpukan:
                # Tingkat yang sama: lanjutkan daftar, atau mulai daftar baru bila jenisnya berbeda
                ind, daftar, wadah = tumpukan[-1]
                if daftar["bernomor"] != bernomor:
                    daftar = {"jenis": "daftar", "bernomor": bernomor, "butir": []}
                    wadah.append(daftar)
                    tumpukan[-1] = (ind, daftar, wadah)
            else:
                daftar = {"jenis": "daftar", "bernomor": bernomor, "butir": []}
                blok.append(daftar)
                tumpukan.append((indentasi, daftar, blok))
            tumpukan[-1][1]["butir"].append({"isi": urai_inline(isi_butir), "anak": []})
            continue

        # --- Baris tanpa penanda ---
        while tumpukan and indentasi < tumpukan[-1][0] + SELISIH_SARANG:
            tumpukan.pop()
        if tumpukan:
            # Paragraf lanjutan butir terakhir pada daftar terdalam yang masih terbuka
            tumpukan[-1][1]["butir"][-1]["anak"].append({"jenis": "paragraf", "isi": urai_inline(isi)})
            continue
        m_judul = _JUDUL.match(rapikan(isi))
        if m_judul and "**" not in m_judul.group(1):
            blok.append({"jenis": "judul", "isi": urai_inline(m_judul.group(1))})
        else:
            blok.append({"jenis": "paragraf", "isi": urai_inline(isi)})
    tutup_tabel()
    return blok


# ---------- HTML (untuk web) ----------
def _html_inline(segmen):
    bagian = []
    for teks, tebal, miring in segmen:
        h = escape(teks)
        if miring:
            h = Markup("<em>") + h + Markup("</em>")
        if tebal:
            h = Markup("<strong>") + h + Markup("</strong>")
        bagian.append(h)
    return Markup("").join(bagian)


def _html_blok(daftar_blok, kedalaman=0):
    keluaran = []
    for b in daftar_blok:
        jenis = b["jenis"]
        if jenis == "paragraf":
            keluaran.append(Markup("<p>") + _html_inline(b["isi"]) + Markup("</p>"))
        elif jenis == "judul":
            keluaran.append(Markup('<p class="judul-jawaban">') + _html_inline(b["isi"]) + Markup("</p>"))
        elif jenis == "daftar":
            tag = "ol" if b["bernomor"] else "ul"
            butir = []
            for item in b["butir"]:
                isi = _html_inline(item["isi"])
                if item["anak"]:
                    isi = Markup("<p>") + isi + Markup("</p>") + _html_blok(item["anak"], kedalaman + 1)
                butir.append(Markup("<li>") + isi + Markup("</li>"))
            keluaran.append(Markup(f'<{tag} data-tingkat="{kedalaman % 3}">') + Markup("").join(butir)
                            + Markup(f"</{tag}>"))
        elif jenis == "tabel":
            baris_html = []
            if b["header"]:
                sel = Markup("").join(Markup('<th scope="col">') + _html_inline(s) + Markup("</th>") for s in b["header"])
                baris_html.append(Markup("<thead><tr>") + sel + Markup("</tr></thead>"))
            isi = Markup("").join(
                Markup("<tr>") + Markup("").join(Markup("<td>") + _html_inline(s) + Markup("</td>") for s in r)
                + Markup("</tr>") for r in b["baris"])
            baris_html.append(Markup("<tbody>") + isi + Markup("</tbody>"))
            # relative: teks sr-only di dalam tabel tidak lolos keluar wadah gulir (lihat CLAUDE.md)
            keluaran.append(Markup('<div class="relative overflow-x-auto" tabindex="0" role="region" '
                                   'aria-label="Tabel dalam jawaban"><table>') + Markup("").join(baris_html)
                            + Markup("</table></div>"))
    return Markup("").join(keluaran)


def html(teks):
    """Teks jawaban -> HTML aman (semua teks di-escape; tidak ada HTML mentah dari pengguna)."""
    return _html_blok(urai(teks))


# ---------- Teks polos (untuk pencarian & uji) ----------
def _teks_blok(daftar_blok):
    for b in daftar_blok:
        if b["jenis"] in ("paragraf", "judul"):
            yield "".join(s[0] for s in b["isi"])
        elif b["jenis"] == "daftar":
            for item in b["butir"]:
                yield "".join(s[0] for s in item["isi"])
                yield from _teks_blok(item["anak"])
        elif b["jenis"] == "tabel":
            for r in ([b["header"]] if b["header"] else []) + b["baris"]:
                for sel in r:
                    yield "".join(s[0] for s in sel)


def teks_polos(teks):
    """Isi jawaban tanpa tanda format, satu baris per paragraf/butir/sel."""
    return "\n".join(t for t in _teks_blok(urai(teks)) if t)
