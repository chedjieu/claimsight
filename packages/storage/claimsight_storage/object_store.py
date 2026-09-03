"""S3-compatible object storage. MinIO locally, Amazon S3 later, GCS via S3-compat or native adapter."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from claimsight_phi_guard.vault import open_bytes, seal_bytes

log = logging.getLogger(__name__)


class ObjectStore:
    """Put/get claim documents. Falls back to local disk if boto is unconfigured.

    Bodies are Fernet-sealed before write so disk/MinIO do not store plaintext PHI.
    """

    def __init__(self) -> None:
        self.bucket = os.getenv("S3_BUCKET", "claimsight-docs")
        self.endpoint = os.getenv("S3_ENDPOINT_URL") or None
        self.region = os.getenv("S3_REGION", "us-east-1")
        self.access = os.getenv("S3_ACCESS_KEY", "")
        self.secret = os.getenv("S3_SECRET_KEY", "")
        self._fallback = Path(os.getenv("CLAIMSIGHT_DOC_DIR", "./data/docs"))
        self._fallback.mkdir(parents=True, exist_ok=True)
        self.kind = "disk"
        self._client = None
        if self.access and self.secret:
            try:
                import boto3
                from botocore.config import Config

                kwargs: dict = {
                    "aws_access_key_id": self.access,
                    "aws_secret_access_key": self.secret,
                    "region_name": self.region,
                    "config": Config(signature_version="s3v4"),
                }
                if self.endpoint:
                    kwargs["endpoint_url"] = self.endpoint
                self._client = boto3.client("s3", **kwargs)
                self.kind = "s3"
            except Exception as exc:  # noqa: BLE001
                log.warning("S3 client unavailable, using disk: %s", exc)

    def put_bytes(self, key: str, body: bytes, content_type: str = "text/plain") -> str:
        sealed = seal_bytes(body)
        if self._client is not None:
            try:
                self._client.put_object(
                    Bucket=self.bucket, Key=key, Body=sealed, ContentType=content_type
                )
                return f"s3://{self.bucket}/{key}"
            except Exception as exc:  # noqa: BLE001
                log.warning("S3 put failed, disk fallback: %s", exc)
        path = self._fallback / key.replace("/", "_")
        path.write_bytes(sealed)
        return str(path)

    def get_bytes(self, key: str) -> bytes:
        raw = b""
        if self._client is not None:
            try:
                obj = self._client.get_object(Bucket=self.bucket, Key=key)
                raw = obj["Body"].read()
            except Exception as exc:  # noqa: BLE001
                log.debug("S3 get failed: %s", exc)
        if not raw:
            path = self._fallback / key.replace("/", "_")
            raw = path.read_bytes() if path.exists() else b""
        return open_bytes(raw) if raw else b""

    def delete_prefix(self, prefix: str) -> None:
        if self._client is not None:
            try:
                listed = self._client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
                for obj in listed.get("Contents") or []:
                    self._client.delete_object(Bucket=self.bucket, Key=obj["Key"])
            except Exception as exc:  # noqa: BLE001
                log.debug("S3 delete skipped: %s", exc)
        for path in self._fallback.glob(prefix.replace("/", "_") + "*"):
            path.unlink(missing_ok=True)
