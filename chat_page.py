"""Halaman chat + aksi deploy.

Rute:
  /chat            -> antarmuka chat (tanya dokumen) + tombol push/deploy
  /chat/ask        (POST) -> tanya (pakai cari_dokumen), balasan teks + sitasi
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

_PERAN_OPSI = "".join(
    f'<option value="{html.escape(n)}">{html.escape(p.label)}</option>'
    for n, p in PERAN.items()
)


def _lokal(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    if host in ("127.0.0.1", "::1", "localhost"):
        return True
    try:
        from auth import host_diizinkan
        req_host = request.headers.get("host", "").split(":")[0]
        if req_host and req_host in [h.split(":")[0] for h in host_diizinkan()]:
            return True
    except Exception:
        pass
    return False


def _laman(pesan: str = "") -> HTMLResponse:
    isi = r'''
<style>
/* ---- Chat shell (ChatGPT/WorkBuddy style) ---- */
.chat-shell{display:flex;flex-direction:column;height:calc(100vh - 150px);min-height:520px;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow-sm);overflow:hidden}
.chat-top{display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:12px 16px;border-bottom:1px solid var(--border);background:var(--surface-2);flex-wrap:wrap}
.chat-title{display:flex;align-items:center;gap:10px;font-weight:600;font-size:.95rem}
.chat-title svg{width:18px;height:18px;color:var(--accent)}
.chat-controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.chat-controls select,.chat-controls button{font:inherit;font-size:.82rem;padding:6px 10px;
  border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--ink);cursor:pointer}
.chat-controls select{min-width:150px}
.chat-controls button:hover{background:var(--surface-2)}
.chat-controls .danger{border-color:var(--danger-border);color:var(--danger)}
.chat-messages{flex:1;overflow:auto;padding:20px 16px;display:flex;flex-direction:column;gap:16px;
  scroll-behavior:smooth}
.empty-state{text-align:center;color:var(--muted);margin:auto;padding:40px 20px;max-width:420px}
.empty-state h3{color:var(--ink);margin:0 0 6px;font-size:1.05rem}
.empty-state p{margin:0;font-size:.85rem}
.msg{display:flex;gap:10px;max-width:100%}
.msg.user{justify-content:flex-end}
.avatar{width:30px;height:30px;border-radius:50%;flex:none;display:flex;align-items:center;
  justify-content:center;font-size:.75rem;font-weight:700;color:#fff}
.avatar.user{background:var(--accent)}
.avatar.agent{background:linear-gradient(135deg,#2B8CE8,#5AB0F5)}
.bubble{max-width:min(78%,720px);padding:12px 16px;border-radius:16px;font-size:.92rem;
  line-height:1.55;word-break:break-word}
.bubble.user{background:var(--accent);color:#fff;border-bottom-right-radius:4px}
.bubble.agent{background:var(--surface-2);border:1px solid var(--border);border-bottom-left-radius:4px}
.bubble.agent p{margin:0 0 8px}.bubble.agent p:last-child{margin:0}
.bubble.agent ul,.bubble.agent ol{margin:6px 0 8px 18px;padding:0}
.bubble.agent li{margin:2px 0}
.bubble.agent code{background:rgba(0,0,0,.35);padding:1px 5px;border-radius:4px;font-size:.85em}
.bubble.agent pre{background:#0e0f11;border:1px solid var(--border);border-radius:8px;
  padding:10px 12px;overflow:auto;margin:8px 0;font-size:.82rem}
.bubble.agent pre code{background:none;padding:0}
.bubble.agent a{color:var(--accent-hover)}
.citations{margin-top:10px;overflow-x:auto}
.cite-table,.md-table{width:100%;border-collapse:collapse;font-size:.78rem;min-width:320px}
.cite-table th,.cite-table td,.md-table th,.md-table td{border:1px solid var(--border);padding:6px 8px;text-align:left;vertical-align:top}
.cite-table th,.md-table th{background:var(--surface);color:var(--muted);font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em}
.cite-table tr:nth-child(even) td,.md-table tr:nth-child(even) td{background:rgba(255,255,255,.02)}
.bubble.agent .md-table{margin:8px 0}
.bubble.agent .md-table th{color:var(--ink-2)}
.cite-badge{font-size:.7rem;padding:2px 7px;border-radius:999px;border:1px solid var(--border);
  color:var(--muted);white-space:nowrap;display:inline-block}
.cite-badge.ok{color:#58C98A;border-color:var(--success-border);background:var(--success-soft)}
.cite-badge.warn{color:#F1B33C;border-color:var(--amber-border);background:var(--amber-soft)}
.cite-link{color:var(--accent);text-decoration:none;font-weight:500}
.cite-link:hover{text-decoration:underline}
.cite-snippet{color:var(--ink-2);font-size:.75rem;margin-top:3px;max-width:320px;white-space:pre-wrap}
.typing{display:flex;gap:4px;padding:4px 0 4px 40px}
.typing span{width:7px;height:7px;border-radius:50%;background:var(--muted);animation:bounce 1.2s infinite}
.typing span:nth-child(2){animation-delay:.15s}.typing span:nth-child(3){animation-delay:.3s}
@keyframes bounce{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-6px);opacity:1}}
.chat-input{display:flex;gap:8px;padding:12px 16px;border-top:1px solid var(--border);
  background:var(--surface-2);align-items:flex-end}
.chat-input textarea{flex:1;resize:none;min-height:42px;max-height:160px;padding:10px 14px;
  border-radius:12px;border:1px solid var(--border);background:var(--surface);color:var(--ink);
  font:inherit;font-size:.92rem;line-height:1.4}
.chat-input textarea:focus{outline:none;border-color:var(--accent)}
.chat-input button{padding:10px 16px;border-radius:12px;border:none;background:var(--accent);
  color:#fff;font-weight:600;cursor:pointer;font-size:.9rem}
.chat-input button:disabled{opacity:.5;cursor:not-allowed}
.chat-input button:hover:not(:disabled){background:var(--accent-hover)}
.status-line{margin:6px 16px 0;font-family:ui-monospace,monospace;font-size:.75rem;
  color:var(--muted);white-space:pre-wrap;max-height:120px;overflow:auto}
@media (max-width:720px){.chat-shell{height:calc(100vh - 120px)}.bubble{max-width:92%}}
</style>

<div class="chat-shell">
  <div class="chat-top">
    <div class="chat-title">__CHAT_ICON__ Chat TigaBe</div>
    <div class="chat-controls">
      <label style="font-size:.78rem;color:var(--muted)">Peran:</label>
      <select id="role">__PERAN_OPTS__</select>
      <button id="btn-clear" type="button">Hapus chat</button>
      <button id="btn-push" type="button">Push GitHub</button>
      <button id="btn-deploy" type="button">Deploy</button>
    </div>
  </div>
  <div class="chat-messages" id="log">
    <div class="empty-state" id="empty">
      <h3>Mulai percakapan</h3>
      <p>Tanyakan soal dokumen sekolah, mis. "seragam kelas 4 hari Rabu pakai apa?".
      Pilih peran di atas untuk menyesuaikan akses dokumen.</p>
    </div>
  </div>
  <div class="typing" id="typing" hidden><span></span><span></span><span></span></div>
  <div class="chat-input">
    <textarea id="q" rows="1" placeholder="Ketik pertanyaan... (Enter kirim, Shift+Enter baris baru)"></textarea>
    <button id="send" type="button">Kirim</button>
  </div>
  <pre class="status-line" id="status"></pre>
</div>

<script>
(function(){
  const log = document.getElementById('log');
  const empty = document.getElementById('empty');
  const q = document.getElementById('q');
  const sendBtn = document.getElementById('send');
  const typing = document.getElementById('typing');
  const status = document.getElementById('status');
  const roleSel = document.getElementById('role');

  // restore role
  const savedRole = localStorage.getItem('tigabe.chat.role');
  if (savedRole) roleSel.value = savedRole;
  roleSel.addEventListener('change', ()=>localStorage.setItem('tigabe.chat.role', roleSel.value));

  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function md(text){
    // code blocks
    let out = esc(text);
    out = out.replace(/```([\s\S]*?)```/g, function(_,c){return '<pre><code>'+c.trim()+'</code></pre>';});
    // inline code
    out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
    // bold
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // italic
    out = out.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');
    // links
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    // headings-ish lines
    // markdown tables: header row + separator row + body rows
    out = out.replace(/(?:^|\n)((?:\|[^\n]*\|\n){2,}(?:\|[^\n]*\|\n?)?)/g, function(block){
      const rows = block.trim().split(/\n/).filter(function(r){return r.trim();});
      if (rows.length < 2) return block;
      const sep = rows[1];
      if (!/^\|[\s:|-]+\|$/.test(sep.trim())) return block;
      function cells(r){ return r.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(function(c){return c.trim();}); }
      const head = cells(rows[0]);
      let html = '<table class="md-table"><thead><tr>';
      head.forEach(function(c){ html += '<th>'+c+'</th>'; });
      html += '</tr></thead><tbody>';
      for (let i=2;i<rows.length;i++){
        const cs = cells(rows[i]);
        html += '<tr>';
        cs.forEach(function(c){ html += '<td>'+c+'</td>'; });
        html += '</tr>';
      }
      html += '</tbody></table>';
      return '\n'+html+'\n';
    });
    // bullets
    out = out.replace(/(?:^|\n)([-*] .+(?:\n[-*] .+)*)/g, function(m){
      const items = m.trim().split(/\n/).map(l=>'<li>'+l.replace(/^[-*] /,'')+'</li>').join('');
      return '\n<ul>'+items+'</ul>';
    });
    // newlines (skip inside table already converted; remaining)
    out = out.replace(/\n/g, '<br>');
    return out;
  }

  function hideEmpty(){ if (empty) empty.style.display = 'none'; }

  function addMsg(who, content, citations){
    hideEmpty();
    const wrap = document.createElement('div');
    wrap.className = 'msg ' + who;
    const av = document.createElement('div');
    av.className = 'avatar ' + who;
    av.textContent = who === 'user' ? 'K' : 'AI';
    const bubble = document.createElement('div');
    bubble.className = 'bubble ' + who;
    if (who === 'user') {
      bubble.textContent = content;
    } else {
      bubble.innerHTML = md(content || '');
      if (citations && citations.length) {
        const c = document.createElement('div');
        c.className = 'citations';
        let rows = '';
        citations.forEach(function(x, i){
          const badgeCls = x.status_waktu === 'berlaku' ? 'ok' : 'warn';
          const snippet = (x.kutipan || '').replace(/\s+/g, ' ').slice(0, 160);
          rows += '<tr>'
            + '<td style="white-space:nowrap;color:var(--muted)">' + (i+1) + '</td>'
            + '<td><div style="font-weight:600">' + esc(x.title || '-') + '</div>'
            +   '<div class="cite-snippet">' + esc(snippet) + (snippet.length>=160?'…':'') + '</div></td>'
            + '<td>' + (x.pasal ? esc(x.pasal) : '-') + '</td>'
            + '<td style="white-space:nowrap">Hal. ' + esc(String(x.halaman || '-')) + '</td>'
            + '<td style="white-space:nowrap">' + esc(String(x.skor ?? '-')) + '</td>'
            + '<td style="white-space:nowrap"><span class="cite-badge ' + badgeCls + '">' + esc(x.status_waktu || '-') + '</span></td>'
            + '<td style="white-space:nowrap"><a class="cite-link" href="' + esc(x.document_url || '#') + '" target="_blank" rel="noopener">Buka ↗</a></td>'
            + '</tr>';
        });
        c.innerHTML = '<table class="cite-table"><thead><tr>'
          + '<th>#</th><th>Sumber</th><th>Pasal</th><th>Halaman</th><th>Skor</th><th>Status</th><th>PDF</th>'
          + '</tr></thead><tbody>' + rows + '</tbody></table>';
        bubble.appendChild(c);
      }
    }
    if (who === 'user') { wrap.appendChild(bubble); wrap.appendChild(av); }
    else { wrap.appendChild(av); wrap.appendChild(bubble); }
    log.appendChild(wrap);
    log.scrollTop = log.scrollHeight;
  }

  async function kirim(){
    const text = q.value.trim();
    if (!text) return;
    addMsg('user', text);
    q.value = ''; autoResize();
    sendBtn.disabled = true;
    typing.hidden = false; log.scrollTop = log.scrollHeight;
    try {
      const r = await fetch('/chat/ask', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({q: text, role: roleSel.value, top_k: 5})
      });
      const d = await r.json();
      typing.hidden = true;
      if (d.error) { addMsg('agent', 'Error: ' + d.error); }
      else {
        const reply = d.reply || (d.status === 'ok' ? 'Selesai.' : 'Tidak ada hasil.');
        addMsg('agent', reply, d.hasil || []);
        if (d.status && d.status !== 'ok') {
          status.textContent = (d.pesan || d.status);
        } else {
          status.textContent = '';
        }
      }
    } catch (e) {
      typing.hidden = true;
      addMsg('agent', 'Gagal menghubungi server: ' + e);
    } finally {
      sendBtn.disabled = false;
      q.focus();
    }
  }

  function autoResize(){
    q.style.height = 'auto';
    q.style.height = Math.min(q.scrollHeight, 160) + 'px';
  }
  q.addEventListener('input', autoResize);
  q.addEventListener('keydown', function(e){
    if (e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); kirim(); }
  });
  sendBtn.addEventListener('click', kirim);

  document.getElementById('btn-clear').addEventListener('click', function(){
    log.innerHTML = '';
    const e2 = document.createElement('div');
    e2.className = 'empty-state'; e2.id = 'empty';
    e2.innerHTML = '<h3>Mulai percakapan</h3><p>Tanyakan soal dokumen sekolah.</p>';
    log.appendChild(e2);
    status.textContent = '';
  });
  document.getElementById('btn-push').addEventListener('click', async function(){
    status.textContent = 'Pushing...';
    hideEmpty();
    try {
      const r = await fetch('/chat/push', {method:'POST'});
      const d = await r.json();
      status.textContent = JSON.stringify(d, null, 2);
      if (d && d.status === 'ok') {
        const raw = (d.output || '').toString().trim();
        const lines = raw.split(/\r?\n/).filter(Boolean);
        const tail = lines.slice(-6).join('\n');
        let sum = '**Push ke GitHub (origin/main): berhasil.**';
        if (tail) sum += '\n\n```\n' + tail + '\n```';
        addMsg('agent', sum, []);
      } else {
        const err = (d && (d.stderr || d.error || d.output)) ? String(d.stderr || d.error || d.output).trim() : 'Gagal push.';
        let sum = '**Push ke GitHub (origin/main): gagal.**';
        if (err) sum += '\n\n```\n' + err.slice(0, 1200) + '\n```';
        addMsg('agent', sum, []);
      }
    } catch(e){
      status.textContent = 'Error: ' + e;
      addMsg('agent', '**Push ke GitHub (origin/main): gagal.**\n\n```\n' + String(e) + '\n```', []);
    }
  });
  document.getElementById('btn-deploy').addEventListener('click', async function(){
    status.textContent = 'Trigger deploy...';
    hideEmpty();
    try {
      const r = await fetch('/chat/deploy', {method:'POST'});
      const d = await r.json();
      status.textContent = JSON.stringify(d, null, 2);
      if (d && d.status === 'ok') {
        const http = (d.http !== undefined && d.http !== null) ? String(d.http) : 'OK';
        addMsg('agent', '**Deploy (GitHub Actions `ci.yml`, ref `main`): dipicu.**\n\nRingkasan: request berhasil dikirim (HTTP ' + http + '). Cek tab Actions di repo untuk status run.', []);
      } else {
        const err = (d && (d.error || d.stderr || d.output)) ? String(d.error || d.stderr || d.output).trim() : 'Gagal trigger deploy.';
        let sum = '**Deploy (GitHub Actions `ci.yml`, ref `main`): gagal.**';
        if (err) sum += '\n\n```\n' + err.slice(0, 1200) + '\n```';
        addMsg('agent', sum, []);
      }
    } catch(e){
      status.textContent = 'Error: ' + e;
      addMsg('agent', '**Deploy (GitHub Actions `ci.yml`, ref `main`): gagal.**\n\n```\n' + String(e) + '\n```', []);
    }
  });

  // restore history (ringan) dari localStorage
  try {
    const hist = JSON.parse(localStorage.getItem('tigabe.chat.hist') || '[]');
    if (hist.length) { empty.style.display='none'; hist.forEach(m=>addMsg(m.who, m.content, m.cit||[])); }
  } catch(e){}
  // simpan history sederhana
  const origAdd = addMsg;
  // wrap addMsg untuk persist
  // (sederhana: simpan teks terakhir 40 pesan)
  const _addMsg = addMsg;
  // override tidak perlu; persist manual setelah kirim selesai via observer tidak trivial.
  // Simpan saat sebelum unload
  window.addEventListener('beforeunload', function(){
    const msgs = [];
    document.querySelectorAll('.msg').forEach(function(m){
      const who = m.classList.contains('user')?'user':'agent';
      const b = m.querySelector('.bubble');
      const txt = b ? b.textContent.slice(0,500) : '';
      msgs.push({who:who, content:txt});
    });
    localStorage.setItem('tigabe.chat.hist', JSON.stringify(msgs.slice(-40)));
  });
})();
</script>
'''

    isi = isi.replace("__CHAT_ICON__", IKON["chat"]).replace("__PERAN_OPTS__", _PERAN_OPSI)

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
        role = str(data.get("role", "publik")).strip()
        try:
            top_k = int(data.get("top_k", 5))
        except (TypeError, ValueError):
            top_k = 5
        top_k = max(1, min(top_k, 10))

        peran = PERAN.get(role) or PERAN.get("publik")
        if peran is None:
            peran = list(PERAN.values())[0]
        akses = akses_efektif(peran)

        try:
            res = cari(q, top_k, None, akses=akses)
        except Exception as e:
            return JSONResponse({"status": "error", "error": f"{type(e).__name__}: {e}"}, status_code=500)

        status = res.get("status", "ok")
        hasil = res.get("hasil", []) or []
        if status != "ok":
            return JSONResponse({
                "status": status,
                "pesan": res.get("pesan", ""),
                "reply": res.get("pesan", "Layanan tidak tersedia."),
                "hasil": [],
            })

        if not hasil:
            reply = "Tidak ditemukan dokumen relevan untuk pertanyaan ini."
        else:
            reply = f"Ditemukan **{len(hasil)}** kutipan relevan.\n\n"
            reply += "| # | Dokumen | Pasal/Bagian | Hal | Status |\n"
            reply += "|---|---------|--------------|-----|--------|\n"
            for i, h in enumerate(hasil[:5], 1):
                title = (h.get("title") or "-").replace("|", " ")
                pasal = (h.get("pasal") or h.get("bagian") or "-").replace("|", " ")
                hal = str(h.get("halaman") or "-")
                status_w = h.get("status_waktu") or "-"
                reply += f"| {i} | {title} | {pasal} | {hal} | {status_w} |\n"
            if len(hasil) > 5:
                reply += f"\n_Lihat tabel sitasi di bawah untuk {len(hasil)-5} hasil lainnya._"
        return JSONResponse({
            "status": "ok",
            "reply": reply,
            "hasil": hasil,
            "jumlah": len(hasil),
            "tanggal_acuan": res.get("tanggal_acuan"),
        })

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
        try:
            import urllib.request
            token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            if not token or not repo:
                return JSONResponse({"status": "error", "error": "GITHUB_TOKEN/GITHUB_REPOSITORY belum di-set"}, status_code=400)
            url = f"https://api.github.com/repos/{repo}/actions/workflows/ci.yml/dispatches"
            req = urllib.request.Request(url, data=json.dumps({"ref": "main"}).encode(),
                                       headers={"Authorization": f"Bearer {token}",
                                                "Accept": "application/vnd.github+json",
                                                "X-GitHub-Api-Version": "2022-11-28"})
            with urllib.request.urlopen(req) as resp:
                return JSONResponse({"status": "ok", "http": resp.status})
        except Exception as e:
            return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


if __name__ == "__main__":
    pass
