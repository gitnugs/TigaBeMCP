"""Authorization-server internal OAuth 2.1 (code + PKCE) untuk TigaBe MCP.

Rute bawaan SDK (/authorize, /token, /register, /revoke) dilayani SDK.
File ini menambahkan sisi yang ada di luar SDK:
  - /login (GET/POST): form di browser, password tidak pernah masuk chat/model
  - penyimpanan in-memory: pending authorize, code, token, klien
  - verifikasi password dari login_users.json (hash scrypt)

Penyimpanan in-memory: restart server menghapus sesi/token; WorkBuddy melakukan
login ulang. Untuk produksi pindahkan ke DB/redis. Cukup untuk PoC.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode
from urllib.parse import urlparse as _urlparse

from dotenv import load_dotenv
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

import os

load_dotenv(Path(__file__).with_name(".env"))

log = logging.getLogger("tigabe.oauth")

_url_publik = os.environ.get("MCP_PUBLIC_URL", "https://epmcp001.aitalent.web.id/mcp").rstrip("/")
PUBLIC_URL = _url_publik
# origin (tanpa path) dipakai untuk URL /login — MCP_PUBLIC_URL boleh berakhir /mcp
from urllib.parse import urlparse as _urlparse
ORIGIN_URL = os.environ.get("MCP_ISSUER_URL", "").rstrip("/") or (
    f"{_urlparse(_url_publik).scheme}://{_urlparse(_url_publik).netloc}"
)
ISSUER_URL = os.environ.get("MCP_ISSUER_URL", "").rstrip("/") or ORIGIN_URL

AKSES_MENIT = int(os.environ.get("MCP_ACCESS_TTL_MINUTES", "60"))
CODE_MENIT = int(os.environ.get("MCP_LOGIN_CODE_MINUTES", "15"))
MAKS_PERCOBAAN = int(os.environ.get("MCP_LOGIN_MAX_ATTEMPTS", "5"))
REFRESH_HARI = int(os.environ.get("MCP_REFRESH_TTL_DAYS", "30"))
PENDING_MENIT = 15

AKSES_DET = AKSES_MENIT * 60
REFRESH_DET = REFRESH_HARI * 86400

_LOGIN_FILE = Path(
    os.environ.get("MCP_LOGIN_USERS", "") or Path(__file__).with_name("login_users.json")
)


def hash_password(password: str) -> str:
    """Format: scrypt$n$r$p$salt_hex$hash_hex."""
    salt = secrets.token_bytes(16)
    dig = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${dig.hex()}"


def verifikasi_password(tercatat: str, password: str) -> bool:
    try:
        _, n, r, p, salt_hex, hash_hex = tercatat.split("$")
        dig = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=32,
        )
        return hmac.compare_digest(dig.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def muat_users() -> dict[str, dict]:
    try:
        if not _LOGIN_FILE.exists():
            _LOGIN_FILE.parent.mkdir(parents=True, exist_ok=True)
            _LOGIN_FILE.write_text('{"users": []}\n', encoding="utf-8")
            return {}
        data = json.loads(_LOGIN_FILE.read_text(encoding="utf-8"))
        out = {}
        for u in data.get("users", []):
            if u.get("username"):
                out[u["username"]] = u
        return out
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


# ---------------- sesi chat (login lewat tool 'masuk', tanpa OAuth flow)
_CHAT: dict[str, dict] = {}     # single-slot: {"username","peran","label","nama"}


def sesi_chat_aktif() -> dict | None:
    """Pengguna chat yang sedang login via tool 'masuk' (bila ada)."""
    return dict(_CHAT["user"]) if "user" in _CHAT else None


def atur_sesi_chat(user: dict) -> None:
    _CHAT["user"] = {"username": user["username"], "peran": user["peran"],
                     "label": user.get("label", user["username"]),
                     "nama": user.get("nama", user["username"])}


def hapus_sesi_chat() -> str | None:
    """Hapus sesi chat; kembalikan username yang sebelumnya aktif."""
    user = _CHAT.pop("user", None)
    return user["username"] if user else None


# --------------- permintaan login via browser (tool 'masuk_browser')
_BROWSER: dict = {}   # {"token": ..., "dibuat": ..., "selesai": False, "user": ...}


def buat_permintaan_login_browser() -> str:
    """Buat token satu-pakai untuk login lewat browser; dipakai tool masuk_browser."""
    token = secrets.token_urlsafe(24)
    _BROWSER.clear()                     # satu permintaan aktif cukup
    _BROWSER.update({"token": token, "dibuat": time.time(), "selesai": False, "user": None})
    return token


def permintaan_login_browser(token: str) -> dict | None:
    """Ambil permintaan aktif bila token cocok dan belum kedaluwarsa (10 menit)."""
    b = _BROWSER.get("token")
    if not b or not hmac.compare_digest(b, token):
        return None
    if time.time() - _BROWSER.get("dibuat", 0) > 600:
        return None
    return _BROWSER


def tandai_login_browser_sukses(token: str, user: dict) -> str:
    """Dipanggil handler /login-browser setelah verifikasi; set sesi chat."""
    _BROWSER["selesai"] = True
    _BROWSER["user"] = {"username": user["username"], "peran": user["peran"],
                        "label": user.get("label", user["username"]),
                        "nama": user.get("nama", user["username"])}
    atur_sesi_chat(user)
    return _BROWSER["token"]


@dataclass
class PendingLogin:
    client: OAuthClientInformationFull
    params: AuthorizationParams
    dibuat: float = field(default_factory=time.time)
    percobaan: int = 0


@dataclass
class EntriToken:
    klien: OAuthClientInformationFull
    scopes: list[str]
    subject: str
    berakhir: float | None
    resource: str | None = None
    code_challenge: str | None = None      # khusus authorization code
    redirect_uri: str | None = None        # khusus authorization code
    claims: dict | None = None
    pasangan: str | None = None            # access & refresh dari satu login berbagi id ini


# ------------------------------------------------ mengelola sesi login (wajib login lagi)
# pasangan-token -> status sesi. Modul-level agar auth.py/server bisa membaca.
SESI: dict[str, dict] = {}


def state_sesi(pasangan: str | None) -> dict | None:
    if not pasangan:
        return None
    s = SESI.get(pasangan)
    return dict(s) if s else None


def minta_login_ulang(pasangan: str) -> None:
    s = SESI.get(pasangan)
    if s:
        s["butuh_login"] = True
        log.info("Sesi %s... diminta logout (butuh login ulang)", pasangan[:8])


def aktifkan_sesi(pasangan: str, user: dict) -> bool:
    """Setelah login browser sukses: peran baru aktif pada sesi yang sama."""
    s = SESI.get(pasangan)
    if not s:
        return False
    s.update({"username": user["username"], "peran": user["peran"],
              "label": user.get("label", user["username"]),
              "nama": user.get("nama", user["username"]),
              "butuh_login": False, "percobaan": 0})
    log.info("Sesi %s... aktif ulang: %s (%s)", pasangan[:8], user["username"], user["peran"])
    return True


class TigaBeOAuthProvider(OAuthAuthorizationServerProvider):
    """Implementasi penyimpanan-sederhana; semua state in-memory."""

    def __init__(self) -> None:
        self.klien: dict[str, OAuthClientInformationFull] = {}
        self.pending: dict[str, PendingLogin] = {}
        self.kode: dict[str, EntriToken] = {}
        self.oauth_tokens: dict[str, EntriToken] = {}
        self.refresh_tokens: dict[str, EntriToken] = {}

    # -- util
    @staticmethod
    def _bersih(store: dict[str, EntriToken]) -> None:
        sekarang = time.time()
        for k in [k for k, v in store.items() if v.berakhir and v.berakhir < sekarang]:
            store.pop(k, None)

    # -- klien
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.klien.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.klien[client_info.client_id] = client_info
        log.info("Klien OAuth terdaftar: %s (%s)",
                 client_info.client_id, client_info.client_name or "-")

    # -- authorize
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        """SDK meneruskan /authorize ke sini; kita arahkan ke halaman /login."""
        try:
            sekarang = time.time()
            kedaluwarsa = sekarang - PENDING_MENIT * 60
            for sid in [s for s, p in self.pending.items() if p.dibuat < kedaluwarsa]:
                self.pending.pop(sid, None)
            sid = secrets.token_urlsafe(24)
            self.pending[sid] = PendingLogin(client=client, params=params)
            return f"{ORIGIN_URL}/login?sid={sid}"
        except Exception:
            log.exception("authorize() gagal menyiapkan sesi login")
            raise

    # -- authorization code
    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        self._bersih(self.kode)
        e = self.kode.get(authorization_code)
        if e is None or e.klien.client_id != client.client_id:
            return None
        return AuthorizationCode(
            code=authorization_code,
            scopes=e.scopes,
            expires_at=e.berakhir or 0.0,
            client_id=e.klien.client_id,
            code_challenge=e.code_challenge or "",
            redirect_uri=e.redirect_uri or "",
            redirect_uri_provided_explicitly=True,
            resource=e.resource,
            subject=e.subject,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        e = self.kode.pop(authorization_code.code, None)
        if e is None:
            raise TokenError(error="invalid_grant", error_description="kode sudah dipakai")
        users = muat_users()
        u = users.get(e.subject)
        if u is None:
            raise TokenError(error="invalid_grant", error_description="pengguna tidak ditemukan")
        return self._keluarkan_token(client, u, e.scopes, e.resource)

    # -- refresh token
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        self._bersih(self.refresh_tokens)
        e = self.refresh_tokens.get(refresh_token)
        if e is None or e.klien.client_id != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token, client_id=client.client_id, scopes=e.scopes,
            expires_at=int(e.berakhir or 0), resource=e.resource, subject=e.subject,
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull,
        refresh_token: RefreshToken, scopes: list[str],
    ) -> OAuthToken:
        e = self.refresh_tokens.pop(refresh_token.token, None)
        if e is None:
            raise TokenError(error="invalid_grant", error_description="refresh tidak valid")
        # sesi yang sudah 'keluar' TIDAK boleh refresh diam-diam;
        # wajib lewat /ganti (login browser) agar peran baru terkonfirmasi.
        if e.pasangan and (SESI.get(e.pasangan) or {}).get("butuh_login"):
            log.info("Refresh ditolak: sesi %s... sedang wajib_login", e.pasangan[:8])
            raise TokenError(error="invalid_grant",
                             error_description="sesi sudah keluar; login ulang lewat browser")
        users = muat_users()
        u = users.get(e.subject)
        if u is None:
            raise TokenError(error="invalid_grant", error_description="pengguna tidak ditemukan")
        # terbitkan token baru TANPA menimpa status sesi (termasuk flag keluar)
        tokens = self._keluarkan_token(client, u, scopes or e.scopes, e.resource,
                                       pertahankan_pasangan=e.pasangan)
        return tokens

    async def load_access_token(self, token: str) -> AccessToken | None:
        self._bersih(self.oauth_tokens)
        e = self.oauth_tokens.get(token)
        if e is None:
            return None
        if e.berakhir is not None and e.berakhir < time.time():
            return None
        return AccessToken(
            token=token, client_id=e.klien.client_id, scopes=e.scopes,
            expires_at=int(e.berakhir or 0), resource=e.resource,
            subject=e.subject, claims=e.claims,
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, AccessToken):
            self.oauth_tokens.pop(token.token, None)
        else:
            self.refresh_tokens.pop(token.token, None)

    def terbitkan_token_langsung(self, username: str, klien_label: str = "chat") -> dict | None:
        """Terbitkan access+refresh token utk user (tanpa lewat OAuth flow).

        Dipakai tool 'masuk' (login dari chat). Password diverifikasi pemanggil;
        di sini cukup lookup user.
        """
        users = muat_users()
        user = users.get(username)
        if user is None:
            return None
        klien_sementara = OAuthClientInformationFull.model_validate({
            "client_id": f"chat-{username}",
            "client_name": f"chat:{username}",
            "redirect_uris": [],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        })
        self.klien.setdefault(klien_sementara.client_id, klien_sementara)
        tokens = self._keluarkan_token(
            klien_sementara, user, scopes=["mcp", f"peran:{user['peran']}"], resource=None,
        )
        return {"access": tokens.access_token, "refresh": tokens.refresh_token,
                "peran": user["peran"], "label": user.get("label", user["username"])}

    def cabut_sesi(self, pasangan: str) -> int:
        """Hapus seluruh token (akses + refresh) milik satu sesi login."""
        jumlah = 0
        for t in [t for t, e in self.oauth_tokens.items() if e.pasangan == pasangan]:
            self.oauth_tokens.pop(t, None); jumlah += 1
        for t in [t for t, e in self.refresh_tokens.items() if e.pasangan == pasangan]:
            self.refresh_tokens.pop(t, None); jumlah += 1
        if jumlah:
            log.info("Sesi %s... dicabut (%s token)", pasangan[:8], jumlah)
        return jumlah

    # -- keluarkan pasangan token
    def _keluarkan_token(
        self, klien: OAuthClientInformationFull, user: dict,
        scopes: list[str], resource: str | None,
        pertahankan_pasangan: str | None = None,
    ) -> OAuthToken:
        akses = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        sekarang = time.time()
        # refresh memakai pasangan sesi yang sama agar flag keluar/peran tetap
        pasangan = pertahankan_pasangan or secrets.token_urlsafe(12)
        claims = {
            "peran": user["peran"],
            "label": user.get("label", user["username"]),
            "nama": user.get("nama", user["username"]),
            "iss": ISSUER_URL,
            "sesi": pasangan,
        }
        self.oauth_tokens[akses] = EntriToken(
            klien=klien, scopes=scopes, subject=user["username"],
            berakhir=sekarang + AKSES_DET, resource=resource, claims=claims,
            pasangan=pasangan,
        )
        self.refresh_tokens[refresh] = EntriToken(
            klien=klien, scopes=scopes, subject=user["username"],
            berakhir=sekarang + REFRESH_DET, resource=resource, claims=claims,
            pasangan=pasangan,
        )
        if pasangan not in SESI:      # login baru; jangan timpa status 'keluar'
            SESI[pasangan] = {
                "username": user["username"], "peran": user["peran"],
                "label": user.get("label", user["username"]),
                "nama": user.get("nama", user["username"]),
                "butuh_login": False, "percobaan": 0,
            }
        log.info("Token diterbitkan: user=%s peran=%s klien=%s",
                 user["username"], user["peran"], klien.client_id)
        return OAuthToken(
            access_token=akses, token_type="Bearer",
            expires_in=AKSES_DET, scope=" ".join(scopes),
            refresh_token=refresh,
        )


# ------------------------------------------------------------------ /login
_LOGIN_HTML = """<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login TigaBe MCP</title>
<style>
body{font-family:system-ui,sans-serif;background:#f4f6f8;display:grid;place-items:center;height:100vh;margin:0}
.kartu{background:#fff;border:1px solid #d9dee3;border-radius:10px;padding:28px 32px;
       box-shadow:0 4px 14px rgba(0,0,0,.08);width:min(320px,92vw)}
h1{font-size:1.15rem;margin:0 0 4px}.sub{color:#69737a;font-size:.72rem;margin:0 0 16px}
label{display:block;font-size:.8rem;color:#3f4650;margin:10px 0 4px}
input{box-sizing:border-box;width:100%;padding:9px 10px;border:1px solid #cfd6dc;border-radius:6px;font-size:.95rem}
button{margin-top:16px;width:100%;padding:10px;border:0;border-radius:6px;
       background:#1a73e8;color:#fff;font-weight:600;cursor:pointer;font-size:.9rem}
.galat{color:#b3261e;font-size:.78rem;margin-top:10px}
</style></head><body>
<div class="kartu">
  <h1>Login TigaBe MCP</h1>
  <p class="sub">Pengesahan dokumen resmi SD TigaBe. Password tidak pernah dikirim ke model.</p>
  {galat}
  <form method="POST" action="/login">
    <input type="hidden" name="sid" value="{sid}">
    <input type="hidden" name="csrf_token" value="{csrf}">
    <label for="u">Username</label>
    <input id="u" name="username" autocomplete="username" required>
    <label for="p">Password</label>
    <input id="p" type="password" name="password" autocomplete="current-password" required>
    <button type="submit">Masuk</button>
  </form>
</div></body></html>"""

_LOGIN_BALIK = """<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Login berhasil</title>
<style>body{font-family:system-ui,sans-serif;background:#f4f6f8;display:grid;place-items:center;height:100vh;margin:0}
.kartu{background:#fff;border:1px solid #d9dee3;border-radius:10px;padding:28px 32px;width:min(320px,92vw)}
h1{font-size:1.1rem;margin:0 0 6px}p{color:#5f6b76;font-size:.85rem}</style></head><body>
<div class="kartu"><h1>Login berhasil</h1>
<p>Peran <b>{peran}</b> ({label}) ditetapkan. Kembali ke WorkBuddy untuk melanjutkan.</p></div>
</body></html>"""


_LOGIN_BROWSER_HTML = """<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login Browser - TigaBe MCP</title>
<style>
body{font-family:system-ui,sans-serif;background:#f4f6f8;display:grid;place-items:center;height:100vh;margin:0}
.kartu{background:#fff;border:1px solid #d9dee3;border-radius:10px;padding:28px 32px;
       box-shadow:0 4px 14px rgba(0,0,0,.08);width:min(320px,92vw)}
h1{font-size:1.15rem;margin:0 0 4px}.sub{color:#69737a;font-size:.72rem;margin:0 0 16px}
label{display:block;font-size:.8rem;color:#3f4650;margin:10px 0 4px}
input{box-sizing:border-box;width:100%;padding:9px 10px;border:1px solid #cfd6dc;border-radius:6px;font-size:.95rem}
button{margin-top:16px;width:100%;padding:10px;border:0;border-radius:6px;
       background:#1a73e8;color:#fff;font-weight:600;cursor:pointer;font-size:.9rem}
.galat{color:#b3261e;font-size:.78rem;margin-top:10px}
</style></head><body>
<div class="kartu">
  <h1>Login TigaBe MCP</h1>
  <p class="sub">Password diketik di sini (browser), TIDAK dikirim ke model/chat.</p>
  {galat}
  <form method="POST" action="/login-browser">
    <input type="hidden" name="token" value="{token}">
    <input type="hidden" name="csrf_token" value="{csrf}">
    <label for="u">Username</label>
    <input id="u" name="username" autocomplete="username" required>
    <label for="p">Password</label>
    <input id="p" type="password" name="password" autocomplete="current-password" required>
    <button type="submit">Masuk</button>
  </form>
</div></body></html>"""

_LOGIN_BROWSER_BERHASIL = """<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Login berhasil</title>
<style>body{font-family:system-ui,sans-serif;background:#f4f6f8;display:grid;place-items:center;height:100vh;margin:0}
.kartu{background:#fff;border:1px solid #d9dee3;border-radius:10px;padding:28px 32px;width:min(320px,92vw)}
h1{font-size:1.1rem;margin:0 0 6px}p{color:#5f6b76;font-size:.85rem}</style></head><body>
<div class="kartu"><h1>Login berhasil ✓</h1>
<p>Peran aktif sekarang: <b>{peran}</b> ({label}).</p>
<p>Silakan kembali ke jendela <b>WorkBuddy</b> dan tanyakan apa saja —
peran ini sudah aktif untuk sesi chat Anda.</p></div>
</body></html>"""


def pasang_login(mcp, provider: TigaBeOAuthProvider) -> None:
    """Pasang rute /login (alur OAuth), /ganti (ganti peran dari chat),
    dan /login-browser (login dari chat tanpa mengetik password di chat)."""

    @mcp.custom_route("/login", methods=["GET", "POST"])
    async def halaman_login(request: Request):
        try:
            return await _proses_login(request, buat_kode=True)
        except Exception:
            log.exception("handler /login gagal")
            raise

    @mcp.custom_route("/ganti", methods=["GET", "POST"])
    async def halaman_ganti(request: Request):
        """Login ulang untuk sesi yang sudah 'keluar' dari chat.

        sid = id pasangan sesi (dari tool keluar/peran_saya). Berhasil login ->
        peran baru aktif pada sesi yang sama; klien tidak perlu reconnect."""
        try:
            return await _proses_login(request, buat_kode=False)
        except Exception:
            log.exception("handler /ganti gagal")
            raise

    @mcp.custom_route("/login-browser", methods=["GET", "POST"])
    async def halaman_login_browser(request: Request):
        """Dibuka dari link yang diberikan tool 'masuk_browser'.

        GET  : form login (token permintaan tersemat).
        POST : verifikasi -> sesi chat diganti -> halaman 'kembali ke chat'.
        Password diketik di browser, tidak pernah dikirim ke model."""
        try:
            if request.method == "GET":
                token = request.query_params.get("token") or ""
                if permintaan_login_browser(token) is None:
                    return HTMLResponse("<h3>Tautan login kedudaluarsa</h3>"
                                        "<p>Minta tautan baru lewat chat "
                                        "(panggil tool masuk_browser).</p>",
                                        status_code=404)
                sesi_browser = request.session
                csrf_olah = sesi_browser.get("csrf") or secrets.token_hex(16)
                sesi_browser["csrf"] = csrf_olah
                return HTMLResponse(_LOGIN_BROWSER_HTML
                                    .replace("{token}", html.escape(token))
                                    .replace("{csrf}", html.escape(csrf_olah)),
                                    headers={"Cache-Control": "no-store"})

            form = await request.form()
            token = str(form.get("token") or "")
            permintaan = permintaan_login_browser(token)
            if permintaan is None:
                return HTMLResponse("<h3>Tautan login kedudaluarsa</h3>"
                                    "<p>Minta tautan baru lewat chat.</p>",
                                    status_code=404)
            sesi_browser = request.session
            csrf_olah = sesi_browser.get("csrf") or ""
            if not hmac.compare_digest(str(form.get("csrf_token") or ""), csrf_olah):
                return HTMLResponse("<h3>Form tidak valid</h3><p>Muat ulang tautan.</p>",
                                    status_code=400)
            username = str(form.get("username") or "").strip()
            password = str(form.get("password") or "")
            user = muat_users().get(username)
            if user is None or not verifikasi_password(user.get("password_hash", ""), password):
                log.warning("login-browser gagal: user=%s***", username[:3])
                csrf_olah = secrets.token_hex(16)
                sesi_browser["csrf"] = csrf_olah
                return HTMLResponse(_LOGIN_BROWSER_HTML
                                    .replace("{token}", html.escape(token))
                                    .replace("{csrf}", html.escape(csrf_olah))
                                    .replace("{galat}", '<p class="galat">Username / password salah.</p>'),
                                    headers={"Cache-Control": "no-store"})
            tandai_login_browser_sukses(token, user)
            import audit as audit_lib
            audit_lib.catat_aktivitas(user["username"], user["peran"], "login_browser",
                            {"username": user["username"]},
                            ringkas=f"peran aktif {user['peran']} via browser")
            return HTMLResponse(_LOGIN_BROWSER_BERHASIL
                                .replace("{peran}", html.escape(user["peran"]))
                                .replace("{label}", html.escape(user.get("label", user["username"]))),
                                headers={"Cache-Control": "no-store"})
        except Exception:
            log.exception("handler /login-browser gagal")
            raise

    def _rerender(galat: str, sid: str, csrf_olah: str) -> HTMLResponse:
        halaman = (_LOGIN_HTML
                   .replace("{galat}", f'<p class="galat">{html.escape(galat)}</p>' if galat else "")
                   .replace("{sid}", html.escape(sid))
                   .replace("{csrf}", html.escape(csrf_olah)))
        return HTMLResponse(halaman, headers={"Cache-Control": "no-store"})

    async def _proses_login(request: Request, buat_kode: bool):
        if request.method == "GET":
            sid = request.query_params.get("sid")
        else:
            sid = (await request.form()).get("sid")

        if buat_kode:
            pending = provider.pending.get(str(sid or ""))
            valid = pending is not None and time.time() - pending.dibuat <= PENDING_MENIT * 60
            if not valid:
                return HTMLResponse("<h3>Login kedudaluarsa</h3>"
                                    "<p>Silakan ulangi permintaan dari klien MCP Anda.</p>",
                                    status_code=404)
        else:
            # /ganti: sid adalah id sesi pasangan-token yang sudah 'keluar'
            state_s = state_sesi(str(sid or ""))
            if state_s is None:
                return HTMLResponse("<h3>Sesi tidak dikenal</h3>"
                                    "<p>Minta tautan login baru lewat chat "
                                    "(panggil tool peran_saya atau keluar).</p>",
                                    status_code=404)

        sesi_browser = request.session
        csrf_olah = sesi_browser.get("csrf")
        if request.method == "GET" or not csrf_olah:
            csrf_olah = secrets.token_hex(16)
            sesi_browser["csrf"] = csrf_olah
        galat = ""

        if request.method == "POST":
            form = await request.form()
            form_csrf = str(form.get("csrf_token") or "")
            if not hmac.compare_digest(form_csrf, csrf_olah):
                galat = "Form tidak valid, silakan muat ulang."
            else:
                username = str(form.get("username") or "").strip()
                password = str(form.get("password") or "")
                users = muat_users()
                user = users.get(username)
                if user is None or not verifikasi_password(user.get("password_hash", ""), password):
                    # hitung percobaan: pakai pending bila ada, atau SESI
                    if buat_kode:
                        pending = provider.pending.get(str(sid))
                        pending.percobaan += 1
                        percobaan = pending.percobaan
                    else:
                        st = SESI.get(str(sid))
                        st["percobaan"] = st.get("percobaan", 0) + 1
                        percobaan = st["percobaan"]
                    log.warning("Login gagal: user=%s (percobaan %s)",
                                username[:3] + "***", percobaan)
                    if percobaan >= MAKS_PERCOBAAN:
                        if buat_kode:
                            provider.pending.pop(str(sid), None)
                        return HTMLResponse("<h3>Login diblokir</h3><p>Minta tautan baru "
                                            "dari klien MCP.</p>", status_code=429)
                    galat = "Username / password salah."
                else:
                    if buat_kode:
                        kode = secrets.token_urlsafe(32)
                        provider.kode[kode] = EntriToken(
                            klien=pending.client, scopes=pending.params.scopes or [],
                            subject=user["username"], berakhir=time.time() + CODE_MENIT * 60,
                            resource=pending.params.resource,
                            code_challenge=pending.params.code_challenge,
                            redirect_uri=str(pending.params.redirect_uri),
                        )
                        provider.pending.pop(str(sid), None)
                        sesi_browser.pop("csrf", None)
                        query = urlencode({"code": kode, "state": pending.params.state or ""})
                        return RedirectResponse(
                            url=f"{pending.params.redirect_uri}?{query}", status_code=302,
                            headers={"Cache-Control": "no-store"},
                        )
                    # mode /ganti: aktifkan peran baru pada sesi yang sama
                    aktifkan_sesi(str(sid), user)
                    sesi_browser.pop("csrf", None)
                    return HTMLResponse(_LOGIN_BALIK.replace(
                        "{peran}", html.escape(user["peran"])
                    ).replace("{label}", html.escape(user.get("label", user["username"]))),
                        headers={"Cache-Control": "no-store"})

        return _rerender(galat, str(sid), csrf_olah)

    return None
