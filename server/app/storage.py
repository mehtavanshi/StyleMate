import os
import uuid
from abc import ABC, abstractmethod

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


class StorageProvider(ABC):
    @abstractmethod
    def save_file(self, file_content: bytes, filename: str, content_type: str) -> str:
        """Save a file and return its URL path."""

    @abstractmethod
    def get_file_url(self, path: str) -> str:
        """Return a full URL for a stored file path."""


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
        return self.get_file_url(f"/uploads/{unique_name}")

    def get_file_url(self, path: str) -> str:
        return path


def get_storage_provider() -> StorageProvider:
    """Factory — swap this for S3/Cloudinary provider as needed."""
    return LocalStorageProvider()
