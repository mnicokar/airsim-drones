"""
Fleet router - Fleet-wide control endpoints.

Provides simple endpoints for coordinating multiple drones:
- Initialize all
- Takeoff/land all
- Emergency stop
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from ..models import EmergencyResponse, GroupFlightRequest, GroupFlightResponse
from ..services import get_drone_service, get_safety_service


def normalize_drone_id(drone_id: str) -> str:
    """Normalize drone ID to standard format (e.g., 'Drone1')."""
    lower = drone_id.lower()
    if lower.startswith("drone"):
        num = lower[5:]
        return f"Drone{num}"
    elif lower.startswith("d") and lower[1:].isdigit():
        return f"Drone{lower[1:]}"
    return drone_id

router = APIRouter(prefix="/fleet", tags=["Fleet"])


def get_services():
    """Get service instances."""
    return get_drone_service(), get_safety_service()


# =========================================================================
# Fleet-wide Commands
# =========================================================================

@router.post(
    "/initialize",
    summary="Initialize all drones",
    description="Discover and initialize all available drones for API control."
)
async def initialize_fleet():
    """Initialize all drones in the fleet."""
    drone_service, _ = get_services()

    if not drone_service.is_connected:
        drone_service.connect()

    initialized = drone_service.initialize_all_drones()
    return {
        "status": "initialized",
        "drones": initialized,
        "count": len(initialized)
    }


@router.post(
    "/takeoff",
    summary="Take off all drones",
    description="Command all drones to take off."
)
async def takeoff_fleet():
    """Take off all drones."""
    drone_service, _ = get_services()

    if not drone_service.is_connected:
        drone_service.connect()

    # Auto-initialize if needed
    if not drone_service._available_drones:
        drone_service.initialize_all_drones()

    result = drone_service.takeoff_all()
    return {
        "status": "airborne",
        "drones": result,
        "count": len(result)
    }


@router.post(
    "/land",
    summary="Land all drones",
    description="Command all drones to land."
)
async def land_fleet():
    """Land all drones."""
    drone_service, _ = get_services()
    result = drone_service.land_all()
    return {
        "status": "landed",
        "drones": result,
        "count": len(result)
    }


@router.post(
    "/hover",
    summary="Hover all drones",
    description="Command all drones to stop and hover in place."
)
async def hover_fleet():
    """Hover all drones."""
    drone_service, _ = get_services()
    result = drone_service.hover_all()
    return {
        "status": "hovering",
        "drones": result,
        "count": len(result)
    }


# =========================================================================
# Formation Flying
# =========================================================================

@router.post(
    "/group-flight",
    response_model=GroupFlightResponse,
    summary="Formation group flight to house",
    description="""
    Fly all drones in formation to a house with a designated leader.

    **Formations available:**
    - `v` - V-formation (leader at front, others trail in V shape)
    - `line` - Side-by-side line
    - `diamond` - Diamond pattern
    - `echelon` - Diagonal line
    - `column` - Single file behind leader

    **Example:** Send Drone1 as leader with all drones in V-formation to House A:
    ```json
    {"leader": "drone1", "house": "A", "formation": "v"}
    ```
    """
)
async def group_flight(request: GroupFlightRequest):
    """Execute formation group flight to a house."""
    drone_service, _ = get_services()

    if not drone_service.is_connected:
        drone_service.connect()

    # Auto-initialize all drones if needed
    if not drone_service._available_drones:
        drone_service.initialize_all_drones()

    # Normalize the leader ID
    leader_id = normalize_drone_id(request.leader)

    # Ensure leader is initialized
    if leader_id not in drone_service._drone_states:
        drone_service.initialize_drone(leader_id)

    result = drone_service.group_flight(
        leader_id=leader_id,
        house_identifier=request.house,
        formation=request.formation,
        spacing=request.spacing,
        speed=request.speed,
        wait=request.wait
    )

    if "error" in result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=result["error"])

    return GroupFlightResponse(**result)


# =========================================================================
# Safety and Emergency
# =========================================================================

@router.post(
    "/emergency-stop",
    response_model=EmergencyResponse,
    summary="Emergency stop all drones",
    description="Immediately stop all drones and command them to hover in place."
)
async def emergency_stop():
    """Emergency stop all drones."""
    _, safety_service = get_services()
    result = safety_service.emergency_stop_all()
    return EmergencyResponse(**result)


@router.post(
    "/clear-emergency",
    response_model=EmergencyResponse,
    summary="Clear emergency status",
    description="Clear emergency status and allow normal operations to resume."
)
async def clear_emergency():
    """Clear emergency status."""
    _, safety_service = get_services()
    result = safety_service.clear_emergency()
    return EmergencyResponse(**result)
