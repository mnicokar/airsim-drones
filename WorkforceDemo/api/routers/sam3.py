"""
SAM3 router - Segment Anything Model 3 endpoints.

Provides endpoints for text-prompted image segmentation using SAM3.
"""

from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from fastapi.responses import Response
import cv2
import numpy as np
import json

from ..services.sam3_service import get_sam3_service
from ..services import get_drone_service

router = APIRouter(prefix="/api/sam3", tags=["SAM3"])


@router.get("/status")
async def get_status():
    """Check if SAM3 model is loaded."""
    service = get_sam3_service()
    return {
        "loaded": service.is_loaded,
        "status": "ready" if service.is_loaded else "not_loaded",
        "message": "Model loaded and ready" if service.is_loaded else "Model will load on first inference request",
    }


@router.post("/segment/upload")
async def segment_upload(
    file: UploadFile = File(...),
    prompt: str = Form(...),
):
    """
    Segment an uploaded image using SAM3 with a text prompt.

    Returns annotated JPEG with detection metadata in headers.
    """
    # Read uploaded file
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Run segmentation
    service = get_sam3_service()
    try:
        result = service.segment(image, prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Encode annotated image as JPEG
    _, jpeg_buf = cv2.imencode(".jpg", result["annotated_image"], [cv2.IMWRITE_JPEG_QUALITY, 90])

    return Response(
        content=jpeg_buf.tobytes(),
        media_type="image/jpeg",
        headers={
            "X-SAM3-Num-Masks": str(result["num_masks"]),
            "X-SAM3-Detections": json.dumps(result["detections"]),
            "X-SAM3-Prompt": prompt,
        },
    )


@router.post("/segment/drone")
async def segment_drone(
    drone_id: str = Form(...),
    prompt: str = Form(...),
):
    """
    Grab a camera frame from a drone and segment it using SAM3.

    Returns annotated JPEG with detection metadata in headers.
    """
    # Get raw drone camera frame (without YOLO annotations)
    drone_service = get_drone_service()
    frame = drone_service.get_camera_frame(drone_id, run_detection=False)

    if frame is None:
        raise HTTPException(status_code=404, detail=f"Could not get camera frame from drone '{drone_id}'")

    # Run segmentation
    sam3_service = get_sam3_service()
    try:
        result = sam3_service.segment(frame, prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Encode annotated image as JPEG
    _, jpeg_buf = cv2.imencode(".jpg", result["annotated_image"], [cv2.IMWRITE_JPEG_QUALITY, 90])

    return Response(
        content=jpeg_buf.tobytes(),
        media_type="image/jpeg",
        headers={
            "X-SAM3-Num-Masks": str(result["num_masks"]),
            "X-SAM3-Detections": json.dumps(result["detections"]),
            "X-SAM3-Prompt": prompt,
            "X-SAM3-Drone-ID": drone_id,
        },
    )
