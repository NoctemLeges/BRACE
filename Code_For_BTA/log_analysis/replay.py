"""End-to-end replay demo.

Reads CSIC 2010 records, formats each as a synthetic nginx Common Log Format
line, mixes benign and anomalous, and ships them in batches to a running
BTA_SERVER over the LOG_UPLOAD protocol on :65432.
"""
import argparse
import os
import random
import socket
import sys
import time
from datetime import datetime

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from log_analysis.dataset import ensure_present, load_replay_rows
else:
    from .dataset import ensure_present, load_replay_rows


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


def _format_nginx_line(payload: str, src_ip: str) -> str:
    from urllib.parse import quote
    ts = datetime.now().strftime("%d/%b/%Y:%H:%M:%S +0000")
    uri = "/search?q=" + quote(payload or "", safe="")
    request_line = f"GET {uri} HTTP/1.1"
    return f'{src_ip} - - [{ts}] "{request_line}" 200 0 "-" "replay-demo"'


def _ship_batch(host: str, port: int, host_id: str, batch_bytes: bytes) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        send_message(s, f"LOG_UPLOAD {host_id}".encode())
        ack = recv_message(s).decode()
        if ack != "READY":
            return f"unexpected ack: {ack}"
        send_message(s, batch_bytes)
        return recv_message(s).decode()


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay CSIC 2010 records through BTA's LOG_UPLOAD pipeline.")
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--bta-host", default="127.0.0.1")
    ap.add_argument("--bta-port", type=int, default=65432)
    ap.add_argument("--total", type=int, default=1000)
    ap.add_argument("--benign-mix", type=float, default=0.7)
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--host-id", default="replay-host")
    ap.add_argument("--src-ip", default="10.0.0.99",
                    help="Synthetic remote_addr to put in the fabricated nginx lines.")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    ensure_present(args.dataset_dir)
    print(f"[+] Loading replay records from {args.dataset_dir}")
    benign, anom = load_replay_rows(args.dataset_dir)
    print(f"    benign={len(benign)}  anomalous={len(anom)}")

    rnd = random.Random(args.seed)
    n_benign = int(args.total * args.benign_mix)
    n_anom = args.total - n_benign
    sample_b = rnd.sample(benign, min(n_benign, len(benign)))
    sample_a = rnd.sample(anom, min(n_anom, len(anom)))
    mixed = [(r, False) for r in sample_b] + [(r, True) for r in sample_a]
    rnd.shuffle(mixed)
    print(f"[+] Shipping {len(mixed)} records ({len(sample_b)} benign / {len(sample_a)} anomalous) "
          f"in batches of {args.batch_size}")

    sent = 0
    while sent < len(mixed):
        chunk = mixed[sent : sent + args.batch_size]
        sent += len(chunk)
        lines = [_format_nginx_line(r["payload"], args.src_ip) for r, _ in chunk]
        batch_bytes = ("\n".join(lines) + "\n").encode()
        reply = _ship_batch(args.bta_host, args.bta_port, args.host_id, batch_bytes)
        print(f"[Server] ({sent}/{len(mixed)}) {reply}")
        time.sleep(0.2)

    print("[+] Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
