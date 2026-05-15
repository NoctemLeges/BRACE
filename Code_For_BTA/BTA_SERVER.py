import socket
import sys
import os
import json
import shutil
import threading
import subprocess
from checkVulnVersions import readVersionInfo, checkVulnVersion
from log_analysis.detector import HTTPDetector
from log_analysis.model_io import try_load

HOST = '0.0.0.0'
PORT = 65432

WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_prompt_worker.py")
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "iforest.joblib")
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
RAW_LOGS_DIR = os.path.join(LOGS_DIR, "raw")
EVENTS_PATH = os.path.join(LOGS_DIR, "bta_events.jsonl")

_DETECTOR: "HTTPDetector | None" = None
_PRINTERS: dict = {}
_PRINTERS_LOCK = threading.Lock()
_EVENTS_LOCK = threading.Lock()


def _load_detector_once() -> None:
    global _DETECTOR
    bundle = try_load(MODEL_PATH)
    if bundle is None:
        print(f"[!] No model at {MODEL_PATH} — log analysis disabled. "
              f"Run train_and_eval.py to enable.")
        return
    _DETECTOR = HTTPDetector(bundle)
    print(f"[+] HTTP log detector loaded from {MODEL_PATH} "
          f"(threshold={bundle.threshold:.4f}, train_n={bundle.meta.get('train_n')})")


def recv_all(conn, length):
    data = b''
    while len(data) < length:
        chunk = conn.recv(length - len(data))
        if not chunk:
            raise ConnectionError("Connection lost during data receive")
        data += chunk
    return data

def recv_message(conn):
    length_bytes = conn.recv(4)
    if not length_bytes:
        return None
    length = int.from_bytes(length_bytes, 'big')
    return recv_all(conn, length)

def send_message(conn, data_bytes):
    conn.sendall(len(data_bytes).to_bytes(4, 'big'))
    conn.sendall(data_bytes)


def _spawn_admin_terminal(port, tag):
    cmd = [sys.executable, WORKER_SCRIPT, str(port), tag]

    if sys.platform.startswith("win"):
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(cmd, creationflags=creationflags)
        return True

    inner = " ".join(_shell_quote(c) for c in cmd)
    title = f"BTA Admin {tag}"

    if shutil.which("gnome-terminal"):
        subprocess.Popen(["gnome-terminal", "--title", title, "--", *cmd])
        return True
    if shutil.which("konsole"):
        subprocess.Popen(["konsole", "--title", title, "-e", *cmd])
        return True
    if shutil.which("xfce4-terminal"):
        subprocess.Popen(["xfce4-terminal", "--title", title, "-x", *cmd])
        return True
    if shutil.which("xterm"):
        subprocess.Popen(["xterm", "-T", title, "-e", inner])
        return True
    return False


def _shell_quote(s):
    if not s or any(c in s for c in " \t\"'\\$`"):
        return "'" + s.replace("'", "'\\''") + "'"
    return s


class ClientPrinter:
    """Owns the IPC channel to one spawned admin terminal.

    If no terminal could be spawned (headless environment), falls back to
    printing on the server's own stdout and prompting on its stdin.
    """

    def __init__(self, tag):
        self.tag = tag
        self.ipc_conn = None
        self.ipc_srv = None
        self.fallback = False

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        srv.settimeout(10.0)
        port = srv.getsockname()[1]

        if not _spawn_admin_terminal(port, tag):
            srv.close()
            print(f"[!] No terminal emulator found; falling back to inline prompt for {tag}")
            self.fallback = True
            return

        try:
            conn, _ = srv.accept()
            conn.settimeout(None)
            self.ipc_srv = srv
            self.ipc_conn = conn
        except socket.timeout:
            srv.close()
            print(f"[!] Admin terminal for {tag} did not connect; falling back to inline prompt")
            self.fallback = True

    def _send(self, obj):
        if self.fallback or self.ipc_conn is None:
            return False
        try:
            send_message(self.ipc_conn, json.dumps(obj).encode())
            return True
        except (OSError, ConnectionError):
            return False

    def log(self, msg):
        if self.fallback or not self._send({"type": "log", "data": msg}):
            print(f"[{self.tag}] {msg}")

    def prompt(self, msg):
        if self.fallback:
            try:
                return input(f"[{self.tag}] {msg}").strip()
            except EOFError:
                return ""

        if not self._send({"type": "prompt", "data": msg}):
            return ""

        try:
            raw = recv_message(self.ipc_conn)
        except (OSError, ConnectionError):
            return ""
        if raw is None:
            return ""
        try:
            frame = json.loads(raw.decode())
        except json.JSONDecodeError:
            return ""
        return (frame.get("data") or "").strip()

    def close(self):
        self._send({"type": "done"})
        if self.ipc_conn is not None:
            try:
                self.ipc_conn.close()
            except OSError:
                pass
        if self.ipc_srv is not None:
            try:
                self.ipc_srv.close()
            except OSError:
                pass


