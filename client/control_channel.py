"""
TCP Control Channel for Hybrid FTP Client.
Handles command sending and reply receiving over TCP.
"""
import socket
import threading
import time


class ControlChannel:
    def __init__(self, host: str, port: int = 21):
        self.host = host
        self.port = port
        self.sock = None
        self.lock = threading.Lock()
        self.connected = False
        self.last_reply = ""
        self._buffer = b""

    def connect(self) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.host, self.port))
            self.connected = True
            self.last_reply = self._recv_reply()
            return True
        except Exception as e:
            print(f"[Control] Connection failed: {e}")
            return False

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.connected = False

    def send_cmd(self, cmd: str) -> str:
        """Send a command and return the server reply."""
        with self.lock:
            if not self.connected:
                return ""
            try:
                self.sock.sendall((cmd + "\r\n").encode("utf-8"))
                self.last_reply = self._recv_reply()
                return self.last_reply
            except Exception as e:
                print(f"[Control] Send error: {e}")
                self.connected = False
                return ""

    def read_reply(self) -> str:
        """Read one pending reply from the server without sending a command.

        Needed because the server sends a completion reply (e.g. '226
        Transfer complete') on the control channel *after* the UDP data
        phase finishes, not as a response to any command the client
        just sent. If nobody reads it, it sits in the socket buffer and
        the next send_cmd() call reads it instead of the real reply to
        that next command -- desyncing every reply for the rest of the
        session by one.
        """
        with self.lock:
            if not self.connected:
                return ""
            try:
                self.last_reply = self._recv_reply()
                return self.last_reply
            except Exception as e:
                print(f"[Control] Read error: {e}")
                self.connected = False
                return ""

    def _recv_reply(self) -> str:
        """Receive multi-line FTP reply."""
        while b"\r\n" not in self._buffer:
            try:
                chunk = self.sock.recv(4096)
            except (socket.timeout, OSError):
                chunk = b""
            if not chunk:
                reply_text = self._buffer.decode("utf-8", errors="replace").strip()
                self._buffer = b""
                return reply_text
            self._buffer += chunk
 
        line, self._buffer = self._buffer.split(b"\r\n", 1)
        return line.decode("utf-8", errors="replace").strip()

    def get_reply_code(self, reply: str) -> str:
        if reply and len(reply) >= 3:
            return reply[:3]
        return ""
