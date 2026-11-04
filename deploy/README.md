# Deploy & CI/CD TigaBeMCP

Dua layanan harus berjalan di server: MCP (`server.py`) dan embedding
(`embed_service.py`). Systemd unit tersedia di folder ini.

## 1. Sekali di server (setup tujuan deploy)

```bash
# pastikan repo sudah ada
cd /workspaceaitf/TigaBeMCP

# env rahasia HARUS sudah ada di server (tidak pernah di-commit/deploy)
test -f .env || echo "SALIN .env ke server!"

# dependensi
pip install -r requirements.txt

# pasang unit systemd (sesuaikan WorkingDirectory & ExecStart)
sudo cp deploy/tigabe-mcp.service /etc/systemd/system/
sudo cp deploy/tigabe-embed.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tigabe-embed tigabe-mcp
sudo systemctl status --no-pager tigabe-mcp tigabe-embed
```

## 2. Secrets GitHub (Settings → Secrets → Actions)

| Nama | Isi |
| --- | --- |
| `DEPLOY_HOST` | `epmcp001.aitalent.web.id` (atau IP server) |
| `DEPLOY_PORT` | port SSH, mis. `22` (kosongkan bila 22) |
| `DEPLOY_USER` | user SSH, mis. `root` |
| `DEPLOY_PATH` | path remote, mis. `/workspaceaitf/TigaBeMCP` |
| `DEPLOY_SSH_KEY` | private key yang cocok dengan `~/.ssh/id_ed25519.pub` di server |

Penting: `DEPLOY_SSH_KEY` adalah private key — disimpan sebagai **GitHub secret**,
tidak pernah di file repo.

## 3. Alur CI/CD

```mermaid
flowchart LR
    P[push ke main] --> CI[CI: compile + smoke]
    CI --> CD[CD: rsync ke server]
    CD --> R[restart tigabe-mcp & tigabe-embed]
```

- **CI** jalan untuk tiap push & PR: syntax-check semua `.py` + smoke import
  (tanpa butuh Qdrant/MinIO hidup).
- **CD** jalan otomatis hanya saat push ke `main` (environment `production`):
  rsync semua file KECUALI `.env`, `roles.json`, `login_users.json`,
  `audit_log.json`, `.venv`, `__pycache__`, `.git` — lalu restart dua service.

## 4. Keamanan deploy

File sensitif **tidak pernah di-deploy** via CD; harus dibuat manual sekali di
server:

| File | Keterangan |
| --- | --- |
| `.env` | MinIO/Qdrant/embedding credential |
| `roles.json` | override peran (opsional) |
| `login_users.json` | pengguna login (hash password) |
| `audit_log.json` | riwayat audit |

CD rsync mengecualikan keempatnya (`--exclude`).