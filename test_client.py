"""Uji MCP Server via OAuth lokal lalu panggil tool.

Prasyarat:
  python scripts/buat_user.py --username uji --peran guru --password rahasia
  server.py aktif di 127.0.0.1:18105

Jalankan:
  python test_client.py
"""
import asyncio
import base64
import hashlib
import http.cookiejar
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
import urllib.response


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None


BASE = os.environ.get("MCP_URL", "http://127.0.0.1:18105")
USERNAME = os.environ.get("MCP_USER", "uji")
PASSWORD = os.environ.get("MCP_PASS", "")


def _req(opener, method, url, data=None, headers=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    h = dict(headers or {})
    if body is not None:
        h.setdefault("Content-Type", "application/x-www-form-urlencoded")
    r = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        resp = opener.open(r, timeout=15)
        locs = resp.headers.get_all("Location") or []
        return resp.status, (locs[0] if locs else None), resp.read().decode()
    except urllib.error.HTTPError as e:
        locs = e.headers.get_all("Location") or []
        return e.code, (locs[0] if locs else None), e.read().decode()


async def dapatkan_token() -> str:
    """OAuth code + PKCE: register -> authorize -> login -> token."""
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), NoRedirect)
    if not PASSWORD:
        raise SystemExit("Set MCP_PASS untuk password pengguna uji")

    reg = {"client_name": "uji-cli",
           "redirect_uris": ["http://127.0.0.1:19999/callback"],
           "grant_types": ["authorization_code", "refresh_token"],
           "response_types": ["code"],
           "token_endpoint_auth_method": "none"}
    r = urllib.request.Request(BASE + "/register", data=json.dumps(reg).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    client = json.loads(op.open(r, timeout=15).read().decode())

    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    qs = urllib.parse.urlencode({
        "response_type": "code", "client_id": client["client_id"],
        "redirect_uri": "http://127.0.0.1:19999/callback",
        "code_challenge": challenge, "code_challenge_method": "S256",
        "state": "uji", "scope": "mcp"})
    try:
        op.open(BASE + "/authorize?" + qs, timeout=15)
        raise RuntimeError("authorize seharusnya 302")
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location")
    halaman = op.open(loc, timeout=15).read().decode()
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', halaman).group(1)
    sid = re.search(r'name="sid" value="([^"]+)"', halaman).group(1)

    data = urllib.parse.urlencode({"sid": sid, "csrf_token": csrf,
                                   "username": USERNAME, "password": PASSWORD}).encode()
    r = urllib.request.Request(BASE + "/login", data=data,
                               headers={"Content-Type": "application/x-www-form-urlencoded"},
                               method="POST")
    try:
        resp = op.open(r, timeout=15)
        raise RuntimeError("login seharusnya 302; cek username/password")
    except urllib.error.HTTPError as e:
        loc_cb = e.headers.get("Location")
    kode = urllib.parse.parse_qs(urllib.parse.urlparse(loc_cb).query)["code"][0]

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": kode,
        "redirect_uri": "http://127.0.0.1:19999/callback",
        "client_id": client["client_id"], "code_verifier": verifier}).encode()
    r = urllib.request.Request(BASE + "/token", data=body,
                               headers={"Content-Type": "application/x-www-form-urlencoded"},
                               method="POST")
    token_json = json.loads(op.open(r, timeout=15).read().decode())
    return token_json["access_token"]


async def main() -> None:
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    token = await dapatkan_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx2.AsyncClient(headers=headers) as http:
        async with Client(streamable_http_client(BASE + "/mcp", http_client=http)) as client:
            daftar = await client.list_tools()
            print("Tools tersedia:", [t.name for t in daftar.tools])

            peran = await client.call_tool("peran_saya", {})
            if peran.is_error:
                raise RuntimeError(f"peran_saya gagal: {peran.content}")
            data = json.loads("\n".join(getattr(c, "text", "") for c in peran.content))
            print("Peran sesi:", data.get("peran"), "| akses:", data.get("akses_dokumen"))

            hasil = await client.call_tool(
                "cari_dokumen", {"query": "seragam Rabu kelas 4", "top_k": 3})
            if hasil.is_error:
                raise RuntimeError(f"cari_dokumen gagal: {hasil.content}")
            data = json.loads("\n".join(getattr(c, "text", str(c)) for c in hasil.content))
            for h in data.get("hasil", []):
                print(f"  {h['skor']}  {h['document_id']} hlm {h['halaman']} | {h['kutipan'][:70]!r}")


if __name__ == "__main__":
    asyncio.run(main())
