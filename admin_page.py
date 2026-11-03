"""Halaman admin sederhana: kelola pengguna login + definisi peran.

Rute:
  /admin            -> halaman web (_fetch + form)
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


def _lokal(request: Request) -> bool:
    """Izinkan hanya klien dari mesin yang sama (keamanan PoC)."""
    host = (request.client.host if request.client else "") or ""
    ip = urlsplit(f"http://{host}").hostname or host
    return ip in ("127.0.0.1", "::1", "localhost")


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


def _laman(pesan: str = "", galat: str = "", tab: str = "user") -> HTMLResponse:
    users = muat_users()
    roles_file = _baca_roles_file()
    peran_kustom = roles_file.get("roles", {})
    token_entries = roles_file.get("tokens", {})

    tr_users = "".join(
        f"<tr><td>{html.escape(u['username'])}</td>"
        f"<td>{html.escape(u['peran'])}</td>"
        f"<td>{html.escape(u.get('label', ''))}</td>"
        f"<td><form method='POST' action='/admin/user/hapus' style='display:inline'>"
        f"<input type='hidden' name='username' value='{html.escape(u['username'])}'>"
        f"<button class='btn-hapus'>Hapus</button></form></td></tr>"
        for u in users.values()
    ) or "<tr><td colspan='4' class='kosong'>Belum ada pengguna.</td></tr>"

    semua_peran = {**PERAN_BAWAAN, **peran_kustom}
    rows_peran = []
    for nama, cfg in semua_peran.items():
        akses_txt = "semua dokumen" if cfg.get("semua_akses") else (", ".join(cfg.get("akses", [])) or "(kosong)")
        asal = "bawaan" if nama in PERAN_BAWAAN else "kustom"
        if nama in peran_kustom:
            tombol = ("<form method='POST' action='/admin/peran/hapus'>"
                      f"<input type='hidden' name='nama' value='{html.escape(nama)}'>"
                      "<button class='btn-hapus'>Hapus</button></form>")
        else:
            tombol = "—"
        rows_peran.append(
            f"<tr><td>{html.escape(nama)}</td>"
            f"<td>{html.escape(str(cfg.get('label', nama)))}</td>"
            f"<td>{html.escape(akses_txt)}</td>"
            f"<td>{asal}</td>"
            f"<td>{tombol}</td></tr>")
    tr_peran = "".join(rows_peran)

    opsi_peran = "".join(f"<option value='{html.escape(n)}'>{html.escape(n)}</option>"
                         for n in semua_peran)
    opsi_akses = "".join(
        f"<label class='chip'><input type='checkbox' name='akses' value='{html.escape(a)}'> {html.escape(a)}</label>"
        for a in ("public", "class", "internal", "restricted"))

    pesan_html = f"<p class='ok'>{html.escape(pesan)}</p>" if pesan else ""
    galat_html = f"<p class='galat'>{html.escape(galat)}</p>" if galat else ""

    return HTMLResponse(f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin TigaBe MCP</title><style>
body{{font-family:system-ui,sans-serif;background:#f4f6f8;margin:0;padding:24px}}
.wrap{{max-width:860px;margin:0 auto}}
h1{{font-size:1.3rem}} h2{{font-size:1.05rem;margin-top:28px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #e6e9ec;font-size:.86rem}}
th{{background:#eef2f6}}
.btn{{background:#1a73e8;color:#fff;border:0;border-radius:6px;padding:8px 14px;cursor:pointer;font-weight:600}}
.btn-hapus{{background:#b3261e;color:#fff;border:0;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:.78rem}}
input[type=text],input[type=password]{{padding:8px;border:1px solid #cfd6dc;border-radius:6px;width:100%;box-sizing:border-box}}
form.baris{{background:#fff;border:1px solid #e6e9ec;border-radius:8px;padding:14px;margin-top:10px}}
label.f{{display:block;font-size:.78rem;color:#3f4650;margin:8px 0 3px}}
.chip{{display:inline-flex;align-items:center;gap:4px;margin:4px 10px 0 0;font-size:.8rem}}
.ok{{color:#1b7f4d}} .galat{{color:#b3261e}} .kosong{{color:#8794a0}}
.small{{font-size:.75rem;color:#8794a0}}
.tab{{display:inline-block;padding:6px 14px;border-radius:6px;background:#fff;border:1px solid #d9dee3;
     color:#3f4650;text-decoration:none;font-size:.85rem;margin-right:6px}}
.tab.aktif{{background:#1a73e8;color:#fff;border-color:#1a73e8;font-weight:600}}
</style></head><body><div class="wrap">
<h1>🛠️ Admin TigaBe MCP</h1>
<p>
  <a class="tab {'aktif' if tab=='user' else ''}" href="/admin">👤 Pengguna &amp; Peran</a>
  <a class="tab {'aktif' if tab=='audit' else ''}" href="/admin/audit">📜 Audit Chat</a>
</p>
<p class="small">Halaman ini hanya bisa dibuka dari komputer ini (localhost).</p>
{pesan_html}{galat_html}

<h2>👤 Pengguna Login</h2>
<table><tr><th>Username</th><th>Peran</th><th>Nama/Label</th><th></th></tr>{tr_users}</table>

<form class="baris" method="POST" action="/admin/user/simpan">
  <b>Tambah / Ubah Pengguna</b>
  <label class="f">Username</label><input type="text" name="username" required>
  <label class="f">Password {("(kosongkan bila tetap)" )}</label><input type="password" name="password">
  <label class="f">Nama/Label (opsional)</label><input type="text" name="label">
  <label class="f">Peran</label>
  <select name="peran">{''.join(f'<option value="{html.escape(n)}">{html.escape(n)}</option>' for n in semua_peran)}</select>
  <p><button class="btn">Simpan Pengguna</button></p>
</form>

<h2>🎭 Peran (akses dokumen)</h2>
<table><tr><th>Nama</th><th>Label</th><th>Akses</th><th>Asal</th><th></th></tr>{tr_peran}</table>

<form class="baris" method="POST" action="/admin/peran/simpan">
  <b>Tambah / Ubah Peran</b>
  <label class="f">Nama peran (tanpa spasi)</label><input type="text" name="nama" required pattern="[a-z_]+" >
  <label class="f">Label</label><input type="text" name="label">
  <label class="f">Tingkat akses dokumen</label>
  {opsi_akses}
  <label class="chip"><input type="checkbox" name="semua"> semua_akses (boleh semua dokumen)</label>
  <p><button class="btn">Simpan Peran</button></p>
</form>

<p class="small">Catatan: nilai akses harus sama dengan payload <code>tingkat_akses</code> di Qdrant.
Hapus peran kustom tidak akan menghapus user yang memakainya.<br>
Token statis tersisa di roles.json: {len(token_entries)}.</p>
</div></body></html>""")


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

    def _laman_audit(pesan: str = "") -> HTMLResponse:
        entri = audit_lib.terakhir(200)
        baris = []
        for e in entri:
            kelas = ""
            if e.get("status") in ("login_gagal", "error", "error_qdrant", "error_embed"):
                kelas = " style='background:#fdeceb'"
            elif e.get("status") == "login_sukses":
                kelas = " style='background:#eaf6ef'"
            arg = json.dumps(e.get("argumen", {}), ensure_ascii=False)
            baris.append(
                f"<tr{kelas}><td>{html.escape(str(e.get('no','')))}</td>"
                f"<td>{html.escape(str(e.get('waktu','')))}</td>"
                f"<td>{html.escape(str(e.get('user','')))}</td>"
                f"<td>{html.escape(str(e.get('peran','')))}</td>"
                f"<td><b>{html.escape(str(e.get('tool','')))}</b></td>"
                f"<td class='small'>{html.escape(arg[:160])}</td>"
                f"<td>{html.escape(str(e.get('status','')))}</td>"
                f"<td class='small'>{html.escape(str(e.get('ringkas',''))[:120])}</td></tr>")
        tbody = "".join(baris) or "<tr><td colspan='8' class='kosong'>Belum ada aktivitas.</td></tr>"
        pesan_html = f"<p class='ok'>{html.escape(pesan)}</p>" if pesan else ""
        return HTMLResponse(f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Audit TigaBe MCP</title><style>
body{{font-family:system-ui,sans-serif;background:#f4f6f8;margin:0;padding:24px}}
.wrap{{max-width:1050px;margin:0 auto}}
h1{{font-size:1.3rem}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid #e6e9ec;font-size:.8rem;vertical-align:top}}
th{{background:#eef2f6}}
.btn{{background:#b3261e;color:#fff;border:0;border-radius:6px;padding:8px 14px;cursor:pointer;font-weight:600}}
.small{{font-size:.75rem;color:#5f6b76;word-break:break-word}}
.ok{{color:#1b7f4d}} .kosong{{color:#8794a0}}
.tab{{display:inline-block;padding:6px 14px;border-radius:6px;background:#fff;border:1px solid #d9dee3;
     color:#3f4650;text-decoration:none;font-size:.85rem;margin-right:6px}}
.tab.aktif{{background:#1a73e8;color:#fff;border-color:#1a73e8;font-weight:600}}
</style></head><body><div class="wrap">
<h1>📜 Audit Chat TigaBe MCP</h1>
<p>
  <a class="tab" href="/admin">👤 Pengguna &amp; Peran</a>
  <a class="tab aktif" href="/admin/audit">📜 Audit Chat</a>
</p>
{pesan_html}
<p class="small">200 aktivitas terakhir: setiap panggilan tool dari chat/workbuddy
(user, peran, tool, argumen tanpa password, status, ringkasan).
Semua riwayat tersimpan di <code>audit_log.json</code> (format array JSON).</p>
<form method="POST" action="/admin/audit/hapus" onsubmit="return confirm('Hapus semua audit?')">
  <button class="btn">🧹 Bersihkan Audit</button>
</form>
<table style="margin-top:14px"><tr><th>#</th><th>Waktu</th><th>User</th><th>Peran</th>
<th>Tool</th><th>Argumen</th><th>Status</th><th>Keterangan</th></tr>{tbody}</table>
</div></body></html>""")

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
        return RedirectResponse("/admin?pesan=Login+users+disimpan", status_code=303)

    @mcp.custom_route("/admin/user/hapus", methods=["POST"])
    async def hapus_user(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        form = await request.form()
        username = str(form.get("username") or "")
        users = muat_users()
        users.pop(username, None)
        _simpan_users_file(users)
        return RedirectResponse(f"/admin?pesan=User+{username}+dihapus", status_code=303)

    @mcp.custom_route("/admin/peran/simpan", methods=["POST"])
    async def simpan_peran(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        form = await request.form()
        nama = str(form.get("nama") or "").strip()
        label = str(form.get("label") or "").strip()
        if not nama:
            return _laman(galat="Nama peran kosong.")
        akses = form.getall("akses") if hasattr(form, "getall") else form.get("akses", [])
        if not isinstance(akses, list):
            akses = [akses]
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
