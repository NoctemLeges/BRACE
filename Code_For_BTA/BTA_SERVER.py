import socket

HOST = '172.16.10.52'  # Server's LAN IP
PORT = 65432

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind to the server's IP
server_socket.bind((HOST, PORT))

server_socket.listen()
print("Server listening on", HOST, PORT)

conn, addr = server_socket.accept()
print("Connected by", addr)

data = conn.recv(1024)
print("Received:", data.decode())

conn.sendall(b"Hello from server")

conn.close()
server_socket.close()