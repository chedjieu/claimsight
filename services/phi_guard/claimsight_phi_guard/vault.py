"""AES-256 (Fernet) vault for PHI at rest. Demo key is not a production KMS."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

PREFIX = "cs1:"
BYTE_PREFIX = b"CS1:"


def _fernet() -> Fernet:
    secret = os.getenv("CLAIMSIGHT_VAULT_KEY", "claimsight-dev-vault-not-for-prod")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal(plaintext: str | None) -> str:
    if not plaintext:
        return ""
    return PREFIX + _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def open_sealed(token: str | None) -> str:
    if not token:
        return ""
    if token.startswith(PREFIX):
        try:
            return _fernet().decrypt(token[len(PREFIX) :].encode("ascii")).decode("utf-8")
        except InvalidToken:
            return ""
    return token


def seal_bytes(body: bytes) -> bytes:
    return BYTE_PREFIX + _fernet().encrypt(body)


def open_bytes(body: bytes) -> bytes:
    if body.startswith(BYTE_PREFIX):
        try:
            return _fernet().decrypt(body[len(BYTE_PREFIX) :])
        except InvalidToken:
            return b""
    return body
