"""Desain UI bersama (palet, ikon, CSS, kerangka halaman).

Dipakai oleh halaman admin (admin_page.py) dan pengetahuan (pengetahuan_ui.py)
agar tampilan konsisten dari satu sumber. Tidak mengimpor modul aplikasi lain,
jadi aman diimpor dari mana pun.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Ikon (SVG stroke 1.75, konsisten 20x20)
# ---------------------------------------------------------------------------
def svg(*d: str) -> str:
    """Bungkus path jadi ikon SVG inline yang konsisten."""
    bagian = "".join(f'<path d="{p}"/>' for p in d)
    return (f'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" '
            f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{bagian}</svg>')


IKON = {
    "users": svg(
        '<circle cx="7.5" cy="6" r="3.25"/><path d="M2.5 17a5 5 0 0 1 10 0"/>'
        '<path d="M14 4.25a3.25 3.25 0 0 1 0 6.1"/><path d="M15.5 12.6a5 5 0 0 1 3 4.4"/>',
    ),
    "audit": svg(
        '<rect x="4.5" y="3.5" width="11" height="13.5" rx="2"/>'
        '<path d="M7.25 3.5h5.5v2a.5.5 0 0 1-.5.5h-4.5a.5.5 0 0 1-.5-.5z"/>'
        '<path d="M7.25 9h5.5M7.25 12h5.5M7.25 15h3.25"/>',
    ),
    "book": svg(
        '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H16v14.25H6.5A2.5 2.5 0 0 0 4 18.75z"/>'
        '<path d="M4 18.75V4.5A2.5 2.5 0 0 1 6.5 2"/>',
    ),
    "plus": svg('<path d="M10 4.25v11.5M4.25 10h11.5"/>'),
    "trash": svg(
        '<path d="M4 6h12M8.25 6V4.5a1 1 0 0 1 1-1h1.5a1 1 0 0 1 1 1V6"/>'
        '<path d="M6.5 6l.7 10.2a1.5 1.5 0 0 0 1.5 1.4h2.6a1.5 1.5 0 0 0 1.5-1.4L13.5 6"/>'
        '<path d="M8.5 9.5v4.25M11.5 9.5v4.25"/>',
    ),
    "simpan": svg(
        '<path d="M4 4.5A1.5 1.5 0 0 1 5.5 3h9A1.5 1.5 0 0 1 16 4.5v11a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 4 17z"/>'
        '<path d="M7.25 3v4h5.5V3"/>',
    ),
    "ok": svg('<circle cx="10" cy="10" r="7.25"/><path d="M6.75 10.4l2.2 2.2 4.3-4.6"/>'),
    "galat": svg(
        '<circle cx="10" cy="10" r="7.25"/><path d="M10 6.25v4.5M10 13.75h.01"/>',
    ),
    "upload": svg(
        '<path d="M10 13V4.75M6.5 8.25L10 4.75l3.5 3.5"/>'
        '<path d="M4 13.5v1.75A1.75 1.75 0 0 0 5.75 17h8.5A1.75 1.75 0 0 0 16 15.25V13.5"/>',
    ),
    "eye": svg(
        '<path d="M2.5 10S5 5.5 10 5.5 17.5 10 17.5 10 15 14.5 10 14.5 2.5 10 2.5 10z"/>'
        '<circle cx="10" cy="10" r="2.25"/>',
    ),
    "pulse": svg('<path d="M2.75 10h3.5l2-4.5 3.5 9 2-4.5h3.5"/>'),
    "doc": svg(
        '<path d="M5 2.75h6.5L14.5 5.75v9.5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/>'
        '<path d="M11.5 2.75v3h3"/>',
    ),
    "back": svg('<path d="M10 4.25L4.25 10 10 15.75"/><path d="M4.25 10h11.5"/>'),
}

LOGO = (
    '<svg width="30" height="30" viewBox="0 0 28 28" aria-hidden="true">'
    '<defs><linearGradient id="lgShared" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#4F46E5"/><stop offset="1" stop-color="#8B5CF6"/>'
    '</linearGradient></defs>'
    '<rect width="28" height="28" rx="8" fill="url(#lgShared)"/>'
    '<g fill="#fff"><circle cx="9" cy="9.5" r="1.9"/><circle cx="19" cy="9.5" r="1.9"/>'
    '<circle cx="14" cy="18.5" r="1.9"/></g>'
    '<g stroke="#fff" stroke-width="1.3" stroke-linecap="round">'
    '<path d="M10.4 10.2l1.9 5.4M17.6 10.2l-1.9 5.4M9 9.5h2.6M16.4 9.5H19"/></g></svg>'
)


# ---------------------------------------------------------------------------
# Desain (tokens + CSS)
# ---------------------------------------------------------------------------
CSS = r"""
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
.doc-main{display:flex;flex-direction:column;gap:2px}
.doc-title{font-weight:600;color:var(--ink);overflow:hidden;text-overflow:ellipsis;max-width:280px;white-space:nowrap}
.doc-id{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.72rem;color:var(--muted)}

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
input[type=text],input[type=password],select,textarea{
  width:100%;padding:9px 12px;border:1px solid var(--border-2);border-radius:var(--radius-sm);
  font-size:.88rem;font-family:inherit;color:var(--ink);background:var(--surface);
  caret-color:var(--accent);transition:border-color .15s,box-shadow .15s;
}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
input::placeholder,textarea::placeholder{color:var(--faint)}
textarea{resize:vertical;min-height:70px}
select{
  appearance:none;-webkit-appearance:none;padding-right:38px;cursor:pointer;
  background-image:url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="%2364748B" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M5 8l5 5 5-5"/></svg>');
  background-repeat:no-repeat;background-position:right 12px center;background-size:16px;
}
input[type=file]{
  width:100%;padding:9px 12px;border:1px dashed var(--border-2);border-radius:var(--radius-sm);
  font-size:.85rem;font-family:inherit;color:var(--ink-2);background:var(--surface-2);
  cursor:pointer;
}
input[type=file]:hover{border-color:var(--accent);background:var(--accent-soft)}
input[type=file]::file-selector-button{
  margin-right:12px;border:1px solid var(--border-2);border-radius:var(--radius-sm);
  background:var(--surface);padding:6px 12px;font-family:inherit;font-size:.82rem;
  font-weight:600;color:var(--ink-2);cursor:pointer;
}
input[type=file]::file-selector-button:hover{border-color:var(--accent);color:var(--accent)}

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

