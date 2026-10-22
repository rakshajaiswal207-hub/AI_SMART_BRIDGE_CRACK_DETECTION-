"""Flask back end for the bridge crack inspection prototype.

Routes match Table 9.3:

    POST /upload       image from the ESP32-CAM or the dashboard
    GET  /             dashboard
    GET  /history      inspection records as JSON
    GET  /image/<id>   original, processed mask, or highlighted result
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, abort, jsonify, render_template, request, send_file

import config
import database
from crack_detection import detect_cracks
from sample_images import save_samples

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_BYTES
PROCESSING_MS: dict[int, int] = {}


def prepare() -> None:
    for directory in (
        config.UPLOAD_DIR,
        config.RESULT_DIR,
        config.PROCESSED_DIR,
        config.SAMPLE_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    detail = database.init_db()
    save_samples(config.SAMPLE_DIR)
    print(f"Records: {detail}")


@app.route("/")
def dashboard():
    history = database.list_inspections()
    latest = history[0] if history else None
    return render_template(
        "dashboard.html",
        latest=latest,
        history=history,
        db_engine=database.ENGINE_DETAIL,
    )


@app.route("/upload", methods=["POST"])
def upload():
    payload = _read_upload()
    if not payload:
        return jsonify(error="No image was received. Send a JPEG in the request body or as the form field 'image'."), 400

    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return jsonify(error="The file is not a readable image."), 400

    image = _limit_size(image)
    started = time.perf_counter()
    try:
        highlighted, status, region_count, mask = detect_cracks(image)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S_%f")
    original_path = config.UPLOAD_DIR / f"{stamp}_original.jpg"
    result_path = config.RESULT_DIR / f"{stamp}_result.jpg"
    processed_path = config.PROCESSED_DIR / f"{stamp}_processed.png"

    if not cv2.imwrite(str(original_path), image, [int(cv2.IMWRITE_JPEG_QUALITY), 92]):
        return jsonify(error="Could not save the original image."), 500
    if not cv2.imwrite(str(result_path), highlighted, [int(cv2.IMWRITE_JPEG_QUALITY), 92]):
        return jsonify(error="Could not save the highlighted image."), 500
    if not cv2.imwrite(str(processed_path), mask):
        return jsonify(error="Could not save the processed image."), 500

    inspection_id = database.insert_inspection(
        captured_date=now.date().isoformat(),
        captured_time=now.strftime("%H:%M:%S"),
        original_path=_relative(original_path),
        result_path=_relative(result_path),
        status=status,
        region_count=region_count,
    )
    PROCESSING_MS[inspection_id] = elapsed_ms
    print(
        f"inspection {inspection_id}: {status}, regions={region_count}, processing={elapsed_ms} ms"
    )
    return jsonify(
        id=inspection_id,
        status=status,
        region_count=region_count,
        captured_date=now.date().isoformat(),
        captured_time=now.strftime("%H:%M:%S"),
        processing_ms=elapsed_ms,
    )


@app.route("/history")
def history():
    rows = database.list_inspections()
    return jsonify(
        [
            {
                "id": row["id"],
                "captured_date": row["captured_date"],
                "captured_time": row["captured_time"],
                "status": row["status"],
                "region_count": row["region_count"],
                "processing_ms": PROCESSING_MS.get(row["id"]),
            }
            for row in rows
        ]
    )


@app.route("/image/<int:image_id>")
def serve_image(image_id: int):
    kind = request.args.get("type", "original")
    record = database.get_inspection(image_id)
    if record is None:
        abort(404)

    if kind == "original":
        stored = record["original_path"]
    elif kind == "result":
        stored = record["result_path"]
    elif kind == "processed":
        stored = _processed_from_original(record["original_path"])
    else:
        abort(404)

    path = (config.ROOT / stored).resolve()
    data_root = (config.ROOT / "data").resolve()
    if not path.is_relative_to(data_root) or not path.is_file():
        abort(404)

    response = send_file(path)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="Image is larger than 8 MB."), 413


def _read_upload() -> bytes:
    if request.files:
        upload = (
            request.files.get("image")
            or request.files.get("file")
            or next(iter(request.files.values()))
        )
        return upload.read()
    return request.get_data() or b""


def _limit_size(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= config.MAX_IMAGE_SIDE:
        return image
    scale = config.MAX_IMAGE_SIDE / longest
    return cv2.resize(
        image,
        (int(width * scale), int(height * scale)),
        interpolation=cv2.INTER_AREA,
    )


def _relative(path: Path) -> str:
    return path.resolve().relative_to(config.ROOT).as_posix()


def _processed_from_original(original_path: str) -> str:
    name = Path(original_path).name.replace("_original.jpg", "_processed.png")
    return f"data/processed/{name}"


prepare()


if __name__ == "__main__":
    print(f"Dashboard: http://127.0.0.1:{config.PORT}/")
    print("ESP32-CAM should POST JPEG frames to /upload on this computer's LAN address.")
    app.run(host=config.HOST, port=config.PORT, debug=False)