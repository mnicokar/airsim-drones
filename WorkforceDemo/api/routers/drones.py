"""
Drone router - Individual drone control endpoints.

Provides endpoints for controlling individual drones:
- Movement (position, altitude)
- Navigation to houses
- Photo capture
- Rotation
- Takeoff/landing
"""

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import Response
from typing import Optional, List
import cv2

from ..models import (
    DroneStatusResponse,
    MoveRequest,
    GotoHouseRequest,
    GotoHouseResponse,
    RotateRequest,
    PhotoRequest,
    PhotoResponse,
    TakeoffRequest,
    AltitudeRequest,
    HouseInfo,
    HousesResponse,
)
from ..services import get_drone_service

router = APIRouter(prefix="/drones", tags=["Drones"])


def get_service():
    """Get drone service instance."""
    return get_drone_service()


def normalize_drone_id(drone_id: str) -> str:
    """
    Normalize drone ID to proper case (e.g., 'drone1' -> 'Drone1').
    Makes the API case-insensitive for LLM friendliness.
    """
    # Handle common formats: drone1, DRONE1, Drone1, d1, D1
    lower = drone_id.lower()
    if lower.startswith("drone"):
        num = lower[5:]
        return f"Drone{num}"
    elif lower.startswith("d") and lower[1:].isdigit():
        return f"Drone{lower[1:]}"
    return drone_id  # Return as-is if unknown format


def ensure_drone_ready(service, drone_id: str) -> str:
    """
    Ensure drone is connected and initialized. Auto-initializes if needed.
    Returns the normalized drone ID.
    """
    drone_id = normalize_drone_id(drone_id)

    # Ensure connected
    if not service.is_connected:
        service.connect()

    # Auto-initialize if not already
    if drone_id not in service._drone_states:
        service.initialize_drone(drone_id)

    return drone_id


# =========================================================================
# Drone Status and Discovery
# =========================================================================

@router.get(
    "",
    response_model=List[str],
    summary="List all available drones",
    description="Discover and return a list of all drone IDs available in the simulation."
)
async def list_drones():
    """Get list of available drone IDs."""
    service = get_service()
    if not service.is_connected:
        service.connect()
    return service.discover_drones()


@router.get(
    "/houses",
    response_model=HousesResponse,
    summary="List all house locations",
    description="Get all predefined house locations (A-T) that drones can navigate to."
)
async def list_houses():
    """Get all house locations."""
    service = get_service()
    houses = service.get_houses()

    house_list = [
        HouseInfo(name=name, x=data["x"], y=data["y"], parts=data.get("parts"))
        for name, data in houses.items()
    ]

    return HousesResponse(houses=house_list, count=len(house_list))


@router.get(
    "/{drone_id}",
    response_model=DroneStatusResponse,
    summary="Get drone status",
    description="Get detailed status of a specific drone including position, velocity, heading, and current task."
)
async def get_drone_status(
    drone_id: str = Path(..., description="Drone ID (e.g., 'Drone1')")
):
    """Get status of a specific drone."""
    service = get_service()
    try:
        status = service.get_drone_status(drone_id)
        return DroneStatusResponse(**status.to_dict())
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Drone {drone_id} not found: {str(e)}")


# =========================================================================
# Basic Movement
# =========================================================================

@router.post(
    "/{drone_id}/takeoff",
    summary="Take off drone",
    description="Command the drone to take off and ascend to the specified altitude. Auto-initializes the drone if needed."
)
async def takeoff_drone(
    drone_id: str = Path(..., description="Drone ID (e.g., 'Drone1' or 'drone1')"),
    request: Optional[TakeoffRequest] = None
):
    """Take off a drone."""
    service = get_service()
    drone_id = ensure_drone_ready(service, drone_id)

    altitude = request.altitude if request else None
    wait = request.wait if request else True

    success = service.takeoff(drone_id, altitude, wait)
    if success:
        return {"status": "airborne", "drone_id": drone_id}
    else:
        raise HTTPException(status_code=500, detail=f"Takeoff failed for {drone_id}")


@router.post(
    "/{drone_id}/land",
    summary="Land drone",
    description="Command the drone to land at its current position. Auto-initializes the drone if needed."
)
async def land_drone(
    drone_id: str = Path(..., description="Drone ID (e.g., 'Drone1' or 'drone1')"),
    wait: bool = Query(False, description="Wait for landing to complete (default: false for async)")
):
    """Land a drone."""
    service = get_service()
    drone_id = ensure_drone_ready(service, drone_id)

    success = service.land(drone_id, wait)
    if success:
        return {"status": "landed", "drone_id": drone_id}
    else:
        raise HTTPException(status_code=500, detail=f"Landing failed for {drone_id}")


@router.post(
    "/{drone_id}/hover",
    summary="Hover in place",
    description="Command the drone to stop and hover at its current position. Auto-initializes the drone if needed."
)
async def hover_drone(
    drone_id: str = Path(..., description="Drone ID (e.g., 'Drone1' or 'drone1')")
):
    """Command drone to hover."""
    service = get_service()
    drone_id = ensure_drone_ready(service, drone_id)

    success = service.hover(drone_id)
    if success:
        return {"status": "hovering", "drone_id": drone_id}
    else:
        raise HTTPException(status_code=500, detail=f"Hover failed for {drone_id}")


