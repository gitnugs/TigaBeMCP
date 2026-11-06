"""Halaman admin: kelola pengguna login + definisi peran.

Rute:
  /admin            -> halaman web (fetch + form)
  /admin/user/simpan  (POST)  -> tambah/ubah user (username, peran, password, nama)
  /admin/user/hapus   (POST)  -> hapus user
  /admin/peran/simpan (POST)  -> tambah/ubah definisi peran (akses dokumen)
  /admin/peran/hapus  (POST)  -> hapus definisi peran kustom

Akses: hanya dari localhost, plus password admin (env MCP_ADMIN_PASSWORD,
kosong = tanpa password; untuk uji lokal). Halaman memakai form POST biasa.

File yang ditulis: login_users.json (hash scrypt) dan roles.json.
"""
from __future__ import annotations

import html
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit

import audit as audit_lib

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from oauth_provider import hash_password, _LOGIN_FILE, muat_users
from auth import PERAN_BAWAAN
from auth import ROLES_PATH

log = logging.getLogger("tigabe.admin")

_PERAN_FILE_TULIS = ROLES_PATH

_SANDI = os.environ.get("MCP_ADMIN_PASSWORD", "").strip()

_AKSES_TINGKAT = ("public", "class", "internal", "restricted")


# ---------------------------------------------------------------------------
# Ikon (SVG stroke 1.75, konsisten 20x20)
# ---------------------------------------------------------------------------
def _svg(path: str, *d: str) -> str:
    """Bungkus path jadi ikon SVG inline yang konsisten."""
    bagian = "".join(f'<path d="{p}"/>' for p in d)
    return (f'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" '
            f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{bagian}</svg>')


_IKON = {
    "users": _svg(
        '<circle cx="7.5" cy="6" r="3.25"/><path d="M2.5 17a5 5 0 0 1 10 0"/>'
        '<path d="M14 4.25a3.25 3.25 0 0 1 0 6.1"/><path d="M15.5 12.6a5 5 0 0 1 3 4.4"/>',
    ),
    "audit": _svg(
        '<rect x="4.5" y="3.5" width="11" height="13.5" rx="2"/>'
        '<path d="M7.25 3.5h5.5v2a.5.5 0 0 1-.5.5h-4.5a.5.5 0 0 1-.5-.5z"/>'
        '<path d="M7.25 9h5.5M7.25 12h5.5M7.25 15h3.25"/>',
    ),
    "book": _svg(
        '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H16v14.25H6.5A2.5 2.5 0 0 0 4 18.75z"/>'
        '<path d="M4 18.75V4.5A2.5 2.5 0 0 1 6.5 2"/>',
    ),
    "plus": _svg('<path d="M10 4.25v11.5M4.25 10h11.5"/>'),
    "trash": _svg(
        '<path d="M4 6h12M8.25 6V4.5a1 1 0 0 1 1-1h1.5a1 1 0 0 1 1 1V6"/>'
        '<path d="M6.5 6l.7 10.2a1.5 1.5 0 0 0 1.5 1.4h2.6a1.5 1.5 0 0 0 1.5-1.4L13.5 6"/>'
        '<path d="M8.5 9.5v4.25M11.5 9.5v4.25"/>',
    ),
    "simpan": _svg(
        '<path d="M4 4.5A1.5 1.5 0 0 1 5.5 3h9A1.5 1.5 0 0 1 16 4.5v11a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 4 17z"/>'
        '<path d="M7.25 3v4h5.5V3"/>',
    ),
    "ok": _svg('<circle cx="10" cy="10" r="7.25"/><path d="M6.75 10.4l2.2 2.2 4.3-4.6"/>'),
    "galat": _svg(
        '<circle cx="10" cy="10" r="7.25"/><path d="M10 6.25v4.5M10 13.75h.01"/>',
    ),
}

_LOGO = (
    '<svg width="30" height="30" viewBox="0 0 28 28" aria-hidden="true">'
    '<defs><linearGradient id="lgAdmin" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#4F46E5"/><stop offset="1" stop-color="#8B5CF6"/>'
    '</linearGradient></defs>'
    '<rect width="28" height="28" rx="8" fill="url(#lgAdmin)"/>'
    '<g fill="#fff"><circle cx="9" cy="9.5" r="1.9"/><circle cx="19" cy="9.5" r="1.9"/>'
    '<circle cx="14" cy="18.5" r="1.9"/></g>'
    '<g stroke="#fff" stroke-width="1.3" stroke-linecap="round">'
    '<path d="M10.4 10.2l1.9 5.4M17.6 10.2l-1.9 5.4M9 9.5h2.6M16.4 9.5H19"/></g></svg>'
)


# ---------------------------------------------------------------------------
# Desain (tokens + CSS)
# ---------------------------------------------------------------------------
_CSS = r"""
:root{
  --bg:#F5F6F8;
  --surface:#FFFFFF;
  --surface-2:#F8FAFC;
  --ink:#0F172A;
  --ink-2:#334155;
  --muted:#64748B;
  --faint:#94A3B8;
  --border:#E5E8EE;
  --border-2:#D8DDE5;
  --accent:#4F46E5;
  --accent-hover:#4338CA;
  --accent-soft:#EEF2FF;
  --accent-border:#C7D2FE;
  --violet:#7C3AED;
  --violet-soft:#F5F3FF;
  --danger:#DC2626;
  --danger-hover:#B91C1C;
  --danger-soft:#FEF2F2;
  --danger-border:#FECACA;
  --success:#16A34A;
  --success-soft:#F0FDF4;
  --success-border:#BBF7D0;
  --warn:#D97706;
  --warn-soft:#FFFBEB;
  --warn-border:#FDE68A;
  --radius:12px;
  --radius-sm:8px;
  --shadow-sm:0 1px 2px rgba(15,23,42,.05);
  --shadow-md:0 4px 6px -1px rgba(15,23,42,.06),0 2px 4px -2px rgba(15,23,42,.05);
}
*{box-sizing:border-box}
html,body{margin:0}
body{
  font-family:Inter,"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  background:var(--bg);color:var(--ink);line-height:1.5;
  -webkit-font-smoothing:antialiased;font-size:15px;
}
::selection{background:var(--accent);color:#fff}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.9em}
a{color:inherit}

/* ---- kerangka ---- */
.app{display:grid;grid-template-columns:248px minmax(0,1fr);min-height:100vh}
.side{
  background:var(--surface);border-right:1px solid var(--border);
  display:flex;flex-direction:column;position:sticky;top:0;height:100vh;
  padding:20px 14px;
}
.brand{display:flex;align-items:center;gap:11px;padding:2px 8px 18px;
  border-bottom:1px solid var(--border);margin-bottom:16px}
.brand-name{font-weight:700;font-size:1.06rem;letter-spacing:-.02em;line-height:1.1}
.brand-name em{font-style:normal;color:var(--accent)}
.brand-sub{font-size:.72rem;color:var(--muted);margin-top:1px}
.nav{display:flex;flex-direction:column;gap:3px}
.nav-item{
  display:flex;align-items:center;gap:10px;padding:9px 11px;border-radius:var(--radius-sm);
  color:var(--muted);text-decoration:none;font-weight:500;font-size:.88rem;
  border:1px solid transparent;transition:background .15s,color .15s;
}
.nav-item svg{width:18px;height:18px;flex:none}
.nav-item:hover{background:var(--surface-2);color:var(--ink)}
.nav-item.active{background:var(--accent-soft);color:var(--accent);font-weight:600}
.side-foot{
  margin-top:auto;display:flex;align-items:center;gap:8px;padding:12px 10px 4px;
  font-size:.75rem;color:var(--muted);border-top:1px solid var(--border);
}
.dot{width:8px;height:8px;border-radius:50%;background:var(--success);
  box-shadow:0 0 0 3px var(--success-soft);flex:none}
.main{min-width:0;display:flex;flex-direction:column}
.topbar{
  background:var(--surface);border-bottom:1px solid var(--border);
  padding:22px 32px;display:flex;align-items:flex-end;justify-content:space-between;gap:16px;
}
.topbar h1{margin:0;font-size:1.32rem;letter-spacing:-.02em;line-height:1.2;font-weight:700}
.topbar .desc{margin:5px 0 0;color:var(--muted);font-size:.86rem}
.content{padding:24px 32px 44px;max-width:1180px;width:100%}

/* ---- alert pesan ---- */
.alert{
  display:flex;align-items:flex-start;gap:10px;padding:12px 16px;border-radius:var(--radius-sm);
  font-size:.87rem;margin-bottom:18px;border:1px solid;
}
.alert svg{width:18px;height:18px;flex:none;margin-top:1px}
.alert.ok{background:var(--success-soft);border-color:var(--success-border);color:#15803D}
.alert.galat{background:var(--danger-soft);border-color:var(--danger-border);color:#B91C1C}

/* ---- kartu ---- */
.grid-utama{display:grid;gap:20px}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow-sm);min-width:0}
.card-head{
  padding:15px 20px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;gap:12px;
}
.card-head h2{margin:0;font-size:.97rem;font-weight:600;letter-spacing:-.01em;display:flex;align-items:center;gap:9px}
.card-head h2 svg{width:17px;height:17px;color:var(--accent)}
.card-head .meta{margin:2px 0 0;color:var(--muted);font-size:.79rem}
.card-head .count{font-weight:600;color:var(--muted);font-size:.8rem;
  background:var(--surface-2);border:1px solid var(--border);border-radius:999px;padding:2px 9px}
.card-body{padding:20px}
.card-body.ketat{padding:0}

/* ---- tabel ---- */
.table-scroll{overflow-x:auto;border-radius:0 0 var(--radius) var(--radius)}
table{width:100%;border-collapse:collapse;font-size:.85rem}
thead th{
  background:var(--surface-2);color:var(--muted);font-weight:600;text-align:left;
  padding:10px 14px;border-bottom:1px solid var(--border);font-size:.72rem;
  text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;
}
tbody td{padding:12px 14px;border-bottom:1px solid var(--border);vertical-align:middle}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--surface-2)}
.num{font-variant-numeric:tabular-nums}
td .sel{max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* ---- tombol ---- */
.btn{
  display:inline-flex;align-items:center;gap:7px;border:1px solid transparent;
  border-radius:var(--radius-sm);padding:9px 14px;font-size:.85rem;font-weight:600;
  cursor:pointer;font-family:inherit;line-height:1;text-decoration:none;
  transition:background .15s,border-color .15s,color .15s;
}
.btn svg{width:16px;height:16px;flex:none}
.btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent-hover)}
.btn-primary:active{background:#3730A3}
.btn-ghost{background:transparent;color:var(--muted);border-color:var(--border-2)}
.btn-ghost:hover{color:var(--ink);border-color:var(--faint);background:var(--surface-2)}
.btn-danger{background:transparent;color:var(--danger)}
.btn-danger:hover{background:var(--danger-soft);color:var(--danger-hover);border-color:var(--danger-border)}
.btn-danger.solid{background:var(--danger);color:#fff}
.btn-danger.solid:hover{background:var(--danger-hover)}
.btn-sm{padding:6px 10px;font-size:.79rem}

/* ---- form ---- */
.field{margin-bottom:15px}
.field:last-child{margin-bottom:0}
.field>label{display:block;font-size:.8rem;font-weight:600;color:var(--ink-2);margin-bottom:6px}
.field .hint{font-size:.74rem;color:var(--muted);margin-top:5px}
.field .wajib{color:var(--danger);font-weight:600}
input[type=text],input[type=password],select{
  width:100%;padding:9px 12px;border:1px solid var(--border-2);border-radius:var(--radius-sm);
  font-size:.88rem;font-family:inherit;color:var(--ink);background:var(--surface);
  caret-color:var(--accent);transition:border-color .15s,box-shadow .15s;
}
input:focus,select:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
input::placeholder{color:var(--faint)}
select{
  appearance:none;-webkit-appearance:none;padding-right:38px;cursor:pointer;
  background-image:url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="%2364748B" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M5 8l5 5 5-5"/></svg>');
  background-repeat:no-repeat;background-position:right 12px center;background-size:16px;
}

/* ---- chip pilihan akses ---- */
.chip-row{display:flex;flex-wrap:wrap;gap:8px}
.chip{position:relative;display:inline-flex}
.chip input{position:absolute;opacity:0;width:0;height:0}
.chip span{
  display:inline-flex;align-items:center;gap:6px;padding:7px 13px;border:1px solid var(--border-2);
  border-radius:999px;font-size:.82rem;font-weight:500;color:var(--muted);cursor:pointer;
  transition:.15s;user-select:none;
}
.chip:hover span{border-color:var(--faint)}
.chip input:checked+span{background:var(--accent-soft);border-color:var(--accent);color:var(--accent);font-weight:600}
.chip input:focus-visible+span{outline:2px solid var(--accent);outline-offset:2px}

/* ---- tag (baca-saja) ---- */
.tag{
  display:inline-flex;align-items:center;padding:3px 9px;border-radius:999px;
  font-size:.74rem;font-weight:600;background:var(--surface-2);border:1px solid var(--border);
  color:var(--ink-2);white-space:nowrap;
}
.tag.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.72rem}
.tag-all{background:var(--violet-soft);border-color:#DDD6FE;color:var(--violet)}
.tag-asal-kustom{background:var(--accent-soft);border-color:var(--accent-border);color:var(--accent)}
.tag-campur>*{margin:2px 1px}

/* ---- pilar status (audit) ---- */
.pill{display:inline-flex;align-items:center;padding:2px 9px;border-radius:999px;
  font-size:.72rem;font-weight:600;border:1px solid;white-space:nowrap}
.pill-neutral{background:var(--surface-2);border-color:var(--border);color:var(--ink-2)}
.pill-success{background:var(--success-soft);border-color:var(--success-border);color:#15803D}
.pill-danger{background:var(--danger-soft);border-color:var(--danger-border);color:#B91C1C}
.pill-warn{background:var(--warn-soft);border-color:var(--warn-border);color:#B45309}

/* ---- kosong ---- */
.empty{padding:30px 16px;text-align:center;color:var(--muted);font-size:.85rem}
.empty .judul{font-size:.95rem;font-weight:600;color:var(--ink-2);margin-bottom:3px}

.catatan{margin-top:16px;font-size:.78rem;color:var(--muted);line-height:1.6}

@media (max-width:980px){
  .grid-2{grid-template-columns:1fr}
}
@media (max-width:760px){
  .app{grid-template-columns:1fr}
  .side{position:static;height:auto;flex-direction:row;align-items:center;gap:12px;
    padding:12px;border-right:0;border-bottom:1px solid var(--border);flex-wrap:wrap}
  .brand{border:0;margin:0;padding:0 4px 0 0}
  .nav{flex-direction:row;gap:2px}
  .nav-item{padding:7px 10px;font-size:.82rem}
  .side-foot{display:none}
  .topbar{padding:18px 20px}
  .content{padding:18px 20px 32px}
}
"""


def _lokal(request: Request) -> bool:
    """Izinkan klien loopback ATAU jaringan yang diizinkan lewat env
    MCP_ALLOW_ADMIN_FROM (dipisah koma). Di dalam Docker, request.client.host
    adalah IP bridge (172.x), bukan 127.0.0.1 — jadi default tetap aman."""
    host = (request.client.host if request.client else "") or ""
    ip = urlsplit(f"http://{host}").hostname or host
    if ip in ("127.0.0.1", "::1", "localhost"):
        return True
    izinkan = [h.strip() for h in os.environ.get("MCP_ALLOW_ADMIN_FROM", "").split(",") if h.strip()]
    if not izinkan:
        return False
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entri in izinkan:
        try:
            net = ipaddress.ip_network(entri, strict=False)
        except ValueError:
            if ip == entri:
                return True
            continue
        if addr in net:
            return True
    return False


def _beres(request: Request) -> bool:
    return _lokal(request)


def _baca_roles_file() -> dict:
    if _PERAN_FILE_TULIS.exists():
        try:
            return json.loads(_PERAN_FILE_TULIS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _simpan_roles_file(data: dict) -> None:
    _PERAN_FILE_TULIS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _simpan_users_file(users: dict[str, dict]) -> None:
    _LOGIN_FILE.write_text(json.dumps({"users": list(users.values())},
                                      indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Pembangun HTML
# ---------------------------------------------------------------------------
def _nav(aktif: str) -> str:
    item = (
        '<a class="nav-item {aktif}" href="{href}">{ikon}<span>{teks}</span></a>'
    )
    return "".join([
        item.format(aktif="active" if aktif == "user" else "", href="/admin",
                    ikon=_IKON["users"], teks="Pengguna &amp; Peran"),
        item.format(aktif="active" if aktif == "audit" else "", href="/admin/audit",
                    ikon=_IKON["audit"], teks="Audit Chat"),
        item.format(aktif="", href="/pengetahuan",
                    ikon=_IKON["book"], teks="Pengetahuan"),
    ])


def _wadah(judul_halaman: str, deskripsi: str, aktif: str, isi: str,
           judul: str, aksi: str = "") -> str:
    """Kerangka halaman: sidebar + topbar + konten."""
    sidebar = (
        '<aside class="side">'
        '<div class="brand">{logo}'
        '<div><div class="brand-name">TigaBe <em>MCP</em></div>'
        '<div class="brand-sub">Konsol Admin</div></div></div>'
        '<nav class="nav">{nav}</nav>'
        '<div class="side-foot"><span class="dot"></span>Hanya dari localhost</div>'
        '</aside>'
    ).format(logo=_LOGO, nav=_nav(aktif))

    pesan = galat = ""
    if isi.get("pesan"):
        pesan = ('<div class="alert ok">{ikon}<span>{teks}</span></div>').format(
            ikon=_IKON["ok"], teks=isi["pesan"])
    if isi.get("galat"):
        galat = ('<div class="alert galat">{ikon}<span>{teks}</span></div>').format(
            ikon=_IKON["galat"], teks=isi["galat"])

    topbar = (
        '<header class="topbar"><div>'
        '<h1>{judul_halaman}</h1><p class="desc">{deskripsi}</p></div>'
        '{aksi}</header>'
    ).format(judul_halaman=judul_halaman, deskripsi=deskripsi, aksi=aksi)

    return (
        "<!doctype html><html lang='id'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>{judul}</title><style>{css}</style></head>"
        "<body><div class='app'>{sidebar}<main class='main'>{topbar}"
        "<div class='content'>{pesan}{galat}{konten}</div></main></div></body></html>"
    ).format(judul=judul, css=_CSS, sidebar=sidebar, topbar=topbar,
             pesan=pesan, galat=galat, konten=isi["isi"])


def _tag_akses_teks(akses: list[str] | None) -> str:
    return ", ".join(akses) if akses else "(kosong)"


def _tag_asal(nama: str, kustom: bool) -> str:
    if kustom:
        return '<span class="tag tag-asal-kustom">kustom</span>'
    return '<span class="tag">bawaan</span>'


def _chip_akses_html(cfg: dict) -> str:
    if cfg.get("semua_akses"):
        return '<span class="tag tag-all">Semua dokumen</span>'
    akses = cfg.get("akses", []) or []
    if not akses:
        return '<span class="tag">(kosong)</span>'
    return '<span class="tag-campur">' + "".join(
        f'<span class="tag mono">{html.escape(a)}</span>' for a in akses
    ) + "</span>"


def _laman(pesan: str = "", galat: str = "", tab: str = "user") -> HTMLResponse:
    users = muat_users()
    roles_file = _baca_roles_file()
    peran_kustom = roles_file.get("roles", {})
    token_entries = roles_file.get("tokens", {})

    # ---- tabel pengguna ----
    if users:
        tr_users = "".join(
            f"<tr><td><strong>{html.escape(u['username'])}</strong></td>"
            f"<td>{html.escape(u['peran'])}</td>"
            f"<td><span class='sel'>{html.escape(u.get('label', ''))}</span></td>"
            f"<td style='text-align:right'>"
            f"<form method='POST' action='/admin/user/hapus' "
            f"onsubmit=\"return confirm('Hapus pengguna ini?')\" style='margin:0'>"
            f"<input type='hidden' name='username' value='{html.escape(u['username'])}'>"
            f"<button class='btn btn-danger btn-sm' type='submit' title='Hapus pengguna'>"
            f"{_IKON['trash']}</button></form></td></tr>"
            for u in users.values()
        )
    else:
        tr_users = ("<tr><td colspan='4'><div class='empty'>"
                    "<div class='judul'>Belum ada pengguna</div>"
                    "Tambahkan pengguna lewat form di samping.</div></td></tr>")

    # ---- tabel peran ----
    semua_peran = {**PERAN_BAWAAN, **peran_kustom}
    rows_peran = []
    for nama, cfg in semua_peran.items():
        kustom = nama in peran_kustom
        if kustom:
            tombol = (f"<form method='POST' action='/admin/peran/hapus' "
                      f"onsubmit=\"return confirm('Hapus peran kustom ini?')\" style='margin:0'>"
                      f"<input type='hidden' name='nama' value='{html.escape(nama)}'>"
                      f"<button class='btn btn-danger btn-sm' type='submit' title='Hapus peran'>"
                      f"{_IKON['trash']}</button></form>")
        else:
            tombol = '<span style="color:var(--faint)">—</span>'
        rows_peran.append(
            f"<tr><td><strong>{html.escape(nama)}</strong></td>"
            f"<td>{html.escape(str(cfg.get('label', nama)))}</td>"
            f"<td>{_chip_akses_html(cfg)}</td>"
            f"<td>{_tag_asal(nama, kustom)}</td>"
            f"<td style='text-align:right'>{tombol}</td></tr>")
    tr_peran = "".join(rows_peran)

    opsi_peran = "".join(f"<option value='{html.escape(n)}'>{html.escape(n)}</option>"
                         for n in semua_peran)
    opsi_akses = "".join(
        f"<label class='chip'><input type='checkbox' name='akses' value='{html.escape(a)}'>"
        f"<span>{html.escape(a)}</span></label>"
        for a in _AKSES_TINGKAT)

    # ---- kartu pengguna + form ----
    kartu_pengguna = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{_IKON["users"]} Pengguna Login</h2>'
        '<div class="meta">Akun yang bisa masuk lewat chat / browser.</div></div>'
        f'<span class="count">{len(users)}</span></div>'
        '<div class="card-body ketat"><div class="table-scroll"><table>'
        '<thead><tr><th>Username</th><th>Peran</th><th>Label</th><th></th></tr></thead>'
        f'<tbody>{tr_users}</tbody></table></div></div></section>'
    )

    form_pengguna = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{_IKON["plus"]} Tambah / Ubah Pengguna</h2>'
        '<div class="meta">Mengisi username yang sudah ada akan mengubahnya.</div></div></div>'
        '<div class="card-body">'
        "<form method='POST' action='/admin/user/simpan'>"
        "<div class='field'><label for='f-username'>Username <span class='wajib'>*</span></label>"
        "<input type='text' id='f-username' name='username' required autocomplete='off' "
        "placeholder='mis. sari'></div>"
        "<div class='field'><label for='f-password'>Password</label>"
        "<input type='password' id='f-password' name='password' autocomplete='new-password' "
        "placeholder='••••••••'><p class='hint'>Kosongkan saat mengubah user untuk mempertahankan "
        "password lama.</p></div>"
        "<div class='field'><label for='f-label'>Nama / Label</label>"
        "<input type='text' id='f-label' name='label' autocomplete='off' placeholder='opsional'></div>"
        "<div class='field'><label for='f-peran'>Peran</label>"
        f"<select id='f-peran' name='peran'>{opsi_peran}</select></div>"
        f"<button class='btn btn-primary' type='submit'>{_IKON['simpan']} Simpan Pengguna</button>"
        "</form></div></section>"
    )

    # ---- kartu peran + form ----
    kartu_peran = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{_IKON["audit"]} Peran &amp; Akses Dokumen</h2>'
        '<div class="meta">Peran bawaan ditimpa oleh peran kustom di roles.json.</div></div>'
        f'<span class="count">{len(semua_peran)}</span></div>'
        '<div class="card-body ketat"><div class="table-scroll"><table>'
        '<thead><tr><th>Nama</th><th>Label</th><th>Akses</th><th>Asal</th><th></th></tr></thead>'
        f'<tbody>{tr_peran}</tbody></table></div></div></section>'
    )

    form_peran = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{_IKON["plus"]} Tambah / Ubah Peran</h2>'
        '<div class="meta">Tentukan tingkat akses dokumen (payload Qdrant).</div></div></div>'
        '<div class="card-body">'
        "<form method='POST' action='/admin/peran/simpan'>"
        "<div class='field'><label for='f-nama'>Nama peran <span class='wajib'>*</span></label>"
        "<input type='text' id='f-nama' name='nama' required pattern='[a-z_]+' autocomplete='off' "
        "placeholder='mis. tata_usaha'><p class='hint'>Tanpa spasi; huruf kecil &amp; garis bawah.</p></div>"
        "<div class='field'><label for='f-label-peran'>Label</label>"
        "<input type='text' id='f-label-peran' name='label' autocomplete='off' "
        "placeholder='mis. Tata Usaha'></div>"
        "<div class='field'><label>Tingkat akses dokumen</label>"
        f"<div class='chip-row'>{opsi_akses}</div></div>"
        "<div class='field'>"
        "<label class='chip'><input type='checkbox' name='semua' value='1'>"
        "<span>semua_akses — boleh melihat seluruh dokumen</span></label>"
        "</div>"
        f"<button class='btn btn-primary' type='submit'>{_IKON['simpan']} Simpan Peran</button>"
        "</form></div></section>"
    )

    catatan = (
        "<div class='catatan'>Nilai akses harus sama dengan payload <code>tingkat_akses</code> "
        "di Qdrant. Menghapus peran kustom tidak menghapus pengguna yang memakainya; perubahan peran "
        "butuh <strong>restart server</strong>. Token statis tersisa di roles.json: "
        f"<strong>{len(token_entries)}</strong>.</div>"
    )

    isi = (
        '<div class="grid-utama">'
        '<div class="grid-2">{kartu_pengguna}{form_pengguna}</div>'
        '<div class="grid-2">{kartu_peran}{form_peran}</div>'
        '{catatan}</div>'
    ).format(kartu_pengguna=kartu_pengguna, form_pengguna=form_pengguna,
             kartu_peran=kartu_peran, form_peran=form_peran, catatan=catatan)

    html_doc = _wadah(
        judul_halaman="Pengguna &amp; Peran",
        deskripsi="Kelola akun login dan tingkat akses dokumen.",
        aktif="user",
        isi={"isi": isi, "pesan": pesan, "galat": galat},
        judul="Admin TigaBe MCP",
    )
    return HTMLResponse(html_doc)


