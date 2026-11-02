import os
import uuid
from collections import Counter

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

DETECTED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "detected")
os.makedirs(DETECTED_DIR, exist_ok=True)

_model = None


def _get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO("yolov8n.pt")
    return _model


def _count_and_annotate(r):
    import cv2

    if r.boxes is None or r.boxes.cls is None:
        cls_ids = []
    else:
        cls_ids = r.boxes.cls.cpu().numpy().astype(int).tolist()

    raw_counts = Counter(cls_ids)
    vehicle_counts = {name: raw_counts.get(cid, 0) for cid, name in VEHICLE_CLASSES.items()}
    total = sum(vehicle_counts.values())

    annotated = r.plot()
    annotated_name = f"{uuid.uuid4().hex}.jpg"
    cv2.imwrite(os.path.join(DETECTED_DIR, annotated_name), annotated)

    return {
        "counts": vehicle_counts,
        "total": total,
        "annotated_filename": annotated_name,
    }


def run_detection(image_path, conf=0.25):
    model = _get_model()
    results = model(
        image_path,
        conf=conf,
        classes=list(VEHICLE_CLASSES.keys()),
        verbose=False,
    )
    return _count_and_annotate(results[0])


def run_detection_from_frame(frame, conf=0.25):
    model = _get_model()
    results = model(
        frame,
        conf=conf,
        classes=list(VEHICLE_CLASSES.keys()),
        verbose=False,
    )
    return _count_and_annotate(results[0])


def detect_from_frame_with_lanes(frame, conf=0.25):
    """
    Runs YOLO once on the full frame, then assigns each detected vehicle
    to one of 4 lanes based on its center point's quadrant.
    """
    import cv2

    model = _get_model()
    results = model(
        frame,
        conf=conf,
        classes=list(VEHICLE_CLASSES.keys()),
        verbose=False,
    )
    r = results[0]
    h, w = frame.shape[:2]

    # 4 quadrant ROIs — tweak these to match your camera angle
    rois = {
        "north": (w // 4, 0,         3 * w // 4, h // 2),
        "south": (w // 4, h // 2,    3 * w // 4, h),
        "east":  (w // 2, h // 4,    w,          3 * h // 4),
        "west":  (0,      h // 4,    w // 2,     3 * h // 4),
    }

    counts = {lane: 0 for lane in rois}

    if r.boxes is not None and len(r.boxes) > 0:
        boxes = r.boxes.xyxy.cpu().numpy()
        for box in boxes:
            cx = (box[0] + box[2]) / 2
            cy = (box[1] + box[3]) / 2
            for lane, (x1, y1, x2, y2) in rois.items():
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    counts[lane] += 1
                    break

    annotated = r.plot()
    for lane, (x1, y1, x2, y2) in rois.items():
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (99, 102, 241), 2)
        cv2.putText(annotated, f"{lane}: {counts[lane]}", (x1 + 5, y1 + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (99, 102, 241), 2)

    annotated_name = f"{uuid.uuid4().hex}.jpg"
    cv2.imwrite(os.path.join(DETECTED_DIR, annotated_name), annotated)

    return {
        "counts": counts,
        "total": sum(counts.values()),
        "annotated_filename": annotated_name,
    }