@router.post(
    "/{drone_id}/move",
    summary="Move to position",
    description="Move the drone to a specific X, Y coordinate. Optionally specify altitude and speed. Auto-initializes the drone if needed."
)
async def move_drone(
    drone_id: str = Path(..., description="Drone ID (e.g., 'Drone1' or 'drone1')"),
    request: MoveRequest = ...
):
    """Move drone to a position."""
    service = get_service()
    drone_id = ensure_drone_ready(service, drone_id)

    z = -request.altitude if request.altitude else None
    success = service.move_to_position(
        drone_id,
        request.x,
        request.y,
        z,
        request.speed,
        request.wait
    )

    if success:
        return {
            "status": "moved",
            "drone_id": drone_id,
            "position": {"x": request.x, "y": request.y, "altitude": request.altitude}
        }
    else:
        raise HTTPException(status_code=500, detail=f"Move failed for {drone_id}")


@router.post(
    "/{drone_id}/altitude",
    summary="Change altitude",
    description="Change the drone's altitude while maintaining current X, Y position. Auto-initializes the drone if needed."
)
async def change_altitude(
    drone_id: str = Path(..., description="Drone ID (e.g., 'Drone1' or 'drone1')"),
    request: AltitudeRequest = ...
):
    """Change drone altitude."""
    service = get_service()
    drone_id = ensure_drone_ready(service, drone_id)

    success = service.move_to_altitude(drone_id, request.altitude, request.speed, request.wait)

    if success:
        return {"status": "altitude_changed", "drone_id": drone_id, "altitude": request.altitude}
    else:
        raise HTTPException(status_code=500, detail=f"Altitude change failed for {drone_id}")


# =========================================================================
# Navigation
# =========================================================================

@router.post(
    "/{drone_id}/goto-house",
    response_model=GotoHouseResponse,
    summary="Navigate to house",
    description="Navigate the drone to view a specific house (A-T). The drone will position itself at a viewing distance from the house and face it. Auto-initializes and takes off if needed."
)
async def goto_house(
    drone_id: str = Path(..., description="Drone ID (e.g., 'Drone1' or 'drone1')"),
    request: GotoHouseRequest = ...
):
    """Navigate drone to a house."""
    service = get_service()
    drone_id = ensure_drone_ready(service, drone_id)

    # Auto-takeoff if drone is landed
    status = service.get_drone_status(drone_id)
    if status.state.value in ['landed', 'idle']:
        service.takeoff(drone_id, wait=True)

    result = service.goto_house(
        drone_id,
        request.house,
        request.speed,
        request.view_distance,
        request.wait
    )

    if result:
        return GotoHouseResponse(**result)
    else:
        raise HTTPException(status_code=404, detail=f"House '{request.house}' not found")


# =========================================================================
# Rotation
# =========================================================================

@router.post(
    "/{drone_id}/rotate",
    summary="Rotate to heading",
    description="Rotate the drone to face a specific compass heading (0-360 degrees, 0=North). Auto-initializes the drone if needed."
)
async def rotate_drone(
    drone_id: str = Path(..., description="Drone ID (e.g., 'Drone1' or 'drone1')"),
    request: RotateRequest = ...
):
    """Rotate drone to a heading."""
    service = get_service()
    drone_id = ensure_drone_ready(service, drone_id)

    success = service.rotate_to_heading(drone_id, request.heading, request.wait)

    if success:
        return {"status": "rotated", "drone_id": drone_id, "heading": request.heading}
    else:
        raise HTTPException(status_code=500, detail=f"Rotation failed for {drone_id}")


# =========================================================================
# Camera and Photos
# =========================================================================

@router.post(
    "/{drone_id}/photo",
    response_model=PhotoResponse,
    summary="Capture photo",
    description="Capture images from the drone's camera. Supports scene (RGB), depth, and segmentation images. Auto-initializes the drone if needed."
)
async def capture_photo(
    drone_id: str = Path(..., description="Drone ID (e.g., 'Drone1' or 'drone1')"),
    request: Optional[PhotoRequest] = None
):
    """Capture photos from drone camera."""
    service = get_service()
    drone_id = ensure_drone_ready(service, drone_id)

    image_types = request.image_types if request else None
    save_to_disk = request.save_to_disk if request else True
    label = request.label if request else "photo"

    result = service.capture_photo(drone_id, image_types, save_to_disk, label)

    return PhotoResponse(
        files=result.get("files", {}),
        captured_types=list(result.get("images", {}).keys())
    )


@router.get(
    "/{drone_id}/camera/frame",
    summary="Get live camera frame",
    description="Get a single camera frame as JPEG image. Use for live camera feed updates.",
    responses={
        200: {
            "content": {"image/jpeg": {}},
            "description": "JPEG image from drone camera"
        }
    }
)
async def get_camera_frame(
    drone_id: str = Path(..., description="Drone ID (e.g., 'Drone1')"),
    type: str = Query("scene", description="Image type: scene (RGB), depth, or segmentation")
):
    """Get a single camera frame from the drone."""
    service = get_service()

    # Validate image type
    valid_types = ["scene", "depth", "segmentation"]
    if type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type '{type}'. Must be one of: {valid_types}"
        )

    try:
        frame = service.get_camera_frame(drone_id, type)
        if frame is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to capture frame from {drone_id}"
            )

        # Encode frame as JPEG (high quality, good balance of quality/speed)
        success, jpeg_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to encode image as JPEG"
            )

        return Response(
            content=jpeg_data.tobytes(),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Camera error: {str(e)}")
