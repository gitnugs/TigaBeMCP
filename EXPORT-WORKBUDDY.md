# Dokumentasi Ekspor WorkBuddy — TigaBe MCP

Ekspor WorkBuddy memungkinkan **alur proyek TigaBeMCP** dipanggil langsung
dari WorkBuddy sebagai **skill + MCP app**. Berkas lengkap ada di folder
`workbuddy-export/`.

## Ringkasan

| Berkas | Fungsi |
| --- | --- |
| `workbuddy-export/.codebuddy-plugin/plugin.json` | Identitas plugin MCP app (author, kategori, keyword) |
| `workbuddy-export/.mcp.json` | Definisi server MCP: HTTP `http://127.0.0.1:18105/mcp` |
| `workbuddy-export/skills/tigabe-mcp/SKILL.md` | Instruksi AI: tabel tools, aturan login browser, anti-mengarang |
| `workbuddy-export/skills/tigabe-mcp/references/rumus-alur.md` | Rumus dialog + daftar status server |
| `workbuddy-export/README.md` | Panduan pasang & keamanan |

## Prasyarat

```powershell
pip install -r requirements.txt
python scripts/buat_user.py --username sari --peran guru --password "rahasia"
python scripts/jalankan_embed.py     # service embedding (model E5)
python scripts/jalankan_lokal.py     # MCP + login + admin
```

## Pasang di WorkBuddy

1. Salin isi `workbuddy-export/skills/tigabe-mcp/` ke:
   - WorkBuddy desktop: `%USERPROFILE%\.workbuddy-ai\skills\tigabe-mcp\`
   - CodeBuddy CLI: `%USERPROFILE%\.codebuddy\skills\tigabe-mcp\`
2. WorkBuddy → **Settings → MCP → Add MCP Server**:
   - Type: **HTTP**
   - URL: `http://127.0.0.1:18105/mcp`
   - Tanpa header autentikasi (server melayani tanpa 401 saat connect).
3. Restart WorkBuddy (tray → Quit → buka lagi).

## Alur yang bisa dipanggil dari WorkBuddy

1. `peran_saya` — deteksi peran aktif.
2. `cari_dokumen(query, top_k, tanggal_acuan)` — cari aturan/jadwal/seragam.
3. `masuk_browser` — buat tautan login browser (ganti peran tanpa password di chat).
4. `cek_login` — konfirmasi selesai login browser.
5. `masuk(username, password)` — cadangan (hanya bila user paksa; password terlihat model).
6. `keluar` — kembali ke peran publik.

## Pemantauan

- Halaman admin: `http://127.0.0.1:18105/admin`
- Audit chat: `http://127.0.0.1:18105/admin/audit`
- Audit tersimpan sebagai JSON: `audit_log.json` (password disensor `********`).