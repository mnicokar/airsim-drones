"""
Missions router - Mission planning and execution endpoints.

Provides endpoints for:
- Creating and managing missions
- Planning waypoint, survey, and inspection missions
- Starting, pausing, resuming, and aborting missions
"""

from fastapi import APIRouter, HTTPException, Path
from typing import Optional, List

from ..models import (
    CreateMissionRequest,
    PlanWaypointMissionRequest,
    PlanSurveyMissionRequest,
    PlanInspectionMissionRequest,
    MissionResponse,
    MissionListResponse,
    WaypointModel,
)
from ..services import get_mission_service

router = APIRouter(prefix="/missions", tags=["Missions"])


def get_service():
    """Get mission service instance."""
    return get_mission_service()


# =========================================================================
# Mission CRUD
# =========================================================================

@router.get(
    "",
    response_model=MissionListResponse,
    summary="List all missions",
    description="Get a list of all missions with their status."
)
async def list_missions():
    """List all missions."""
    service = get_service()
    missions = service.get_all_missions()
    return MissionListResponse(
        missions=[MissionResponse(**m.to_dict()) for m in missions],
        count=len(missions)
    )


@router.post(
    "",
    response_model=MissionResponse,
    summary="Create a new mission",
    description="""
    Create a new mission. After creation, use the planning endpoints to add waypoints.

    **Mission types:**
    - `waypoint` - Fly through a sequence of points with optional actions at each
    - `survey` - Systematic area coverage (parallel lanes)
    - `inspection` - Circle around a target from multiple angles
    - `search` - Coordinated search pattern
    """
)
async def create_mission(request: CreateMissionRequest):
    """Create a new mission."""
    service = get_service()
    mission = service.create_mission(
        request.name,
        request.mission_type,
        request.drone_ids,
        request.params
    )
    return MissionResponse(**mission.to_dict())


@router.get(
    "/{mission_id}",
    response_model=MissionResponse,
    summary="Get mission details",
    description="Get detailed information about a specific mission."
)
async def get_mission(
    mission_id: str = Path(..., description="Mission ID")
):
    """Get a mission by ID."""
    service = get_service()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")
    return MissionResponse(**mission.to_dict())


@router.delete(
    "/{mission_id}",
    summary="Delete a mission",
    description="Delete a mission. Running missions will be aborted first."
)
async def delete_mission(
    mission_id: str = Path(..., description="Mission ID")
):
    """Delete a mission."""
    service = get_service()
    success = service.delete_mission(mission_id)
    if success:
        return {"status": "deleted", "mission_id": mission_id}
    else:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")


# =========================================================================
# Mission Planning
# =========================================================================

@router.post(
    "/{mission_id}/plan/waypoints",
    response_model=MissionResponse,
    summary="Plan waypoint mission",
    description="""
    Add waypoints to a mission. Each waypoint can have an action.

    **Waypoint actions:**
    - `none` - No action, just fly through
    - `hover` - Hover for specified duration (action_params: {"duration": seconds})
    - `photo` - Take photos (action_params: {"label": "photo_label"})
    - `rotate` - Rotate to heading (action_params: {"heading": degrees})
    - `face_target` - Face a point (action_params: {"target_x": x, "target_y": y})
    """
)
async def plan_waypoint_mission(
    mission_id: str = Path(..., description="Mission ID"),
    request: PlanWaypointMissionRequest = ...
):
    """Plan a waypoint mission."""
    service = get_service()

    waypoints = [
        {
            "x": wp.x,
            "y": wp.y,
            "altitude": wp.altitude,
            "action": wp.action,
            "action_params": wp.action_params,
            "speed": wp.speed
        }
        for wp in request.waypoints
    ]

    mission = service.plan_waypoint_mission(mission_id, waypoints)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found or not in draft status")
    return MissionResponse(**mission.to_dict())


@router.post(
    "/{mission_id}/plan/survey",
    response_model=MissionResponse,
    summary="Plan survey mission",
    description="Plan a survey mission for systematic area coverage with optional photo capture."
)
async def plan_survey_mission(
    mission_id: str = Path(..., description="Mission ID"),
    request: PlanSurveyMissionRequest = ...
):
    """Plan a survey mission."""
    service = get_service()

    mission = service.plan_survey_mission(
        mission_id,
        request.center_x,
        request.center_y,
        request.width,
        request.height,
        request.altitude,
        request.lane_spacing,
        request.take_photos
    )

    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")
    return MissionResponse(**mission.to_dict())


