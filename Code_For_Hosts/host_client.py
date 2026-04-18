import socket
import subprocess

SERVER_IP = "172.16.10.52"
PORT = 65432

#subprocess.run(["./Code_For_Hosts/extract_version_scripts/extract_version_linux.sh"])

try:
    # Create a TCP socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        print(f"Connecting to {SERVER_IP}:{PORT}...")
        client_socket.connect((SERVER_IP, PORT))

        hello_msg = b"Hello from Client"
        client_socket.sendall(hello_msg)
        print(f"Sent: {hello_msg}")

        response = client_socket.recv(1024)
        print(f"Server says: {response.decode('utf-8')}")

        with open("VersionInfo.txt", "rb") as file:
            file_data = file.read()

        # Send actual file data
        client_socket.sendall(file_data)
        print(f"Sent file")

        response = client_socket.recv(1024)
        print(f"Final response: {response.decode('utf-8')}")

        update_response = client_socket.recv(1024)
        print(f"Update: {update_response.decode('utf-8')}")

except FileNotFoundError:
    print("VersionInfo.txt not found.")
except ConnectionRefusedError:
    print("Connection refused. Make sure the server is running.")
except Exception as e:
    print(f"An error occurred: {e}")