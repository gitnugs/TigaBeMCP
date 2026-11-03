# TigaBe AI

Asisten informasi resmi SD TigaBe (agent). Menjawab aturan, jadwal, seragam,
penjemputan, dan perlindungan anak berdasarkan dokumen resmi lewat MCP.

## Tipe

Agent (satu AI expert) yang memakai server MCP `tigabe`.

## Fitur

- `peran_saya` — deteksi peran aktif.
- `cari_dokumen` — cari aturan/jadwal/seragam/penjemputan.
- `masuk_browser` + `cek_login` — ganti peran via login browser (tanpa password di chat).
- `keluar` — logout kembali ke peran publik.

## Contoh prompt

- "Jadwal pelajaran hari ini apa saja?"
- "Ketentuan seragam sekolah apa?"
- "Bagaimana prosedur penjemputan siswa?"
- "SOP perlindungan anak seperti apa?"

## Prasyarat

Dua service proyek harus jalan:

```bash
python scripts/jalankan_embed.py
python scripts/jalankan_lokal.py
```

Server MCP aktif di `http://127.0.0.1:18105/mcp`.

## Avatar

`avatars/expert.png` (1024×1024).

## Install

Paket expert ini sudah ada di marketplace lokal `my-experts`.