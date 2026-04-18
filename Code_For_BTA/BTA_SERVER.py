import socket
from checkVulnVersions import readVersionInfo, checkVulnVersion

HOST = '0.0.0.0'
PORT = 65432

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

def handle_client(conn, addr):
    print(f"\n[+] Connected: {addr[0]}:{addr[1]}")

    try:
        # Step 1: Receive greeting
        greeting = recv_message(conn).decode()
        print(f"[Client] {greeting}")

        send_message(conn, b"Hello from server")

        # Step 2: Receive file data
        file_data = recv_message(conn)
        print(f"[+] Received file ({len(file_data)} bytes)")

        filename = f"VersionInfo_{addr[0]}.txt"
        with open(filename, "wb") as f:
            f.write(file_data)

        print(f"[+] Saved as {filename}")

        send_message(conn, b"File received successfully")

        # Step 3: Process file
        vuln_count_dict = checkVulnVersion(readVersionInfo(filename))

        reply_list = [k for k, v in vuln_count_dict.items() if v > 0]
        reply = "\n".join(reply_list) if reply_list else "No vulnerabilities found"

        #Temporary Stand-in code for Op. Admin
        if reply != "No vulnerabilities found":
            Admin_Choice = input(f"Send Update Command to {addr[0]}?[Y/N]: ")
            if Admin_Choice in "Yy":
                send_message(conn, reply.encode())
            else:
                send_message(conn,"No Updates Pending".encode())
        else:
            send_message(conn, reply.encode())

        print(f"[+] Analysis complete. Sent results.")

    except Exception as e:
        print(f"[!] Error: {e}")
        try:
            send_message(conn, f"Error: {str(e)}".encode())
        except:
            pass

    finally:
        conn.close()
        print(f"[-] Connection closed: {addr[0]}")


def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()

        print("=" * 50)
        print(f"Server running on {HOST}:{PORT}")
        print("Waiting for connections...")
        print("=" * 50)

        while True:
            conn, addr = server_socket.accept()
            handle_client(conn, addr)   # single-client (can upgrade to threading)


if __name__ == "__main__":
    start_server()