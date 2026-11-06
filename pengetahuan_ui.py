"""Halaman web kelola pengetahuan: CRUD dokumen + unggah PDF.
Memakai knowledge (MinIO + Qdrant) yang dibangun di modul terpisah.
"""
from __future__ import annotations

import html
import logging
import os
from urllib.parse import quote, urlsplit

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

import knowledge
from storage import buat_document_url
from html_theme import IKON, wadah

log = logging.getLogger("tigabe.pengetahuan")

_AKSES_TINGKAT = ("public", "class", "internal", "restricted")

# Status unggah/status dokumen -> tampilan
_STATUS_PETA = {
    "lengkap": ("pill-success", "Lengkap"),
    "minio": ("pill-warn", "Hanya MinIO"),
    "qdrant": ("pill-warn", "Hanya Qdrant"),
    "gagal": ("pill-danger", "Gagal"),
    "dihapus": ("pill-success", "Dihapus"),
}


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
    return "".join(
        f"<option value='{a}' {'selected' if a == dipilih else ''}>{a}</option>"
        for a in _AKSES_TINGKAT
    )


def _pillin(teks: str, kelas: str) -> str:
    return f"<span class='pill {kelas}'>{html.escape(teks)}</span>"


def _pilin_status(status: str | None) -> str:
    kelas, teks = _STATUS_PETA.get(str(status or "").strip(), ("pill-neutral", status or "—"))
    return _pillin(teks, kelas)


def _pilin_minio(ada: bool) -> str:
    if ada:
        return _pillin("Ada", "pill-success")
    return _pillin("Tidak", "pill-neutral")


