from io import BytesIO
from datetime import timedelta
from uuid import uuid4

from fastapi import UploadFile
from minio import Minio
from minio.error import S3Error

from app.config import get_settings


def get_s3_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.s3_endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        secure=settings.s3_secure,
    )


def ensure_bucket() -> None:
    settings = get_settings()
    client = get_s3_client()
    if not client.bucket_exists(settings.s3_bucket):
        client.make_bucket(settings.s3_bucket)


async def save_upload(file: UploadFile, claim_id: str) -> tuple[str, str]:
    settings = get_settings()
    ensure_bucket()
    client = get_s3_client()
    content = await file.read()
    object_name = f"{claim_id}/{uuid4()}-{file.filename}"
    client.put_object(
        settings.s3_bucket,
        object_name,
        BytesIO(content),
        length=len(content),
        content_type=file.content_type or "application/octet-stream",
    )
    url = client.presigned_get_object(settings.s3_bucket, object_name, expires=timedelta(days=7))
    return object_name, url


def assert_storage_ready() -> None:
    try:
        ensure_bucket()
    except S3Error as exc:
        raise RuntimeError(f"S3-compatible storage is not reachable or bucket setup failed: {exc}") from exc
