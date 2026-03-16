"""
config.py — All configuration constants for AI Proctor
"""

import os

# ── Camera ──────────────────────────────────────────────────────────────
CAMERA_INDEX = 0

# ── Face / Proctor ──────────────────────────────────────────────────────
FACE_OUT_SECS          = 2.0
NO_FACE_CONFIRM_FRAMES = 2

# ── Mobile / Object detector ────────────────────────────────────────────
CONF_THRESH    = 0.20
IOU_THRESH     = 0.45
INFER_EVERY    = 1
INFER_SIZE     = 640
TARGET_CLASSES = {
    67: "phone",   # upright phone
    65: "phone",   # remote — YOLO often classifies horizontal phones as remotes
}

# Phone violation debounce
PHONE_COOLDOWN_SECS = 2.0

# ── Recordings folder ───────────────────────────────────────────────────
RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# ── MediaPipe model ─────────────────────────────────────────────────────
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "face_landmarker.task")

# ── Face mesh tesselation edges ─────────────────────────────────────────
TESSELATION = [
    (10,338),(338,297),(297,332),(332,284),(284,251),(251,389),(389,356),
    (356,454),(454,323),(323,361),(361,288),(288,397),(397,365),(365,379),
    (379,378),(378,400),(400,377),(377,152),(152,148),(148,176),(176,149),
    (149,150),(150,136),(136,172),(172,58),(58,132),(132,93),(93,234),
    (234,127),(127,162),(162,21),(21,54),(54,103),(103,67),(67,109),
    (109,10),
]

# ── Drawing constants ───────────────────────────────────────────────────
FONT      = None   # set at runtime after cv2 is imported
BOX_COLOR = (0, 220, 100)
TEXT_BG   = (20, 20, 20)