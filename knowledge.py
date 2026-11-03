"""Backend manajemen pengetahuan TigaBeMCP.

CRUD dokumen pengetahuan: daftar, unggah PDF (MinIO) -> vectorize (Qdrant),
cek status, dan hapus.

Fungsi-fungsi ini dipakai oleh lapisan UI/MCP; nama dan kunci kembalian sudah
menjadi kontrak bersama UI.
"""
from __future__ import annotations

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.dirname(_here))

from dotenv import load_dotenv

load_dotenv(os.path.join(_here, ".env"))

from storage import unggah_objek, ada_objek, hapus_objek  # noqa: E402
from ingest import proses_pdf, dorong_ke_qdrant, buat_klien, COLLECTION  # noqa: E402

# Kunci internal per-chunk di payload Qdrant; jangan tampilkan sebagai meta.
_KUNCI_INTERNAL = {"text", "object_key", "page", "page_end", "pasal", "section"}


def _filter_qdrant_dokumen(document_id: str):
    """Filter Qdrant untuk memilih seluruh titik milik satu dokumen."""
    from qdrant_client import models

    return models.Filter(must=[
        models.FieldCondition(
            key="document_id",
            match=models.MatchValue(value=document_id),
        ),
    ])


def _ringkas_meta(payload: dict) -> dict:
    """Payload Qdrant tanpa kunci internal per-chunk (jadi mirip meta dokumen)."""
    return {k: v for k, v in (payload or {}).items() if k not in _KUNCI_INTERNAL}


def daftar_pengetahuan() -> list[dict]:
    """Daftar semua dokumen pengetahuan (dedup per document_id dari Qdrant)."""
    client = buat_klien()
    hasil: dict[str, dict] = {}
    offset = None
    while True:
        pts, offset = client.scroll(
            COLLECTION,
            with_payload=True,
            with_vectors=False,
            limit=256,
            offset=offset,
        )
        for p in pts:
            d = p.payload or {}
            doc_id = d.get("document_id")
            if not doc_id or doc_id in hasil:
                continue
            hasil[doc_id] = {
                "document_id": doc_id,
                "object_key": d.get("object_key") or f"{doc_id}.pdf",
                "title": d.get("title") or doc_id,
                "tingkat_akses": d.get("tingkat_akses"),
                "status": d.get("status"),
                "meta": _ringkas_meta(d),
            }
        if offset is None:
            break
    return list(hasil.values())


def unggah_pdf(data: bytes, nama_file: str, tingkat_akses: str, keterangan: str = "") -> dict:
    """Unggah PDF ke MinIO lalu vektorisasi ke Qdrant.

    document_id = meta["document_id"] jika ada, selain itu stem nama berkas
    (huruf besar). object_key = f"{document_id}.pdf".
    """
    meta, chunks = proses_pdf(data)
    if not (meta.get("document_id") or "").strip():
        fallback_id = os.path.splitext(os.path.basename(nama_file))[0].upper()
        meta, chunks = proses_pdf(data, overrides={"document_id": fallback_id})

    doc_id = meta["document_id"]
    object_key = f"{doc_id}.pdf"

    final_meta = dict(meta)
    final_meta["tingkat_akses"] = tingkat_akses.lower()
    final_meta["keterangan"] = keterangan
    # sinkronkan payload chunk dengan meta final (tingkat_akses dkk.)
    for _n, _et, payload in chunks:
        payload.update(final_meta)

    di_minio, minio_ok = False, False
    chunk_qdrant, qdrant_ok = 0, False

    try:
        unggah_objek(object_key, data)
        di_minio = ada_objek(object_key)
        minio_ok = di_minio
    except Exception as _e:
        minio_ok = False
        di_minio = ada_objek(object_key)

    try:
        chunk_qdrant = dorong_ke_qdrant(final_meta, chunks)
        qdrant_ok = True
    except Exception as _e:
        qdrant_ok = False
        chunk_qdrant = 0

    if minio_ok and qdrant_ok:
        status = "lengkap"
    elif minio_ok:
        status = "minio"
    elif qdrant_ok:
        status = "qdrant"
    else:
        status = "gagal"

    return {
        "document_id": doc_id,
        "object_key": object_key,
        "tingkat_akses": final_meta["tingkat_akses"],
        "di_minio": di_minio,
        "chunk_qdrant": chunk_qdrant,
        "status": status,
        "meta": final_meta,
    }


def status_pengetahuan(document_id: str) -> dict:
    """Cek keberadaan PDF (MinIO) dan vektor (Qdrant) satu dokumen."""
    object_key = f"{document_id}.pdf"
    di_minio = ada_objek(object_key)

    meta = {}
    chunk_qdrant = 0
    try:
        client = buat_klien()
        chunk_qdrant = client.count(
            COLLECTION,
            count_filter=_filter_qdrant_dokumen(document_id),
            exact=True,
        ).count
        # ambil payload pertama untuk meta (bila masih ada)
        pts, _ = client.scroll(
            COLLECTION,
            with_payload=True,
            with_vectors=False,
            scroll_filter=_filter_qdrant_dokumen(document_id),
            limit=1,
        )
        if pts:
            meta = _ringkas_meta(pts[0].payload or {})
    except Exception as _e:
        chunk_qdrant = 0

    if di_minio and chunk_qdrant:
        status = "lengkap"
    elif di_minio:
        status = "minio"
    elif chunk_qdrant:
        status = "qdrant"
    else:
        status = "gagal"

    return {
        "document_id": document_id,
        "object_key": object_key,
        "di_minio": di_minio,
        "chunk_qdrant": chunk_qdrant,
        "status": status,
        "meta": meta,
    }


def hapus_pengetahuan(document_id: str) -> dict:
    """Hapus PDF dari MinIO dan vektor dari Qdrant."""
    object_key = f"{document_id}.pdf"
    di_minio = hapus_objek(object_key)

    qdrant_ok = False
    sisa = None
    try:
        client = buat_klien()
        from qdrant_client import models

        selector = models.FilterSelector(filter=_filter_qdrant_dokumen(document_id))
        client.delete(COLLECTION, points_selector=selector)
        qdrant_ok = True
        sisa = client.count(
            COLLECTION,
            count_filter=_filter_qdrant_dokumen(document_id),
            exact=True,
        ).count
    except Exception as _e:
        qdrant_ok = False

    status = "dihapus" if (di_minio or qdrant_ok) else "gagal"
    return {
        "document_id": document_id,
        "object_key": object_key,
        "di_minio": di_minio,
        "qdrant_dihapus": qdrant_ok,
        "sisa_chunk": sisa,
        "status": status,
    }