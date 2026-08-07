"""
Interactive CLI for Hybrid FTP Client.
Usage: python -m client.cli <server_host> [port]
"""
import sys
import os
import threading
from client.client import HybridFTPClient


def print_help():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           HYBRID FTP CLIENT - SANG'S MODULES                 ║
╠══════════════════════════════════════════════════════════════╣
║  connect <host> [port]  - Connect to server                  ║
║  login <user> <pass>    - Authenticate                       ║
║  type <A|I>             - Set ASCII or Binary mode           ║
║  port                   - Enable active (PORT) mode          ║
║  pasv                   - Enable passive (PASV) mode         ║
║  upload <local> [remote]- Upload file (with hash verify)     ║
║  download <remote> <local>- Download file (with hash verify) ║
║  ls [path]              - List directory                     ║
║  cd <path>              - Change directory                   ║
║  pwd                    - Print working directory            ║
║  hash <file>            - Get server file hash               ║
║  quit                   - Disconnect and exit                ║
║  help                   - Show this help                     ║
╚══════════════════════════════════════════════════════════════╝
""")


def main():
    client = None
    mode = "PORT"

    print("=" * 60)
    print("  HYBRID FTP CLIENT - Sang's Implementation")
    print("  Features: PORT | TYPE | HASH Verify | Reliable UDP")
    print("=" * 60)

    if len(sys.argv) >= 2:
        host = sys.argv[1]
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 21
        client = HybridFTPClient(host, port)
        if client.connect():
            print(f"Connected to {host}:{port}")
        else:
            print("Connection failed.")
            client = None

    print_help()

    while True:
        try:
            cmd = input("ftp> ").strip()
            if not cmd:
                continue
            parts = cmd.split()
            action = parts[0].lower()

            if action == "connect":
                if len(parts) < 2:
                    print("Usage: connect <host> [port]")
                    continue
                host = parts[1]
                port = int(parts[2]) if len(parts) > 2 else 21
                if client:
                    client.quit()
                client = HybridFTPClient(host, port)
                if client.connect():
                    print(f"Connected to {host}:{port}")
                else:
                    print("Connection failed.")
                    client = None

            elif action == "login":
                if not client:
                    print("Not connected.")
                    continue
                if len(parts) < 3:
                    print("Usage: login <username> <password>")
                    continue
                client.login(parts[1], parts[2])

            elif action == "type":
                if not client:
                    print("Not connected.")
                    continue
                if len(parts) < 2:
                    print("Usage: type <A|I>")
                    continue
                client.type_cmd(parts[1].upper())

            elif action == "port":
                mode = "PORT"
                print("[CLI] Mode set to PORT (active)")

            elif action == "pasv":
                mode = "PASV"
                print("[CLI] Mode set to PASV (passive)")

            elif action == "upload" or action == "stor":
                if not client:
                    print("Not connected.")
                    continue
                if len(parts) < 2:
                    print("Usage: upload <local_path> [remote_name]")
                    continue
                local = parts[1]
                remote = parts[2] if len(parts) > 2 else os.path.basename(local)
                client.upload(local, remote, mode)

            elif action == "download" or action == "retr":
                if not client:
                    print("Not connected.")
                    continue
                if len(parts) < 3:
                    print("Usage: download <remote_name> <local_path>")
                    continue
                client.download(parts[1], parts[2], mode)

            elif action == "ls" or action == "list":
                if not client:
                    print("Not connected.")
                    continue
                path = parts[1] if len(parts) > 1 else ""
                print(client.list_dir(path))

            elif action == "cd" or action == "cwd":
                if not client:
                    print("Not connected.")
                    continue
                if len(parts) < 2:
                    print("Usage: cd <path>")
                    continue
                print(client.cwd(parts[1]))

            elif action == "pwd":
                if not client:
                    print("Not connected.")
                    continue
                print(client.pwd())

            elif action == "hash":
                if not client:
                    print("Not connected.")
                    continue
                if len(parts) < 2:
                    print("Usage: hash <filename>")
                    continue
                print(client.control.send_cmd(f"HASH {parts[1]}"))

            elif action == "quit" or action == "exit":
                if client:
                    client.quit()
                print("Goodbye.")
                break

            elif action == "help":
                print_help()

            else:
                # Passthrough raw command
                if client:
                    print(client.control.send_cmd(cmd))
                else:
                    print("Unknown command. Type 'help'.")

        except KeyboardInterrupt:
            print("\nUse 'quit' to exit.")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
