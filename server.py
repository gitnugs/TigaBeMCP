"""TigaBe AI - MCP Server PoC tahap 1.

Menggunakan data simulasi publik, tanpa data anak maupun autentikasi.
JANGAN memaparkan port backend ini langsung ke Internet.
"""
from pathlib import Path
from mcp.server import MCPServer

mcp = MCPServer("TigaBe School References (PoC)")
BASE_DIR = Path(__file__).resolve().parent

# Katalog minimal. Nantinya diganti database + ACL.
DOKUMEN = {
    "SIM-JADWAL-004": {
        "judul": "Jadwal Seragam Kelas 4 (SIMULASI)",
        "kelas": 4,
        "tanggal_berlaku": "2026-10-01",
        "nama_file": "jadwal_seragam_kelas4.md",
    }
}


def _muat_dokumen(document_id: str) -> dict | None:
    meta = DOKUMEN.get(document_id)
    if meta is None:
        return None
    path = BASE_DIR / "data" / meta["nama_file"]
    return {
        "document_id": document_id,
        "judul": meta["judul"],
        "kelas": meta["kelas"],
        "tanggal_berlaku": meta["tanggal_berlaku"],
        "konten": path.read_text(encoding="utf-8"),
        "document_url": None,  # URL unduh terotorisasi disiapkan pada tahap berikutnya.
    }


@mcp.tool()
def cari_referensi_jadwal(pertanyaan: str, kelas: int) -> dict:
    """Cari dokumen referensi jadwal/seragam sekolah yang tersedia untuk kelas.

    Hanya menggunakan katalog simulasi publik. Mengembalikan ID dan metadata sumber.
    """
    q = pertanyaan.casefold()
    kata_kunci = ("seragam", "baju", "pakaian", "jadwal")
    hasil = []
    if any(kata in q for kata in kata_kunci):
        for doc_id, meta in DOKUMEN.items():
            if meta["kelas"] == kelas:
                hasil.append({
                    "document_id": doc_id,
                    "judul": meta["judul"],
                    "kelas": kelas,
                    "tanggal_berlaku": meta["tanggal_berlaku"],
                    "sumber": "dokumen simulasi sekolah",
                })
    return {"status": "found" if hasil else "not_found", "results": hasil}


@mcp.tool()
def ambil_dokumen_referensi(document_id: str) -> dict:
    """Ambil isi dan metadata dokumen referensi publik berdasarkan ID dari pencarian.

    Konten yang dikembalikan dapat digunakan AI untuk menjawab dengan sitasi.
    """
    dokumen = _muat_dokumen(document_id)
    if dokumen is None:
        return {"status": "not_found", "document": None}
    return {"status": "found", "document": dokumen}


if __name__ == "__main__":
    # Backend pada VPS. Nanti diekspos secara aman melalui reverse proxy HTTPS.
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8105,
        stateless_http=True,
        json_response=True,
    )
