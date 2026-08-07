"""
Utility functions for Hybrid FTP.
"""
import os
import hashlib


def sha256_file(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hash of byte string."""
    return hashlib.sha256(data).hexdigest()


def file_size(filepath: str) -> int:
    return os.path.getsize(filepath)


def read_file_in_chunks(filepath: str, chunk_size: int = 1024):
    """Generator to read a file in chunks."""
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk
