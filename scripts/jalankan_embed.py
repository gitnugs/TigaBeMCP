"""Jalankan embed service lokal (model E5). Model dimuat saat start, jadi
panggilan pertama cepat.

Pakai:
  python scripts/jalankan_embed.py            # host 127.0.0.1, port 18110
  python scripts/jalankan_embed.py --port 18111
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=18110)
    args = ap.parse_args()

    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    import uvicorn
    import embed_service

    uvicorn.run(embed_service.app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
