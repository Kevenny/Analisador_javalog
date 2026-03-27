import io
import shutil
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from ..config import settings


class StorageService:
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
        self.bucket = settings.minio_bucket

    def ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_file(self, key: str, file_obj, content_type: str, size: int):
        self.client.put_object(
            self.bucket,
            key,
            file_obj,
            length=size,
            content_type=content_type,
        )

    def download_file(self, key: str, dest_path: str):
        response = self.client.get_object(self.bucket, key)
        try:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(response, f)
        finally:
            response.close()
            response.release_conn()

    def delete_file(self, key: str):
        try:
            self.client.remove_object(self.bucket, key)
        except S3Error:
            pass  # ignora se o objeto já não existir

    def get_url(self, key: str) -> str:
        return self.client.presigned_get_object(self.bucket, key)


storage_service = StorageService()
