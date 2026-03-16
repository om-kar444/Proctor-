"""
routes.py — All Flask routes and the MJPEG stream generator
"""

import time
import threading

from flask import Response, render_template, jsonify, request as flask_request

from config  import RECORDINGS_DIR
from state   import state, state_lock, frame_lock, stop_event, output_frame
import state as _state_mod
import proctor as _proctor_mod


# ════════════════════════════════════════════════════════════════════════
#  MJPEG STREAM GENERATOR
# ════════════════════════════════════════════════════════════════════════
def gen_frames():
    """Rate-limited MJPEG generator — sends latest frame at max 25 fps."""
    last_sent = None
    interval  = 1.0 / 25
    next_send = time.time()
    while True:
        now = time.time()
        if now < next_send:
            time.sleep(max(0, next_send - now))
            continue
        with frame_lock:
            f = _state_mod.output_frame
        if f is None or f is last_sent:
            time.sleep(0.01)
            continue
        last_sent = f
        next_send = time.time() + interval
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + f + b"\r\n"


# ════════════════════════════════════════════════════════════════════════
#  ROUTE REGISTRATION
# ════════════════════════════════════════════════════════════════════════
def register_routes(app):

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/video_feed")
    def video_feed():
        return Response(gen_frames(),
                        mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/api/start", methods=["POST"])
    def api_start():
        with state_lock:
            if state["running"]:
                return jsonify({"ok": False, "msg": "Already running"})
            state.update({
                "running"          : True,
                "face_out_count"   : 0,
                "phone_count"      : 0,
                "tab_switch_count" : 0,
                "copy_paste_count" : 0,
                "absent_secs"      : 0.0,
                "no_face_raw"      : False,
                "verdict"          : None,
            })
        stop_event.clear()
        threading.Thread(target=_proctor_mod.proctor_thread, daemon=True).start()
        return jsonify({"ok": True})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        stop_event.set()
        return jsonify({"ok": True})

    @app.route("/api/status")
    def api_status():
        with state_lock:
            return jsonify(dict(state))

    @app.route("/api/save_recording", methods=["POST"])
    def save_recording():
        """Receive WebM blob from browser and save to ./recordings/ folder."""
        import os
        data = flask_request.data
        if not data:
            return jsonify({"ok": False, "msg": "No data"})
        filename = f"recording_{time.strftime('%Y%m%d_%H%M%S')}.webm"
        filepath = os.path.join(RECORDINGS_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(data)
        print(f"[REC] Saved → {filepath}")
        return jsonify({"ok": True, "file": filename})

    @app.route("/api/violation/tab_switch", methods=["POST"])
    def api_tab_switch():
        """Record a tab-switch or window-resize violation."""
        with state_lock:
            if state["running"]:
                state["tab_switch_count"] += 1
                print(f"[TAB] #{state['tab_switch_count']}")
        return jsonify({"ok": True})

    @app.route("/api/violation/copy_paste", methods=["POST"])
    def api_copy_paste():
        """Record a copy/paste violation."""
        with state_lock:
            if state["running"]:
                state["copy_paste_count"] += 1
                print(f"[COPY] #{state['copy_paste_count']}")
        return jsonify({"ok": True})