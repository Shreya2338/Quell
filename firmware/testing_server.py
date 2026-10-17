
import socket

HOST = "0.0.0.0"
PORT = 5000

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)

    print(f"Listening on TCP port {PORT}...")
    print("Waiting for ESP32 connection...")

    conn, addr = server.accept()

    with conn:
        print(f"ESP32 connected from {addr}")

        buffer = b""

        while True:
            data = conn.recv(4096)
            if not data:
                print("ESP32 disconnected.")
                break

            buffer += data

            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r")
                print("ESP32:", line)
