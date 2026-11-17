"""Catatan audit cadangan: instance/cadangan/audit.log, satu JSON per baris, hanya ditambah (append-only).

Terpisah dari tabel Log karena tabel itu ikut tertimpa saat database dipulihkan.
"""
import json
from datetime import datetime
from pathlib import Path


def tulis(folder, aksi, pelaku, hasil, rincian=""):
    """pelaku: "web:<nama_pengguna>" atau "terminal"; hasil: "sukses" | "gagal"."""
    Path(folder).mkdir(parents=True, exist_ok=True)
    baris = {"waktu": datetime.now().astimezone().isoformat(timespec="seconds"), "aksi": aksi,
             "pelaku": pelaku, "hasil": hasil, "rincian": str(rincian)[:1000]}
    with open(Path(folder) / "audit.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(baris, ensure_ascii=False) + "\n")


def baca(folder):
    """Semua baris audit (untuk uji & pemeriksaan)."""
    jalur = Path(folder) / "audit.log"
    if not jalur.is_file():
        return []
    return [json.loads(b) for b in jalur.read_text(encoding="utf-8").splitlines() if b.strip()]
