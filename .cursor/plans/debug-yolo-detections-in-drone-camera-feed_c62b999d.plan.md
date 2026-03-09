---
name: debug-yolo-detections-in-drone-camera-feed
overview: Investigate and fix why YOLO object detection boxes are not appearing on the drone camera feed in the web UI, even though the backend has YOLO integration wired into camera frames.
todos:
  - id: verify-ui-api-wiring
    content: Verify the web UI requests `/drones/{id}/camera/frame?type=scene` from the correct API base URL when showing the camera feed.
    status: completed
  - id: check-yolo-loading
    content: Check that `ultralytics` is installed and YOLO loads successfully in `_get_yolo_model()` with clear logs.
    status: completed
  - id: instrument-yolo-detection
    content: Add logging and (temporarily) lower thresholds in `_run_yolo_detection()` to confirm detections are happening.
    status: completed
  - id: validate-drawn-boxes
    content: Save a few debug frames from `_run_yolo_detection()` to disk and confirm bounding boxes and labels appear in the images before encoding.
    status: completed
  - id: test-end-to-end
    content: Fetch a frame directly from the API, verify boxes in the JPEG, then confirm they appear in the web UI camera feed.
    status: completed
isProject: false
---

## Goals

- **Ensure YOLO runs on each `scene` camera frame** returned by the API.
- **Confirm bounding boxes and labels are drawn into the JPEG sent to the browser.**
- **Verify the web UI is requesting the YOLO-processed `scene` feed and not a raw/other image type.**

## Key Places in Code

- **YOLO integration & camera frames**: `[WorkforceDemo/api/services/drone_service.py](WorkforceDemo/api/services/drone_service.py)`
  - `_get_yolo_model()` and `_run_yolo_detection()`
  - `get_camera_frame()` (calls YOLO for `image_type == "scene"`)
- **Camera frame API route**: `[WorkforceDemo/api/routers/drones.py](WorkforceDemo/api/routers/drones.py)` (`get_camera_frame` endpoint at `/drones/{drone_id}/camera/frame`).
- **Web camera feed logic**: `[WorkforceDemo/web/map.js](WorkforceDemo/web/map.js)` (`startCameraFeed`, `fetchCameraFrame`) and `[WorkforceDemo/web/index.html](WorkforceDemo/web/index.html)` (the `img#camera-image`).

## Plan

### 1. Confirm wiring and basic behavior

- **Check front-end requests**:
  - Verify `fetchCameraFrame()` is calling the backend with `type=scene` when you expect YOLO boxes.
  - Optionally log or inspect a live network request in the browser dev tools to confirm the URL matches `/drones/Drone1/camera/frame?type=scene&...`.
- **Confirm API path**:
  - Ensure the `CONFIG.apiUrl` base matches the host/port where `run_api.py` is serving the FastAPI app.

### 2. Verify YOLO model loading and dependencies

- **Confirm `ultralytics` is installed in the same environment as the API** (per `[WorkforceDemo/requirements.txt](WorkforceDemo/requirements.txt)`).
- **Add or review logging inside `_get_yolo_model()**` in `drone_service.py`:
  - Ensure a clear log line on success (e.g., "YOLO model loaded successfully") and on failure (warning with stack trace).
  - Check API terminal logs while hitting `/drones/{id}/camera/frame` to see whether the model actually loads or if it's failing and returning the original image.

### 3. Validate YOLO inference is executing on frames

- **Strengthen logging in `_run_yolo_detection()**`:
  - Log when detection starts and ends for each frame (but without spamming excessively).
  - Log how many detections are found per frame and a few sample class names and confidences.
- **Temporarily simplify detection for debugging**:
  - Lower `conf` threshold in `model.predict(img, conf=0.25, ...)` to something like `0.1` just to confirm boxes can appear.
  - Optionally restrict to a small selection of classes and log them, if needed.

### 4. Confirm bounding boxes are visually drawn into the image

- **Double-check OpenCV drawing code** in `_run_yolo_detection()`:
  - Make sure `cv2.rectangle` and `cv2.putText` operate directly on the same `img` array that is later JPEG-encoded in the route.
  - Optionally change the box color and line thickness to something very obvious (bright color, thicker lines) to rule out subtle styling.
- **Save debug frames to disk** from inside `_run_yolo_detection()`:
  - For a few frames, call `cv2.imwrite("debug_yolo_frame.jpg", img)` after drawing boxes.
  - Inspect these saved images manually to confirm whether YOLO boxes appear before the image goes to the browser.

### 5. Ensure the correct image type is used end-to-end

- **Validate `image_type` conditional** in `get_camera_frame()`:
  - Confirm that `image_type == "scene"` is the only case that should run YOLO, and that any other type (depth/segmentation) correctly bypasses detection.
- **Align UI control with backend**:
  - In `map.js`, verify the `#camera-type` select’s values match the backend’s expected strings (`scene`, `depth`, `segmentation`).
  - Make sure you have `scene` selected in the UI when expecting YOLO overlays.

### 6. Performance and resolution considerations

- **Check resizing logic** in `get_camera_frame()`:
  - Confirm the `max_width` resize step does not distort or strip the boxes (it shouldn’t, but verifying dimensions during debugging can help).
- **Measure timing** (optional):
  - Add timing logs around `model.predict` to ensure inference is fast enough to keep up with the 10 fps fetch loop.
  - If needed, increase the fetch interval (e.g., 200–300ms) to reduce load while debugging.

### 7. End-to-end testing steps

- **Backend-only test**:
  - Call the camera frame endpoint directly (e.g., via curl or a browser: `/drones/Drone1/camera/frame?type=scene`) and save the JPEG to disk.
  - Open the saved JPEG and confirm whether it has YOLO boxes.
- **Frontend verification**:
  - With boxes verified in the saved JPEG, open the web UI, start the camera feed, and confirm that the same frame shows boxes in the `img#camera-image`.
- **Iterate thresholds and viewpoints**:
  - Move the drone so that objects known to be in YOLO’s COCO classes (e.g., cars, people) are in view and adjust thresholds until you reliably see detections.

### 8. Optional improvements

- **Add a server-side toggle** (e.g., query param `yolo=true/false`) to enable/disable detection for performance testing.
- **Expose detection metadata** alongside the JPEG in a JSON endpoint (for future UI features such as clickable detections or overlays drawn in canvas instead of directly on the image).

## Simple Data Flow Diagram

```mermaid
flowchart LR
  subgraph frontend [Frontend]
    webUI[web_map.js]
    cameraImg[camera-image img]
  end

  subgraph backend [Backend]
    router[drones.py get_camera_frame]
    service[DroneService.get_camera_frame]
    yolo[DroneService._run_yolo_detection]
  end

  subgraph airsimSim [AirSim]
    simCamera[DroneCamera]
  end

  webUI -->|HTTP GET /drones/{id}/camera/frame?type=scene| router
  router --> service
  service -->|simGetImages| simCamera
  simCamera --> service
  service --> yolo
  yolo -->|annotated frame| service
  service -->|JPEG bytes| router
  router -->|image/jpeg response| cameraImg
```



