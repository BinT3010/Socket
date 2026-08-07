"""
Hash Verification Module.
Sang's Task #3: Compute SHA-256 before STOR and after RETR,
compare with server HASH response.
"""
from common.utils import sha256_file, sha256_bytes


class HashVerifier:
    @staticmethod
    def compute_local_hash(filepath: str) -> str:
        """Compute SHA-256 of a local file."""
        return sha256_file(filepath)

    @staticmethod
    def compute_bytes_hash(data: bytes) -> str:
        """Compute SHA-256 of byte data."""
        return sha256_bytes(data)

    @staticmethod
    def verify_transfer(local_hash: str, server_hash: str) -> bool:
        """Compare two hashes and report integrity."""
        return local_hash.lower() == server_hash.lower()

    @staticmethod
    def report(local_hash: str, server_hash: str, operation: str):
        """Print a user-friendly integrity report."""
        match = HashVerifier.verify_transfer(local_hash, server_hash)
        print("=" * 60)
        print(f"  HASH VERIFICATION REPORT - {operation}")
        print("=" * 60)
        print(f"  Local  SHA-256: {local_hash}")
        print(f"  Server SHA-256: {server_hash}")
        print(f"  Status: {'✅ TOÀN VẸN (Integrity OK)' if match else '❌ LỖI (Integrity FAILED)'}")
        print("=" * 60)
        return match
