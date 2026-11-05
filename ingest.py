"""
Ingest PDF dari MinIO -> parse header -> chunk per pasal -> embedding -> Qdrant.

Jalankan:
  python ingest.py --dry           # tampilkan chunk (dipotong), tanpa embedding/Qdrant
  python ingest.py --dry --full    # tampilkan teks chunk lengkap
  python ingest.py                 # ingest sungguhan
"""
import io, logging, os, re, sys, uuid
from urllib.parse import urlparse

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.dirname(_here))
from storage import ambil_objek   # sekaligus memuat .env

log = logging.getLogger("tigabe.ingest")

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

DAFTAR = [
#    "SK-2026-014.pdf", "SK-2026-021.pdf", "JADWAL-2026-27.pdf",
#    "ANN-SCH-0077.pdf", "SOP-PA-01.pdf",
"SOP-IZIN-01.pdf",
]
COLLECTION = os.environ.get("QDRANT_COLLECTION", "tigabe_docs")
FULL = "--full" in sys.argv

LABELS = [
    ("document_id", "ID sumber"), ("jenis", "Jenis"),
    ("penerbit", "Penerbit / otoritas"), ("tanggal_terbit", "Tanggal terbit"),
    ("berlaku_mulai", "Berlaku mulai"), ("berlaku_sampai", "Berlaku sampai"),
    ("status", "Status"), ("tingkat_akses", "Tingkat akses"),
    ("menggantikan", "Menggantikan"), ("penanggung_jawab", "Penanggung jawab"),
]
# header berulang dan footer tiap halaman
SKIP = re.compile(r"^(Dokumen simulasi SD TigaBe|SD TigaBe - |Halaman \d+$|"
                  r"[A-Z0-9]+(-[A-Z0-9]+)+ (TERBATAS - AKSES TERBATAS )?SD TigaBe - )")
ID_ONLY = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)+$")   # baris yang hanya berisi ID dokumen


def _ocr_pdf(data: bytes) -> bytes:
    """OCR seluruh halaman scan (tanpa teks) menjadi PDF berteks.

    Memakai biner `tesseract` (harus terpasang di image, lihat Dockerfile.mcp)
    dengan bahasa `OCR_LANG` (default ind+eng). Hasil teks disisipkan per halaman
    sebagai lapisan teks sehingga `baca_pdf` bisa membacanya.
    """
    import shutil, subprocess, tempfile

    if shutil.which("tesseract") is None:
        raise RuntimeError(
            "OCR tidak tersedia: biner `tesseract` tidak ditemukan di container. "
            "File scan tidak dapat diindeks."
        )

    lang = os.environ.get("OCR_LANG", "ind+eng")
    doc = pymupdf.open(stream=data, filetype="pdf")
    out = pymupdf.open()
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            pix.save(tmp.name)
            tmp_name = tmp.name
        try:
            hasil = subprocess.run(
                ["tesseract", tmp_name, "stdout", "-l", lang, "--psm", "6"],
                check=True, capture_output=True, text=True,
            )
        finally:
            os.unlink(tmp_name)
        teks = " ".join(hasil.stdout.split())
        page_out = out.new_page(width=page.rect.width, height=page.rect.height)
        if teks:
            page_out.insert_text((10, 10), teks, fontsize=9)
    buf = io.BytesIO()
    out.save(buf)
    return buf.getvalue()


def baca_pdf(data: bytes) -> list[tuple[int, str]]:
    doc = pymupdf.open(stream=data, filetype="pdf")
    out = []
    for no, page in enumerate(doc, start=1):
        for raw in page.get_text("text").splitlines():
            line = " ".join(raw.split())
            if line and not SKIP.match(line):
                out.append((no, line))
    if all(t.strip() == "" for _, t in out):
        # PDF scan (gambar) tanpa teks -> jalankan OCR ulang
        log.info("PDF tanpa teks; mencoba OCR (lang=%s)", os.environ.get("OCR_LANG", "ind+eng"))
        data = _ocr_pdf(data)
        doc = pymupdf.open(stream=data, filetype="pdf")
        out = []
        for no, page in enumerate(doc, start=1):
            for raw in page.get_text("text").splitlines():
                line = " ".join(raw.split())
                if line and not SKIP.match(line):
                    out.append((no, line))
    return out


def parse_header(lines):
    texts = [t for _, t in lines]
    i0 = next(i for i, t in enumerate(texts) if t.startswith("ID sumber"))
    i1 = next(i for i, t in enumerate(texts) if i > i0 and re.match(r"^1\.\s+\D", t))

    nilai, kunci = {}, None
    for t in texts[i0:i1]:
        for k, label in LABELS:
            m = re.match(rf"^{re.escape(label)}\b\s*:?\s*(.*)$", t)
            if m:
                kunci = k
                nilai[k] = [m.group(1)] if m.group(1) else []
                break
        else:
            if kunci:
                nilai[kunci].append(t)
    meta = {k: " ".join(v).strip() for k, v in nilai.items()}

    # judul = baris sebelum "ID sumber", tanpa sisa header/footer halaman
    doc_id = meta.get("document_id", "")
    pre = [t for t in texts[:i0]
           if t != doc_id and not ID_ONLY.match(t)
           and not t.startswith(("SD TigaBe -", "Halaman", "TERBATAS", "Dokumen simulasi"))]
    judul = pre[0] if pre else doc_id
    if len(pre) > 1 and len(pre[1]) < 10:      # judul yang terpotong, mis. "2026"
        judul += " " + pre[1]
    meta["title"] = judul

    meta["tingkat_akses"] = meta.get("tingkat_akses", "").lower()
    meta["status"] = meta.get("status", "").lower()
    if meta.get("berlaku_sampai", "").lower().startswith("tidak"):
        meta["berlaku_sampai"] = None            # tanpa batas
    if meta.get("menggantikan") in ("-", ""):
        meta["menggantikan"] = None
    return meta, lines[i1:]


def buat_chunk(body, doc_id):
    units, cur = [], None
    sec_no, sec_label = 0, ""

    def tutup():
        nonlocal cur
        if cur and " ".join(cur["lines"]).strip():
            units.append(cur)
        cur = None

    for page, line in body:
        if line == doc_id or ID_ONLY.match(line):    # sisa header halaman
            continue
        m_sec = re.match(r"^(\d+)\.\s+(\D.*)$", line)
        m_cl = re.match(r"^(\d+\.\d+)\s+(.*)$", line)
        if m_sec and int(m_sec.group(1)) == sec_no + 1:   # nomor bagian harus berurutan
            tutup()
            sec_no = int(m_sec.group(1))
            sec_label = f"{sec_no}. {m_sec.group(2)}"
            cur = dict(pasal=str(sec_no), section=sec_label, page=page, page_end=page, lines=[])
        elif m_cl and m_cl.group(1).split(".")[0] == str(sec_no):
            tutup()
            cur = dict(pasal=m_cl.group(1), section=sec_label, page=page, page_end=page,
                       lines=[m_cl.group(2)])
        else:
            if cur is None:
                cur = dict(pasal=None, section=sec_label, page=page, page_end=page, lines=[])
            cur["lines"].append(line)
            cur["page_end"] = page
    tutup()
    return units


def proses_pdf(data: bytes, overrides: dict | None = None):
    """Parse PDF jadi (meta, chunks) tanpa menyentuh MinIO/Qdrant.

    `chunks` = list[(n, embed_text, payload)]; `n` indeks urut chunk.
    `overrides` menimpa/mengisi nilai meta SEBELUM chunk dibangun, sehingga
    payload & embed_text konsisten (dipakai knowledge.unggah_pdf)."""
    lines = baca_pdf(data)
    try:
        meta, body = parse_header(lines)
    except (StopIteration, IndexError):
        # PDF tanpa blok header terstruktur: seluruh teks menjadi isi dokumen
        body = lines
        meta = {k: None for k, _ in LABELS}
        meta["document_id"] = ""
        meta["title"] = None
    if overrides:
        meta.update(overrides)
    doc_id = meta.get("document_id") or ""
    if not meta.get("title"):
        meta["title"] = doc_id
    object_key = doc_id + ".pdf"
    chunks = []
    for n, u in enumerate(buat_chunk(body, doc_id)):
        teks = "\n".join(u["lines"])
        pasal = f"Pasal {u['pasal']}" if u["pasal"] else "Pengantar"
        embed_text = f"{meta['title']} [{doc_id}] - {u['section']} - {pasal}\n{teks}"
        payload = dict(meta, object_key=object_key, page=u["page"], page_end=u["page_end"],
                       pasal=u["pasal"], section=u["section"], text=teks)
        chunks.append((n, embed_text, payload))
    return meta, chunks


def siapkan(key):
    data = ambil_objek(key)
    meta, chunks = proses_pdf(data)
    if key != meta["document_id"] + ".pdf":
        print(f"  PERINGATAN: object_key {key} tidak sama dengan ID sumber {meta['document_id']}")
    return meta, chunks


