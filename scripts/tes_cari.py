import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from search import cari

PERTANYAAN = [
    "Batas pengajuan penjemput pengganti jam berapa?",
    "Besok ada literasi pagi?",
    "Seragam hari Rabu untuk kelas 4 dan kelas 5?",
    "Kapan pembagian rapor?",
    "Kapan libur semester genap?",
    "Kalau penjemput terlambat sampai jam 15.00, bagaimana?",
]
for q in PERTANYAAN:
    print("\n" + "=" * 70 + "\nQ:", q)
    r = cari(q, top_k=6)
    for h in r["hasil"]:
        print(f"  {h['skor']}  {h['document_id']} hlm {h['halaman']} pasal {h['pasal']} "
              f"[{h['status_waktu']}] | {h['kutipan'][:70]!r}")
print("\nContoh URL:", r["hasil"][0]["document_url"][:90], "...")