/* ---- pilar status ---- */
.pill{display:inline-flex;align-items:center;padding:2px 9px;border-radius:999px;
  font-size:.72rem;font-weight:600;border:1px solid;white-space:nowrap}
.pill-neutral{background:var(--surface-2);border-color:var(--border);color:var(--ink-2)}
.pill-success{background:var(--success-soft);border-color:var(--success-border);color:#15803D}
.pill-danger{background:var(--danger-soft);border-color:var(--danger-border);color:#B91C1C}
.pill-warn{background:var(--warn-soft);border-color:var(--warn-border);color:#B45309}

/* ---- kosong ---- */
.empty{padding:30px 16px;text-align:center;color:var(--muted);font-size:.85rem}
.empty .judul{font-size:.95rem;font-weight:600;color:var(--ink-2);margin-bottom:3px}

/* ---- blok kode / detail status ---- */
.mono-block{
  background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius-sm);
  padding:14px 16px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:.8rem;line-height:1.6;white-space:pre-wrap;word-break:break-word;color:var(--ink-2);
  overflow:auto;margin:0;
}
.kv{display:grid;grid-template-columns:minmax(180px,1fr) minmax(0,1fr);gap:0;margin:0}
.kv dt{padding:10px 14px;border-bottom:1px solid var(--border);background:var(--surface-2);
  font-size:.8rem;font-weight:600;color:var(--muted)}
.kv dd{padding:10px 14px;border-bottom:1px solid var(--border);margin:0;font-size:.86rem;
  overflow-wrap:anywhere}

/* ---- frame preview PDF ---- */
.frame{width:100%;height:82vh;border:1px solid var(--border);border-radius:var(--radius);background:#fff}

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


# ---------------------------------------------------------------------------
# Kerangka halaman
# ---------------------------------------------------------------------------
def nav(aktif: str) -> str:
    item = '<a class="nav-item {aktif}" href="{href}">{ikon}<span>{teks}</span></a>'
    return "".join([
        item.format(aktif="active" if aktif == "user" else "", href="/admin",
                    ikon=IKON["users"], teks="Pengguna &amp; Peran"),
        item.format(aktif="active" if aktif == "audit" else "", href="/admin/audit",
                    ikon=IKON["audit"], teks="Audit Chat"),
        item.format(aktif="active" if aktif == "knowledge" else "", href="/pengetahuan",
                    ikon=IKON["book"], teks="Pengetahuan"),
    ])


def wadah(judul_halaman: str, deskripsi: str, aktif: str, isi: dict,
          judul: str, aksi: str = "") -> str:
    """Kerangka halaman: sidebar + topbar + konten.

    `isi` wajib berisi kunci "isi" (html inti), opsional "pesan" & "galat".
    """
    sidebar = (
        '<aside class="side">'
        '<div class="brand">{logo}'
        '<div><div class="brand-name">TigaBe <em>MCP</em></div>'
        '<div class="brand-sub">Konsol Pengelolaan</div></div></div>'
        '<nav class="nav">{nav}</nav>'
        '<div class="side-foot"><span class="dot"></span>Hanya dari localhost</div>'
        '</aside>'
    ).format(logo=LOGO, nav=nav(aktif))

    pesan = galat = ""
    if isi.get("pesan"):
        pesan = '<div class="alert ok">{ikon}<span>{teks}</span></div>'.format(
            ikon=IKON["ok"], teks=isi["pesan"])
    if isi.get("galat"):
        galat = '<div class="alert galat">{ikon}<span>{teks}</span></div>'.format(
            ikon=IKON["galat"], teks=isi["galat"])

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
    ).format(judul=judul, css=CSS, sidebar=sidebar, topbar=topbar,
             pesan=pesan, galat=galat, konten=isi["isi"])