def _laman_audit(pesan: str = "") -> HTMLResponse:
    entri = audit_lib.terakhir(200)
    baris = []
    for e in entri:
        status = str(e.get("status", ""))
        if status in ("login_gagal", "error", "error_qdrant", "error_embed"):
            pil = "pill-danger"
        elif status == "login_sukses":
            pil = "pill-success"
        elif status in ("keluar",):
            pil = "pill-warn"
        else:
            pil = "pill-neutral"
        arg = json.dumps(e.get("argumen", {}), ensure_ascii=False)
        baris.append(
            f"<tr><td class='num'>{html.escape(str(e.get('no', '')))}</td>"
            f"<td class='num'>{html.escape(str(e.get('waktu', '')))}</td>"
            f"<td>{html.escape(str(e.get('user', '')))}</td>"
            f"<td>{html.escape(str(e.get('peran', '')))}</td>"
            f"<td><strong>{html.escape(str(e.get('tool', '')))}</strong></td>"
            f"<td class='sel'>{html.escape(arg[:160])}</td>"
            f"<td><span class='pill {pil}'>{html.escape(status or 'ok')}</span></td>"
            f"<td class='sel'>{html.escape(str(e.get('ringkas', ''))[:120])}</td></tr>")
    tbody = "".join(baris) or (
        "<tr><td colspan='8'><div class='empty'><div class='judul'>Belum ada aktivitas</div>"
        "Setiap panggilan tool dari chat / WorkBuddy akan tercatat di sini.</div></td></tr>")

    aksi = (
        "<form method='POST' action='/admin/audit/hapus' "
        "onsubmit=\"return confirm('Hapus semua riwayat audit?')\" style='margin:0'>"
        f"<button class='btn btn-danger solid'>{_IKON['trash']} Bersihkan Audit</button></form>"
    )

    isi = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{_IKON["audit"]} 200 Aktivitas Terakhir</h2>'
        '<div class="meta">Panggilan tool (user, peran, argumen tersensor, status, ringkasan). '
        "Seluruh riwayat tersimpan di <code>audit_log.json</code>.</div></div>"
        f'<span class="count">{len(entri)}</span></div>'
        '<div class="card-body ketat"><div class="table-scroll"><table class="audit">'
        '<thead><tr><th>#</th><th>Waktu</th><th>User</th><th>Peran</th><th>Tool</th>'
        '<th>Argumen</th><th>Status</th><th>Keterangan</th></tr></thead>'
        f'<tbody>{tbody}</tbody></table></div></div></section>'
    )

    html_doc = _wadah(
        judul_halaman="Audit Chat",
        deskripsi="Riwayat panggilan MCP untuk pemantauan.",
        aktif="audit",
        isi={"isi": isi, "pesan": pesan, "galat": ""},
        judul="Audit TigaBe MCP",
        aksi=aksi,
    )
    return HTMLResponse(html_doc)


