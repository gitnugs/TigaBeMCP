import os, threading
os.environ.setdefault("HF_HUB_OFFLINE", "1")
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import embedding_lokal as lokal          # model dimuat saat service start

TOKEN = os.environ.get("EMBED_TOKEN")    # opsional, tapi disarankan
lock = threading.Lock()                  # satu inferensi pada satu waktu
app = FastAPI(title="TigaBe Embedding")


class Teks(BaseModel):
    texts: list[str]


def cek(auth):
    if TOKEN and auth != f"Bearer {TOKEN}":
        raise HTTPException(401, "token salah")


@app.get("/health")
def health():
    return {"model": lokal.MODEL_NAME, "dim": lokal.DIM}


@app.post("/embed/passages")
def passages(body: Teks, authorization: str | None = Header(None)):
    cek(authorization)
    if not body.texts or len(body.texts) > 64:
        raise HTTPException(400, "texts harus 1-64 item")
    with lock:
        return {"vectors": lokal.embed_passages(body.texts)}


@app.post("/embed/query")
def query(body: Teks, authorization: str | None = Header(None)):
    cek(authorization)
    if len(body.texts) != 1:
        raise HTTPException(400, "kirim tepat 1 teks")
    with lock:
        return {"vector": lokal.embed_query(body.texts[0])}
