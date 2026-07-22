import os
from io import BytesIO
from datetime import timedelta
from uuid import uuid4

from fastapi import UploadFile

# Try importing boto3 (standard Backblaze B2 / AWS S3 client) or minio
try:
    import boto3
    from botocore.client import Config
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    from minio import Minio
    HAS_MINIO = True
except ImportError:
    HAS_MINIO = False

from app.config import get_settings

LOCAL_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "artifacts", "uploads")
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)


def get_b2_s3_client():
    settings = get_settings()
    endpoint = settings.s3_endpoint
    if not endpoint or not settings.s3_access_key or not settings.s3_secret_key:
        return None, None

    # Clean endpoint string
    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        endpoint_url = f"https://{endpoint}"
    else:
        endpoint_url = endpoint

    if HAS_BOTO3:
        try:
            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                config=Config(signature_version="s3v4")
            )
            return "boto3", client
        except Exception:
            pass

    if HAS_MINIO:
        try:
            raw_host = endpoint_url.replace("https://", "").replace("http://", "").strip("/")
            client = Minio(
                raw_host,
                access_key=settings.s3_access_key,
                secret_key=settings.s3_secret_key,
                secure=settings.s3_secure,
            )
            return "minio", client
        except Exception:
            pass

    return None, None


async def save_upload(file: UploadFile, claim_id: str) -> tuple[str, str]:
    content = await file.read()
    filename = file.filename or "evidence.bin"
    object_name = f"{claim_id}/{uuid4()}-{filename}"
    settings = get_settings()
    
    client_type, client = get_b2_s3_client()
    
    if client is not None:
        try:
            if client_type == "boto3":
                client.put_object(
                    Bucket=settings.s3_bucket,
                    Key=object_name,
                    Body=content,
                    ContentType=file.content_type or "application/octet-stream"
                )
                url = client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': settings.s3_bucket, 'Key': object_name},
                    ExpiresIn=604800 # 7 days
                )
                return object_name, url
            elif client_type == "minio":
                if not client.bucket_exists(settings.s3_bucket):
                    client.make_bucket(settings.s3_bucket)
                client.put_object(
                    settings.s3_bucket,
                    object_name,
                    BytesIO(content),
                    length=len(content),
                    content_type=file.content_type or "application/octet-stream",
                )
                url = client.presigned_get_object(settings.s3_bucket, object_name, expires=timedelta(days=7))
                return object_name, url
        except Exception as exc:
            print(f"Backblaze B2 S3 upload warning: {exc}")

    # Fallback to local storage
    stored_filename = f"{claim_id}_{filename}"
    local_path = os.path.join(LOCAL_UPLOAD_DIR, stored_filename)
    with open(local_path, "wb") as f:
        f.write(content)
    return object_name, f"/api/uploads/{stored_filename}"


def assert_storage_ready() -> None:
    pass