@router.post(
    "/{mission_id}/plan/inspection",
    response_model=MissionResponse,
    summary="Plan inspection mission",
    description="Plan an inspection mission that circles a target from multiple angles. Can specify coordinates or a house letter."
)
async def plan_inspection_mission(
    mission_id: str = Path(..., description="Mission ID"),
    request: PlanInspectionMissionRequest = ...
):
    """Plan an inspection mission."""
    service = get_service()

    if request.house:
        # Inspection by house
        mission = service.plan_house_inspection(
            mission_id,
            request.house,
            request.radius,
            request.altitude,
            request.num_angles
        )
    elif request.target_x is not None and request.target_y is not None:
        # Inspection by coordinates
        mission = service.plan_inspection_mission(
            mission_id,
            request.target_x,
            request.target_y,
            request.radius,
            request.altitude,
            request.num_angles,
            request.take_photos
        )
    else:
        raise HTTPException(status_code=400, detail="Must specify either house or target coordinates")

    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found or house not found")
    return MissionResponse(**mission.to_dict())


@router.post(
    "/{mission_id}/waypoint",
    response_model=MissionResponse,
    summary="Add a waypoint",
    description="Add a single waypoint to an existing mission."
)
async def add_waypoint(
    mission_id: str = Path(..., description="Mission ID"),
    waypoint: WaypointModel = ...
):
    """Add a waypoint to a mission."""
    service = get_service()

    wp = service.add_waypoint(
        mission_id,
        waypoint.x,
        waypoint.y,
        waypoint.altitude,
        waypoint.action,
        waypoint.action_params,
        waypoint.speed
    )

    if not wp:
        raise HTTPException(status_code=400, detail=f"Cannot add waypoint to mission {mission_id} (not found or not in draft status)")

    mission = service.get_mission(mission_id)
    return MissionResponse(**mission.to_dict())


# =========================================================================
# Mission Execution Control
# =========================================================================

@router.post(
    "/{mission_id}/start",
    summary="Start mission",
    description="Start executing a planned mission. Mission must be in 'ready' or 'paused' status."
)
async def start_mission(
    mission_id: str = Path(..., description="Mission ID")
):
    """Start executing a mission."""
    service = get_service()
    result = service.start_mission(mission_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post(
    "/{mission_id}/pause",
    summary="Pause mission",
    description="Pause a running mission. The drone will hover in place."
)
async def pause_mission(
    mission_id: str = Path(..., description="Mission ID")
):
    """Pause a running mission."""
    service = get_service()
    result = service.pause_mission(mission_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post(
    "/{mission_id}/resume",
    summary="Resume mission",
    description="Resume a paused mission from where it stopped."
)
async def resume_mission(
    mission_id: str = Path(..., description="Mission ID")
):
    """Resume a paused mission."""
    service = get_service()
    result = service.resume_mission(mission_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post(
    "/{mission_id}/abort",
    summary="Abort mission",
    description="Abort a running or paused mission. The drone will hover in place."
)
async def abort_mission(
    mission_id: str = Path(..., description="Mission ID")
):
    """Abort a mission."""
    service = get_service()
    result = service.abort_mission(mission_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# =========================================================================
# Pre-built Mission Templates
# =========================================================================

@router.post(
    "/templates/neighborhood-survey",
    response_model=MissionResponse,
    summary="Create neighborhood survey mission",
    description="Create a pre-planned mission to survey all houses in the neighborhood."
)
async def create_neighborhood_survey(
    name: str = "Neighborhood Survey",
    drone_id: str = "Drone1",
    altitude: float = 25.0
):
    """Create a neighborhood survey mission."""
    service = get_service()
    mission = service.create_neighborhood_survey(name, drone_id, altitude)
    return MissionResponse(**mission.to_dict())


@router.post(
    "/templates/house-tour",
    response_model=MissionResponse,
    summary="Create house tour mission",
    description="Create a mission to tour specific houses in sequence."
)
async def create_house_tour(
    houses: List[str],
    name: str = "House Tour",
    drone_id: str = "Drone1"
):
    """Create a house tour mission."""
    service = get_service()
    mission = service.create_house_tour(houses, name, drone_id)

    if not mission:
        raise HTTPException(status_code=400, detail="No valid houses found in the specified list")

    return MissionResponse(**mission.to_dict())
