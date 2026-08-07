"""
Server - Final Week
Member: Dung (Server & TCP Control Channel)

Builds on server_week3_tan.py. Adds:
  - cmd_type: handle TYPE A/I
  - cmd_port: Active mode (client tells server its address; server
    already knows client_addr, so RETR/LIST skip the recv()-first
    handshake needed in Passive mode)
  - cmd_hash: SHA-256 integrity check for a file
  - RETR/LIST/NLST now branch on session.data_mode ("PASV" or "PORT")
"""

import socket
import threading
import os
import time
import hashlib
from rdt import RDT

REPLIES = {
    "READY": (220, "Service ready for new user."),
    "USER_OK": (331, "Username OK, need password."),
    "LOGIN_OK": (230, "Login successful."),
    "LOGIN_FAIL": (530, "Not logged in."),
    "GOODBYE": (221, "Goodbye."),
    "CMD_OK": (200, "Command OK."),
    "NOT_LOGGED_IN": (530, "Please login with USER and PASS."),
    "SYNTAX_ERR": (500, "Syntax error, command unrecognized."),
    "PATH_OK": (250, "Requested file action OK."),
    "PATH_FAIL": (550, "File or directory unavailable."),
    "UNKNOWN_CMD": (502, "Command not implemented."),
    "RMD_OK": (250, "Directory removed."),
    "DELE_OK": (250, "File deleted."),
    "RNFR_OK": (350, "Ready for RNTO."),
    "RNTO_OK": (250, "Rename successful."),
    "NEED_RNFR": (503, "Bad sequence of commands, use RNFR first."),
    "DATA_OPEN": (150, "Opening data connection."),
    "TRANSFER_OK": (226, "Transfer complete."),
    "NO_DATA_CONN": (425, "Use PASV or PORT first."),
}

def reply(sock, key):
    code, msg = REPLIES[key]
    sock.sendall(f"{code} {msg}\r\n".encode())


class Session:
    def __init__(self, conn, addr, root_dir):
        self.conn = conn
        self.addr = addr
        self.root_dir = os.path.abspath(root_dir)
        self.cwd = "/"
        self.username = None
        self.authenticated = False
        self.transfer_type = "A"
        self.rename_from = None
        self.rdt = None
        self.data_mode = None            # "PASV" or "PORT"
        self.client_data_addr = None     # (ip, port) -- only set when data_mode == "PORT"


def resolve_safe_path(session, user_path):
    """Return the safe absolute path, or None if the client tried to escape the root."""
    candidate = os.path.normpath(os.path.join(session.root_dir, session.cwd.lstrip("/"), user_path))
    candidate = os.path.abspath(candidate)
    if os.path.commonpath([candidate, session.root_dir]) != session.root_dir:
        return None
    return candidate

def _close_data_channel(session):
    if session.rdt is not None:
        session.rdt.close()
    session.rdt = None
    session.data_mode = None
    session.client_data_addr = None


def cmd_user(session, args):
    session.username = args[0] if args else None
    reply(session.conn, "USER_OK")

def cmd_pass(session, args):
    session.authenticated = True
    reply(session.conn, "LOGIN_OK")

def cmd_pwd(session, args):
    session.conn.sendall(f'257 "{session.cwd}" is current directory.\r\n'.encode())

def cmd_quit(session, args):
    reply(session.conn, "GOODBYE")
    _close_data_channel(session)
    session.conn.close()
    return "CLOSE"

def cmd_noop(session, args):
    reply(session.conn, "CMD_OK")

def cmd_cwd(session, args):
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    new_path = resolve_safe_path(session, args[0])
    if new_path is None or not os.path.isdir(new_path):
        reply(session.conn, "PATH_FAIL")
        return
    rel = os.path.relpath(new_path, session.root_dir).replace("\\", "/")
    session.cwd = "/" + rel if rel != "." else "/"
    reply(session.conn, "PATH_OK")

def cmd_cdup(session, args):
    cmd_cwd(session, [".."])

def cmd_mkd(session, args):
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    new_path = resolve_safe_path(session, args[0])
    if new_path is None:
        reply(session.conn, "PATH_FAIL")
        return
    try:
        os.makedirs(new_path, exist_ok=False)
        session.conn.sendall(f'257 "{args[0]}" directory created.\r\n'.encode())
    except FileExistsError:
        reply(session.conn, "PATH_FAIL")

def cmd_rmd(session, args):
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    target = resolve_safe_path(session, args[0])
    if target is None or not os.path.isdir(target):
        reply(session.conn, "PATH_FAIL")
        return
    try:
        os.rmdir(target)
        reply(session.conn, "RMD_OK")
    except OSError:
        reply(session.conn, "PATH_FAIL")

def cmd_dele(session, args):
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    target = resolve_safe_path(session, args[0])
    if target is None or not os.path.isfile(target):
        reply(session.conn, "PATH_FAIL")
        return
    os.remove(target)
    reply(session.conn, "DELE_OK")

