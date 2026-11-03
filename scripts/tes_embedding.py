import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from embedding import embed_passages, embed_query, DIM

t = time.time()
docs = [
    "Pengajuan penjemput pengganti paling lambat pukul 12.00 pada hari yang sama.",
    "Semester ganjil berlangsung 13 Juli 2026 sampai 18 Desember 2026.",
    "Siswa yang belum dijemput sampai pukul 14.30 menunggu di ruang tunggu.",
]
dv = embed_passages(docs)
print("dimensi:", len(dv[0]), "(harus", DIM, ")")
print(f"waktu muat + embed: {time.time()-t:.1f} detik")

q = embed_query("Jam berapa batas mendaftarkan orang lain untuk menjemput anak?")
for d, v in zip(docs, dv):
    skor = sum(a*b for a, b in zip(q, v))   # cosine, karena sudah dinormalisasi
    print(f"{skor:.3f}  {d}")
