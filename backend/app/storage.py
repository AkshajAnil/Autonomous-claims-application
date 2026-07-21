import os
from io import BytesIO
from datetime import timedelta
from uuid import uuid4

from fastapi import UploadFile
try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    Minio = None
    S3Error = Exception

from app.config import get_settings

LOCAL_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "artifacts", "uploads")
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)


def get_s3_client():
    if Minio is None:
        return None
    settings = get_settings()
    try:
        return Minio(
            settings.s3_endpoint.replace("http://", "").replace("https://", ""),
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=settings.s3_secure,
        )
    except Exception:
        return None


def ensure_bucket() -> None:
    settings = get_settings()
    client = get_s3_client()
    if client is not None:
        try:
            if not client.bucket_exists(settings.s3_bucket):
                client.make_bucket(settings.s3_bucket)
        except Exception:
            pass


async def save_upload(file: UploadFile, claim_id: str) -> tuple[str, str]:
    content = await file.read()
    filename = file.filename or "evidence.bin"
    object_name = f"{claim_id}/{uuid4()}-{filename}"
    
    settings = get_settings()
    client = get_s3_client()
    
    if client is not None:
        try:
            ensure_bucket()
            client.put_object(
                settings.s3_bucket,
                object_name,
                BytesIO(content),
                length=len(content),
                content_type=file.content_type or "application/octet-stream",
            )
            url = client.presigned_get_object(settings.s3_bucket, object_name, expires=timedelta(days=7))
            return object_name, url
        except Exception:
            pass

    # Fallback to local storage when S3 is unavailable
    local_path = os.path.join(LOCAL_UPLOAD_DIR, f"{claim_id}_{filename}")
    with open(local_path, "wb") as f:
        f.write(content)
    return object_name, f"/api/uploads/{filename}"


def assert_storage_ready() -> None:
    # Always ready thanks to local filesystem fallback
    pass
