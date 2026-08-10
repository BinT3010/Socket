"""
File Transfer Logic for STOR and RETR.
Integrates DataChannel, ControlChannel, and HashVerifier.
"""
import os
import time
from client.control_channel import ControlChannel
from client.data_channel import DataChannel
from client.hash_verify import HashVerifier
from common.protocol import ReplyCode, format_port_cmd, parse_pasv_response, DataType
from common.utils import file_size


class TransferManager:
    def __init__(self, control: ControlChannel):
        self.control = control
        self.data = DataChannel()
        self.transfer_type = DataType.BINARY  # Default to binary

    def set_type(self, t: str) -> bool:
        """Set transfer type (A=ASCII, I=Binary)."""
        reply = self.control.send_cmd(f"TYPE {t}")
        if self.control.get_reply_code(reply) == ReplyCode.COMMAND_OK:
            self.transfer_type = t
            print(f"[Transfer] Type set to {'ASCII' if t == 'A' else 'BINARY'}")
            return True
        print(f"[Transfer] TYPE failed: {reply}")
        return False

    def _setup_port_mode(self, local_ip: str) -> bool:
        """Sang's Task #1: Open UDP port, send PORT command to server."""
        port = self.data.open_listener(bind_ip="0.0.0.0", bind_port=0)
        port_cmd = f"PORT {format_port_cmd(local_ip, port)}"
        reply = self.control.send_cmd(port_cmd)
        if self.control.get_reply_code(reply) in (ReplyCode.COMMAND_OK, ReplyCode.OPENING_DATA):
            # Server embeds its own data-channel address in this reply
            # (see cmd_port) so we know where to send STOR bytes -- in
            # active mode the server opens a fresh random UDP port we
            # have no other way to learn.
            srv_ip, srv_port = parse_pasv_response(reply)
            if srv_ip and srv_port:
                self.data.set_send_target(srv_ip, srv_port)
            print(f"[Transfer] PORT mode active on {local_ip}:{port}")
            return True
        print(f"[Transfer] PORT command failed: {reply}")
        self.data.close()
        return False

    def _setup_pasv_mode(self) -> bool:
        """Passive mode: ask server for IP+port, connect UDP."""
        reply = self.control.send_cmd("PASV")
        if self.control.get_reply_code(reply) == ReplyCode.ENTERING_PASV:
            ip, port = parse_pasv_response(reply)
            if ip and port:
                self.data.open_listener(bind_ip="0.0.0.0", bind_port=0)
                self.data.connect_to(ip, port)
                print(f"[Transfer] PASV mode connected to {ip}:{port}")
                return True
        print(f"[Transfer] PASV command failed: {reply}")
        return False

    def stor(self, local_path: str, remote_name: str = None, mode: str = "PORT") -> bool:
        """Upload a file to server with hash verification."""
        if not os.path.exists(local_path):
            print(f"[Transfer] File not found: {local_path}")
            return False

        remote_name = remote_name or os.path.basename(local_path)

        # Sang's Task #3: Compute local hash BEFORE transfer
        local_hash = HashVerifier.compute_local_hash(local_path)
        print(f"[Hash] Pre-transfer SHA-256: {local_hash}")

        # Setup data connection
        if mode == "PORT":
            if not self._setup_port_mode(self._get_local_ip()):
                return False
        else:
            if not self._setup_pasv_mode():
                return False

        # Send STOR command
        reply = self.control.send_cmd(f"STOR {remote_name}")
        if self.control.get_reply_code(reply) not in (ReplyCode.OPENING_DATA, ReplyCode.ACTION_OK):
            print(f"[Transfer] STOR rejected: {reply}")
            self.data.close()
            return False

        # Read and send file
        print(f"[Transfer] Uploading {local_path} -> {remote_name}")
        start = time.time()
        with open(local_path, "rb") as f:
            file_data = f.read()
        success = self.data.send_reliable(file_data)
        elapsed = time.time() - start
        self.data.close()

        if not success:
            print("[Transfer] Upload failed (data channel error).")
            return False

        # The server sends its completion reply (226 Transfer complete)
        # on the control channel only after the UDP transfer finishes,
        # not as a direct response to STOR -- read it now or it desyncs
        # every reply after this one.
        completion_reply = self.control.read_reply()
        print(f"[Transfer] Upload complete in {elapsed:.2f}s ({completion_reply})")

        # Sang's Task #3: Request server hash and verify
        reply = self.control.send_cmd(f"HASH {remote_name}")
        if reply.startswith("2"):
            server_hash = reply.split()[-1].strip()
            HashVerifier.report(local_hash, server_hash, "UPLOAD (STOR)")
        else:
            print(f"[Hash] Server did not return hash: {reply}")

        return True

    def list_dir(self, path: str = "", mode: str = "PORT") -> str:
        """List remote directory contents via the data channel.
 
        Same shape as retr(): the server sends the listing bytes to us
        over the data connection, so this follows the same
        setup -> send cmd -> recv -> close -> drain-completion-reply
        sequence, just returning a decoded string instead of writing
        a file to disk.
        """
        # Setup data connection
        if mode == "PORT":
            if not self._setup_port_mode(self._get_local_ip()):
                return ""
        else:
            if not self._setup_pasv_mode():
                return ""
 
        # Send LIST command
        reply = self.control.send_cmd(f"LIST {path}".strip())
        if self.control.get_reply_code(reply) not in (ReplyCode.OPENING_DATA, ReplyCode.ACTION_OK):
            print(f"[Transfer] LIST rejected: {reply}")
            self.data.close()
            return ""
 
        # Receive the listing (server -> client, same direction as RETR)
        listing_bytes = self.data.recv_reliable()
        self.data.close()
 
        # Same reason as in stor()/retr(): drain the server's
        # post-transfer completion reply before issuing the next
        # control command, or it desyncs subsequent replies.
        completion_reply = self.control.read_reply()
        print(f"[Transfer] LIST complete ({completion_reply})")
 
        if not listing_bytes:
            return ""
        return listing_bytes.decode("utf-8", errors="replace")
    
    def retr(self, remote_name: str, local_path: str, mode: str = "PORT") -> bool:
        """Download a file from server with hash verification."""
        # Setup data connection
        if mode == "PORT":
            if not self._setup_port_mode(self._get_local_ip()):
                return False
        else:
            if not self._setup_pasv_mode():
                return False

        # Send RETR command
        reply = self.control.send_cmd(f"RETR {remote_name}")
        if self.control.get_reply_code(reply) not in (ReplyCode.OPENING_DATA, ReplyCode.ACTION_OK):
            print(f"[Transfer] RETR rejected: {reply}")
            self.data.close()
            return False

        # Receive file
        print(f"[Transfer] Downloading {remote_name} -> {local_path}")
        start = time.time()
        file_data = self.data.recv_reliable()
        elapsed = time.time() - start
        self.data.close()

        # Same reason as in stor(): drain the server's post-transfer
        # completion reply before issuing the next control command.
        completion_reply = self.control.read_reply()

        with open(local_path, "wb") as f:
            f.write(file_data)
        print(f"[Transfer] Download complete in {elapsed:.2f}s ({len(file_data)} bytes) ({completion_reply})")

        # Sang's Task #3: Compute local hash AFTER transfer and compare
        local_hash = HashVerifier.compute_local_hash(local_path)
        print(f"[Hash] Post-transfer SHA-256: {local_hash}")

        reply = self.control.send_cmd(f"HASH {remote_name}")
        if reply.startswith("2"):
            server_hash = reply.split()[-1].strip()
            HashVerifier.report(local_hash, server_hash, "DOWNLOAD (RETR)")
        else:
            print(f"[Hash] Server did not return hash: {reply}")

        return True

    def _get_local_ip(self) -> str:
        """Get local IP for PORT command."""
        import socket as sk
        s = sk.socket(sk.AF_INET, sk.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip
