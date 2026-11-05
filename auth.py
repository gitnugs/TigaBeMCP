"""Pemetaan peran dan utilitas akses dokumen MCP TigaBe.-

Peran menentukan tingkat akses dokumen yang boleh dicari di Qdrant. Nilai pada
`akses` harus sama dengan nilai payload `tingkat_akses` di collection Qdrant.

Autentikasi memakai OAuth internal (lihat oauth_provider.py); peran dibaca dari
klaim access token. Skript uji lokal bisa memakai token statis dari roles.json.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from mcp.server.auth.middleware.auth_context import get_access_token
from oauth_provider import PUBLIC_URL, state_sesi

load_dotenv(Path(__file__).with_name(".env"))

log = logging.getLogger("tigabe.auth")


@dataclass(frozen=True)
class Peran:
    nama: str
    label: str
    deskripsi: str
    akses: tuple[str, ...]
    semua_akses: bool = False


# Peran bawaan. Bisa ditimpa/ditambah lewat kunci "roles" di roles.json.
PERAN_BAWAAN: dict[str, dict] = {
    "publik": {
        "label": "Publik",
        "deskripsi": "Pengguna umum; hanya dokumen publik yang sudah berlaku.",
        "akses": ["public"],
    },
    "siswa": {
        "label": "Siswa",
        "deskripsi": "Murid; dokumen publik dan pengumuman tingkat kelas.",
        "akses": ["public", "class"],
    },
    "orang_tua": {
        "label": "Orang Tua/Wali",
        "deskripsi": "Orang tua/wali murid; hanya dokumen publik.",
        "akses": ["public"],
    },
    "guru": {
        "label": "Guru",
        "deskripsi": "Guru/staf sekolah; dokumen publik dan dokumen tingkat kelas.",
        "akses": ["public", "class"],
    },
    "kepala_sekolah": {
        "label": "Kepala Sekolah",
        "deskripsi": "Pimpinan sekolah; seluruh dokumen yang aktif.",
        "akses": [],
        "semua_akses": True,
    },
}

_PATH_ENV = os.environ.get("MCP_ROLES_FILE")
ROLES_PATH = Path(_PATH_ENV).expanduser() if _PATH_ENV else Path(__file__).with_name("roles.json")


def _bangun_peran(nama: str, cfg: dict) -> Peran:
    semua = bool(cfg.get("semua_akses", False))
    akses = tuple(cfg.get("akses", [] if semua else ["public"]))
    if not akses and not semua:
        raise RuntimeError(f"Peran {nama!r} tidak punya akses dokumen dan bukan semua_akses")
    return Peran(
        nama=nama,
        label=str(cfg.get("label", nama)),
        deskripsi=str(cfg.get("deskripsi", "")),
        akses=akses,
        semua_akses=semua,
    )


def muat_peran(path: Path) -> dict[str, Peran]:
    """Muat definisi peran; kunci "roles" di file menimpa peran bawaan."""
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"{path} bukan JSON yang valid: {e}") from e

    mentah = {**PERAN_BAWAAN, **data.get("roles", {})}
    hasil: dict[str, Peran] = {}
    for nama, cfg in mentah.items():
        try:
            hasil[nama] = _bangun_peran(nama, cfg)
        except RuntimeError as e:
            log.warning("%s", e)
    return hasil


PERAN = muat_peran(ROLES_PATH)


def peran_aktif() -> tuple[Peran | None, dict | None]:
    """Peran milik access token OAuth pada permintaan MCP yang berjalan.

    Sumber kebenaran = registry SESI (dapat diperbarui setelah ganti peran di
    /ganti). Klaim token hanya awal; bila registry menyimpan peran berbeda,
    registry yang menang. sesi.butuh_login -> (None, sesi) wajib login dulu.
    """
    token = get_access_token()
    if token is None:
        return None, None
    sesi = state_sesi((token.claims or {}).get("sesi"))
    if sesi is not None:
        if sesi.get("butuh_login"):
            return None, sesi
        nama = sesi.get("peran")
    else:
        nama = (token.claims or {}).get("peran")
    peran = PERAN.get(nama) if isinstance(nama, str) else None
    return peran, sesi


def akses_efektif(peran: Peran) -> list[str] | None:
    """Daftar `tingkat_akses` yang boleh dilihat; None berarti semua."""
    return None if peran.semua_akses else list(peran.akses)


def ringkas_peran(peran: Peran) -> dict:
    return {
        "peran": peran.nama,
        "label": peran.label,
        "deskripsi": peran.deskripsi,
        "akses_dokumen": "semua" if peran.semua_akses else list(peran.akses),
    }


def _ip_lokal() -> list[str]:
    """Deteksi alamat IPv4 LAN host ini (non-loopback) agar akses via IP server
    tidak ditolak dengan 421 Misdirected Request."""
    import socket
    hasil = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            hasil.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    return hasil


def host_diizinkan() -> list[str]:
    host = urlparse(PUBLIC_URL).hostname
    dasar = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*", "[::1]", "[::1]:*"]
    if host:
        dasar += [host, f"{host}:*"]
    # izinkan IP LAN host ini + port wildcard (penting saat bind 0.0.0.0)
    for ip in _ip_lokal():
        dasar += [ip, f"{ip}:*"]
    tambahan = os.environ.get("MCP_ALLOWED_HOSTS", "")
    dasar += [h.strip() for h in tambahan.split(",") if h.strip()]
    return list(dict.fromkeys(dasar))


def origin_diizinkan() -> list[str]:
    u = urlparse(PUBLIC_URL)
    dasar = [
        "http://127.0.0.1:*",
        "http://localhost:*",
    ]
    if u.scheme and u.netloc:
        dasar.append(f"{u.scheme}://{u.netloc}")
    # WorkBuddy memanggil server dari cloud-nya; origin browser tidak selalu ada,
    # tetapi izinkan domain resminya agar klien berbasis web tidak tertolak.
    dasar += [
        "https://workbuddy.ai",
        "https://www.workbuddy.ai",
        "https://codebuddy.ai",
        "https://www.codebuddy.ai",
    ]
    tambahan = os.environ.get("MCP_ALLOWED_ORIGINS", "")
    dasar += [o.strip() for o in tambahan.split(",") if o.strip()]
    return list(dict.fromkeys(dasar))