def cmd_rnfr(session, args):
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    target = resolve_safe_path(session, args[0])
    if target is None or not os.path.exists(target):
        reply(session.conn, "PATH_FAIL")
        return
    session.rename_from = target
    reply(session.conn, "RNFR_OK")

def cmd_rnto(session, args):
    if session.rename_from is None:
        reply(session.conn, "NEED_RNFR")
        return
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    new_target = resolve_safe_path(session, args[0])
    if new_target is None:
        reply(session.conn, "PATH_FAIL")
        return
    os.rename(session.rename_from, new_target)
    session.rename_from = None
    reply(session.conn, "RNTO_OK")

def cmd_size(session, args):
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    target = resolve_safe_path(session, args[0])
    if target is None or not os.path.isfile(target):
        reply(session.conn, "PATH_FAIL")
        return
    size = os.path.getsize(target)
    session.conn.sendall(f"213 {size}\r\n".encode())

def cmd_mdtm(session, args):
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    target = resolve_safe_path(session, args[0])
    if target is None or not os.path.isfile(target):
        reply(session.conn, "PATH_FAIL")
        return
    mtime_str = time.strftime("%Y%m%d%H%M%S", time.localtime(os.path.getmtime(target)))
    session.conn.sendall(f"213 {mtime_str}\r\n".encode())

def cmd_stat(session, args):
    session.conn.sendall(f"211 Server status: cwd={session.cwd}\r\n".encode())


# ---------------------------------------------------------------------
# NEW -- TYPE command
# ---------------------------------------------------------------------
def cmd_type(session, args):
    if not args or args[0].upper() not in ("A", "I"):
        reply(session.conn, "SYNTAX_ERR")
        return
    session.transfer_type = args[0].upper()
    session.conn.sendall(f"200 Type set to {session.transfer_type}.\r\n".encode())


