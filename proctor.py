"""
proctor.py — Camera reader thread, YOLO worker thread, main proctor loop
"""

import os
import cv2
import json
import time
import queue
import threading
import numpy as np
import mediapipe as mp

from mediapipe.tasks.python        import BaseOptions
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode

from config    import (CAMERA_INDEX, FACE_OUT_SECS, NO_FACE_CONFIRM_FRAMES,
                       CONF_THRESH, IOU_THRESH, TARGET_CLASSES,
                       PHONE_COOLDOWN_SECS, TESSELATION, MODEL_PATH)
from detection import get_yolo, draw_phone_boxes, draw_hud
from state     import state, state_lock, frame_lock, stop_event
import state as _state_mod

# ── Internal pipeline queues (created fresh each session) ───────────────
_raw_q  = None   # camera frames  (maxsize=1, drop-on-full)
_yolo_q = None   # frames for YOLO (maxsize=1, drop-on-full)
_det_q  = None   # YOLO detections (maxsize=1, drop-on-full)


# ════════════════════════════════════════════════════════════════════════
#  CAMERA READER THREAD
# ════════════════════════════════════════════════════════════════════════
def camera_reader(cap):
    """Read camera frames and push only the latest to the raw queue."""
    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            stop_event.set()
            break
        frame = cv2.flip(frame, 1)          # mirror for natural view
        try: _raw_q.get_nowait()            # drop stale frame
        except Exception: pass
        try: _raw_q.put_nowait(frame)       # push latest
        except Exception: pass


# ════════════════════════════════════════════════════════════════════════
#  YOLO WORKER THREAD
# ════════════════════════════════════════════════════════════════════════
def yolo_worker(yolo):
    """Run YOLO phone detection on clean frames; push results to det queue."""
    while not stop_event.is_set():
        try:
            frame = _yolo_q.get(timeout=0.5)
        except Exception:
            continue

        results = yolo.predict(
            frame,
            classes=list(TARGET_CLASSES.keys()),
            imgsz=640,
            conf=CONF_THRESH,
            iou=IOU_THRESH,
            augment=True,    # multi-angle augment catches sideways/rotated phones
            verbose=False,
            half=False,      # CPU does not support FP16
        )
        detections = [
            ((int(b.xyxy[0][0]), int(b.xyxy[0][1]),
              int(b.xyxy[0][2]), int(b.xyxy[0][3])),
             float(b.conf[0]),
             TARGET_CLASSES.get(int(b.cls[0]), "phone"))
            for r in results for b in r.boxes
        ]
        try: _det_q.get_nowait()            # drop stale result
        except Exception: pass
        try: _det_q.put_nowait(detections)  # push latest
        except Exception: pass


