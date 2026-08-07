"""
UDP Data Channel - adapter over Tan's RDT module (project-root rdt.py).

This keeps the same public interface Sang's transfer.py already calls
(open_listener / connect_to / close / send_reliable / recv_reliable),
plus one new method (set_send_target, used only by PORT/active mode),
but the actual bytes-on-the-wire are produced by Tan's RDT class so the
client speaks the same protocol Dung's server understands.
"""
import sys
import os

# project root (two levels up from client/) must be importable so
# "import rdt" (Tan's module) resolves, same way server_final.py does.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from rdt import RDT  # Tan's Reliable Data Transfer module


class DataChannel:
    def __init__(self):
        self.rdt = None
        self.local_addr = None
        self.send_addr = None    # where send_reliable() sends to
        self._need_hello = False  # True only for PASV: server doesn't
                                   # know our address yet, so
                                   # recv_reliable() must announce it
                                   # with one packet before the real
                                   # transfer starts.

    def open_listener(self, bind_ip="0.0.0.0", bind_port=0) -> int:
        """Open a UDP socket (via RDT) and return the assigned port (for PORT command)."""
        self.rdt = RDT(local_ip=bind_ip, local_port=bind_port)
        self.local_addr = self.rdt.sock.getsockname()
        self.send_addr = None
        self._need_hello = False
        return self.local_addr[1]

    def connect_to(self, ip: str, port: int):
        """PASV mode: server told us its data address in the 227 reply.
        It doesn't know ours, so recv_reliable() must say hello first."""
        self.send_addr = (ip, port)
        self._need_hello = True

    def set_send_target(self, ip: str, port: int):
        """PORT/active mode: server disclosed the data port it wants
        STOR bytes sent to (see cmd_port on the server). The server
        already knows our address from the PORT command itself, so no
        hello packet is needed before recv_reliable()."""
        self.send_addr = (ip, port)
        self._need_hello = False

    def close(self):
        if self.rdt:
            self.rdt.close()
        self.rdt = None

    # ------------------------------------------------------------------
    def send_reliable(self, data: bytes) -> bool:
        """Send all data reliably using Tan's Stop-and-Wait RDT."""
        if self.send_addr is None:
            print("[DataChannel] No send target set.")
            return False
        chunk_size = 1024
        for i in range(0, len(data), chunk_size):
            self.rdt.send(data[i:i + chunk_size], self.send_addr)
        # empty packet marks EOF, matching rdt.receive_file_reliable()
        self.rdt.send(b"", self.send_addr)
        return True

    def recv_reliable(self) -> bytes:
        """Receive all data reliably using Tan's Stop-and-Wait RDT."""
        if self._need_hello:
            self.rdt.send(b"", self.send_addr)

        buffer = bytearray()
        while True:
            data, addr = self.rdt.recv()
            if data == b"":
                break
            buffer.extend(data)
        return bytes(buffer)
