import os
import time
import uuid

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from controller import get_controller
from db import init_db, recent_cycles, stats as db_stats
from detector import DETECTED_DIR, run_detection
from pipeline import get_pipeline
from timing import compute_timings, LANES

app = Flask(__name__)
init_db()
get_controller().start()

UPLOAD_DIR = os.path.join(app.root_path, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
FRAMES_DIR = os.path.join(app.root_path, "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


def allowed_file(name: str) -> bool:
    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED_EXT


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify(status="ok", service="smart-traffic-backend", version="0.7.0")


@app.route("/api/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        return jsonify(ok=False, error="No file part named 'image'"), 400

    f = request.files["image"]
    if f.filename == "":
        return jsonify(ok=False, error="No file selected"), 400

    if not allowed_file(f.filename):
        return jsonify(ok=False, error="Only png / jpg / jpeg / webp are allowed"), 400

    safe_name = secure_filename(f.filename)
    ext = safe_name.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    f.save(save_path)

    return jsonify(
        ok=True,
        filename=unique_name,
        url=url_for("serve_upload", filename=unique_name),
        size=os.path.getsize(save_path),
    )


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/frames/<path:filename>")
def serve_frame(filename):
    return send_from_directory(FRAMES_DIR, filename)


@app.route("/api/detect/<filename>", methods=["POST"])
def detect(filename):
    safe = secure_filename(filename)
    src = os.path.join(UPLOAD_DIR, safe)
    if not os.path.isfile(src):
        return jsonify(ok=False, error="Uploaded file not found"), 404

    try:
        result = run_detection(src)
    except ImportError:
        return jsonify(ok=False, error="ultralytics not installed. Run: pip install ultralytics==8.3.40"), 500
    except Exception as e:
        return jsonify(ok=False, error=f"Detection failed: {e}"), 500

    return jsonify(
        ok=True,
        counts=result["counts"],
        total=result["total"],
        annotated_url=url_for("serve_detected", filename=result["annotated_filename"]),
        annotated_filename=result["annotated_filename"],
    )


@app.route("/detected/<path:filename>")
def serve_detected(filename):
    return send_from_directory(DETECTED_DIR, filename)


@app.route("/api/timing", methods=["POST"])
def timing_route():
    body = request.get_json(silent=True) or {}
    counts = body.get("counts") or {}
    if not isinstance(counts, dict):
        return jsonify(ok=False, error="counts must be an object"), 400
    try:
        result = compute_timings(counts)
    except Exception as e:
        return jsonify(ok=False, error=f"Timing failed: {e}"), 500
    get_controller().update_timings(result)
    return jsonify(ok=True, lanes=LANES, **result)


@app.route("/api/live/config", methods=["POST"])
def live_config():
    body = request.get_json(silent=True) or {}
    urls = body.get("urls") or {}
    if not isinstance(urls, dict):
        return jsonify(ok=False, error="urls must be an object"), 400
    get_pipeline().set_urls(urls)
    return jsonify(ok=True)


@app.route("/api/live/start", methods=["POST"])
def live_start():
    started = get_pipeline().start()
    return jsonify(ok=True, started=started, running=True)


@app.route("/api/live/stop", methods=["POST"])
def live_stop():
    get_pipeline().stop()
    return jsonify(ok=True, running=False)


@app.route("/api/live")
def live_status():
    return jsonify(ok=True, **get_pipeline().snapshot())


@app.route("/api/history")
def api_history():
    limit = request.args.get("limit", 20, type=int)
    limit = max(1, min(200, limit))
    return jsonify(ok=True, stats=db_stats(), cycles=recent_cycles(limit))


# ---- ESP8266 endpoints ----
@app.route("/api/esp8266/signals")
def esp8266_signals():
    return jsonify(ok=True, **get_controller().get_state())

# Latest status posted by each ESP board, keyed by device name
esp_boards = {}


@app.route("/api/esp8266/status", methods=["POST"])
def esp8266_status_post():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(ok=False, error="Send a JSON object"), 400
    device = str(body.get("device") or "unknown")[:32]
    body["time"] = time.strftime("%H:%M:%S")
    body["last_seen"] = time.time()
    esp_boards[device] = body
    return jsonify(ok=True, received=body)


@app.route("/api/esp8266/status", methods=["GET"])
def esp8266_status_get():
    now = time.time()
    boards = {
        name: {**b, "online": (now - b["last_seen"]) < 15}
        for name, b in esp_boards.items()
    }
    return jsonify(ok=True, boards=boards)


@app.route("/api/export/csv")
def export_csv():
    import csv
    import io

    rows = recent_cycles(limit=1000)
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return (
        buf.getvalue(),
        200,
        {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=traffic_history.csv",
        },
    )


@app.errorhandler(413)
def too_large(_e):
    return jsonify(ok=False, error="File too large (max 10 MB)"), 413

if __name__ == "__main__":
    # Use the PORT environment variable provided by Render, or default to 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)