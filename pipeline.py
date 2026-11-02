import os
import threading
import time
from datetime import datetime

from camera import grab_frame
from controller import get_controller
from db import log_cycle
from detector import run_detection_from_frame
from timing import compute_timings, LANES

FRAMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)


class LivePipeline:
    def __init__(self):
        self.urls = {l: "" for l in LANES}
        self.state = {
            "running": False,
            "updated": None,
            "lanes": {l: {"count": 0, "error": None, "annotated_filename": None, "frame_ts": None} for l in LANES},
            "timings": None,
        }
        self._thread = None
        self._stop = threading.Event()
        self._interval = 5.0
        self._lock = threading.Lock()

    def set_urls(self, urls):
        with self._lock:
            for l in LANES:
                self.urls[l] = (urls.get(l) or "").strip()

    def start(self):
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        with self._lock:
            self.state["running"] = True
        return True

    def stop(self):
        self._stop.set()
        with self._lock:
            self.state["running"] = False

    def snapshot(self):
        with self._lock:
            return {
                "running": self.state["running"],
                "updated": self.state["updated"],
                "lanes": {l: dict(v) for l, v in self.state["lanes"].items()},
                "timings": self.state["timings"],
            }

    def _save_raw_frame(self, lane, frame):
        try:
            import cv2
            path = os.path.join(FRAMES_DIR, f"{lane}_latest.jpg")
            tmp = path + ".tmp.jpg"
            cv2.imwrite(tmp, frame)
            os.replace(tmp, path)
            with self._lock:
                self.state["lanes"][lane]["frame_ts"] = datetime.now().strftime("%H:%M:%S")
        except Exception as e:
            print(f"frame save failed for {lane}:", e)

    def _loop(self):
        while not self._stop.is_set():
            cycle_start = time.time()
            with self._lock:
                urls = dict(self.urls)

            counts = {}
            for lane in LANES:
                url = urls[lane]
                if not url:
                    counts[lane] = 0
                    with self._lock:
                        self.state["lanes"][lane] = {"count": 0, "error": "no url", "annotated_filename": None, "frame_ts": None}
                    continue

                frame = grab_frame(url)
                if frame is None:
                    counts[lane] = 0
                    with self._lock:
                        self.state["lanes"][lane] = {"count": 0, "error": "grab failed", "annotated_filename": None, "frame_ts": None}
                    continue

                self._save_raw_frame(lane, frame)
                
                try:
                    r = run_detection_from_frame(frame)
                    counts[lane] = r["total"]
                    with self._lock:
                        self.state["lanes"][lane].update({
                            "count": r["total"],
                            "error": None,
                            "annotated_filename": r["annotated_filename"],
                        })
                except Exception as e:
                    counts[lane] = 0
                    with self._lock:
                        self.state["lanes"][lane].update({"count": 0, "error": str(e), "annotated_filename": None})

            timings = compute_timings(counts)
            get_controller().update_timings(timings)
            try:
                log_cycle("live", counts, timings)
            except Exception as e:
                print("db log failed:", e)

            with self._lock:
                self.state["timings"] = timings
                self.state["updated"] = datetime.now().strftime("%H:%M:%S")

            elapsed = time.time() - cycle_start
            self._stop.wait(max(0.5, self._interval - elapsed))


_pipeline = LivePipeline()

def get_pipeline():
    return _pipeline