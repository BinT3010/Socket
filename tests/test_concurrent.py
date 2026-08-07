"""
Concurrent Client Test - Sang's Task #5.
Tạo nhiều client kết nối đồng thờii để test server multi-threaded.
Mỗi client upload một file khác nhau, sau đó download lại và verify hash.
"""
import os
import sys
import threading
import time

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from client.client import HybridFTPClient
from common.utils import sha256_file

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 2121
NUM_CLIENTS = 5
TEST_DIR = os.path.dirname(__file__)


def client_worker(client_id: int):
    """Một worker client thực hiện upload + download + hash verify."""
    local_file = os.path.join(TEST_DIR, "test_image.png")
    remote_name = f"client{client_id}_image.png"
    download_path = os.path.join(TEST_DIR, f"downloaded_{client_id}.png")

    print(f"[Client-{client_id}] Starting...")
    client = HybridFTPClient(SERVER_HOST, SERVER_PORT)

    if not client.connect():
        print(f"[Client-{client_id}] ❌ Connection failed.")
        return

    if not client.login(f"sang{client_id}", "pass"):
        print(f"[Client-{client_id}] ❌ Login failed.")
        return

    # Set binary mode
    client.type_cmd("I")

    # Upload
    print(f"[Client-{client_id}] Uploading {remote_name}...")
    t0 = time.time()
    ok = client.upload(local_file, remote_name, mode="PORT")
    t1 = time.time()
    if ok:
        print(f"[Client-{client_id}] ✅ Upload done in {t1-t0:.2f}s")
    else:
        print(f"[Client-{client_id}] ❌ Upload failed.")
        client.quit()
        return

    # Download
    print(f"[Client-{client_id}] Downloading {remote_name}...")
    t0 = time.time()
    ok = client.download(remote_name, download_path, mode="PORT")
    t1 = time.time()
    if ok:
        print(f"[Client-{client_id}] ✅ Download done in {t1-t0:.2f}s")
    else:
        print(f"[Client-{client_id}] ❌ Download failed.")

    # Final local verification
    orig_hash = sha256_file(local_file)
    down_hash = sha256_file(download_path)
    if orig_hash == down_hash:
        print(f"[Client-{client_id}] ✅ End-to-end hash match!")
    else:
        print(f"[Client-{client_id}] ❌ Hash mismatch!")

    client.quit()
    print(f"[Client-{client_id}] Finished.")


def main():
    print("=" * 60)
    print("  CONCURRENT CLIENT TEST - Sang's Task #5")
    print(f"  Server: {SERVER_HOST}:{SERVER_PORT}")
    print(f"  Clients: {NUM_CLIENTS}")
    print("=" * 60)

    threads = []
    for i in range(NUM_CLIENTS):
        t = threading.Thread(target=client_worker, args=(i,))
        threads.append(t)

    start = time.time()
    for t in threads:
        t.start()
        time.sleep(0.1)  # Stagger slightly

    for t in threads:
        t.join()

    elapsed = time.time() - start
    print("=" * 60)
    print(f"  All {NUM_CLIENTS} clients completed in {elapsed:.2f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
