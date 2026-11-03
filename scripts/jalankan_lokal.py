"""Jalankan MCP TigaBe untuk uji lokal dengan env yang benar.

Selalu menyetel MCP_PUBLIC_URL ke origin server yang didengar proses ini, agar
metadata OAuth (issuer/WWW-Authenticate) menunjuk URL yang benar-benar bisa
dibuka browser WorkBuddy. Tanpa ini, server default ke domain publik dan
popup login WorkBuddy tidak muncul.

Pakai:
  python scripts/jalankan_lokal.py            # host 127.0.0.1, port 18105
  python scripts/jalankan_lokal.py --port 19000
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
    ap.add_argument("--port", type=int, default=18105)
    args = ap.parse_args()

    os.environ["MCP_HOST"] = args.host
    os.environ["MCP_PORT"] = str(args.port)
    skema = "https" if args.host not in ("127.0.0.1", "localhost", "::1") else "http"
    os.environ["MCP_PUBLIC_URL"] = f"{skema}://{args.host}:{args.port}/mcp"
    # kunci sesi/cookie login harus konsisten antar restart di mesin yang sama
    os.environ.setdefault("MCP_SESSION_SECRET", "lokal-" + args.host + "-" + str(args.port))

    from server import jalankan   # noqa: E402
    jalankan()


if __name__ == "__main__":
    main()
