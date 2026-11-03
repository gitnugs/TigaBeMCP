import os
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DIM = 384
_URL = os.environ.get("EMBED_URL", "http://127.0.0.1:18110")
_HEAD = {"Authorization": f"Bearer {os.environ['EMBED_TOKEN']}"} if os.environ.get("EMBED_TOKEN") else {}
_http = httpx.Client(base_url=_URL, headers=_HEAD, timeout=60)


def embed_passages(texts: list[str]) -> list[list[float]]:
    r = _http.post("/embed/passages", json={"texts": texts})
    r.raise_for_status()
    return r.json()["vectors"]


def embed_query(text: str) -> list[float]:
    r = _http.post("/embed/query", json={"texts": [text]})
    r.raise_for_status()
    return r.json()["vector"]
