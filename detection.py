"""
detection.py — YOLO model loader and OpenCV drawing helpers
"""

import threading
import numpy as np
import cv2

from config import (
    INFER_SIZE, TARGET_CLASSES, CONF_THRESH, IOU_THRESH,
    TESSELATION, BOX_COLOR, TEXT_BG,
)

# ── YOLO availability check ──────────────────────────────────────────────
try:
    from ultralytics import YOLO
    _yolo_available = True
except ImportError:
    print("[WARN] ultralytics not installed — phone detection disabled")
    _yolo_available = False

FONT = cv2.FONT_HERSHEY_SIMPLEX

# ════════════════════════════════════════════════════════════════════════
#  YOLO MODEL LOADER (lazy singleton)
# ════════════════════════════════════════════════════════════════════════
_yolo_model      = None
_yolo_model_lock = threading.Lock()


def get_yolo():
    """Return a warm YOLOv8n model, loading it once on first call."""
    global _yolo_model
    if not _yolo_available:
        return None
    with _yolo_model_lock:
        if _yolo_model is None:
            print("[*] Loading YOLOv8n …")
            m = YOLO("yolov8n.pt")
            # Warm-up inference so first real call isn't slow
            m.predict(
                np.zeros((INFER_SIZE, INFER_SIZE, 3), dtype="uint8"),
                classes=list(TARGET_CLASSES.keys()),
                imgsz=INFER_SIZE,
                verbose=False,
            )
            _yolo_model = m
            print("[OK] YOLO ready")
    return _yolo_model


# ════════════════════════════════════════════════════════════════════════
#  DRAW HELPERS
# ════════════════════════════════════════════════════════════════════════
def draw_face_mesh(frame, landmarks):
    """Render the tesselation wire-frame over a detected face."""
    h, w = frame.shape[:2]
    for a, b in TESSELATION:
        if a < len(landmarks) and b < len(landmarks):
            x1 = int(landmarks[a].x * w); y1 = int(landmarks[a].y * h)
            x2 = int(landmarks[b].x * w); y2 = int(landmarks[b].y * h)
            cv2.line(frame, (x1, y1), (x2, y2), (60, 100, 60), 1, cv2.LINE_AA)


def draw_phone_boxes(frame, detections):
    """Draw corner-bracket bounding boxes and confidence badges for phones."""
    for (x1, y1, x2, y2), conf, label in detections:
        cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 2)
        L = 12
        for px, py, dx, dy in [
            (x1, y1,  1,  1), (x2, y1, -1,  1),
            (x1, y2,  1, -1), (x2, y2, -1, -1)
        ]:
            cv2.line(frame, (px, py), (px + dx * L, py), BOX_COLOR, 3)
            cv2.line(frame, (px, py), (px, py + dy * L), BOX_COLOR, 3)

        badge = f"{label} {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(badge, FONT, 0.48, 1)
        cv2.rectangle(frame, (x1, y1 - th - 7), (x1 + tw + 6, y1), TEXT_BG, -1)
        cv2.putText(frame, badge, (x1 + 3, y1 - 4), FONT, 0.48, (200, 200, 200), 1)


def draw_hud(frame, face_out_count, absent_secs, no_face_raw, phone_count):
    """Render the heads-up display: violation counters, absence bar and status bar."""
    h, w = frame.shape[:2]

    # Face violation counter
    face_col = (30, 60, 255) if face_out_count else (30, 220, 80)
    cv2.putText(frame, f"Face violations: {face_out_count}",
                (14, 32), FONT, 0.72, face_col, 2, cv2.LINE_AA)

    # Phone counter
    if phone_count > 0:
        cv2.putText(frame, f"PHONE DETECTED: {phone_count}",
                    (14, 62), FONT, 0.72, (0, 80, 255), 2, cv2.LINE_AA)

    if no_face_raw:
        pct     = min(absent_secs / 2.0, 1.0)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 140), -1)
        cv2.addWeighted(overlay, 0.08 + 0.30 * pct, frame, 0.92 - 0.30 * pct, 0, frame)
        label = ("!! FACE OUT — VIOLATION !!" if pct >= 1.0
                 else f"No face  {absent_secs:.1f}s / 2s")
        col   = (0, 0, 255) if pct >= 1.0 else (0, 200, 255)
        cv2.putText(frame, label, (w // 2 - 220, h // 2 - 20),
                    FONT, 0.82, col, 2, cv2.LINE_AA)
        bar_w = int(pct * (w - 40))
        cv2.rectangle(frame, (20, h - 30), (20 + bar_w, h - 10), col, -1)
        cv2.rectangle(frame, (20, h - 30), (w - 20, h - 10), (200, 200, 200), 1)
    else:
        bar_h = 36
        cv2.rectangle(frame, (0, h - bar_h), (w, h), (15, 15, 15), -1)
        cv2.putText(frame, "MONITORING", (12, h - 9), FONT, 0.68, (80, 200, 100), 2)