def buat_klien():
    from qdrant_client import QdrantClient
    url = os.environ["QDRANT_URL"].strip()
    if "://" not in url:
        url = "https://" + url
    u = urlparse(url)
    port = u.port or (443 if u.scheme == "https" else 6333)
    return QdrantClient(url=f"{u.scheme}://{u.hostname}", port=port,
                        api_key=os.environ["QDRANT_API_KEY"], timeout=60)


def _embed_ready(waktu_tunggu: float = 120.0) -> None:
    """Tunggu sampai layanan embed siap (model termuat) sebelum embedding.

    /health hanya 200 setelah model E5 selesai dimuat (lifespan warm-up).
    Tanpa ini, upload tepat setelah deploy/restart akan kena connection
    refused karena embed masih loading berat (~30-60 detik di CPU).
    """
    import time

    import httpx

    url = os.environ.get("EMBED_URL", "http://127.0.0.1:18110").rstrip("/")
    batas = time.monotonic() + waktu_tunggu
    terakhir = None
    while time.monotonic() < batas:
        try:
            r = httpx.get(f"{url}/health", timeout=5)
            r.raise_for_status()
            return
        except Exception as e:  # noqa: BLE001 — semua error readiness boleh ditunggu
            terakhir = e
            time.sleep(2)
    raise RuntimeError(f"Layanan embedding tidak siap setelah {waktu_tunggu:.0f}s: {terakhir}")


def _embed_passages_retry(texts: list[str], upaya: int = 5) -> list[list[float]]:
    """Embedding dengan readiness gate + retry; layanan embed bisa gagal
    cold-start (model baru dimuat) pada request pertama setelah deploy."""
    import time
    from embedding import embed_passages

    _embed_ready()
    terakhir = None
    for i in range(upaya):
        try:
            return embed_passages(texts)
        except Exception as e:  # noqa: BLE001 — semua error embed boleh dicoba ulang
            terakhir = e
            log.warning("embed_passages gagal (upaya %d/%d): %s", i + 1, upaya, e)
            if i + 1 < upaya:
                time.sleep(2 * (i + 1))   # backoff 2s, 4s, 6s, 8s
    raise terakhir


def dorong_ke_qdrant(meta, chunks) -> int:
    """Vektorisasi + simpan `chunks` satu dokumen ke Qdrant (idempoten).

    TIDAK memfilter tingkat_akses; seluruh chunk dikirim. Kembalikan jumlah titik
    yang berhasil di-upsert (0 jika tidak ada chunk)."""
    doc_id = meta["document_id"]
    if not chunks:
        return 0

    from qdrant_client import models
    from embedding import DIM

    client = buat_klien()
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            COLLECTION,
            vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE),
        )
    for f in ("document_id", "tingkat_akses", "status", "jenis"):
        client.create_payload_index(COLLECTION, f, models.PayloadSchemaType.KEYWORD)

    # idempoten: hapus chunk lama dokumen ini lebih dulu
    client.delete(
        COLLECTION,
        points_selector=models.FilterSelector(filter=models.Filter(must=[
            models.FieldCondition(key="document_id", match=models.MatchValue(value=doc_id))
        ])),
    )
    vecs = _embed_passages_retry([c[1] for c in chunks])
    points = [
        models.PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}|{n}")),
            vector=v, payload=p,
        )
        for (n, _, p), v in zip(chunks, vecs)
    ]
    client.upsert(COLLECTION, points=points)
    return len(points)


def main():
    dry = "--dry" in sys.argv
    hasil = []
    for key in DAFTAR:
        print(f"\n=== {key}")
        meta, chunks = siapkan(key)
        print({k: meta.get(k) for k in ("document_id", "title", "tingkat_akses", "status",
                                         "berlaku_mulai", "berlaku_sampai", "menggantikan")})
        if meta["tingkat_akses"] != "class":     # pagar pengaman PoC
            print("  DILEWATI: bukan dokumen public")
            continue
        for n, et, p in chunks:
            teks = p["text"] if FULL else p["text"][:110]
            print(f"  [{n}] hlm {p['page']} pasal {p['pasal']} | {p['section']}\n      "
                  + teks.replace("\n", "\n      " if FULL else " / "))
        hasil.append((meta, chunks))

    if dry:
        print("\n(dry run: tidak ada yang dikirim ke Qdrant)")
        return

    total = 0
    for meta, chunks in hasil:
        n = dorong_ke_qdrant(meta, chunks)
        doc_id = meta["document_id"]
        print(f"{doc_id}: {n} chunk tersimpan")
        total += n

    client = buat_klien()
    print("Total titik di collection:", client.count(COLLECTION).count)


if __name__ == "__main__":
    main()
