import os
from datetime import timedelta
from dotenv import load_dotenv
from minio import Minio

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

_client = Minio(
    os.environ["MINIO_PUBLIC_ENDPOINT"],   # tanpa https://
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=True,
    region="us-east-1",   # mencegah panggilan jaringan untuk cek region
)

def buat_document_url(object_key: str) -> str:
    return _client.presigned_get_object(
        os.environ["MINIO_BUCKET"],
        object_key,
        expires=timedelta(minutes=int(os.environ.get("PRESIGN_EXPIRY_MINUTES", 30))),
        response_headers={
            "response-content-type": "application/pdf",
            "response-content-disposition": f'inline; filename="{os.path.basename(object_key)}"',
        },
    )

def ambil_objek(object_key: str) -> bytes:
    resp = _client.get_object(os.environ["MINIO_BUCKET"], object_key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def unggah_objek(object_key: str, data: bytes, content_type: str = "application/pdf") -> None:
    import io
    _client.put_object(
        os.environ["MINIO_BUCKET"],
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def ada_objek(object_key: str) -> bool:
    try:
        _client.stat_object(os.environ["MINIO_BUCKET"], object_key)
        return True
    except Exception:
        return False


def hapus_objek(object_key: str) -> bool:
    try:
        _client.remove_object(os.environ["MINIO_BUCKET"], object_key)
        return True
    except Exception:
        return not ada_objek(object_key)