# ════════════════════════════════════════════════════════════════════════
#  MAIN PROCTOR THREAD
# ════════════════════════════════════════════════════════════════════════
def proctor_thread():
    """Main proctoring loop: face detection + phone detection + HUD drawing."""
    global _raw_q, _yolo_q, _det_q

    _raw_q  = queue.Queue(maxsize=1)
    _yolo_q = queue.Queue(maxsize=1)
    _det_q  = queue.Queue(maxsize=1)

    # ── MediaPipe face landmarker ────────────────────────────────────────
    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionTaskRunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=False,
        min_face_detection_confidence=0.3,
        min_face_presence_confidence=0.3,
        min_tracking_confidence=0.3,
    )
    landmarker = FaceLandmarker.create_from_options(options)

    # ── Open camera ─────────────────────────────────────────────────────
    cap = cv2.VideoCapture(
        CAMERA_INDEX,
        cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY
    )
    if not cap.isOpened():
        print("[ERROR] Cannot open camera.")
        with state_lock:
            state["running"] = False
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)
    cap.set(cv2.CAP_PROP_FPS,          30)

    # ── Spin up sub-threads ──────────────────────────────────────────────
    cam_t = threading.Thread(target=camera_reader, args=(cap,), daemon=True)
    cam_t.start()

    yolo = get_yolo()
    if yolo is not None:
        yolo_t = threading.Thread(target=yolo_worker, args=(yolo,), daemon=True)
        yolo_t.start()

    # ── Per-session counters / state ─────────────────────────────────────
    face_out_count       = 0
    phone_count          = 0
    absent_since         = None
    face_was_absent      = False
    no_face_streak       = 0
    session_start        = time.time()
    frame_n              = 0
    obj_detections       = []
    yolo_frame_skip      = 0
    phone_present        = False
    phone_last_seen      = 0.0
    phone_violation_time = 0.0

    with state_lock:
        state["session_start"] = session_start

    print("[INFO] Proctoring started.")

    # ── Main loop ────────────────────────────────────────────────────────
    while not stop_event.is_set():

        try:
            frame = _raw_q.get(timeout=0.2)
        except Exception:
            continue

        now   = time.time()
        ts_ms = int((now - session_start) * 1000)
        frame_n += 1

        h_f, w_f  = frame.shape[:2]
        clean_frame = frame.copy()          # keep clean copy for YOLO

        # ── Face detection ───────────────────────────────────────────────
        small  = cv2.resize(frame, (480, 270), interpolation=cv2.INTER_LINEAR)
        rgb    = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect_for_video(mp_img, ts_ms)

        face_detected = bool(result.face_landmarks)
        absent_secs   = 0.0

        if face_detected:
            no_face_streak = 0
            if absent_since is not None:
                absent_since    = None
                face_was_absent = False
            lms = result.face_landmarks[0]
            for a, b in TESSELATION:
                if a < len(lms) and b < len(lms):
                    x1 = int(lms[a].x * w_f); y1 = int(lms[a].y * h_f)
                    x2 = int(lms[b].x * w_f); y2 = int(lms[b].y * h_f)
                    cv2.line(frame, (x1,y1),(x2,y2),(60,100,60),1,cv2.LINE_AA)
            for idx in [468, 473]:
                if idx < len(lms):
                    cx = int(lms[idx].x * w_f)
                    cy = int(lms[idx].y * h_f)
                    cv2.circle(frame,(cx,cy),5,(0,0,255),-1,cv2.LINE_AA)
        else:
            no_face_streak += 1
            if no_face_streak >= NO_FACE_CONFIRM_FRAMES:
                if absent_since is None:
                    absent_since    = now
                    face_was_absent = False
                absent_secs = now - absent_since
                if absent_secs >= FACE_OUT_SECS and not face_was_absent:
                    face_out_count += 1
                    face_was_absent = True
                    print(f"[VIOLATION] Face out — total: {face_out_count}")

        no_face_raw = (no_face_streak >= NO_FACE_CONFIRM_FRAMES)

        # ── YOLO phone detection ─────────────────────────────────────────
        if yolo is not None:
            yolo_frame_skip += 1
            if yolo_frame_skip >= 2:
                yolo_frame_skip = 0
                try: _yolo_q.get_nowait()
                except Exception: pass
                try: _yolo_q.put_nowait(clean_frame)
                except Exception: pass

            try:
                new_dets     = _det_q.get_nowait()
                detected_now = any(l == "phone" for _,_,l in new_dets)

                if detected_now:
                    phone_last_seen = now
                    if not phone_present:
                        phone_present = True
                    if now - phone_violation_time >= PHONE_COOLDOWN_SECS:
                        phone_count          += 1
                        phone_violation_time  = now
                        print(f"[VIOLATION] Phone detected — violation #{phone_count}")
                else:
                    if phone_present and (now - phone_last_seen > PHONE_COOLDOWN_SECS):
                        phone_present = False

                obj_detections = new_dets
            except Exception:
                pass

        # ── Overlay drawing ──────────────────────────────────────────────
        draw_phone_boxes(frame, obj_detections)
        draw_hud(frame, face_out_count, absent_secs, no_face_raw, len(obj_detections))

        # ── Publish state ────────────────────────────────────────────────
        with state_lock:
            state["face_out_count"] = face_out_count
            state["phone_count"]    = phone_count
            state["absent_secs"]    = round(absent_secs, 1)
            state["no_face_raw"]    = no_face_raw

        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with frame_lock:
            _state_mod.output_frame = buf.tobytes()

    # ── Cleanup ──────────────────────────────────────────────────────────
    stop_event.set()
    cap.release()
    landmarker.close()

    duration = round(time.time() - session_start, 2)
    with state_lock:
        fc  = state["face_out_count"]
        pc  = state["phone_count"]
        tc  = state["tab_switch_count"]
        cpc = state["copy_paste_count"]
        total_v = fc + (1 if pc > 0 else 0) + tc + cpc
        report = {
            "session_duration_seconds" : duration,
            "face_out_violations"      : fc,
            "object_detections"        : pc,
            "tab_switch_violations"    : tc,
            "copy_paste_violations"    : cpc,
            "total_violations"         : total_v,
        }
        state["running"] = False
        state["verdict"] = report

    print(json.dumps(report, indent=2))