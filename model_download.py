"""
model_download.py — Downloads the MediaPipe face_landmarker.task model if absent
"""

import os
import sys
import urllib.request
from config import MODEL_URL, MODEL_PATH


def download_model():
    """Download face_landmarker.task from Google's MediaPipe CDN if not present."""
    if os.path.exists(MODEL_PATH):
        return

    print("[DOWNLOAD] face_landmarker.task …")
    tmp = MODEL_PATH + ".part"
    try:
        def _progress(count, block, total):
            done = min(count * block, total)
            pct  = done * 100 / total if total else 0
            bar  = int(pct / 2)
            sys.stdout.write(f"\r  [{'#'*bar}{' '*(50-bar)}] {pct:.0f}%")
            sys.stdout.flush()

        urllib.request.urlretrieve(MODEL_URL, tmp, _progress)
        print()
        os.replace(tmp, MODEL_PATH)
        print("[OK] face_landmarker.task downloaded")

    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(f"Model download failed: {e}")