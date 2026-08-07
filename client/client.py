"""
Hybrid FTP Client - Main Entry Point.
Implementation focusing on PORT, TYPE, HASH, and reliable UDP.
"""
import sys
from client.control_channel import ControlChannel
from client.transfer import TransferManager
from client.hash_verify import HashVerifier
from common.protocol import ReplyCode


class HybridFTPClient:
    def __init__(self, server_host: str, server_port: int = 21):
        self.control = ControlChannel(server_host, server_port)
        self.transfer = TransferManager(self.control)
        self.logged_in = False

    def connect(self) -> bool:
        if not self.control.connect():
            return False
        print(f"[Client] Server says: {self.control.last_reply}")
        return True

    def login(self, username: str, password: str) -> bool:
        reply = self.control.send_cmd(f"USER {username}")
        if self.control.get_reply_code(reply) == ReplyCode.USERNAME_OK:
            reply = self.control.send_cmd(f"PASS {password}")
            if self.control.get_reply_code(reply) == ReplyCode.LOGIN_SUCCESS:
                self.logged_in = True
                print("[Client]", reply)
                return True
        print(f"[Client] Login failed: {reply}")
        return False

    def quit(self):
        self.control.send_cmd("QUIT")
        self.control.disconnect()
        print("[Client] Disconnected.")

    def pwd(self) -> str:
        return self.control.send_cmd("PWD")

    def cwd(self, path: str) -> str:
        return self.control.send_cmd(f"CWD {path}")

    def list_dir(self, path: str = "", mode: str = "PORT") -> str:
        return self.transfer.list_dir(path, mode)

    def type_cmd(self, t: str) -> bool:
        """Task #2: Set TYPE A (ASCII) or I (Binary)."""
        return self.transfer.set_type(t)

    def upload(self, local_path: str, remote_name: str = None, mode: str = "PORT") -> bool:
        """Task #3 + #4: Upload with hash check, supports image files."""
        if not self.logged_in:
            print("[Client] Not logged in.")
            return False
        return self.transfer.stor(local_path, remote_name, mode)

    def download(self, remote_name: str, local_path: str, mode: str = "PORT") -> bool:
        """Task #3 + #4: Download with hash check, supports image files."""
        if not self.logged_in:
            print("[Client] Not logged in.")
            return False
        return self.transfer.retr(remote_name, local_path, mode)
