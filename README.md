<div style="display:flex; overflow-x:auto; gap:10px;">

<img src="https://github.com/user-attachments/assets/70b90cc3-da5c-454c-86d5-962d26c9fc87" width="400"/>
<img src="https://github.com/user-attachments/assets/9148bd51-c2d9-4f7b-93f5-a7ee339f7cbf" width="400"/>
<img src="https://github.com/user-attachments/assets/f7619cdf-5349-46eb-9e29-076ee3089655" width="400"/>
<img src="https://github.com/user-attachments/assets/7bdaa762-1220-40cf-800c-b5f36523a044" width="400"/>
<img src="https://github.com/user-attachments/assets/1d5b1f0c-b63b-469e-8ee0-084aad3104c2" width="400"/>
<img src="https://github.com/user-attachments/assets/c6f0b52b-1e06-46c7-914e-7666c869882e" width="400"/>
<img src="https://github.com/user-attachments/assets/65922850-76d6-4ad1-bd2d-39c19729dea0" width="400"/>
<img src="https://github.com/user-attachments/assets/f25b7919-eb2d-4ca3-88be-dae234603260" width="400"/>
<img src="https://github.com/user-attachments/assets/b3257d6c-c5df-4263-8827-00ff562f6717" width="400"/>

</div>




# AI Proctoring System

## 1. Project Structure

```
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
```

---

# 2. Requirements

Create a file named **requirements.txt**

```
flask==3.0.2
opencv-python==4.9.0.80
numpy==1.26.4
mediapipe==0.10.14
ultralytics==8.2.0
torch
torchvision
```

Install dependencies:

```
pip install -r requirements.txt
```

---

# 3. Project Overview

**AI Proctor** is a Flask web application that monitors exam candidates in real time using a webcam.

It detects **4 types of violations:**

1. Face out of frame for more than **2 seconds**
2. **Mobile phone detected** on camera (YOLOv8n)
3. **Tab switching or window resize** in the browser
4. **Copy / paste actions** in the browser

---

# 4. How to Run

Install dependencies:

```
pip install flask opencv-python numpy mediapipe==0.10.14 ultralytics
```

Navigate to the project folder:

```
cd ai_proctor
```

Run the server:

```
python proctor_app.py
```

Open browser:

```
http://localhost:5000
```

---

# 5. Functionality Breakdown

## proctor_app.py

• `download_model()`
Downloads the face model before the server starts.

• `Flask(__name__)`
Creates the web server.

• `register_routes(app)`
Connects all URLs to their functions.

• `app.run(port=5000)`
Starts the server.

---

## state.py

• `state = {...}`
Stores all violation counters shared between threads.

• `state_lock`
Prevents two threads from writing to state at the same time.

• `output_frame`
Holds the latest processed camera frame.

• `frame_lock`
Ensures only one thread writes to the frame.

• `stop_event`
Stops all running threads when triggered.

---

## config.py

• `CAMERA_INDEX` → Which webcam to use
• `FACE_OUT_SECS` → Time face must be missing before violation
• `NO_FACE_CONFIRM_FRAMES` → Frames required before timer starts
• `CONF_THRESH` → Minimum YOLO confidence threshold
• `PHONE_COOLDOWN_SECS` → Prevents repeated phone detection spam
• `TARGET_CLASSES` → YOLO classes treated as phone
• `TESSELATION` → Face mesh landmark pairs
• `MODEL_PATH` → Path for `face_landmarker.task`

---

## model_download.py

`download_model()`

• Checks if the model exists
• Downloads it if missing
• Uses `.part` temporary file to avoid corrupted downloads

---

## detection.py

`get_yolo()`
Loads YOLOv8 model once and warms it up.

`draw_face_mesh(frame, landmarks)`
Draws face mesh lines.

`draw_phone_boxes(frame, detections)`
Draws bounding boxes for detected phones.

`draw_hud(frame)`

Displays:

• Face violation counter
• Phone detection counter
• Monitoring status bar
• Warning overlay when face missing

---

## routes.py

`gen_frames()`
Streams video frames to browser.

`index()`
Loads the web interface.

`video_feed()`
Streams MJPEG camera feed.

`api_start()`

• Resets violation counters
• Starts the proctor thread

`api_stop()`
Stops all monitoring threads.

`api_status()`
Returns system status to frontend.

`save_recording()`
Stores WebM recordings.

`api_tab_switch()`
Increments tab switch violations.

`api_copy_paste()`
Increments copy/paste violations.

---

## proctor.py

### Threads

`camera_reader()`
Reads frames from webcam continuously.

`yolo_worker()`
Runs YOLO detection on frames.

---

### Main Proctor Loop

`proctor_thread()` performs:

1. Creates processing queues
2. Loads MediaPipe face landmarker
3. Opens webcam (1280x720 @ 30 FPS)
4. Starts camera reader thread
5. Starts YOLO worker thread

For each frame:

• Gets latest frame from queue
• Runs face detection
• Draws face mesh
• Tracks absence timer

If face missing for **2 seconds** → violation added.

Every **2 frames**

• Sends frame to YOLO detection queue

If phone detected

• Increments phone violation counter

Final frame

• Draws HUD
• Encodes frame to JPEG
• Streams to browser

---

## Shutdown

When `stop_event` triggers:

• Camera is released
• Face landmarker is closed
• Final violation report is generated
