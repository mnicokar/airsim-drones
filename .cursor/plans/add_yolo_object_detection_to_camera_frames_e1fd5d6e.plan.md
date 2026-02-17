---
name: Add YOLO object detection to camera frames
overview: Integrate Ultralytics YOLO object detection into the get_camera_frame method to highlight detectable objects with bounding boxes and labels before returning scene images.
todos:
  - id: add_ultralytics_dependency
    content: Add ultralytics>=8.0.0 to requirements.txt
    status: done
  - id: add_yolo_imports
    content: Add YOLO import and Optional type hint to drone_service.py
    status: done
  - id: add_yolo_model_property
    content: Add lazy-loading YOLO model property to DroneService class
    status: done
  - id: implement_detection_logic
    content: Add YOLO detection and annotation logic to get_camera_frame method for scene images
    status: done
  - id: add_error_handling
    content: Add error handling for YOLO initialization and detection failures
    status: done
isProject: false
---

# Add YOLO Object Detection to Camera Frames

## Overview

Add YOLO object detection to the `get_camera_frame` method in `drone_service.py` to detect and highlight objects in scene (RGB) images before returning them.

## Implementation Details

### 1. Dependencies

- Add `ultralytics>=8.0.0` to `requirements.txt`
- The ultralytics package includes YOLOv8/v9/v10 models and will auto-download weights on first use

### 2. Modify DroneService Class

**File: `WorkforceDemo/api/services/drone_service.py**`

- **Add imports** (after line 15):
  - Import `YOLO` from `ultralytics`
  - Optional: Add logging for YOLO initialization errors
- **Add YOLO model initialization** in `__init__` method (around line 71-80):
  - Add `self._yolo_model: Optional[YOLO] = None` to store the model
  - Create a lazy-loading property `_get_yolo_model()` that initializes YOLO on first use
  - Use `YOLO('yolov8n.pt')` for nano model (fastest, good for real-time)
  - Handle initialization errors gracefully (log warning, return None)
- **Modify `get_camera_frame` method** (before line 711):
  - After image processing and resizing, check if `image_type == "scene"`
  - If scene image, run YOLO detection:
    - Get YOLO model via lazy loader
    - Run `model.predict(img, conf=0.25, verbose=False)` 
    - Draw bounding boxes and labels on image using cv2.rectangle and cv2.putText
    - Use different colors for different classes
    - Format: `[class_name] confidence%`
  - Return annotated image

### 3. Implementation Approach

**YOLO Detection Flow:**

```
1. Check if image_type == "scene"
2. Load YOLO model (lazy initialization)
3. Run detection: results = model.predict(img, conf=0.25)
4. For each detection:
   - Extract bounding box coordinates
   - Extract class name and confidence
   - Draw rectangle with cv2.rectangle
   - Draw label text with cv2.putText
5. Return annotated image
```

**Error Handling:**

- If YOLO fails to initialize, log warning and return original image
- If detection fails, catch exception and return original image
- Ensure no performance impact when YOLO is unavailable

### 4. Visual Formatting

- Bounding boxes: Use colored rectangles (e.g., green, blue, red)
- Labels: White text with dark background for readability
- Format: `{class_name} {confidence:.1%}` (e.g., "person 85.3%")
- Font: `cv2.FONT_HERSHEY_SIMPLEX` with appropriate scale

### 5. Performance Considerations

- Lazy-load YOLO model only when needed
- Use YOLOv8n (nano) for faster inference
- Detection runs after resizing (if applied), reducing computation
- Cache model instance in class variable to avoid reloading

## Files to Modify

1. `**WorkforceDemo/requirements.txt**`
  - Add `ultralytics>=8.0.0`
2. `**WorkforceDemo/api/services/drone_service.py**`
  - Add YOLO import
  - Add model initialization logic
  - Modify `get_camera_frame` to apply detection before return

## Testing Considerations

- Test with scene images to verify detections appear
- Test with depth/segmentation images to ensure they're unchanged
- Verify graceful fallback if YOLO unavailable
- Check performance impact on frame rate

