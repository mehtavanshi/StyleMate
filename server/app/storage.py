import os
import uuid
from abc import ABC, abstractmethod

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


class StorageProvider(ABC):
    @abstractmethod
    def save_file(self, file_content: bytes, filename: str, content_type: str) -> str:
        """Save a file and return its storage key/path."""

    @abstractmethod
    def delete_file(self, path: str) -> None:
        """Delete a file from storage by its key/path."""

    @abstractmethod
    def read_file(self, path: str) -> bytes:
        """Read file bytes from storage by its key/path."""

    @abstractmethod
    def get_file_url(self, path: str) -> str:
        """Return a permanent URL for a stored file path (internal use)."""

    @abstractmethod
    def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """Return a signed, expiring URL for client access."""


class LocalStorageProvider(StorageProvider):
    def __init__(self, upload_dir: str = UPLOAD_DIR):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    def save_file(self, file_content: bytes, filename: str, content_type: str) -> str:
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join(self.upload_dir, unique_name)
        with open(file_path, "wb") as f:
            f.write(file_content)
        return f"/uploads/{unique_name}"

    def delete_file(self, path: str) -> None:
        if not path:
            return
        relative = path.lstrip("/")
        file_path = os.path.join(self.upload_dir, os.path.basename(relative))
        if os.path.exists(file_path):
            os.remove(file_path)

    def read_file(self, path: str) -> bytes:
        relative = path.lstrip("/")
        file_path = os.path.join(self.upload_dir, os.path.basename(relative))
        with open(file_path, "rb") as f:
            return f.read()

    def get_file_url(self, path: str) -> str:
        return path

    def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        return path


class S3StorageProvider(StorageProvider):
    def __init__(self):
        import boto3

        self.bucket = os.getenv("S3_BUCKET", "stylemate-photos")
        self.region = os.getenv("S3_REGION", "us-east-1")
        self.client = boto3.client(
            "s3",
            region_name=self.region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

    def save_file(self, file_content: bytes, filename: str, content_type: str) -> str:
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        key = f"photos/{uuid.uuid4().hex}.{ext}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_content,
            ContentType=content_type,
        )
        return key

    def delete_file(self, path: str) -> None:
        if not path:
            return
        self.client.delete_object(Bucket=self.bucket, Key=path)

    def read_file(self, path: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=path)
        return response["Body"].read()

    def get_file_url(self, path: str) -> str:
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{path}"

    def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": path},
            ExpiresIn=expires_in,
        )


class GCSStorageProvider(StorageProvider):
    def __init__(self):
        from google.cloud import storage

        self.bucket_name = os.getenv("GCS_BUCKET", "stylemate-photos")
        self.client = storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)

    def save_file(self, file_content: bytes, filename: str, content_type: str) -> str:
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        key = f"photos/{uuid.uuid4().hex}.{ext}"
        blob = self.bucket.blob(key)
        blob.upload_from_string(file_content, content_type=content_type)
        return key

    def delete_file(self, path: str) -> None:
        if not path:
            return
        blob = self.bucket.blob(path)
        if blob.exists():
            blob.delete()

    def read_file(self, path: str) -> bytes:
        blob = self.bucket.blob(path)
        return blob.download_as_bytes()

    def get_file_url(self, path: str) -> str:
        return f"https://storage.googleapis.com/{self.bucket_name}/{path}"

    def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        from datetime import datetime, timedelta, timezone

        blob = self.bucket.blob(path)
        return blob.generate_signed_url(
            expiration=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            method="GET",
        )


class SupabaseStorageProvider(StorageProvider):
    def __init__(self):
        from supabase import create_client

        self.url = os.environ["SUPABASE_URL"]
        self.key = os.environ["SUPABASE_SERVICE_KEY"]
        self.bucket = os.environ.get("SUPABASE_BUCKET", "uploads")
        self.client = create_client(self.url, self.key)

    def _key(self, path: str) -> str:
        prefix = f"{self.url}/storage/v1/object/public/{self.bucket}/"
        return path[len(prefix):] if path.startswith(prefix) else path

    def _public_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.url}/storage/v1/object/public/{self.bucket}/{path}"

    def save_file(self, file_content: bytes, filename: str, content_type: str) -> str:
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        path = f"photos/{uuid.uuid4().hex}.{ext}"
        self.client.storage.from_(self.bucket).upload(
            path, file_content, {"content-type": content_type}
        )
        return path

    def delete_file(self, path: str) -> None:
        if not path:
            return
        self.client.storage.from_(self.bucket).remove([self._key(path)])

    def read_file(self, path: str) -> bytes:
        return self.client.storage.from_(self.bucket).download(self._key(path))

    def get_file_url(self, path: str) -> str:
        return self._public_url(path)

    def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        return self._public_url(path)


def get_storage_provider() -> StorageProvider:
    provider = os.getenv("STORAGE_PROVIDER", "local").lower()
    if provider == "supabase":
        return SupabaseStorageProvider()
    if provider == "s3":
        return S3StorageProvider()
    if provider == "gcs":
        return GCSStorageProvider()
    return LocalStorageProvider()
