# Deploy Docker — TigaBeMCP

Dua kontainer: **mcp** (server + login + admin + pengetahuan) dan **embed**
(embedding model E5).

## 1. Build & jalankan

```bash
# (a) build kedua image
docker compose build

# (b) jalankan di background
docker compose up -d

# (c) lihat status & log
docker compose ps
docker compose logs -f mcp
```

Port yang dibuka:
- `18105` → server MCP
- `18110` → embedding (di container bisa diakses internal via nama `embed`)

> `.env` harus ada di direktori proyek (dipakai `env_file`). File ini **tidak
> di-commit maupun di-bake** ke image; `.dockerignore` mengecualikannya.

## 2. Model E5 (sekali saja)

Model di-cache ke volume `tigabe-models`. Unduh awal (opsional, supaya start
cepat):

```bash
docker compose run --rm embed \
  python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')"
```

## 3. Service lain & autentikasi

- MinIO & Qdrant TETAP eksternal (endpoint + kredensial dari `.env`).
- Popup login browser memakai `MCP_PUBLIC_URL`; untuk produksi samakan dengan
  domain publik (mis. `https://epmcp001.aitalent.web.id/mcp`).

## 4. Update setelah perubahan kode

```bash
git pull
docker compose build
docker compose up -d
```

## 5. Keamanan

Image TIDAK memuat `.env`, `roles.json`, `login_users.json`, `audit_log.json`,
`data/`, `models/` (`.dockerignore`). Kredensial hanya lewat `env_file` saat run.