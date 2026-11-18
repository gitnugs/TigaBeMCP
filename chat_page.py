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
:root{
  --chat-bg:var(--surface);
  --chat-bg-soft:var(--surface-2);
  --chat-border:var(--border);
  --chat-radius:14px;
  --chat-shadow:0 1px 2px rgba(0,0,0,.06),0 8px 24px rgba(0,0,0,.08);
}
.chat-shell{display:flex;flex-direction:column;height:calc(100vh - 140px);min-height:560px;
  max-width:1280px;margin:0 auto;background:var(--chat-bg);border:1px solid var(--chat-border);
  border-radius:var(--chat-radius);box-shadow:var(--chat-shadow);overflow:hidden}
.chat-top{display:flex;align-items:center;justify-content:space-between;gap:16px;
  padding:14px 20px;border-bottom:1px solid var(--chat-border);background:linear-gradient(180deg,var(--chat-bg-soft) 0%,var(--chat-bg) 100%)}
.chat-top-left{display:flex;align-items:center;gap:12px;min-width:0}
.chat-title{display:flex;align-items:center;gap:10px;font-weight:650;font-size:1.05rem;letter-spacing:-.01em;color:var(--ink)}
.chat-title .icon{width:22px;height:22px;color:var(--accent);display:flex;align-items:center}
.chat-title .icon svg{width:22px;height:22px}
.chat-sub{font-size:.78rem;color:var(--muted);font-weight:400;margin-top:2px}
.chat-controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end}
.chat-ctrl-group{display:flex;align-items:center;gap:8px;background:var(--chat-bg);padding:6px 10px;
  border:1px solid var(--chat-border);border-radius:10px}
.chat-ctrl-group label{font-size:.75rem;color:var(--muted);white-space:nowrap}
.chat-controls select{font:inherit;font-size:.82rem;padding:6px 10px;min-width:170px;
  border-radius:8px;border:1px solid var(--chat-border);background:var(--chat-bg);color:var(--ink);cursor:pointer}
.chat-controls select:focus{outline:2px solid color-mix(in srgb,var(--accent) 35%,transparent);outline-offset:1px}
.chat-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.btn-ghost{font:inherit;font-size:.82rem;padding:7px 12px;border-radius:8px;
  border:1px solid var(--chat-border);background:transparent;color:var(--ink-2);cursor:pointer;transition:all .15s ease}
.btn-ghost:hover{background:var(--chat-bg-soft);color:var(--ink);border-color:color-mix(in srgb,var(--border) 80%,var(--ink))}
.btn-secondary{font:inherit;font-size:.82rem;padding:7px 14px;border-radius:8px;
  border:1px solid var(--chat-border);background:var(--chat-bg);color:var(--ink);cursor:pointer;transition:all .15s ease;font-weight:500}
.btn-secondary:hover{background:var(--chat-bg-soft)}
.btn-accent{font:inherit;font-size:.82rem;padding:7px 14px;border-radius:8px;
  border:1px solid color-mix(in srgb,var(--accent) 40%,var(--border));background:color-mix(in srgb,var(--accent) 12%,transparent);
  color:var(--accent);cursor:pointer;transition:all .15s ease;font-weight:600}
.btn-accent:hover{background:color-mix(in srgb,var(--accent) 22%,transparent)}
.chat-messages{flex:1;overflow-y:auto;overflow-x:hidden;padding:24px 20px;display:flex;flex-direction:column;gap:20px;
  background:var(--chat-bg);scroll-behavior:smooth}
.chat-messages::-webkit-scrollbar{width:8px}
.chat-messages::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--muted) 40%,transparent);border-radius:4px}
.empty-state{text-align:center;color:var(--muted);margin:auto;padding:48px 24px;max-width:460px}
.empty-state .empty-ico{width:48px;height:48px;margin:0 auto 16px;border-radius:14px;background:var(--chat-bg-soft);
  border:1px solid var(--chat-border);display:flex;align-items:center;justify-content:center;color:var(--accent)}
