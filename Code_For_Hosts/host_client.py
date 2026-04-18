import socket
import subprocess
import os
import sys

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

# ---------- Main Flow ----------

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

def main():
    print("=" * 50)
    print("Vulnerability Scanner Client")
    print("=" * 50)

    # Step 1: Run script
    run_extraction_script()

    # Step 2: Validate file exists
    if not os.path.exists(FILE_PATH):
        print(f"[!] Expected file not found: {FILE_PATH}")
        sys.exit(1)

    # Step 3: Read file
    with open(FILE_PATH, "rb") as f:
        file_data = f.read()

    print(f"[+] Loaded file ({len(file_data)} bytes)")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            print(f"[+] Connecting to {SERVER_IP}:{PORT}...")
            sock.connect((SERVER_IP, PORT))
            print("[+] Connected")

            # Step 4: Greeting
            send_message(sock, b"Hello from client")
            response = recv_message(sock).decode()
            print(f"[Server] {response}")

            # Step 5: Send file
            print("[+] Sending VersionInfo file...")
            send_message(sock, file_data)

            response = recv_message(sock).decode()
            print(f"[Server] {response}")

            # Step 6: Receive analysis
            print("\nVulnerability Report")
            print("-" * 40)

            result = recv_message(sock).decode()
            print(result)

            print("-" * 40)
            print("Done")

    except ConnectionRefusedError:
        print("[!] Connection refused. Is the server running?")
    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    main()