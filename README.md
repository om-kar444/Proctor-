1) This should be ur structure :
proctorproduction2/
├── yolov8n.pt
└── ai_proctor/
    ├── config.py
    ├── detection.py
    ├── face_landmarker.task
    ├── model_download.py
    ├── proctor.py
    ├── proctor_app.py
    ├── routes.py
    ├── state.py
    ├── yolov8n.pt
    ├── recordings/
    ├── templates/
    │   └── index.html
    ├── static/
    │   ├── css/
    │   │   └── proctor.css
    │   └── js/
    │       └── proctor.js
    └── __pycache__/


2)Requirements.txt
--------------------
flask==3.0.2
opencv-python==4.9.0.80
numpy==1.26.4
mediapipe==0.10.14
ultralytics==8.2.0
torch
torchvision

>pip install -r requirements.txt(Fire this command)
1. Project Overview
AI Proctor is a Flask web app that monitors exam candidates in real time via webcam. It detects 4 types of violations:

Face out of frame for more than 2 seconds
Mobile phone detected on camera (YOLOv8n)
Tab switching or window resize in the browser
Copy / paste actions in the browser


How to Run : 
----------
pip install flask opencv-python numpy mediapipe==0.10.14 ultralytics
cd ai_proctor
python proctor_app.py


Details of all the Functions as what part is performing which operations step by step guide :
------------------------------------------------------------------------------------------

proctor_app.py:
------------------
download_model() → downloads face model before server starts
Flask(__name__) → creates the web server
register_routes(app) → connects all URLs to their functions
app.run(port=5000) → starts server, open localhost:5000

state.py:
-------------
state = {...} → single dict storing all violation counts, shared by all threads
state_lock → prevents two threads writing to state at same time
output_frame → holds the latest camera JPEG, stream reads from here
frame_lock → prevents two threads writing to output_frame at same time
stop_event → when .set() is called, all threads stop their loops and exit

config.py:
--------------
CAMERA_INDEX → which webcam to use
FACE_OUT_SECS → how many seconds face must be missing to count as violation
NO_FACE_CONFIRM_FRAMES → how many consecutive no-face frames before timer starts
CONF_THRESH → YOLO minimum confidence to count a phone detection
PHONE_COOLDOWN_SECS → gap between phone violation counts so it doesn't explode
TARGET_CLASSES → YOLO class 67=phone, 65=remote, both treated as phone
TESSELATION → list of face landmark pairs, each pair draws one line of face mesh
MODEL_PATH → where face_landmarker.task is saved and loaded from

model_download.py:
------------------
download_model()

checks if face_landmarker.task exists → if yes, does nothing
downloads to .part temp file first → renames to final only after full download
if download fails → deletes .part and throws error


detection.py:
----------------
get_yolo() → loads yolov8n.pt once, runs a dummy prediction to warm it up, returns same model every time after that
draw_face_mesh(frame, landmarks) → loops through TESSELATION pairs, draws green lines on face
draw_phone_boxes(frame, detections) → draws green corner brackets around detected phone, adds confidence % badge
draw_hud(frame, ...)

draws Face violations: N counter top-left
draws PHONE DETECTED: N if phone found
if face missing → adds red overlay + progress bar at bottom showing how close to violation
if face present → draws green MONITORING bar at bottom


routes.py:
-----------
gen_frames() → infinite loop, reads output_frame every 1/25 sec, sends it to browser as MJPEG stream
index() → serves index.html when browser opens /
video_feed() → calls gen_frames(), streams live annotated video to browser
api_start()

resets all counters in state
clears stop_event
starts proctor_thread() in background

api_stop() → calls stop_event.set(), all threads exit
api_status() → returns entire state dict as JSON, frontend polls this every second
save_recording() → receives WebM binary from browser, saves to recordings/ folder with timestamp name
api_tab_switch() → increments tab_switch_count by 1
api_copy_paste() → increments copy_paste_count by 1

proctor.py:
----------
camera_reader(cap) → runs in its own thread, reads webcam frame, flips it, pushes to _raw_q (always keeps only latest frame)
yolo_worker(yolo) → runs in its own thread, takes frame from _yolo_q, runs YOLO prediction, pushes detections to _det_q
proctor_thread() — main loop, step by step:

creates 3 queues → _raw_q, _yolo_q, _det_q
loads MediaPipe face landmarker from face_landmarker.task
opens webcam, sets 1280x720 @ 30fps
starts camera_reader thread
starts yolo_worker thread
every frame:

pulls latest frame from _raw_q
resizes to 480x270 → runs MediaPipe face detection
if face found → resets absence timer, draws green mesh lines + red iris dots
if face missing → starts timer, if missing 2+ seconds → increments face_out_count
every 2 frames → sends clean frame to _yolo_q for phone detection
reads latest phone detections from _det_q → if phone found → increments phone_count (max once per PHONE_COOLDOWN_SECS)
calls draw_phone_boxes() and draw_hud() on frame
writes updated counts to state
encodes frame as JPEG → writes to output_frame


when stop_event fires → releases camera, closes landmarker, builds final verdict report, writes to state["verdict"]