.empty-state .empty-ico svg{width:24px;height:24px}
.empty-state h3{color:var(--ink);margin:0 0 8px;font-size:1.15rem;font-weight:650;letter-spacing:-.02em}
.empty-state p{margin:0;font-size:.9rem;line-height:1.6;color:var(--ink-2)}
.msg{display:flex;gap:12px;max-width:100%;align-items:flex-start}
.msg.user{justify-content:flex-end}
.avatar{width:34px;height:34px;border-radius:10px;flex:none;display:flex;align-items:center;justify-content:center;
  font-size:.72rem;font-weight:700;color:#fff;letter-spacing:.02em}
.avatar.user{background:linear-gradient(160deg,var(--accent) 0%,color-mix(in srgb,var(--accent) 70%,#1a5f9a) 100%)}
.avatar.agent{background:linear-gradient(145deg,#2B8CE8 0%,#1E6FB8 60%,#155a9c 100%)}
.bubble{max-width:min(85%,780px);padding:14px 18px;border-radius:14px;font-size:.93rem;
  line-height:1.65;word-break:break-word}
.bubble.user{background:var(--accent);color:#fff;border-bottom-right-radius:6px;box-shadow:0 2px 8px rgba(43,140,232,.25)}
.bubble.agent{background:var(--chat-bg-soft);border:1px solid var(--chat-border);border-bottom-left-radius:6px;color:var(--ink)}
.bubble.agent p{margin:0 0 10px}.bubble.agent p:last-child{margin:0}
.bubble.agent ul,.bubble.agent ol{margin:8px 0 10px 20px;padding:0}
.bubble.agent li{margin:4px 0}
.bubble.agent code{background:rgba(0,0,0,.28);padding:2px 6px;border-radius:5px;font-size:.84em;font-family:ui-monospace,monospace}
.bubble.agent pre{background:#0c0d0f;border:1px solid var(--chat-border);border-radius:10px;
  padding:12px 14px;overflow:auto;margin:10px 0;font-size:.82rem;line-height:1.5}
.bubble.agent pre code{background:none;padding:0}
.bubble.agent a{color:var(--accent-hover);text-decoration:none}
.bubble.agent a:hover{text-decoration:underline}
.bubble.agent strong{font-weight:600;color:var(--ink)}
.citations{margin-top:14px;padding-top:14px;border-top:1px solid var(--chat-border);overflow-x:auto}
.cite-table,.md-table{width:100%;border-collapse:separate;border-spacing:0;font-size:.78rem;min-width:360px}
.cite-table th,.cite-table td,.md-table th,.md-table td{border-bottom:1px solid var(--chat-border);padding:8px 10px;text-align:left;vertical-align:top}
.cite-table th,.md-table th{background:var(--chat-bg);color:var(--muted);font-weight:600;font-size:.7rem;text-transform:uppercase;letter-spacing:.06em}
.cite-table tbody tr:last-child td,.md-table tbody tr:last-child td{border-bottom:none}
.cite-table tbody tr:hover td,.md-table tbody tr:hover td{background:rgba(255,255,255,.03)}
.bubble.agent .md-table{margin:12px 0;border:1px solid var(--chat-border);border-radius:10px;overflow:hidden}
.bubble.agent .md-table th{color:var(--ink-2);background:var(--chat-bg)}
.cite-badge{font-size:.68rem;padding:3px 8px;border-radius:999px;border:1px solid var(--chat-border);
  color:var(--muted);white-space:nowrap;display:inline-block;font-weight:500}
.cite-badge.ok{color:#5dd99d;border-color:rgba(88,201,138,.35);background:rgba(88,201,138,.12)}
.cite-badge.warn{color:#f5c45e;border-color:rgba(241,179,60,.35);background:rgba(241,179,60,.12)}
.cite-link{color:var(--accent);text-decoration:none;font-weight:600}
.cite-link:hover{text-decoration:underline}
.cite-snippet{color:var(--ink-2);font-size:.75rem;margin-top:4px;line-height:1.45;max-width:340px;white-space:pre-wrap}
.typing{display:flex;gap:4px;padding:6px 0 6px 46px;align-items:center}
.typing span{width:8px;height:8px;border-radius:50%;background:var(--muted);animation:bounce 1.2s infinite}
.typing span:nth-child(2){animation-delay:.15s}.typing span:nth-child(3){animation-delay:.3s}
@keyframes bounce{0%,60%,100%{transform:translateY(0);opacity:.35}30%{transform:translateY(-7px);opacity:1}}
.chat-input-wrap{border-top:1px solid var(--chat-border);background:var(--chat-bg-soft);padding:14px 20px 16px}
.chat-input{display:flex;gap:10px;align-items:flex-end;background:var(--chat-bg);border:1px solid var(--chat-border);
  border-radius:14px;padding:10px 12px;box-shadow:inset 0 1px 2px rgba(0,0,0,.04)}
.chat-input:focus-within{border-color:color-mix(in srgb,var(--accent) 50%,var(--border));box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 15%,transparent)}
.chat-input textarea{flex:1;resize:none;min-height:44px;max-height:200px;padding:6px 8px;
  border:none;background:transparent;color:var(--ink);font:inherit;font-size:.95rem;line-height:1.5}
.chat-input textarea:focus{outline:none}
.chat-input textarea::placeholder{color:var(--muted)}
.chat-input .send-btn{padding:10px 20px;border-radius:10px;border:none;background:var(--accent);
  color:#fff;font-weight:600;cursor:pointer;font-size:.9rem;white-space:nowrap;transition:background .15s ease}
.chat-input .send-btn:hover:not(:disabled){background:var(--accent-hover)}
.chat-input .send-btn:disabled{opacity:.5;cursor:not-allowed}
.status-bar{margin-top:12px;padding:10px 14px;border-radius:10px;background:var(--chat-bg);
  border:1px solid var(--chat-border);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.72rem;
  color:var(--ink-2);white-space:pre-wrap;max-height:140px;overflow:auto;line-height:1.5}
.status-bar:empty{display:none}
.chat-hint{font-size:.72rem;color:var(--muted);margin-top:8px;text-align:center}
@media (max-width:900px){
  .chat-top{flex-direction:column;align-items:stretch}
  .chat-controls{justify-content:flex-start}
  .chat-ctrl-group{flex:1;min-width:200px}
  .chat-actions{width:100%;justify-content:flex-end}
}
@media (max-width:600px){
  .chat-shell{height:calc(100vh - 110px);min-height:480px;border-radius:0;border-left:none;border-right:none}
  .bubble{max-width:94%}
  .chat-messages{padding:16px 14px}
}
</style>

<div class="chat-shell">
  <div class="chat-top">
    <div class="chat-top-left">
      <div class="chat-title"><span class="icon">__CHAT_ICON__</span><div><div>Chat TigaBe</div><div class="chat-sub">Tanya dokumen sekolah · aksi cepat Git & Deploy</div></div></div>
    </div>
    <div class="chat-controls">
      <div class="chat-ctrl-group">
        <label for="role">Peran</label>
        <select id="role">__PERAN_OPTS__</select>
      </div>
      <div class="chat-actions">
        <button class="btn-ghost" id="btn-clear" type="button" title="Bersihkan tampilan chat">Hapus chat</button>
        <button class="btn-secondary" id="btn-push" type="button">Push GitHub</button>
        <button class="btn-accent" id="btn-deploy" type="button">Deploy</button>
      </div>
    </div>
  </div>
  <div class="chat-messages" id="log" role="log" aria-live="polite">
    <div class="empty-state" id="empty">
      <div class="empty-ico" aria-hidden="true">__CHAT_ICON__</div>
      <h3>Mulai percakapan</h3>
      <p>Tanyakan soal dokumen sekolah, misalnya <em>“seragam kelas 4 hari Rabu pakai apa?”</em> Pilih peran di atas untuk menyesuaikan akses dokumen.</p>
    </div>
  </div>
  <div class="typing" id="typing" hidden><span></span><span></span><span></span></div>
  <div class="chat-input-wrap">
    <div class="chat-input">
      <textarea id="q" rows="1" placeholder="Ketik pertanyaan… (Enter kirim, Shift+Enter baris baru)"></textarea>
      <button class="send-btn" id="send" type="button">Kirim</button>
    </div>
    <div class="chat-hint">Jawaban dapat memuat kutipan dari dokumen yang tersedia sesuai peran Anda.</div>
    <div class="status-bar" id="status" aria-live="polite"></div>
  </div>
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

  const savedRole = localStorage.getItem('tigabe.chat.role');
  if (savedRole && roleSel.querySelector('option[value="'+savedRole+'"]')) roleSel.value = savedRole;
  roleSel.addEventListener('change', ()=>localStorage.setItem('tigabe.chat.role', roleSel.value));

  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function md(text){
    let out = esc(text || '');
    out = out.replace(/```([\s\S]*?)```/g, function(_,c){return '<pre><code>'+c.trim()+'</code></pre>';});
    out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
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
        cs.forEach(function(c){ html += '<td>'+esc(c)+'</td>'; });
        html += '</tr>';
      }
      html += '</tbody></table>';
      return '\n'+html+'\n';
    });
    out = out.replace(/(?:^|\n)([-*] .+(?:\n[-*] .+)*)/g, function(m){
      const items = m.trim().split(/\n/).map(l=>'<li>'+l.replace(/^[-*] /,'')+'</li>').join('');
      return '\n<ul>'+items+'</ul>';
    });
    out = out.replace(/\n/g, '<br>');
    return out;
  }

  function hideEmpty(){ const e = document.getElementById('empty'); if (e) e.style.display = 'none'; }

  function getChatIconHTML(){
    const el = document.querySelector('.chat-title .icon');
    return el ? el.innerHTML : '';
  }

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
            + '<td><div style="font-weight:600;color:var(--ink)">' + esc(x.title || '-') + '</div>'
            +   '<div class="cite-snippet">' + esc(snippet) + (snippet.length>=160?'…':'') + '</div></td>'
            + '<td>' + (x.pasal ? esc(x.pasal) : '-') + '</td>'
            + '<td style="white-space:nowrap">Hal. ' + esc(String(x.halaman || '-')) + '</td>'
            + '<td style="white-space:nowrap">' + esc(String(x.skor ?? '-')) + '</td>'
            + '<td style="white-space:nowrap"><span class="cite-badge ' + badgeCls + '">' + esc(x.status_waktu || '-') + '</span></td>'
            + '<td style="white-space:nowrap"><a class="cite-link" href="' + esc(x.document_url || '#') + '" target="_blank" rel="noopener">Buka ↗</a></td>'
            + '</tr>';
        });
        c.innerHTML = '<table class="cite-table"><thead><tr>'
          + '<th>#</th><th>Sumber</th><th>Pasal/Bagian</th><th>Hal</th><th>Skor</th><th>Status</th><th>PDF</th>'
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
        status.textContent = (d.status && d.status !== 'ok') ? (d.pesan || d.status) : '';
      }
    } catch (e) {
      typing.hidden = true;
      addMsg('agent', 'Gagal menghubungi server: ' + String(e));
    } finally {
      sendBtn.disabled = false;
      q.focus();
    }
  }

  function autoResize(){
    q.style.height = 'auto';
    q.style.height = Math.min(q.scrollHeight, 200) + 'px';
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
    const iconWrap = document.createElement('div');
    iconWrap.className = 'empty-ico';
    iconWrap.setAttribute('aria-hidden','true');
    iconWrap.innerHTML = getChatIconHTML();
    e2.appendChild(iconWrap);
    const h3 = document.createElement('h3'); h3.textContent = 'Mulai percakapan'; e2.appendChild(h3);
    const p = document.createElement('p');
    p.innerHTML = 'Tanyakan soal dokumen sekolah, misalnya <em>“seragam kelas 4 hari Rabu pakai apa?”</em> Pilih peran di atas untuk menyesuaikan akses dokumen.';
    e2.appendChild(p);
    log.appendChild(e2);
    status.textContent = '';
  });

  document.getElementById('btn-push').addEventListener('click', async function(){
    status.textContent = 'Pushing ke GitHub…';
    hideEmpty();
    try {
      const r = await fetch('/chat/push', {method:'POST'});
      const d = await r.json();
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
      status.textContent = '';
    } catch(e){
      status.textContent = '';
      addMsg('agent', '**Push ke GitHub (origin/main): gagal.**\n\n```\n' + String(e) + '\n```', []);
    }
  });

  document.getElementById('btn-deploy').addEventListener('click', async function(){
    status.textContent = 'Memicu deploy (GitHub Actions)…';
    hideEmpty();
    try {
      const r = await fetch('/chat/deploy', {method:'POST'});
      const d = await r.json();
      if (d && d.status === 'ok') {
        const http = (d.http !== undefined && d.http !== null) ? String(d.http) : 'OK';
        addMsg('agent', '**Deploy (GitHub Actions `ci.yml`, ref `main`): dipicu.**\n\nRingkasan: request berhasil dikirim (HTTP ' + http + '). Periksa tab Actions di repo untuk status run.', []);
      } else {
        const err = (d && (d.error || d.stderr || d.output)) ? String(d.error || d.stderr || d.output).trim() : 'Gagal trigger deploy.';
        let sum = '**Deploy (GitHub Actions `ci.yml`, ref `main`): gagal.**';
        if (err) sum += '\n\n```\n' + err.slice(0, 1200) + '\n```';
        addMsg('agent', sum, []);
      }
      status.textContent = '';
    } catch(e){
      status.textContent = '';
      addMsg('agent', '**Deploy (GitHub Actions `ci.yml`, ref `main`): gagal.**\n\n```\n' + String(e) + '\n```', []);
    }
  });

  try {
    const hist = JSON.parse(localStorage.getItem('tigabe.chat.hist') || '[]');
    if (hist.length) {
      const e = document.getElementById('empty'); if (e) e.style.display='none';
      hist.forEach(function(m){ addMsg(m.who, m.content, m.cit||[]); });
    }
  } catch(e){}
  window.addEventListener('beforeunload', function(){
    const msgs = [];
    document.querySelectorAll('#log .msg').forEach(function(m){
      const who = m.classList.contains('user')?'user':'agent';
      const b = m.querySelector('.bubble');
      const txt = b ? b.textContent.slice(0,500) : '';
      msgs.push({who:who, content:txt, cit:[]});
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
            # Jawaban spesifik dari kutipan teratas
            top = hasil[0]
            kutipan = (top.get("kutipan") or "").strip()
            title = top.get("title") or "-"
            pasal = top.get("pasal") or top.get("bagian") or "-"
            hal = top.get("halaman")
            src_parts = [f"**Sumber:** {title}"]
            if pasal and pasal != "-":
                src_parts.append(f"Pasal/Bagian: {pasal}")
            if hal:
                src_parts.append(f"Hal {hal}")
            if kutipan:
                reply = f"{kutipan}\n\n" + " · ".join(src_parts)
            else:
                reply = f"Ditemukan dokumen relevan: {title} (Hal {hal or '-'}).\n\n" + " · ".join(src_parts)
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
            # commit may fail if nothing to commit
            cp = subprocess.run(["git", "commit", "-m", "chat: update UI and answer"], cwd=BASE_DIR, capture_output=True, text=True)
            if cp.returncode != 0 and "nothing to commit" not in (cp.stdout + cp.stderr):
                return JSONResponse({"status": "error", "stdout": cp.stdout, "stderr": cp.stderr}, status_code=500)
            # push to github remote if exists, else origin
            remotes = subprocess.run(["git", "remote"], cwd=BASE_DIR, capture_output=True, text=True)
            rname = "github" if "github" in remotes.stdout.split() else "origin"
            r = subprocess.run(["git", "push", rname, "main"], cwd=BASE_DIR, check=True, capture_output=True, text=True)
            return JSONResponse({"status": "ok", "remote": rname, "output": (cp.stdout + cp.stderr + r.stdout + r.stderr).strip()})
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
