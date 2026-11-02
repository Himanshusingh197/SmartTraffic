import urllib.request

import cv2
import numpy as np


def _grab_still(url, timeout=5):
    """Fetch a single JPEG over HTTP. Best for IP Webcam's /shot.jpg."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        if not data:
            print(f"[camera] empty response from {url}")
            return None
        arr = np.frombuffer(data, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            print(f"[camera] imdecode failed (bytes={len(data)}) from {url}")
        return frame
    except Exception as e:
        print(f"[camera] still-grab failed for {url}: {e}")
        return None


def _grab_stream_frame(url, timeout=5):
    """Grab one frame from a video stream (MJPEG, RTSP). Best for IP Webcam's /video."""
    try:
        cap = cv2.VideoCapture(url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)
        if not cap.isOpened():
            cap.release()
            print(f"[camera] could not open stream {url}")
            return None
        ok, frame = cap.read()
        cap.release()
        return frame if ok else None
    except Exception as e:
        print(f"[camera] stream-grab failed for {url}: {e}")
        return None


def grab_frame(url, timeout=5):
    if not url:
        return None
    url = url.strip()
    low = url.lower()

    # IP Webcam still-image endpoints → urllib only (no ffmpeg warnings)
    if "/shot" in low or "/photo" in low or low.endswith((".jpg", ".jpeg", ".png")):
        return _grab_still(url, timeout)

    # Video stream endpoints → cv2 VideoCapture only
    if (
        "/video" in low
        or "/videofeed" in low
        or ".mjpg" in low
        or low.startswith(("rtsp://", "rtmp://"))
    ):
        return _grab_stream_frame(url, timeout)

    # Unknown URL → try still first, then stream
    frame = _grab_still(url, timeout)
    return frame if frame is not None else _grab_stream_frame(url, timeout)