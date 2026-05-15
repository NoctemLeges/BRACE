import socket
import sys
import json


def recv_all(sock, length):
    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise ConnectionError("IPC closed")
        data += chunk
    return data


def recv_message(sock):
    length_bytes = sock.recv(4)
    if not length_bytes:
        return None
    length = int.from_bytes(length_bytes, 'big')
    return recv_all(sock, length)


def send_message(sock, data_bytes):
    sock.sendall(len(data_bytes).to_bytes(4, 'big'))
    sock.sendall(data_bytes)


def main():
    port = int(sys.argv[1])
    tag = sys.argv[2] if len(sys.argv) > 2 else "client"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))

    print("=" * 50)
    print(f"BTA Admin Session — {tag}")
    print("=" * 50)

    try:
        while True:
            raw = recv_message(sock)
            if raw is None:
                break
            frame = json.loads(raw.decode())
            kind = frame.get("type")

            if kind == "log":
                print(frame.get("data", ""))
            elif kind == "prompt":
                try:
                    answer = input(frame.get("data", "")).strip()
                except EOFError:
                    answer = ""
                send_message(sock, json.dumps({"type": "response", "data": answer}).encode())
            elif kind == "done":
                break
    finally:
        sock.close()


if __name__ == "__main__":
    main()