def _laman(pesan: str = "", galat: str = "") -> HTMLResponse:
    try:
        docs = knowledge.daftar_pengetahuan()
        galat_backend = ""
    except Exception as e:
        docs = []
        galat_backend = f"Gagal memuat daftar ({type(e).__name__}). "

    def _baris(i: int, d: dict) -> str:
        doc_id = html.escape(str(d.get("document_id", "")))
        meta_d = d.get("meta") or {}
        title = html.escape(str(d.get("title") or doc_id))
        jenis = html.escape(str(d.get("jenis") or meta_d.get("jenis") or ""))
        akses = html.escape(str(d.get("tingkat_akses") or meta_d.get("tingkat_akses") or ""))
        obj_key = html.escape(str(d.get("object_key") or f"{d.get('document_id', '')}.pdf"))
        chunk = html.escape(str(d.get("chunk_qdrant", 0)))
        dminio = bool(d.get("di_minio"))
        keterangan = html.escape(str(meta_d.get("keterangan") or ""))

        if dminio:
            tombol_preview = (
                f"<form method='GET' action='/pengetahuan/preview' style='margin:0'>"
                f"<input type='hidden' name='object_key' value='{obj_key}'>"
                f"<input type='hidden' name='document_id' value='{doc_id}'>"
                f"<button class='btn btn-ghost btn-sm' type='submit' title='Pratinjau PDF'>"
                f"{IKON['eye']} Preview</button></form>"
            )
        else:
            tombol_preview = (
                f"<span class='btn btn-ghost btn-sm' title='PDF belum ada di MinIO' "
                f"aria-disabled='true'>{IKON['eye']} Preview</span>"
            )

        akses_tampil = f"<span class='tag mono'>{akses}</span>" if akses else \
            '<span class="tag">(kosong)</span>'

        return (
            f"<tr>"
            f"<td class='num'>{i}</td>"
            f"<td><div class='doc-main'><span class='doc-title' title='{title}'>{title}</span>"
            f"<span class='doc-id'>{doc_id}</span></div></td>"
            f"<td>{jenis or '<span style=\"color:var(--faint)\">—</span>'}</td>"
            f"<td>{akses_tampil}</td>"
            f"<td>{_pilin_minio(dminio)}</td>"
            f"<td class='num'>{chunk}</td>"
            f"<td class='sel'>{keterangan or '<span style=\"color:var(--faint)\">—</span>'}</td>"
            f"<td style='text-align:right;white-space:nowrap'>"
            f"<div style='display:inline-flex;gap:6px'>"
            f"{tombol_preview}"
            f"<form method='POST' action='/pengetahuan/status' style='margin:0'>"
            f"<input type='hidden' name='document_id' value='{doc_id}'>"
            f"<button class='btn btn-ghost btn-sm' type='submit' title='Lihat status'>{IKON['pulse']} Status</button></form> "
            f"<form method='POST' action='/pengetahuan/hapus' style='margin:0' "
            f"onsubmit=\"return confirm('Hapus dokumen ini?')\">"
            f"<input type='hidden' name='document_id' value='{doc_id}'>"
            f"<button class='btn btn-danger btn-sm' type='submit' title='Hapus dokumen'>{IKON['trash']} Hapus</button></form>"
            f"</div></td></tr>"
        )

    tr_docs = "".join(_baris(i, d) for i, d in enumerate(docs, start=1)) or (
        '<tr><td colspan="8"><div class="empty">'
        '<div class="judul">Belum ada dokumen</div>'
        'Unggah PDF lewat form di bawah untuk memulai.</div></td></tr>'
    )

    galat_efektif = galat or galat_backend

    # ---- kartu dokumen ----
    kartu_dokumen = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{IKON["doc"]} Dokumen Pengetahuan</h2>'
        '<div class="meta">PDF tersimpan di MinIO, vektor di Qdrant.</div></div>'
        f'<span class="count">{len(docs)}</span></div>'
        '<div class="card-body ketat"><div class="table-scroll"><table>'
        '<thead><tr><th>No</th><th>Dokumen</th><th>Jenis</th><th>Akses</th>'
        '<th>MinIO</th><th>Chunk</th><th>Keterangan</th><th></th></tr></thead>'
        f'<tbody>{tr_docs}</tbody></table></div></div></section>'
    )

    # ---- form unggah ----
    form_unggah = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{IKON["upload"]} Unggah PDF</h2>'
        '<div class="meta">Berkas diurai, dipotong (chunk), lalu di-embed ke Qdrant.</div></div></div>'
        '<div class="card-body">'
        "<form method='POST' action='/pengetahuan/unggah' enctype='multipart/form-data'>"
        "<div class='field'><label for='f-berkas'>Berkas PDF <span class='wajib'>*</span></label>"
        "<input type='file' id='f-berkas' name='berkas' accept='application/pdf,.pdf' required></div>"
        "<div class='field'><label for='f-akses'>Tingkat akses</label>"
        f"<select id='f-akses' name='tingkat_akses'>{_opsi_akses()}</select>"
        "<p class='hint'>Nilai ini jadi filter <code>tingkat_akses</code> saat pencarian.</p></div>"
        "<div class='field'><label for='f-ket'>Keterangan</label>"
        "<textarea id='f-ket' name='keterangan' rows='2' placeholder='Opsional'></textarea></div>"
        f"<button class='btn btn-primary' type='submit'>{IKON['upload']} Unggah PDF</button>"
        "</form></div></section>"
    )

    isi = (
        '<div class="grid-utama">'
        '{kartu_dokumen}{form_unggah}</div>'
    ).format(kartu_dokumen=kartu_dokumen, form_unggah=form_unggah)

    html_doc = wadah(
        judul_halaman="Pengetahuan",
        deskripsi="Kelola dokumen resmi: unggah, cek status, pratinjau, hapus.",
        aktif="knowledge",
        isi={"isi": isi, "pesan": pesan, "galat": galat_efektif},
        judul="Pengetahuan TigaBe MCP",
    )
    return HTMLResponse(html_doc)


def _laman_status(document_id: str, hasil: dict | None = None, galat: str = "") -> HTMLResponse:
    if hasil is not None:
        d_minio = bool(hasil.get("di_minio"))
        chunk = hasil.get("chunk_qdrant", 0)
        status = _pilin_status(hasil.get("status"))
        meta = hasil.get("meta") or {}
        # urutan deterministik, meta internal dulu
        kunci = ["title", "jenis", "tingkat_akses", "keterangan", "status",
                 "tanggal_berlaku", "tanggal_habis", "document_id"]
        kunci += [k for k in meta if k not in kunci]
        rows = []
        rows.append(("Status", status))
        rows.append(("PDF di MinIO", _pilin_minio(d_minio)))
        rows.append(("Chunk di Qdrant", chunk))
        for k in kunci:
            if k in meta and meta[k] not in (None, ""):
                rows.append((k, html.escape(str(meta[k]))))
        detail = hl = ""
        for k, v in rows:
            hl += f"<dt>{html.escape(k)}</dt><dd>{v}</dd>"
        detail = f'<dl class="kv">{hl}</dl>'
    else:
        detail = ""

    galat_html = ""
    if galat:
        galat_html = ('<div class="alert galat">{ikon}<span>{teks}</span></div>').format(
            ikon=IKON["galat"], teks=galat)

    kembali = (
        f"<a class='btn btn-ghost' href='/pengetahuan'>{IKON['back']} Kembali</a>"
    )
    body = (
        '<section class="card"><div class="card-head"><div>'
        f'<h2>{IKON["pulse"]} Status Dokumen</h2>'
        f'<div class="meta">ID: <code>{html.escape(document_id)}</code></div></div></div>'
        '<div class="card-body">{detail}</div></section>'
    ).format(detail=detail or '<div class="empty"><div class="judul">Tidak ada data</div>'
             'Dokumen tidak ditemukan di MinIO maupun Qdrant.</div>')

    isi = '{galat_html}{body}{kembali}'.format(
        galat_html=galat_html, body=body, kembali=kembali)

    html_doc = wadah(
        judul_halaman="Status Dokumen",
        deskripsi="Keberadaan PDF dan vektor dari satu dokumen.",
        aktif="knowledge",
        isi={"isi": isi, "pesan": "", "galat": ""},
        judul="Status Pengetahuan",
    )
    return HTMLResponse(html_doc)


