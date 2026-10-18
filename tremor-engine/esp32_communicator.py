"""
ESP32 Communicator: TCP server that talks to the tremor device.

Runs inside its own process (spawned by server_manager.py). The ESP32 connects
over WiFi/TCP and streams newline-delimited JSON.

Incoming routing:
    {"gyroscope":[x,y,z], "accelerometer":[x,y,z]}  -> sensor_q
    {"actuation_state":1, "actuation_intensity":60} -> event_q
    {"caliberation_status":1}                       -> event_q

Outgoing commands (consumed from command_q):
    {"type": "vibrate", "length": 500, "intensity": 80} -> {"length":500,"intensity":80}\n
    {"type": "calibrate"}                                -> {"calibrate_now":true}\n
"""

import json
import logging
import multiprocessing as mp
import select
import socket
import sys
import time

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [ESP32-Server] %(message)s")


def run_esp32_server(
    sensor_q: mp.Queue,
    event_q: mp.Queue,
    command_q: mp.Queue,
    host: str = "0.0.0.0",
    port: int = 8888,
):
    """
    TCP server loop managing socket I/O and queue translation.
    """
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
        server_sock.listen(1)
        logging.info("Listening for ESP32 connection on %s:%d...", host, port)
    except Exception as e:
        logging.error("Failed to bind TCP server on port %d: %s", port, e)
        sys.exit(1)

    while True:
        logging.info("Waiting for incoming ESP32 connection...")
        client_sock, client_addr = server_sock.accept()
        client_sock.setblocking(False)
        addr_str = f"{client_addr[0]}:{client_addr[1]}"
        logging.info("ESP32 connected from %s", addr_str)

        # Notify event_q of active connection
        event_q.put({"type": "connection", "t": time.time(), "connected": True, "addr": addr_str})

        recv_buffer = ""

        try:
            while True:
                # 1. Send pending commands from command_q to the connected ESP32
                while not command_q.empty():
                    try:
                        cmd = command_q.get_nowait()
                        cmd_type = cmd.get("type")

                        if cmd_type == "vibrate":
                            payload = {
                                "length": int(cmd.get("length", 0)),
                                "intensity": int(cmd.get("intensity", 250)),
                            }
                            wire_msg = json.dumps(payload) + "\n"
                            client_sock.sendall(wire_msg.encode("utf-8"))
                            logging.info("Dispatched vibration command: %s", payload)

                        elif cmd_type == "calibrate":
                            payload = {"calibrate_now": True}
                            wire_msg = json.dumps(payload) + "\n"
                            client_sock.sendall(wire_msg.encode("utf-8"))
                            logging.info("Dispatched calibration command: %s", payload)

                    except mp.queues.Empty:
                        break
                    except (socket.error, BrokenPipeError) as e:
                        logging.warning("Error writing to ESP32: %s", e)
                        raise

                # 2. Poll socket for incoming bytes
                r_ready, _, _ = select.select([client_sock], [], [], 0.01)
                if r_ready:
                    chunk = client_sock.recv(4096).decode("utf-8")
                    if not chunk:
                        logging.warning("ESP32 closed connection unexpectedly.")
                        break

                    recv_buffer += chunk

                    # Parse newline-delimited JSON packets
                    while "\n" in recv_buffer:
                        line, recv_buffer = recv_buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue

                        t_now = time.time()
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Sensor packet -> sensor_q
                        if "gyroscope" in data and "accelerometer" in data:
                            sensor_q.put({
                                "t": t_now,
                                "gyroscope": data["gyroscope"],
                                "accelerometer": data["accelerometer"],
                            })

                        # Actuation telemetry -> event_q
                        elif "actuation_state" in data:
                            event_q.put({
                                "type": "actuation",
                                "t": t_now,
                                "state": bool(data["actuation_state"]),
                                "intensity_hz": int(data.get("actuation_intensity", 0)),
                            })

                        # Calibration telemetry -> event_q
                        elif "caliberation_status" in data:
                            event_q.put({
                                "type": "calibration",
                                "t": t_now,
                                "calibrated": bool(data["caliberation_status"]),
                            })

        except (socket.error, ConnectionResetError, BrokenPipeError) as conn_err:
            logging.warning("Connection lost with %s: %s", addr_str, conn_err)
        finally:
            client_sock.close()
            event_q.put({"type": "connection", "t": time.time(), "connected": False, "addr": None})
            logging.info("Disconnected from %s", addr_str)