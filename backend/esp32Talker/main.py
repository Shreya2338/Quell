"""
Server manager: owns the queues and the child processes.

    ESP32 <--TCP--> [esp32 server process]
                        | sensor_q   (samples)         -> processor process
                        | event_q    (state/calibration/connection) -> manager (logged here)
                        ^ command_q  (vibrate/calibrate) <- processor / anyone

Processes:
    esp32_server : esp32_communicator.run_esp32_server
    processor    : processor.run_processor (DSP/classifier, Supabase, vibration triggers)

Run:  python server_manager.py
"""

import logging
import multiprocessing as mp
import queue
import signal

from receiver import run_esp32_server
from tremor_processor import run_processor

log = logging.getLogger("manager")


class ServerManager:
    def __init__(self, host="0.0.0.0", port=5000, sensor_q_size=10000):
        ctx = mp.get_context("spawn")  # same behaviour on Windows/macOS/Linux
        self.ctx = ctx
        self.host, self.port = host, port
        self.sensor_q = ctx.Queue(maxsize=sensor_q_size)
        self.event_q = ctx.Queue(maxsize=1000)
        self.command_q = ctx.Queue(maxsize=100)
        self.stop_event = ctx.Event()
        self.procs = {}

    def start(self):
        self.procs["esp32_server"] = self.ctx.Process(
            target=run_esp32_server,
            args=(self.sensor_q, self.event_q, self.command_q, self.stop_event,
                  self.host, self.port),
            name="esp32_server", daemon=True)
        self.procs["processor"] = self.ctx.Process(
            target=run_processor,
            args=(self.sensor_q, self.command_q, self.stop_event),
            name="processor", daemon=True)
        for p in self.procs.values():
            p.start()
            log.info("started %s (pid %s)", p.name, p.pid)

    # convenience API usable from any process holding command_q
    def vibrate(self, length_ms, intensity=None):
        self.command_q.put({"type": "vibrate", "length": length_ms,
                            "intensity": intensity})

    def calibrate(self):
        self.command_q.put({"type": "calibrate"})

    def _log_event(self, event):
        kind = event.get("type")
        if kind == "connection":
            log.info("[EVENT] Connection: connected=%s addr=%s",
                     event.get("connected"), event.get("addr"))
        elif kind == "actuation":
            log.info("[EVENT] Actuation: active=%s @ %d Hz",
                     event.get("state"), event.get("intensity_hz"))
        elif kind == "calibration":
            log.info("[EVENT] Calibration: calibrated=%s", event.get("calibrated"))

    def watch(self):
        """Block until stopped; log device events and report dead children."""
        while not self.stop_event.is_set():
            try:
                self._log_event(self.event_q.get(timeout=0.5))
            except queue.Empty:
                pass
            for name, p in self.procs.items():
                if not p.is_alive():
                    log.error("%s died (exit code %s), shutting down", name, p.exitcode)
                    self.stop_event.set()
                    break

    def stop(self):
        self.stop_event.set()
        for p in self.procs.values():
            p.join(timeout=5)  # processor may be saving an open episode
            if p.is_alive():
                p.terminate()
        log.info("all processes stopped")


def main():
    logging.basicConfig(level=logging.INFO,
                        format="[%(asctime)s] [%(name)s] %(message)s")
    log.info("Initializing Quell Server Manager...")
    mgr = ServerManager(port=5000)
    signal.signal(signal.SIGINT, lambda *_: mgr.stop_event.set())
    signal.signal(signal.SIGTERM, lambda *_: mgr.stop_event.set())
    mgr.start()
    try:
        mgr.watch()
    finally:
        mgr.stop()


if __name__ == "__main__":
    main()