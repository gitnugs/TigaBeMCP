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
from html_theme import IKON, wadah

log = logging.getLogger("tigabe.admin")

_PERAN_FILE_TULIS = ROLES_PATH

_SANDI = os.environ.get("MCP_ADMIN_PASSWORD", "").strip()

_AKSES_TINGKAT = ("public", "class", "internal", "restricted")


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
            f"{IKON['trash']}</button></form></td></tr>"
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
                      f"{IKON['trash']}</button></form>")
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
        f'<h2>{IKON["users"]} Pengguna Login</h2>'
        '<div class="meta">Akun yang bisa masuk lewat chat / browser.</div></div>'
        f'<span class="count">{len(users)}</span></div>'
        '<div class="card-body ketat"><div class="table-scroll"><table>'
        '<thead><tr><th>Username</th><th>Peran</th><th>Label</th><th></th></tr></thead>'
        f'<tbody>{tr_users}</tbody></table></div></div></section>'
    )

    form_pengguna = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{IKON["plus"]} Tambah / Ubah Pengguna</h2>'
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
        f"<button class='btn btn-primary' type='submit'>{IKON['simpan']} Simpan Pengguna</button>"
        "</form></div></section>"
    )

    # ---- kartu peran + form ----
    kartu_peran = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{IKON["audit"]} Peran &amp; Akses Dokumen</h2>'
        '<div class="meta">Peran bawaan ditimpa oleh peran kustom di roles.json.</div></div>'
        f'<span class="count">{len(semua_peran)}</span></div>'
        '<div class="card-body ketat"><div class="table-scroll"><table>'
        '<thead><tr><th>Nama</th><th>Label</th><th>Akses</th><th>Asal</th><th></th></tr></thead>'
        f'<tbody>{tr_peran}</tbody></table></div></div></section>'
    )

    form_peran = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{IKON["plus"]} Tambah / Ubah Peran</h2>'
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
        f"<button class='btn btn-primary' type='submit'>{IKON['simpan']} Simpan Peran</button>"
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

    html_doc = wadah(
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
        f"<button class='btn btn-danger solid'>{IKON['trash']} Bersihkan Audit</button></form>"
    )

    isi = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{IKON["audit"]} 200 Aktivitas Terakhir</h2>'
        '<div class="meta">Panggilan tool (user, peran, argumen tersensor, status, ringkasan). '
        "Seluruh riwayat tersimpan di <code>audit_log.json</code>.</div></div>"
        f'<span class="count">{len(entri)}</span></div>'
        '<div class="card-body ketat"><div class="table-scroll"><table class="audit">'
        '<thead><tr><th>#</th><th>Waktu</th><th>User</th><th>Peran</th><th>Tool</th>'
        '<th>Argumen</th><th>Status</th><th>Keterangan</th></tr></thead>'
        f'<tbody>{tbody}</tbody></table></div></div></section>'
    )

    html_doc = wadah(
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