# ---------------------------------------------------------------------
# NEW -- HASH command: SHA-256 integrity check
# ---------------------------------------------------------------------
def cmd_hash(session, args):
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    target = resolve_safe_path(session, args[0])
    if target is None or not os.path.isfile(target):
        reply(session.conn, "PATH_FAIL")
        return
    sha256 = hashlib.sha256()
    with open(target, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha256.update(chunk)
    session.conn.sendall(f"213 {sha256.hexdigest()}\r\n".encode())


def send_bytes_via_rdt(rdt_obj, data: bytes, dest_addr, chunk_size=1024):
    for i in range(0, len(data), chunk_size):
        rdt_obj.send(data[i:i + chunk_size], dest_addr)
    rdt_obj.send(b"", dest_addr)


def cmd_list(session, args):
    target_dir = resolve_safe_path(session, args[0] if args else "")
    if target_dir is None or not os.path.isdir(target_dir):
        reply(session.conn, "PATH_FAIL")
        return
    if session.rdt is None:
        reply(session.conn, "NO_DATA_CONN")
        return

    lines = []
    for name in sorted(os.listdir(target_dir)):
        full_path = os.path.join(target_dir, name)
        kind = "d" if os.path.isdir(full_path) else "-"
        size = os.path.getsize(full_path)
        lines.append(f"{kind}rw-r--r-- 1 ftp ftp {size:>10} {name}")
    content = ("\r\n".join(lines) + ("\r\n" if lines else "")).encode()

    reply(session.conn, "DATA_OPEN")
    if session.data_mode == "PORT":
        client_addr = session.client_data_addr
    else:
        _, client_addr = session.rdt.recv()
    send_bytes_via_rdt(session.rdt, content, client_addr)
    reply(session.conn, "TRANSFER_OK")
    _close_data_channel(session)

def cmd_nlst(session, args):
    target_dir = resolve_safe_path(session, args[0] if args else "")
    if target_dir is None or not os.path.isdir(target_dir):
        reply(session.conn, "PATH_FAIL")
        return
    if session.rdt is None:
        reply(session.conn, "NO_DATA_CONN")
        return

    filenames = sorted(os.listdir(target_dir))
    content = ("\r\n".join(filenames) + ("\r\n" if filenames else "")).encode()

    reply(session.conn, "DATA_OPEN")
    if session.data_mode == "PORT":
        client_addr = session.client_data_addr
    else:
        _, client_addr = session.rdt.recv()
    send_bytes_via_rdt(session.rdt, content, client_addr)
    reply(session.conn, "TRANSFER_OK")
    _close_data_channel(session)


# ---------------------------------------------------------------------
# PASV -- Passive mode (server opens the port)
# ---------------------------------------------------------------------
def cmd_pasv(session, args):
    _close_data_channel(session)

    server_ip = session.conn.getsockname()[0]
    session.rdt = RDT(local_ip="0.0.0.0", local_port=0)
    session.data_mode = "PASV"

    ip_parts = server_ip.split(".")
    port = session.rdt.sock.getsockname()[1]
    p1, p2 = port // 256, port % 256

    msg = f"227 Entering Passive Mode ({ip_parts[0]},{ip_parts[1]},{ip_parts[2]},{ip_parts[3]},{p1},{p2}).\r\n"
    session.conn.sendall(msg.encode())


# ---------------------------------------------------------------------
# NEW -- PORT: Active mode (client opens the port, tells server the
# address; server already knows client_addr, so RETR/LIST skip the
# recv()-first handshake needed in Passive mode)
# ---------------------------------------------------------------------
def cmd_port(session, args):
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    try:
        nums = [int(x) for x in args[0].split(",")]
        if len(nums) != 6:
            raise ValueError
        client_ip = ".".join(str(n) for n in nums[:4])
        client_port = nums[4] * 256 + nums[5]
    except ValueError:
        reply(session.conn, "SYNTAX_ERR")
        return

    _close_data_channel(session)
    session.rdt = RDT(local_ip="0.0.0.0", local_port=0)
    session.data_mode = "PORT"
    session.client_data_addr = (client_ip, client_port)

    # Also tell the client our own data-channel address, in the same
    # "h1,h2,h3,h4,p1,p2" format PASV uses. PORT alone only tells the
    # *server* where the *client* is listening (enough for RETR); STOR
    # needs the reverse, since we just opened a fresh random UDP port
    # the client has no other way to learn.
    server_ip = session.conn.getsockname()[0]
    ip_parts = server_ip.split(".")
    my_port = session.rdt.sock.getsockname()[1]
    p1, p2 = my_port // 256, my_port % 256
    msg = f"200 Command OK ({','.join(ip_parts)},{p1},{p2}).\r\n"
    session.conn.sendall(msg.encode())


def cmd_retr(session, args):
    if not session.authenticated:
        reply(session.conn, "NOT_LOGGED_IN")
        return
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    target = resolve_safe_path(session, args[0])
    if target is None or not os.path.isfile(target):
        reply(session.conn, "PATH_FAIL")
        return
    if session.rdt is None:
        reply(session.conn, "NO_DATA_CONN")
        return

    reply(session.conn, "DATA_OPEN")
    if session.data_mode == "PORT":
        client_addr = session.client_data_addr
    else:
        _, client_addr = session.rdt.recv()
    session.rdt.send_file_reliable(target, client_addr)
    reply(session.conn, "TRANSFER_OK")
    _close_data_channel(session)

def cmd_stor(session, args):
    if not session.authenticated:
        reply(session.conn, "NOT_LOGGED_IN")
        return
    if not args:
        reply(session.conn, "SYNTAX_ERR")
        return
    target = resolve_safe_path(session, args[0])
    if target is None:
        reply(session.conn, "PATH_FAIL")
        return
    if session.rdt is None:
        reply(session.conn, "NO_DATA_CONN")
        return

    reply(session.conn, "DATA_OPEN")
    session.rdt.receive_file_reliable(target)
    reply(session.conn, "TRANSFER_OK")
    _close_data_channel(session)


COMMANDS = {
    "USER": cmd_user,
    "PASS": cmd_pass,
    "PWD": cmd_pwd,
    "QUIT": cmd_quit,
    "NOOP": cmd_noop,
    "CWD": cmd_cwd,
    "CDUP": cmd_cdup,
    "MKD": cmd_mkd,
    "RMD": cmd_rmd,
    "DELE": cmd_dele,
    "RNFR": cmd_rnfr,
    "RNTO": cmd_rnto,
    "SIZE": cmd_size,
    "MDTM": cmd_mdtm,
    "STAT": cmd_stat,
    "TYPE": cmd_type,
    "HASH": cmd_hash,
    "LIST": cmd_list,
    "NLST": cmd_nlst,
    "PASV": cmd_pasv,
    "PORT": cmd_port,
    "RETR": cmd_retr,
    "STOR": cmd_stor,
}


def handle_client(conn, addr, root_dir):
    print(f"[+] Client connected: {addr}")
    session = Session(conn, addr, root_dir)
    reply(conn, "READY")

    with conn:
        buffer = ""
        while True:
            data = conn.recv(1024)
            if not data:
                break
            buffer += data.decode(errors="ignore")

            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)
                if not line.strip():
                    continue

                parts = line.strip().split()
                cmd, args = parts[0].upper(), parts[1:]
                print(f"[{addr}] >> {cmd} {' '.join(args)}")

                handler = COMMANDS.get(cmd)
                if handler is None:
                    reply(conn, "UNKNOWN_CMD")
                    continue

                if handler(session, args) == "CLOSE":
                    print(f"[-] Client disconnected: {addr}")
                    return


def start_server(host="0.0.0.0", port=1909, root_dir="./ftp_root"):
    os.makedirs(root_dir, exist_ok=True)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(5)
    print(f"[*] Server listening on {host}:{port}, root={os.path.abspath(root_dir)}")

    while True:
        conn, addr = server_sock.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr, root_dir), daemon=True)
        t.start()


if __name__ == "__main__":
    start_server()