def _append_event(event: dict) -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)
    with _EVENTS_LOCK:
        with open(EVENTS_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")


def _append_raw_logs(host_id: str, batch_bytes: bytes) -> str:
    os.makedirs(RAW_LOGS_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in host_id) or "unknown"
    path = os.path.join(RAW_LOGS_DIR, f"{safe}_access.log")
    with open(path, "ab") as f:
        f.write(batch_bytes)
        if not batch_bytes.endswith(b"\n"):
            f.write(b"\n")
    return path


def handle_log_upload(conn, addr, greeting: str, printer) -> None:
    """Receive one batch of newline-delimited nginx log lines, score, emit alerts."""
    parts = greeting.split(" ", 1)
    host_id = parts[1].strip() if len(parts) > 1 else addr[0]
    printer.log(f"[+] Log upload from {host_id}")
    send_message(conn, b"READY")

    batch = recv_message(conn)
    if batch is None:
        raise ConnectionError("Client closed before sending log batch")

    _append_raw_logs(host_id, batch)
    lines = batch.decode("utf-8", errors="replace").splitlines()

    if _DETECTOR is None:
        printer.log(f"[!] No detector loaded; archived {len(lines)} lines only.")
        send_message(conn, f"OK no-detector lines={len(lines)}".encode())
        return

    alerts, parsed = _DETECTOR.score_batch(lines, host_id=host_id)
    for a in alerts:
        event = {
            "team": "BLUE",
            "action": "detect",
            "timestamp": a["ts"],
            "host": a["host"],
            "src_addr": addr[0],
            "score": a["score"],
            "threshold": a["threshold"],
            "method": a["method"],
            "uri": a["uri"],
            "query": a["query"],
            "top_contributors": a["top_contributors"],
        }
        _append_event(event)
        summary = f"{a['method']} {a['uri']}"
        if a["query"]:
            summary += "?" + a["query"]
        if len(summary) > 120:
            summary = summary[:117] + "..."
        printer.log(f"[ANOMALY score={a['score']:.3f}] {summary}")

    printer.log(f"[+] Scored {parsed}/{len(lines)} lines, {len(alerts)} alerts.")
    send_message(conn, f"OK lines={len(lines)} parsed={parsed} alerts={len(alerts)}".encode())


def handle_client(conn, addr):
    tag = f"{addr[0]}:{addr[1]}"
    printer = ClientPrinter(tag)
    with _PRINTERS_LOCK:
        _PRINTERS[addr[0]] = printer

    try:
        printer.log(f"[+] Connected: {tag}")

        greeting = recv_message(conn).decode()
        printer.log(f"[Client] {greeting}")

        if greeting.startswith("LOG_UPLOAD"):
            handle_log_upload(conn, addr, greeting, printer)
            return

        send_message(conn, b"Hello from server")

        file_data = recv_message(conn)
        if file_data is None:
            raise ConnectionError("Client closed before sending file")
        printer.log(f"[+] Received file ({len(file_data)} bytes)")

        filename = f"VersionInfo_{addr[0]}.txt"
        with open(filename, "wb") as f:
            f.write(file_data)

        printer.log(f"[+] Saved as {filename}")

        send_message(conn, b"File received successfully")

        vuln_count_dict = checkVulnVersion(readVersionInfo(filename))

        reply_list = [k for k, v in vuln_count_dict.items() if v > 0]
        reply = "\n".join(reply_list) if reply_list else "No vulnerabilities found"

        if reply != "No vulnerabilities found":
            printer.log("Vulnerable products:")
            for product in reply_list:
                printer.log(f"  - {product}")
            answer = printer.prompt(f"Send Update Command to {addr[0]}?[Y/N]: ")
            if answer and answer[0] in "Yy":
                send_message(conn, reply.encode())
                printer.log("[+] Sent update list to client.")
            else:
                send_message(conn, "No Updates Pending".encode())
                printer.log("[+] Sent 'No Updates Pending' to client.")
        else:
            send_message(conn, reply.encode())
            printer.log("[+] No vulnerabilities found. Notified client.")

        printer.log("[+] Analysis complete.")

    except Exception as e:
        printer.log(f"[!] Error: {e}")
        try:
            send_message(conn, f"Error: {str(e)}".encode())
        except Exception:
            pass

    finally:
        conn.close()
        printer.log(f"[-] Connection closed: {addr[0]}")
        printer.close()
        with _PRINTERS_LOCK:
            if _PRINTERS.get(addr[0]) is printer:
                del _PRINTERS[addr[0]]
        print(f"[-] Disconnected {tag}")


def start_server():
    _load_detector_once()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()

        print("=" * 50)
        print(f"Server running on {HOST}:{PORT}")
        print("Waiting for connections...")
        print("=" * 50)

        while True:
            conn, addr = server_socket.accept()
            print(f"[+] Connection from {addr[0]}:{addr[1]}")
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    start_server()
