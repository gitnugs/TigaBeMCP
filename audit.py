"""Audit log MCP TigaBe: hasil chat/pemanggilan tool disimpan sebagai FILE JSON. --ok

Format file: audit_log.json — satu array JSON `[ {...}, {...} ]` (mudah dibuka,
di-copy, di-parse). Entri juga dipakai halaman /admin/audit.

Isi tiap entri: no, waktu, user, peran, tool, argumen (password disensor),
status, ringkas. Batas memori 500 entri terakhir; file menampung semua
(append) sampai dibersihkan lewat /admin/audit.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger("tigabe.audit")

TZ = ZoneInfo("Asia/Jakarta")
_MAX_MEMORI = 500
_FILE = Path(os.environ.get("MCP_AUDIT_FILE", "")
             or Path(__file__).with_name("audit_log.json"))

_kunci = threading.Lock()
_memori: list[dict] = []
_hitung = 0


def _waktu() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _muat_file() -> list[dict]:
    """Baca array entri dari file JSON; korup/kosong dianggap []."""
    if not _FILE.exists():
        return []
    try:
        data = json.loads(_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        log.warning("audit JSON tidak terbaca, mulai baru: %s", e)
        return []


def _tulis_file(entri: list[dict]) -> None:
    try:
        _FILE.write_text(json.dumps(entri, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    except OSError as e:
        log.warning("audit tulis gagal: %s", e)


def catat_aktivitas(user: str, peran: str, tool: str, argumen: dict,
                    status: str = "ok", ringkas: str = "") -> None:
    """Catat satu pemanggilan tool: masuk memori + append ke audit_log.json."""
    global _hitung
    entri = {
        "no": None,               # diisi setelah gabung file (nomor urut global)
        "waktu": _waktu(),
        "user": user or "-",
        "peran": peran or "-",
        "tool": tool,
        "argumen": _budayakan(argumen),
        "status": status,
        "ringkas": (ringkas or "")[:300],
    }
    with _kunci:
        try:
            file_entri = _muat_file()
        except Exception as e:
            log.warning("audit baca gagal: %s", e)
            file_entri = []
        _hitung += 1
        entri["no"] = (file_entri[-1]["no"] + 1) if file_entri else max(_hitung, 1)
        file_entri.append(entri)
        _tulis_file(file_entri[-2000:])          # pagar: maks 2000 entri di file

        _memori.append(entri)
        if len(_memori) > _MAX_MEMORI:
            _memori.pop(0)


def _budayakan(argumen: dict) -> dict:
    """Salin argumen untuk audit: nilai panjang dipotong, password disensor."""
    bersih: dict = {}
    for k, v in (argumen or {}).items():
        if "password" in k.lower():
            bersih[k] = "********"
            continue
        teks = str(v)
        bersih[k] = teks if len(teks) <= 160 else teks[:157] + "..."
    return bersih


def terakhir(n: int = 100) -> list[dict]:
    """Ambil n entri terbaru (terlama di atas) dari file JSON."""
    with _kunci:
        entri = _muat_file()
    return list(reversed(entri))[: max(1, min(n, 2000))]


def kosongkan() -> int:
    """Hapus seluruh audit (memori + file). Kembalikan jumlah yang dihapus."""
    with _kunci:
        try:
            jumlah = len(_muat_file())
        except Exception:
            jumlah = len(_memori)
        _memori.clear()
    try:
        _FILE.unlink(missing_ok=True)
    except OSError as e:
        log.warning("audit hapus file gagal: %s", e)
    return jumlah
