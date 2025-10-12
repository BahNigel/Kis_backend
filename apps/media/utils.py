# media/utils.py
import hashlib
from typing import Dict

def make_canonical_checksum(stream_bytes: bytes) -> str:
    """
    Deterministic checksum for a media asset (SHA256).
    """
    return hashlib.sha256(stream_bytes).hexdigest()

def build_s3_key(user_id: str, filename: str, uuid_str: str) -> str:
    return f"user_{user_id}/{uuid_str}/{filename}"
