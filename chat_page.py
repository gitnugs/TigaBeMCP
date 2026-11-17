"""Halaman chat + aksi deploy.

Rute:
  /chat            -> antarmuka chat (tanya dokumen) + tombol push/deploy
  /chat/ask        (POST) -> tanya (pakai cari_dokumen), balasan teks
  /chat/push       (POST) -> git add/commit/push
  /chat/deploy     (POST) -> trigger workflow_dispatch GitHub Actions

Akses: hanya localhost.
"""
from __future__ import annotations

import html
import json
import os
import subprocess
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from html_theme import IKON, wadah
from search import cari
from auth import akses_efektif, PERAN

BASE_DIR = Path(__file__).resolve().parent

def _lokal(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    return host in ("127.0.0.1", "::1", "localhost")

def _laman(pesan: str = "") -> HTMLResponse:
    isi = (
        '<div class="card"><div class="card-h"><h3>Chat Agent</h3></div>'
        '<div class="card-b">'
        '<div id="log" style="height:320px;overflow:auto;border:1px solid var(--border);'
        'border-radius:8px;padding:10px;margin-bottom:10px;background:var(--surface-2)"></div>'
        '<div style="display:flex;gap:8px">'
        '<input id="q" style="flex:1" placeholder="Tanya soal dokumen sekolah..."/>'
        '<button class="btn primary" onclick="kirim()">Kirim</button>'
        '</div>'
        '<div style="display:flex;gap:8px;margin-top:10px">'
        '<button class="btn" onclick="push()">Push ke GitHub</button>'
        '<button class="btn" onclick="deploy()">Jalankan Pipeline Deploy</button>'
        '</div>'
        '<pre id="status" style="margin-top:10px"></pre>'
        '</div></div>'
        '<script>'
        'async function kirim(){const q=document.getElementById("q").value.trim();'
        'if(!q)return;const r=await fetch("/chat/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({q})});'
        'const d=await r.json();const log=document.getElementById("log");'
        'log.innerHTML+="<p><b>Anda:</b> "+q+"</p>";log.innerHTML+="<p><b>Agent:</b> "+(d.reply||d.error)+"</p>";'
        'document.getElementById("q").value="";}'
        'async function push(){const r=await fetch("/chat/push",{method:"POST"});const d=await r.json();'
        'document.getElementById("status").textContent=JSON.stringify(d,null,2);}'
        'async function deploy(){const r=await fetch("/chat/deploy",{method:"POST"});const d=await r.json();'
        'document.getElementById("status").textContent=JSON.stringify(d,null,2);}'
        '</script>'
    )
    html_doc = wadah("Chat", "Komunikasi dengan agent + aksi deploy.", "chat",
                     {"isi": isi, "pesan": pesan, "galat": ""}, "Chat TigaBe", "")
    return HTMLResponse(html_doc)

def pasang_chat(mcp) -> None:
    @mcp.custom_route("/chat", methods=["GET"])
    async def chat_home(request: Request):
        if not _lokal(request):
            return HTMLResponse("403", status_code=403)
        return _laman()

    @mcp.custom_route("/chat/ask", methods=["POST"])
    async def chat_ask(request: Request):
        if not _lokal(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        data = await request.json()
        q = str(data.get("q", "")).strip()
        if not q:
            return JSONResponse({"error": "query kosong"})
        try:
            res = cari(q, 5, None, akses=["public"])
            hasil = res.get("hasil", [])
            if not hasil:
                reply = "Tidak ditemukan dokumen relevan."
            else:
                reply = "\n".join(f"- {h.get('judul','-')}: {h.get('kutipan','-')[:200]}" for h in hasil)
        except Exception as e:
            reply = f"Error: {type(e).__name__}"
        return JSONResponse({"reply": reply})

    @mcp.custom_route("/chat/push", methods=["POST"])
    async def chat_push(request: Request):
        if not _lokal(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        try:
            subprocess.run(["git", "add", "-A"], cwd=BASE_DIR, check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "chat: update"], cwd=BASE_DIR, check=True, capture_output=True, text=True)
            r = subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, check=True, capture_output=True, text=True)
            return JSONResponse({"status": "ok", "output": r.stdout + r.stderr})
        except subprocess.CalledProcessError as e:
            return JSONResponse({"status": "error", "stdout": e.stdout, "stderr": e.stderr}, status_code=500)

    @mcp.custom_route("/chat/deploy", methods=["POST"])
    async def chat_deploy(request: Request):
        if not _lokal(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        token = os.environ.get("GITHUB_TOKEN", "")
        repo = os.environ.get("GITHUB_REPO", "")
        if not token or not repo:
            return JSONResponse({"error": "GITHUB_TOKEN/GITHUB_REPO belum diset"}, status_code=400)
        import urllib.request
        url = f"https://api.github.com/repos/{repo}/actions/workflows/ci.yml/dispatches"
        req = urllib.request.Request(url, data=json.dumps({"ref": "main"}).encode(), headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                return JSONResponse({"status": "triggered", "http": resp.status})
        except Exception as e:
            return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
