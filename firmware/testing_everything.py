#!/usr/bin/env python3
"""
Tremor device test server.

The ESP32 connects to this server over TCP (port 5000 by default) and streams
newline-delimited JSON. This script:
  - prints a live status line (sample rate, latest gyro/accel values)
  - prints events (calibration status, vibration start/stop)
  - lets you send commands from the keyboard
  - optionally logs the sensor stream to CSV

Run:      python tremor_test_server.py
Options:  --port 5000   --csv log.csv   --verbose

Keyboard commands (type + Enter):
  v <ms> [intensity]   vibrate, e.g.  v 500   or   v 500 80
  c                    calibrate (keep the board still, Z up)
  raw <text>           send a raw line to the board
  s                    toggle the live status line
  h                    help
  q                    quit

Make sure the laptop is the hotspot / on the same network as the board and that
your firewall allows inbound TCP on the chosen port.
"""

import argparse
import csv
import json
import socket
import sys
import threading
import time


def local_ips():
    """Best-effort list of this machine's IPv4 addresses."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ips)


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.conn = None
        self.addr = None
        self.samples = 0
        self.samples_window = 0
        self.total_samples = 0
        self.bad_lines = 0
        self.gyro = (0.0, 0.0, 0.0)
        self.accel = (0.0, 0.0, 0.0)
        self.calibrated = None
        self.vibrating = False
        self.vib_hz = 0
        self.show_status = True
        self.verbose = False
        self.running = True
        self.csv_writer = None
        self.csv_file = None
        self.t0 = None


state = State()


def log(msg):
    # clear the status line, print message
    sys.stdout.write("\r" + " " * 100 + "\r" + msg + "\n")
    sys.stdout.flush()


def send_line(text):
    with state.lock:
        conn = state.conn
    if conn is None:
        log("[server] no device connected")
        return False
    try:
        conn.sendall((text + "\n").encode())
        log(f"[server] -> {text}")
        return True
    except OSError as e:
        log(f"[server] send failed: {e}")
        return False


def handle_message(line):
    line = line.strip()
    if not line:
        return
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        state.bad_lines += 1
        log(f"[device] unparseable line: {line[:120]!r}")
        return

    if state.verbose:
        log(f"[device] {line}")

    if "gyroscope" in msg and "accelerometer" in msg:
        g = msg["gyroscope"]
        a = msg["accelerometer"]
        state.gyro = tuple(g)
        state.accel = tuple(a)
        state.samples_window += 1
        state.total_samples += 1
        if state.csv_writer:
            t = time.time() - state.t0
            state.csv_writer.writerow([f"{t:.4f}", *g, *a])
        return

    if "actuation_state" in msg:
        on = bool(msg["actuation_state"])
        hz = msg.get("actuation_intensity", 0)
        state.vibrating = on
        state.vib_hz = hz
        log(f"[device] vibration {'STARTED' if on else 'STOPPED'} (~{hz} Hz)")
        return

    if "caliberation_status" in msg or "calibration_status" in msg:
        v = msg.get("caliberation_status", msg.get("calibration_status"))
        state.calibrated = bool(v)
        log(f"[device] calibration status: {'CALIBRATED' if v else 'not calibrated / in progress'}")
        return

    log(f"[device] unknown message: {line[:120]}")


def client_thread(conn, addr):
    log(f"[server] device connected from {addr[0]}:{addr[1]}")
    with state.lock:
        state.conn = conn
        state.addr = addr
    state.samples_window = 0
    buf = b""
    try:
        while state.running:
            data = conn.recv(4096)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                handle_message(raw.decode(errors="replace"))
    except OSError as e:
        log(f"[server] connection error: {e}")
    finally:
        with state.lock:
            if state.conn is conn:
                state.conn = None
                state.addr = None
        try:
            conn.close()
        except OSError:
            pass
        log("[server] device disconnected")


def accept_loop(srv):
    while state.running:
        try:
            conn, addr = srv.accept()
        except OSError:
            break
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # only one device at a time: drop the old one
        with state.lock:
            old = state.conn
        if old is not None:
            try:
                old.close()
            except OSError:
                pass
        threading.Thread(target=client_thread, args=(conn, addr), daemon=True).start()


def status_loop():
    last = time.time()
    rate = 0.0
    while state.running:
        time.sleep(0.25)
        now = time.time()
        dt = now - last
        if dt >= 1.0:
            rate = state.samples_window / dt
            state.samples_window = 0
            last = now
        if not state.show_status:
            continue
        with state.lock:
            connected = state.conn is not None
        if not connected:
            line = "waiting for device..."
        else:
            g, a = state.gyro, state.accel
            cal = {None: "?", True: "yes", False: "no"}[state.calibrated]
            line = (f"{rate:6.1f} Hz | ypr {g[0]:7.2f} {g[1]:7.2f} {g[2]:7.2f} | "
                    f"lin-acc g {a[0]:7.4f} {a[1]:7.4f} {a[2]:7.4f} | "
                    f"cal:{cal} vib:{'ON' if state.vibrating else 'off'}")
        sys.stdout.write("\r" + line[:110].ljust(110))
        sys.stdout.flush()


HELP = """\
Commands:
  v <ms> [intensity]   vibrate (intensity 0-100 %), e.g. 'v 500' or 'v 500 80'
  c                    calibrate (keep board still, Z up)
  raw <text>           send a raw line
  s                    toggle live status line
  h                    help
  q                    quit"""


def command_loop():
    while state.running:
        try:
            cmd = input()
        except (EOFError, KeyboardInterrupt):
            state.running = False
            break
        parts = cmd.strip().split()
        if not parts:
            continue
        c = parts[0].lower()
        if c in ("q", "quit", "exit"):
            state.running = False
        elif c in ("h", "help", "?"):
            log(HELP)
        elif c == "s":
            state.show_status = not state.show_status
            log(f"[server] status line {'on' if state.show_status else 'off'}")
        elif c == "c":
            send_line('{"calibrate_now"}')
        elif c == "v":
            if len(parts) < 2 or not parts[1].isdigit():
                log("usage: v <ms> [intensity 0-100]")
                continue
            ms = int(parts[1])
            if len(parts) >= 3 and parts[2].isdigit():
                send_line(json.dumps({"length": ms, "intensity": int(parts[2])},
                                     separators=(",", ":")))
            else:
                send_line(json.dumps({"length": ms}, separators=(",", ":")))
        elif c == "raw":
            send_line(cmd.strip()[3:].strip())
        else:
            log("unknown command, type 'h' for help")


def main():
    ap = argparse.ArgumentParser(description="Tremor device test server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--csv", help="log sensor stream to this CSV file")
    ap.add_argument("--verbose", action="store_true", help="print every raw message")
    args = ap.parse_args()

    state.verbose = args.verbose
    state.t0 = time.time()

    if args.csv:
        state.csv_file = open(args.csv, "w", newline="")
        state.csv_writer = csv.writer(state.csv_file)
        state.csv_writer.writerow(["t_s", "yaw", "pitch", "roll", "lax_g", "lay_g", "laz_g"])

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(1)

    print(f"Listening on {args.host}:{args.port}")
    ips = local_ips()
    if ips:
        print("Laptop IPs (the board uses the WiFi gateway IP by default): " + ", ".join(ips))
    print(HELP + "\n")

    threading.Thread(target=accept_loop, args=(srv,), daemon=True).start()
    threading.Thread(target=status_loop, daemon=True).start()
    threading.Thread(target=command_loop, daemon=True).start()

    try:
        while state.running:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        state.running = False
        try:
            srv.close()
        except OSError:
            pass
        with state.lock:
            if state.conn:
                try:
                    state.conn.close()
                except OSError:
                    pass
        if state.csv_file:
            state.csv_file.close()
        print(f"\nBye. {state.total_samples} samples received, {state.bad_lines} bad lines.")


if __name__ == "__main__":
    main()