# Ekspor WorkBuddy — TigaBe MCP

Paket agar alur proyek TigaBeMCP bisa dipanggil dari WorkBuddy sebagai
**skill + MCP app**. Semua di folder `workbuddy-export/`.

## Isi

```
workbuddy-export/
├── .codebuddy-plugin/
│   └── plugin.json        # identitas plugin (author, keyword, kategori mcp-app)
├── .mcp.json              # definisi server MCP (HTTP ke 127.0.0.1:18105/mcp)
├── skills/
│   └── tigabe-mcp/
│       ├── SKILL.md            # instruksi untuk AI + tabel tools
│       └── references/
│           └── rumus-alur.md   # rumus dialog + status server
└── README.md             # file ini
```

## Cara memasang di WorkBuddy

1. Jalankan proyek (2 service):
   ```powershell
   python scripts/jalankan_embed.py
   python scripts/jalankan_lokal.py
   ```
2. Salin isi `workbuddy-export/` ke lokasi skill WorkBuddy:
   - **WorkBuddy desktop:** `C:\Users\<user>\.workbuddy-ai\skills\tigabe-mcp\`
   - **CodeBuddy CLI:** `C:\Users\<user>\.codebuddy\skills\tigabe-mcp\`
3. Daftarkan server MCP di WorkBuddy: **Settings → MCP → Add MCP Server**, type
   HTTP, URL `http://127.0.0.1:18105/mcp` (sama dengan `.mcp.json`).
4. Tutup & buka ulang WorkBuddy agar skill + tool terbaca.

## Alur pemakaian

- Tanya soal sekolah → AI memanggil `peran_saya` + `cari_dokumen`.
- Ganti peran → AI memanggil `masuk_browser`, beri tautan, user login di
  browser, lalu `cek_login`.
- Logout → `keluar`.
- Riwayat terlihat di `http://127.0.0.1:18105/admin/audit` (format `audit_log.json`).

## Keamanan

- Password tidak lewat chat (jalur utama browser `masuk_browser`).
- Audit menyensor nilai `password` menjadi `********`.