"""
Server Manager: owns IPC queues, the shared stop event, and child processes.

    ESP32 <--TCP--> [esp32_server process]
                        | sensor_q   (samples)         -> processor process
                        | event_q    (state/calibration/connection) -> this process
                        ^ command_q  (vibrate/calibrate) <- processor / anyone

Processes:
    esp32_server : esp32_communicator.run_esp32_server
    processor    : processor.run_processor (DSP, classifier, episodes, DB)
"""

import logging
import multiprocessing as mp
import queue
import signal

from receiver import run_esp32_server
from tremor_processor import run_processor

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [Manager] %(message)s")
log = logging.getLogger("manager")

JOIN_TIMEOUT_S = 5.0


def _log_event(event):
    ev_type = event.get("type")
    if ev_type == "connection":
        log.info("[EVENT] Connection: connected=%s addr=%s",
                 event.get("connected"), event.get("addr"))
    elif ev_type == "actuation":
        log.info("[EVENT] Actuation: active=%s @ %s%%",
                 event.get("state"), event.get("intensity_hz"))
    elif ev_type == "calibration":
        log.info("[EVENT] Calibration: calibrated=%s", event.get("calibrated"))


def main():
    log.info("Initializing Quell Server Manager...")

    stop_event = mp.Event()
    sensor_q = mp.Queue(maxsize=10000)
    event_q = mp.Queue(maxsize=1000)
    command_q = mp.Queue(maxsize=100)

    p_server = mp.Process(
        target=run_esp32_server,
        args=(sensor_q, event_q, command_q, stop_event),
        kwargs={"host": "192.168.137.2", "port": 5000},
        name="esp32_server",
    )
    p_processor = mp.Process(
        target=run_processor,
        args=(sensor_q, command_q, stop_event),
        name="processor",
    )
    procs = [p_server, p_processor]

    # Signal handlers only set the event; cleanup happens in the main flow.
    def request_stop(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    for p in procs:
        p.start()
    log.info("Child processes started [esp32_server (PID %d), processor (PID %d)].",
             p_server.pid, p_processor.pid)

    try:
        while not stop_event.is_set():
            try:
                _log_event(event_q.get(timeout=0.5))
            except queue.Empty:
                pass

            for p in procs:
                if not p.is_alive():
                    log.error("%s process died (exit code %s). Shutting down.",
                              p.name, p.exitcode)
                    stop_event.set()
                    break
    finally:
        stop_event.set()
        log.info("Stopping child processes...")
        # Drain events so children's queue feeder threads can flush and exit.
        for p in procs:
            p.join(timeout=JOIN_TIMEOUT_S)
            while p.is_alive():
                try:
                    _log_event(event_q.get(timeout=0.1))
                except queue.Empty:
                    pass
                if not p.is_alive():
                    break
                log.warning("%s did not exit in time, terminating.", p.name)
                p.terminate()
                p.join(timeout=2.0)
                break
        log.info("Shutdown complete.")


if __name__ == "__main__":
    main()