def pasang_admin(mcp) -> None:
    @mcp.custom_route("/admin", methods=["GET"])
    async def admin_home(request: Request):
        if not _beres(request):
            return HTMLResponse("<h3>403</h3><p>Halaman admin hanya dari localhost.</p>", status_code=403)
        return _laman()

    @mcp.custom_route("/admin/audit", methods=["GET"])
    async def admin_audit(request: Request):
        if not _beres(request):
            return HTMLResponse("<h3>403</h3><p>Halaman admin hanya dari localhost.</p>", status_code=403)
        return _laman_audit()

    @mcp.custom_route("/admin/audit/hapus", methods=["POST"])
    async def admin_audit_hapus(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        jumlah = audit_lib.kosongkan()
        return _laman_audit(pesan=f"{jumlah} entri audit dihapus.")

    @mcp.custom_route("/admin/user/simpan", methods=["POST"])
    async def simpan_user(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        form = await request.form()
        username = str(form.get("username") or "").strip()
        password = str(form.get("password") or "")
        label = str(form.get("label") or "").strip()
        peran = str(form.get("peran") or "").strip()
        if not username or peran not in {**PERAN_BAWAAN, **_baca_roles_file().get("roles", {})}:
            return _laman(galat="Username kosong atau peran tidak dikenal.")
        users = muat_users()
        lama = users.get(username)
        if not password and lama:
            password_hash = lama["password_hash"]        # pertahankan password lama
        else:
            if not password:
                return _laman(galat="Password baru wajib diisi untuk user baru.")
            password_hash = hash_password(password)
        users[username] = {"username": username, "peran": peran,
                           "label": label or username, "password_hash": password_hash}
        _simpan_users_file(users)
        log.info("admin: user disimpan %s peran %s", username, peran)
        return RedirectResponse("/admin?pesan=Pengguna+disimpan", status_code=303)

    @mcp.custom_route("/admin/user/hapus", methods=["POST"])
    async def hapus_user(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        form = await request.form()
        username = str(form.get("username") or "")
        users = muat_users()
        users.pop(username, None)
        _simpan_users_file(users)
        return RedirectResponse(f"/admin?pesan=Pengguna+{username}+dihapus", status_code=303)

    @mcp.custom_route("/admin/peran/simpan", methods=["POST"])
    async def simpan_peran(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        form = await request.form()
        nama = str(form.get("nama") or "").strip()
        label = str(form.get("label") or "").strip()
        if not nama:
            return _laman(galat="Nama peran kosong.")
        akses = form.getlist("akses")
        semua = bool(form.get("semua"))
        cfg = {"label": label or nama, "akses": list(akses), "semua_akses": semua}
        data = _baca_roles_file()
        data.setdefault("roles", {})[nama] = cfg
        _simpan_roles_file(data)
        return RedirectResponse("/admin?pesan=Peran+disimpan+(perlu+restart+server)", status_code=303)

    @mcp.custom_route("/admin/peran/hapus", methods=["POST"])
    async def hapus_peran(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        form = await request.form()
        nama = str(form.get("nama") or "")
        data = _baca_roles_file()
        data.get("roles", {}).pop(nama, None)
        _simpan_roles_file(data)
        return RedirectResponse("/admin?pesan=Peran+kustom+dihapus+(perlu+restart)", status_code=303)