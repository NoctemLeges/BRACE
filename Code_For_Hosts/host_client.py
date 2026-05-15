import argparse
import json
import os
import socket
import socket as _socket
import subprocess
import sys
import time

SERVER_IP = "172.16.10.52"
PORT = 65432
FILE_PATH = "VersionInfo.txt"

# ---------- Helper Functions ----------

def recv_all(sock, length):
    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise ConnectionError("Connection lost during receive")
        data += chunk
    return data

def recv_message(sock):
    length_bytes = sock.recv(4)
    if not length_bytes:
        raise ConnectionError("Failed to receive message length")
    length = int.from_bytes(length_bytes, 'big')
    return recv_all(sock, length)

def send_message(sock, data_bytes):
    sock.sendall(len(data_bytes).to_bytes(4, 'big'))
    sock.sendall(data_bytes)

# ---------- Versions mode (existing flow) ----------

def run_extraction_script():
    print("[*] Running version extraction script...")
    result = subprocess.run(
        ["./Code_For_Hosts/extract_version_scripts/extract_version_linux.sh"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("[!] Script failed:")
        print(result.stderr)
        sys.exit(1)

    print("[+] Script executed successfully.")


def run_versions_mode(server_ip: str, port: int, file_path: str) -> None:
    print("=" * 50)
    print("Vulnerability Scanner Client")
    print("=" * 50)

    if not os.path.exists(file_path):
        print(f"[!] Expected file not found: {file_path}")
        sys.exit(1)

    with open(file_path, "rb") as f:
        file_data = f.read()

    print(f"[+] Loaded file ({len(file_data)} bytes)")

    result = ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            print(f"[+] Connecting to {server_ip}:{port}...")
            sock.connect((server_ip, port))
            print("[+] Connected")

            send_message(sock, b"Hello from client")
            response = recv_message(sock).decode()
            print(f"[Server] {response}")

            print("[+] Sending VersionInfo file...")
            send_message(sock, file_data)

            response = recv_message(sock).decode()
            print(f"[Server] {response}")

            print("\nVulnerability Report")
            print("-" * 40)

            result = recv_message(sock).decode()
            print(result)

            print("-" * 40)
            print("Done")

    except ConnectionRefusedError:
        print("[!] Connection refused. Is the server running?")
        return
    except Exception as e:
        print(f"[!] Error: {e}")
        return

    if result == "No vulnerabilities found" or result == "No Updates Pending":
        return
    update_list = result.split("\n")
    for i in update_list:
        if "openvpn" in i:
            subprocess.run(["python3", "Code_For_Hosts/update_scripts/openvpn_linux.py"])
        elif "openssh" in i:
            subprocess.run(["python3", "Code_For_Hosts/update_scripts/openssh_linux.py"])
        elif "nginx" in i:
            subprocess.run(["python3", "Code_For_Hosts/update_scripts/nginx_linux.py"])


# ---------- Log-upload mode ----------

def _state_path(log_path: str) -> str:
    base = os.path.basename(log_path) or "logfile"
    state_dir = os.path.join(os.path.expanduser("~"), ".brace_log_state")
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, base + ".state.json")


def _load_offset(state_path: str, log_path: str) -> int:
    if not os.path.isfile(state_path):
        return 0
    try:
        with open(state_path) as f:
            s = json.load(f)
        if s.get("inode") != os.stat(log_path).st_ino:
            return 0
        return int(s.get("offset", 0))
    except Exception:
        return 0


def _save_offset(state_path: str, log_path: str, offset: int) -> None:
    try:
        inode = os.stat(log_path).st_ino
    except OSError:
        inode = 0
    with open(state_path, "w") as f:
        json.dump({"offset": offset, "inode": inode}, f)


def _read_new_bytes(log_path: str, offset: int) -> tuple[bytes, int]:
    size = os.path.getsize(log_path)
    if size < offset:
        offset = 0
    if size == offset:
        return b"", offset
    with open(log_path, "rb") as f:
        f.seek(offset)
        data = f.read()
    return data, offset + len(data)


def _ship_batch(server_ip: str, port: int, host_id: str, batch: bytes) -> str:
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as sock:
        sock.connect((server_ip, port))
        send_message(sock, f"LOG_UPLOAD {host_id}".encode())
        ack = recv_message(sock).decode()
        if ack != "READY":
            return f"unexpected ack: {ack}"
        send_message(sock, batch)
        reply = recv_message(sock).decode()
        return reply


def run_log_upload_mode(server_ip: str, port: int, log_path: str,
                       host_id: str, interval: float, once: bool) -> None:
    print(f"[+] Log uploader: shipping {log_path} → {server_ip}:{port} every {interval}s as '{host_id}'")
    if not os.path.exists(log_path):
        print(f"[!] Log file not found: {log_path}")
        sys.exit(1)

    state_path = _state_path(log_path)
    offset = _load_offset(state_path, log_path)
    print(f"[+] Starting at offset {offset}")

    while True:
        try:
            data, new_offset = _read_new_bytes(log_path, offset)
            if data:
                reply = _ship_batch(server_ip, port, host_id, data)
                print(f"[Server] {reply}")
                offset = new_offset
                _save_offset(state_path, log_path, offset)
            else:
                print("[*] No new bytes.")
        except ConnectionRefusedError:
            print("[!] Connection refused; will retry next interval.")
        except Exception as e:
            print(f"[!] Upload error: {e}")
        if once:
            return
        time.sleep(interval)


# ---------- CLI ----------

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="BRACE host client.")
    ap.add_argument("--mode", choices=["versions", "log-upload"], default="versions")
    ap.add_argument("--bta-host", default=SERVER_IP)
    ap.add_argument("--bta-port", type=int, default=PORT)
    ap.add_argument("--file", default=FILE_PATH,
                    help="(versions mode) path to VersionInfo.txt")
    ap.add_argument("--log-path", default="/var/log/nginx/access.log",
                    help="(log-upload mode) path to log file to ship")
    ap.add_argument("--host-id", default=_socket.gethostname(),
                    help="(log-upload mode) identifier sent in the LOG_UPLOAD greeting")
    ap.add_argument("--interval", type=float, default=10.0,
                    help="(log-upload mode) seconds between batches")
    ap.add_argument("--once", action="store_true",
                    help="(log-upload mode) ship one batch and exit")
    return ap.parse_args(argv)


def main():
    args = parse_args()
    if args.mode == "versions":
        run_versions_mode(args.bta_host, args.bta_port, args.file)
    else:
        run_log_upload_mode(
            args.bta_host, args.bta_port, args.log_path,
            args.host_id, args.interval, args.once,
        )


if __name__ == "__main__":
    main()
