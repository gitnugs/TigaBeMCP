"""Buat pengguna login untuk OAuth TigaBe MCP (login_users.json).

Contoh:
  python scripts/buat_user.py --username budi --peran siswa --password "..."
  python scripts/buat_user.py --username guru1 --peran guru --password "..." --nama "Bu Sari"

Password di-hash scrypt; file login_users.json hanya menyimpan hash.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auth import PERAN_BAWAAN   # noqa: E402
from oauth_provider import hash_password   # noqa: E402

FILE = Path(os.environ.get("MCP_LOGIN_USERS", "")
            or Path(__file__).resolve().parent.parent / "login_users.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--username", required=True)
    ap.add_argument("--peran", required=True, choices=sorted(PERAN_BAWAAN))
    ap.add_argument("--password", required=True)
    ap.add_argument("--nama", default=None, help="nama lengkap (label)")
    ap.add_argument("--file", default=str(FILE))
    args = ap.parse_args()

    path = Path(args.file)
    data = {"users": []}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("users", [])

    data["users"] = [u for u in data["users"] if u.get("username") != args.username]
    data["users"].append({
        "username": args.username,
        "peran": args.peran,
        "label": args.nama or args.username,
        "password_hash": hash_password(args.password),
    })

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    print(f"OK: '{args.username}' peran '{args.peran}' tersimpan di {path}")


if __name__ == "__main__":
    main()
