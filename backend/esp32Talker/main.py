"""
Server manager: owns the queues and the child processes.

    ESP32 <--TCP--> [esp32 server process]
                        | sensor_q   (samples)         -> processor process
                        | event_q    (state/calibration/connection)
                        ^ command_q  (vibrate/calibrate) <- processor / anyone

Processes:
    esp32_server : esp32_communicator.run_esp32_server
    processor    : consumes sensor_q, may push to command_q  (placeholder below)

Run:  python server_manager.py
"""

import logging
import multiprocessing as mp
import queue
import signal
import time

from receiver import run_esp32_server

log = logging.getLogger("manager")


# ---------------------------------------------------------------- processor
# Placeholder. Swap SensorProcessor for your real class when you have it.
# Contract: process(sample) is called per sample (~200 Hz) and may return a
# command dict, e.g. {"type": "vibrate", "length": 500, "intensity": 80}.

class SensorProcessor:
    def __init__(self):
        self.count = 0
        self.t0 = time.time()

    def process(self, sample):
        self.count += 1
        if self.count % 200 == 0:
            rate = self.count / (time.time() - self.t0)
            log.info("processor: %d samples (%.0f Hz), last accel=%s",
                     self.count, rate, sample["accelerometer"])
        return None

    def on_event(self, event):
        log.info("event: %s", event)


def run_processor(sensor_q, event_q, command_q, stop_event):
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")
    proc = SensorProcessor()
    while not stop_event.is_set():
        try:
            sample = sensor_q.get(timeout=0.1)
        except queue.Empty:
            sample = None
        if sample is not None:
            cmd = proc.process(sample)
            if cmd:
                command_q.put(cmd)
        # drain device events (actuation / calibration / connection)
        while True:
            try:
                proc.on_event(event_q.get_nowait())
            except queue.Empty:
                break


# ---------------------------------------------------------------- manager

class ServerManager:
    def __init__(self, host="0.0.0.0", port=5000, sensor_q_size=2000):
        ctx = mp.get_context("spawn")  # same behaviour on Windows/macOS/Linux
        self.ctx = ctx
        self.host, self.port = host, port
        self.sensor_q = ctx.Queue(maxsize=sensor_q_size)
        self.event_q = ctx.Queue(maxsize=1000)
        self.command_q = ctx.Queue()
        self.stop_event = ctx.Event()
        self.procs = {}

    def start(self):
        queues = (self.sensor_q, self.event_q, self.command_q, self.stop_event)
        self.procs["esp32_server"] = self.ctx.Process(
            target=run_esp32_server, args=queues + (self.host, self.port),
            name="esp32_server", daemon=True)
        self.procs["processor"] = self.ctx.Process(
            target=run_processor, args=queues,
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

    def watch(self):
        """Block until stopped; restart nothing, just report dead children."""
        while not self.stop_event.is_set():
            for name, p in self.procs.items():
                if not p.is_alive():
                    log.error("%s died (exit code %s), shutting down", name, p.exitcode)
                    self.stop_event.set()
                    break
            time.sleep(0.5)

    def stop(self):
        self.stop_event.set()
        for p in self.procs.values():
            p.join(timeout=3)
            if p.is_alive():
                p.terminate()
        log.info("all processes stopped")


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")
    mgr = ServerManager(port=5000)
    signal.signal(signal.SIGINT, lambda *_: mgr.stop_event.set())
    mgr.start()
    try:
        mgr.watch()
    finally:
        mgr.stop()


if __name__ == "__main__":
    main()