import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-small"
DIM = 384

# Model di-bake ke image memakai `cache_folder` (layout datar:
# <dir>/models--intfloat--multilingual-e5-small) lalu entrypoint menyalinnya ke
# HF_HOME. Tanpa cache_folder eksplisit, transformers mencari di HF_HOME/hub
# sehingga tidak menemukan model -> coba unduh -> gagal saat offline.
_CACHE = (
    os.environ.get("MODEL_CACHE_DIR")
    or os.environ.get("HF_HOME")
    or None
)

_model = None

def _get_model():
    global _model
    if _model is None:               # dimuat sekali, bukan setiap permintaan
        kwargs = {"device": "cpu"}
        if _CACHE:
            kwargs["cache_folder"] = _CACHE
        _model = SentenceTransformer(MODEL_NAME, **kwargs)
    return _model

def embed_passages(texts: list[str]) -> list[list[float]]:
    # E5 mewajibkan awalan "passage: " untuk isi dokumen
    return _get_model().encode(
        [f"passage: {t}" for t in texts],
        normalize_embeddings=True, batch_size=16,
    ).tolist()

def embed_query(text: str) -> list[float]:
    # dan "query: " untuk pertanyaan pengguna
    return _get_model().encode(
        f"query: {text}", normalize_embeddings=True
    ).tolist()
