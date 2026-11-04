"""Halaman web kelola pengetahuan: CRUD dokumen + unggah PDF.
Memakai knowledge (MinIO + Qdrant) yang dibangun di modul terpisah.
"""
from __future__ import annotations

import html
import logging
import os
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

import knowledge

log = logging.getLogger("tigabe.pengetahuan")


def _lokal(request: Request) -> bool:
    """Izinkan loopback atau jaringan via MCP_ALLOW_ADMIN_FROM (lihat admin_page)."""
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


def _opsi_akses(dipilih: str = "public") -> str:
    """Pilihan tingkat_akses untuk form unggah."""
    opsi = ["public", "class", "internal", "restricted"]
    return "".join(
        f"<option value='{a}' {'selected' if a == dipilih else ''}>{a}</option>"
        for a in opsi
    )


def _laman(pesan: str = "", galat: str = "") -> HTMLResponse:
    try:
        docs = knowledge.daftar_pengetahuan()
        galat_backend = ""
    except Exception as e:
        docs = []
        galat_backend = f"Gagal memuat daftar ({type(e).__name__}). "

    tr_docs = "".join(
        f"<tr>"
        f"<td>{html.escape(str(d.get('document_id', '')))}</td>"
        f"<td>{html.escape(str(d.get('title', '')))}</td>"
        f"<td>{html.escape(str(d.get('jenis', '')))}</td>"
        f"<td>{html.escape(str(d.get('tingkat_akses', '')))}</td>"
        f"<td>{'<span class=ya>✓</span>' if d.get('di_minio') else '<span class=tidak>✗</span>'}</td>"
        f"<td>{html.escape(str(d.get('chunk_qdrant', 0)))}</td>"
        f"<td class='none' style='white-space:nowrap'>"
        f"<form method='POST' action='/pengetahuan/status' style='display:inline'>"
        f"<input type='hidden' name='document_id' value='{html.escape(str(d.get('document_id', '')))}'>"
        f"<button class='btn-status'>Status</button></form> "
        f"<form method='POST' action='/pengetahuan/hapus' style='display:inline' "
        f"onsubmit=\"return confirm('Hapus dokumen ini?')\">"
        f"<input type='hidden' name='document_id' value='{html.escape(str(d.get('document_id', '')))}'>"
        f"<button class='btn-hapus'>Hapus</button></form></td></tr>"
        for d in docs
    ) or "<tr><td colspan='7' class='kosong'>Belum ada dokumen pengetahuan.</td></tr>"

    pesan_html = f"<p class='ok'>{html.escape(pesan)}</p>" if pesan else ""
    galat_html = f"<p class='galat'>{html.escape(galat or galat_backend)}</p>" if (galat or galat_backend) else ""

    return HTMLResponse(f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pengetahuan TigaBe MCP</title><style>
body{{font-family:system-ui,sans-serif;background:#f4f6f8;margin:0;padding:24px}}
.wrap{{max-width:960px;margin:0 auto}}
h1{{font-size:1.3rem}} h2{{font-size:1.05rem;margin-top:28px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #e6e9ec;font-size:.86rem;vertical-align:top}}
th{{background:#eef2f6}}
.btn{{background:#1a73e8;color:#fff;border:0;border-radius:6px;padding:8px 14px;cursor:pointer;font-weight:600}}
.btn-hapus{{background:#b3261e;color:#fff;border:0;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:.78rem}}
.btn-status{{background:#5f6b76;color:#fff;border:0;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:.78rem}}
input[type=file],select{{padding:8px;border:1px solid #cfd6dc;border-radius:6px;width:100%;box-sizing:border-box;font-family:inherit}}
textarea{{padding:8px;border:1px solid #cfd6dc;border-radius:6px;width:100%;box-sizing:border-box;font-family:inherit}}
form.baris{{background:#fff;border:1px solid #e6e9ec;border-radius:8px;padding:14px;margin-top:10px}}
label.f{{display:block;font-size:.78rem;color:#3f4650;margin:8px 0 3px}}
.ok{{color:#1b7f4d}} .galat{{color:#b3261e}} .kosong{{color:#8794a0}}
.small{{font-size:.75rem;color:#8794a0}}
.ya{{color:#1b7f4d;font-weight:600}} .tidak{{color:#b3261e;font-weight:600}}
.tab{{display:inline-block;padding:6px 14px;border-radius:6px;background:#fff;border:1px solid #d9dee3;
     color:#3f4650;text-decoration:none;font-size:.85rem;margin-right:6px}}
.tab.aktif{{background:#1a73e8;color:#fff;border-color:#1a73e8;font-weight:600}}
</style></head><body><div class="wrap">
<h1>📚 Pengetahuan TigaBe MCP</h1>
<p>
  <a class="tab aktif" href="/pengetahuan">📚 Dokumen</a>
  <a class="tab" href="/admin">🛠️ Admin</a>
</p>
<p class="small">Halaman ini hanya bisa dibuka dari komputer ini (localhost).</p>
{pesan_html}{galat_html}

<h2>📄 Dokumen Pengetahuan</h2>
<table><tr><th>ID</th><th>Judul</th><th>Jenis</th><th>Akses</th><th>MinIO</th><th>Chunk Qdrant</th><th>Aksi</th></tr>{tr_docs}</table>

<h2>⬆️ Unggah PDF</h2>
<form class="baris" method="POST" action="/pengetahuan/unggah" enctype="multipart/form-data">
  <label class="f">Berkas PDF</label>
  <input type="file" name="berkas" accept="application/pdf,.pdf" required>
  <label class="f">Tingkat akses</label>
  <select name="tingkat_akses">{_opsi_akses()}</select>
  <label class="f">Keterangan</label>
  <textarea name="keterangan" rows="2" placeholder="Opsional"></textarea>
  <p><button class="btn">Unggah</button></p>
</form>

<p class="small">Dokumen disimpan di MinIO dan dipotong (chunk) &amp; di-embed ke Qdrant.</p>
</div></body></html>""")


def _laman_status(document_id: str, hasil: dict | None = None, galat: str = "") -> HTMLResponse:
    if hasil is not None:
        detail = "<pre>" + html.escape(
            "\n".join(f"{k}: {v}" for k, v in hasil.items())
        ) + "</pre>"
    else:
        detail = ""

    pesan_html = f"<p class='ok'>{html.escape(galat)}</p>" if galat else ""
    return HTMLResponse(f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Status Pengetahuan</title><style>
body{{font-family:system-ui,sans-serif;background:#f4f6f8;margin:0;padding:24px}}
.wrap{{max-width:720px;margin:0 auto}}
h1{{font-size:1.3rem}}
.btn{{background:#1a73e8;color:#fff;border:0;border-radius:6px;padding:8px 14px;cursor:pointer;font-weight:600;text-decoration:none;display:inline-block}}
.galat{{color:#b3261e}} .small{{font-size:.75rem;color:#8794a0}}
pre{{white-space:pre-wrap;word-break:break-word;background:#fff;border:1px solid #e6e9ec;padding:12px;border-radius:6px;font-size:.82rem}}
</style></head><body><div class="wrap">
<h1>🔍 Status Dokumen</h1>
<p class="small">ID: {html.escape(document_id)}</p>
{pesan_html}
{detail}
<p><a class="btn" href="/pengetahuan">← Kembali</a></p>
</div></body></html>""")


def pasang_pengetahuan(mcp) -> None:
    @mcp.custom_route("/pengetahuan", methods=["GET"])
    async def pengetahuan_home(request: Request):
        if not _beres(request):
            return HTMLResponse("<h3>403</h3><p>Halaman pengetahuan hanya dari localhost.</p>", status_code=403)
        return _laman()

    @mcp.custom_route("/pengetahuan/unggah", methods=["POST"])
    async def unggah_pdf_route(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        form = await request.form()
        berkas = form.get("berkas")
        tingkat_akses = str(form.get("tingkat_akses") or "public").strip() or "public"
        keterangan = str(form.get("keterangan") or "").strip()
        if berkas is None:
            return _laman(galat="Berkas PDF wajib diisi.")
        nama_file = getattr(berkas, "filename", "") or "unggahan.pdf"
        data_bytes = await berkas.read()
        if not data_bytes:
            return _laman(galat="Berkas PDF kosong.")
        try:
            knowledge.unggah_pdf(data_bytes, nama_file, tingkat_akses, keterangan)
        except Exception as e:
            log.exception("unggah_pdf gagal")
            return _laman(galat=f"Unggah gagal ({type(e).__name__}).")
        return RedirectResponse("/pengetahuan?pesan=Dokumen+diunggah", status_code=303)

    @mcp.custom_route("/pengetahuan/hapus", methods=["POST"])
    async def hapus_pdf_route(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        form = await request.form()
        document_id = str(form.get("document_id") or "").strip()
        if not document_id:
            return _laman(galat="ID dokumen kosong.")
        try:
            knowledge.hapus_pengetahuan(document_id)
        except Exception as e:
            log.exception("hapus_pengetahuan gagal")
            return _laman(galat=f"Hapus gagal ({type(e).__name__}).")
        return RedirectResponse("/pengetahuan?pesan=Dokumen+dihapus", status_code=303)

    @mcp.custom_route("/pengetahuan/status", methods=["POST"])
    async def status_pdf_route(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        form = await request.form()
        document_id = str(form.get("document_id") or "").strip()
        if not document_id:
            return _laman(galat="ID dokumen kosong.")
        try:
            hasil = knowledge.status_pengetahuan(document_id)
        except Exception as e:
            log.exception("status_pengetahuan gagal")
            return _laman_status(document_id, galat=f"Status gagal ({type(e).__name__}).")
        return _laman_status(document_id, hasil=hasil)