def _laman_preview(object_key: str, document_id: str, galat: str = "") -> HTMLResponse:
    """Tampilkan PDF dalam iframe via presigned URL (30 menit) dari MinIO."""
    try:
        url = buat_document_url(object_key)
        galat_js = ""
    except Exception as e:
        url = ""
        galat_js = html.escape(f"Gagal membuat tautan preview ({type(e).__name__}).")

    galat_html = ""
    if galat_js:
        galat_html = ('<div class="alert galat">{ikon}<span>{teks}</span></div>').format(
            ikon=IKON["galat"], teks=galat_js)

    frame = ("<iframe class='frame' src='" + html.escape(url) +
             "' title='Preview PDF' loading='lazy'></iframe>") if url else ""

    kembali = (
        f"<a class='btn btn-ghost' href='/pengetahuan'>{IKON['back']} Kembali</a>"
    )
    body = (
        '<div class="catatan" style="margin-top:0;margin-bottom:14px">'
        'Pratinjau memakai tautan presigned MinIO (berlaku 30 menit).</div>'
        '{galat_html}{frame}'
    ).format(galat_html=galat_html, frame=frame)

    html_doc = wadah(
        judul_halaman=f"Preview {html.escape(document_id)}",
        deskripsi="Pratinjau dokumen PDF dari MinIO.",
        aktif="knowledge",
        isi={"isi": body, "pesan": "", "galat": ""},
        judul=f"Preview {html.escape(document_id)}",
        aksi=kembali,
    )
    return HTMLResponse(html_doc)


def pasang_pengetahuan(mcp) -> None:
    @mcp.custom_route("/pengetahuan", methods=["GET"])
    async def pengetahuan_home(request: Request):
        if not _beres(request):
            return HTMLResponse("<h3>403</h3><p>Halaman pengetahuan hanya dari localhost.</p>", status_code=403)
        pesan = str(request.query_params.get("pesan") or "").strip()
        return _laman(pesan=pesan)

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
            hasil = knowledge.unggah_pdf(data_bytes, nama_file, tingkat_akses, keterangan)
        except Exception as e:
            log.exception("unggah_pdf gagal")
            return _laman(galat=f"Unggah gagal: {type(e).__name__}: {str(e)[:200]}")
        status = hasil.get("status")
        pesan = None
        galat = None
        if status == "lengkap":
            pesan = f"Dokumen ditambahkan: {hasil.get('document_id')} ({hasil.get('chunk_qdrant')} chunk)."
        elif status == "minio":
            galat = f"PDF tersimpan di MinIO tapi GAGAL di-indeks ke Qdrant ({hasil.get('document_id')}). Dokumen belum bisa dicari/daftar."
        elif status == "qdrant":
            galat = f"Tervermda di Qdrant tapi PDF belum tersimpan di MinIO ({hasil.get('document_id')})."
        else:
            galat = f"Unggah gagal (status={status}) untuk {hasil.get('document_id')}."
        if pesan:
            return RedirectResponse(f"/pengetahuan?pesan={quote(pesan)}", status_code=303)
        return _laman(galat=galat or "Unggah gagal tanpa keterangan.")

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

    @mcp.custom_route("/pengetahuan/preview", methods=["GET"])
    async def preview_pdf_route(request: Request):
        if not _beres(request):
            return HTMLResponse("403", status_code=403)
        object_key = str(request.query_params.get("object_key") or "").strip()
        document_id = str(request.query_params.get("document_id") or "").strip()
        if not object_key:
            return _laman_preview("", document_id, "object_key kosong.")
        return _laman_preview(object_key, document_id)

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