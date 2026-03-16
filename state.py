"""
state.py — Shared mutable state, frame buffer, and threading primitives
"""

import threading

# ── Shared proctoring state (protected by state_lock) ──────────────────
state = {
    "running"          : False,
    "face_out_count"   : 0,
    "phone_count"      : 0,
    "tab_switch_count" : 0,
    "copy_paste_count" : 0,
    "absent_secs"      : 0.0,
    "no_face_raw"      : False,
    "session_start"    : None,
    "verdict"          : None,
}
state_lock = threading.Lock()

# ── Latest JPEG frame for MJPEG streaming (protected by frame_lock) ────
output_frame = None
frame_lock   = threading.Lock()

# ── Stop signal: set() to gracefully terminate the proctor thread ───────
stop_event = threading.Event()