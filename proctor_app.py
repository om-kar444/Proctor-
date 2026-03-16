"""
AI Proctor — Entry Point
========================
Install : pip install flask opencv-python numpy mediapipe==0.10.14 ultralytics
Run     : python proctor_app.py
Open    : http://localhost:5000
"""

import os
from flask import Flask
from model_download import download_model

# Download MediaPipe model before anything else
download_model()

app = Flask(__name__, template_folder="templates", static_folder="static")

# ── Import and register all route blueprints ──────────────────────────
from routes import register_routes
register_routes(app)

# ════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from config import RECORDINGS_DIR
    from detection import _yolo_available

    print("=" * 56)
    print("  AI Proctor  —  http://localhost:5000")
    print(f"  Recordings dir: {RECORDINGS_DIR}")
    print("  YOLO phone detection:", "enabled" if _yolo_available else "disabled")
    print("=" * 56)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)