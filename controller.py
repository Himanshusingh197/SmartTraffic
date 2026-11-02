import threading
import time

from timing import LANES


class SignalController:
    def __init__(self):
        self._state = {l: "RED" for l in LANES}
        self._remaining = {l: 0 for l in LANES}
        self._active_lane = None
        self._phase = "idle"
        self._latest_timings = None
        self._lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()

    def update_timings(self, timings_obj):
        with self._lock:
            self._latest_timings = timings_obj

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def get_state(self):
        with self._lock:
            return {
                "signals": dict(self._state),
                "remaining": dict(self._remaining),
                "active": self._active_lane,
                "phase": self._phase,
            }

    def _set_all_red(self):
        self._state = {l: "RED" for l in LANES}
        self._remaining = {l: 0 for l in LANES}

    def _run_phase(self, lane, color, duration, phase_name):
        with self._lock:
            self._set_all_red()
            self._state[lane] = color
            self._active_lane = lane if color != "RED" else None
            self._phase = phase_name
        end = time.time() + duration
        while time.time() < end:
            if self._stop.is_set():
                return
            with self._lock:
                if color != "RED":
                    self._remaining[lane] = max(0, int(round(end - time.time())))
            time.sleep(0.2)

    def _loop(self):
        while not self._stop.is_set():
            with self._lock:
                timings = self._latest_timings
            if not timings:
                with self._lock:
                    self._set_all_red()
                    self._active_lane = None
                    self._phase = "idle"
                time.sleep(0.5)
                continue

            for lane in LANES:
                if self._stop.is_set():
                    return
                t = timings["timings"][lane]
                self._run_phase(lane, "GREEN",  t["green"],  "green")
                self._run_phase(lane, "YELLOW", t["yellow"], "yellow")
                self._run_phase(lane, "RED",    t["all_red"], "all_red")


_controller = SignalController()


def get_controller():
    return _controller