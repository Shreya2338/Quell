"""
ESP32 communicator: TCP server that talks to the tremor device.

Runs inside its own process (see server_manager.py). The ESP32 connects to us
over WiFi and streams newline-delimited JSON.

ESP32 -> server (parsed and routed to queues):
    {"gyroscope":[x,y,z],"accelerometer":[x,y,z]}   -> sensor_q
    {"actuation_state":1,"actuation_intensity":60}  -> event_q
    {"caliberation_status":1}                       -> event_q

server -> ESP32 (built from dicts taken off command_q):
    {"type": "vibrate", "length": 500, "intensity": 80}  ->  {"length":500,"intensity":80}\n
    {"type": "calibrate"}                                 ->  {"calibrate_now"}\n

Queue message formats:
    sensor_q : {"t": float, "gyroscope": [x,y,z], "accelerometer": [x,y,z]}
    event_q  : {"type": "actuation",   "t": float, "state": bool, "intensity_hz": int}
               {"type": "calibration", "t": float, "calibrated": bool}
               {"type": "connection",  "t": float, "connected": bool, "addr": str|None}
"""

import json
import logging
import queue
import selectors
import socket
import time

log = logging.getLogger("esp32_comm")

MAX_BUFFER_BYTES = 1_000_000


class ESP32Communicator:
    def __init__(self, sensor_q, event_q, command_q, stop_event,
                 host="0.0.0.0", port=5000):
        self.sensor_q = sensor_q
        self.event_q = event_q
        self.command_q = command_q
        self.stop_event = stop_event
        self.host = host
        self.port = port

        self._sel = selectors.DefaultSelector()
        self._listener = None
        self._client = None
        self._buf = bytearray()
        self._dropped = 0

    # ------------------------------------------------------------ lifecycle

    def run(self):
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(name)s] %(message)s")
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((self.host, self.port))
        self._listener.listen(1)
        self._listener.setblocking(False)
        self._sel.register(self._listener, selectors.EVENT_READ, "listener")
        log.info("listening on %s:%d", self.host, self.port)

        try:
            while not self.stop_event.is_set():
                for key, _ in self._sel.select(timeout=0.005):
                    if key.data == "listener":
                        self._accept()
                    else:
                        self._read()
                self._flush_commands()
        finally:
            self._close_client()
            self._sel.close()
            self._listener.close()
            log.info("stopped (dropped %d sensor samples)", self._dropped)

    # ------------------------------------------------------------ connection

    def _accept(self):
        conn, addr = self._listener.accept()
        self._close_client()  # only one device at a time; newest wins
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        conn.settimeout(1.0)
        self._client = conn
        self._buf.clear()
        self._sel.register(conn, selectors.EVENT_READ, "client")
        log.info("ESP32 connected from %s:%d", *addr)
        self._emit({"type": "connection", "connected": True, "addr": addr[0]})

    def _close_client(self):
        if self._client is None:
            return
        try:
            self._sel.unregister(self._client)
        except (KeyError, ValueError):
            pass
        try:
            self._client.close()
        except OSError:
            pass
        self._client = None
        self._emit({"type": "connection", "connected": False, "addr": None})
        log.info("ESP32 disconnected")

    # ------------------------------------------------------------ receiving

    def _read(self):
        try:
            data = self._client.recv(65536)
        except (socket.timeout, BlockingIOError):
            return
        except OSError:
            data = b""
        if not data:
            self._close_client()
            return

        self._buf.extend(data)
        if len(self._buf) > MAX_BUFFER_BYTES and b"\n" not in self._buf:
            log.warning("no newline in %d bytes, clearing buffer", len(self._buf))
            self._buf.clear()
            return

        while True:
            idx = self._buf.find(b"\n")
            if idx < 0:
                break
            line = bytes(self._buf[:idx]).strip()
            del self._buf[:idx + 1]
            if line:
                self._handle_line(line)

    def _handle_line(self, line):
        try:
            msg = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            log.debug("bad JSON line: %r", line[:80])
            return
        if not isinstance(msg, dict):
            return

        now = time.time()
        if "gyroscope" in msg and "accelerometer" in msg:
            self._put_sensor({"t": now,
                              "gyroscope": msg["gyroscope"],
                              "accelerometer": msg["accelerometer"]})
        elif "actuation_state" in msg:
            self._emit({"type": "actuation",
                        "state": bool(msg["actuation_state"]),
                        "intensity_hz": int(msg.get("actuation_intensity", 0))})
        elif "caliberation_status" in msg:  # spelling matches the firmware
            self._emit({"type": "calibration",
                        "calibrated": bool(msg["caliberation_status"])})

    def _put_sensor(self, sample):
        """Never block the socket loop: if the consumer lags, drop the oldest."""
        try:
            self.sensor_q.put_nowait(sample)
        except queue.Full:
            try:
                self.sensor_q.get_nowait()
                self._dropped += 1
            except queue.Empty:
                pass
            try:
                self.sensor_q.put_nowait(sample)
            except queue.Full:
                self._dropped += 1

    def _emit(self, event):
        event["t"] = time.time()
        try:
            self.event_q.put_nowait(event)
        except queue.Full:
            log.warning("event_q full, dropping %s", event.get("type"))

    # ------------------------------------------------------------ sending

    def _flush_commands(self):
        while True:
            try:
                cmd = self.command_q.get_nowait()
            except queue.Empty:
                return
            payload = self._encode(cmd)
            if payload is None:
                continue
            if self._client is None:
                log.warning("no ESP32 connected, dropping command %s", cmd)
                continue
            try:
                self._client.sendall(payload)
            except OSError as e:
                log.warning("send failed (%s), closing connection", e)
                self._close_client()

    @staticmethod
    def _encode(cmd):
        kind = cmd.get("type") if isinstance(cmd, dict) else None
        if kind == "vibrate":
            try:
                length = max(0, int(cmd["length"]))
            except (KeyError, TypeError, ValueError):
                log.warning("vibrate command needs integer 'length': %s", cmd)
                return None
            out = {"length": length}
            if cmd.get("intensity") is not None:
                out["intensity"] = max(0, min(100, int(cmd["intensity"])))
            return (json.dumps(out, separators=(",", ":")) + "\n").encode()
        if kind == "calibrate":
            # Not valid JSON, but it is exactly what the firmware looks for.
            return b'{"calibrate_now"}\n'
        log.warning("unknown command: %s", cmd)
        return None


def run_esp32_server(sensor_q, event_q, command_q, stop_event,
                     host="0.0.0.0", port=5000):
    """multiprocessing.Process target."""
    ESP32Communicator(sensor_q, event_q, command_q, stop_event, host, port).run()