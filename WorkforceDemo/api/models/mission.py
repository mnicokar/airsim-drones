"""
Pydantic models for mission and fleet API requests and responses.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# Fleet Models

class FormationRequest(BaseModel):
    """Request to form a fleet formation."""
    formation: str = Field(
        ...,
        description="Formation type: 'line', 'grid', 'v', 'circle', 'diamond', 'echelon'"
    )
    drone_ids: Optional[List[str]] = Field(
        None,
        description="List of drone IDs to include. If not specified, uses all available drones."
    )
    center_x: float = Field(0.0, description="Center X coordinate of formation")
    center_y: float = Field(0.0, description="Center Y coordinate of formation")
    altitude: float = Field(20.0, description="Formation altitude in meters", ge=5, le=100)
    spacing: float = Field(10.0, description="Distance between drones in meters", ge=3, le=50)
    heading: float = Field(0.0, description="Formation heading in degrees", ge=0, le=360)
    speed: float = Field(5.0, description="Movement speed in m/s", ge=1, le=20)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "formation": "v",
                    "center_x": 0.0,
                    "center_y": 0.0,
                    "altitude": 25.0,
                    "spacing": 12.0,
                    "heading": 45.0
                }
            ]
        }
    }


class FormationResponse(BaseModel):
    """Response for formation command."""
    formation: str = Field(..., description="Formation type")
    center: Dict[str, float] = Field(..., description="Formation center {x, y}")
    altitude: float = Field(..., description="Formation altitude")
    spacing: float = Field(..., description="Drone spacing")
    heading: float = Field(..., description="Formation heading")
    assignments: Dict[str, Dict[str, float]] = Field(..., description="Drone position assignments")


class SearchRequest(BaseModel):
    """Request to execute a search pattern."""
    pattern: str = Field(
        ...,
        description="Search pattern: 'parallel_sweep', 'expanding_square', 'sector_search'"
    )
    drone_ids: Optional[List[str]] = Field(
        None,
        description="Drones to use for search. If not specified, uses all available."
    )
    center_x: float = Field(0.0, description="Center X of search area")
    center_y: float = Field(0.0, description="Center Y of search area")
    width: float = Field(100.0, description="Search area width in meters", ge=20, le=500)
    height: float = Field(100.0, description="Search area height in meters", ge=20, le=500)
    altitude: float = Field(20.0, description="Search altitude in meters", ge=5, le=100)
    lane_spacing: float = Field(15.0, description="Spacing between search lanes", ge=5, le=50)
    speed: float = Field(5.0, description="Search speed in m/s", ge=1, le=15)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pattern": "parallel_sweep",
                    "center_x": 0.0,
                    "center_y": 0.0,
                    "width": 80.0,
                    "height": 80.0,
                    "altitude": 25.0,
                    "lane_spacing": 20.0
                }
            ]
        }
    }


class SearchResponse(BaseModel):
    """Response for search pattern execution."""
    pattern: str = Field(..., description="Search pattern executed")
    area: Dict[str, float] = Field(..., description="Search area definition")
    drones_used: List[str] = Field(..., description="Drones that participated")
    status: str = Field(..., description="Execution status")


class FollowLeaderRequest(BaseModel):
    """Request to start follow-the-leader mode."""
    leader_id: str = Field(..., description="ID of the leader drone")
    follower_ids: Optional[List[str]] = Field(
        None,
        description="IDs of follower drones. If not specified, all other drones follow."
    )
    speed: float = Field(5.0, description="Following speed in m/s", ge=1, le=15)


class FollowLeaderResponse(BaseModel):
    """Response for follow-the-leader setup."""
    leader: str = Field(..., description="Leader drone ID")
    followers: List[str] = Field(..., description="Follower drone IDs")
    offsets: Dict[str, Dict[str, float]] = Field(..., description="Follower position offsets")
    status: str = Field(..., description="Mode status")


class FleetMoveRequest(BaseModel):
    """Request to move entire fleet."""
    x: float = Field(..., description="Target X coordinate (center of fleet)")
    y: float = Field(..., description="Target Y coordinate (center of fleet)")
    altitude: float = Field(20.0, description="Target altitude", ge=5, le=100)
    drone_ids: Optional[List[str]] = Field(None, description="Drones to move, or all if not specified")
    maintain_formation: bool = Field(True, description="Maintain current relative positions")
    speed: float = Field(5.0, description="Movement speed", ge=1, le=20)


# Mission Models

class WaypointModel(BaseModel):
    """A waypoint in a mission."""
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")
    altitude: float = Field(20.0, description="Altitude in meters", ge=1, le=100)
    action: str = Field("none", description="Action at waypoint: 'none', 'hover', 'photo', 'rotate', 'face_target'")
    action_params: Optional[Dict[str, Any]] = Field(None, description="Parameters for the action")
    speed: Optional[float] = Field(None, description="Speed to reach this waypoint", ge=1, le=20)


class CreateMissionRequest(BaseModel):
    """Request to create a new mission."""
    name: str = Field(..., description="Mission name")
    mission_type: str = Field(
        "waypoint",
        description="Mission type: 'waypoint', 'survey', 'inspection', 'search'"
    )
    drone_ids: List[str] = Field(..., description="Drones assigned to this mission")
    params: Optional[Dict[str, Any]] = Field(None, description="Mission-specific parameters")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "House Inspection",
                    "mission_type": "inspection",
                    "drone_ids": ["Drone1"],
                    "params": {"target": "House A"}
                }
            ]
        }
    }


class PlanWaypointMissionRequest(BaseModel):
    """Request to plan a waypoint mission."""
    waypoints: List[WaypointModel] = Field(..., description="List of waypoints")


class PlanSurveyMissionRequest(BaseModel):
    """Request to plan a survey mission."""
    center_x: float = Field(..., description="Center X of survey area")
    center_y: float = Field(..., description="Center Y of survey area")
    width: float = Field(..., description="Survey area width", ge=10, le=500)
    height: float = Field(..., description="Survey area height", ge=10, le=500)
    altitude: float = Field(20.0, description="Survey altitude", ge=5, le=100)
    lane_spacing: float = Field(15.0, description="Distance between lanes", ge=5, le=50)
    take_photos: bool = Field(True, description="Take photos at lane endpoints")


class PlanInspectionMissionRequest(BaseModel):
    """Request to plan an inspection mission."""
    target_x: Optional[float] = Field(None, description="Target X coordinate (use this OR house)")
    target_y: Optional[float] = Field(None, description="Target Y coordinate (use this OR house)")
    house: Optional[str] = Field(None, description="House identifier (A-T) to inspect (alternative to coordinates)")
    radius: float = Field(15.0, description="Inspection circle radius", ge=5, le=50)
    altitude: float = Field(20.0, description="Inspection altitude", ge=5, le=100)
    num_angles: int = Field(8, description="Number of positions around target", ge=4, le=16)
    take_photos: bool = Field(True, description="Take photos at each position")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "house": "C",
                    "radius": 15.0,
                    "altitude": 20.0,
                    "num_angles": 8
                }
            ]
        }
    }


class MissionResponse(BaseModel):
    """Response model for a mission."""
    id: str = Field(..., description="Mission ID")
    name: str = Field(..., description="Mission name")
    mission_type: str = Field(..., description="Mission type")
    drone_ids: List[str] = Field(..., description="Assigned drones")
    status: str = Field(..., description="Mission status: draft, ready, in_progress, paused, completed, aborted")
    waypoints: List[Dict[str, Any]] = Field(..., description="Mission waypoints")
    params: Dict[str, Any] = Field(..., description="Mission parameters")
    progress: float = Field(..., description="Progress percentage (0-100)")
    current_waypoint: int = Field(..., description="Current waypoint index")
    total_waypoints: int = Field(..., description="Total number of waypoints")
    created_at: str = Field(..., description="Creation timestamp")
    started_at: Optional[str] = Field(None, description="Start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    error: Optional[str] = Field(None, description="Error message if aborted")


class MissionListResponse(BaseModel):
    """Response listing all missions."""
    missions: List[MissionResponse] = Field(..., description="List of all missions")
    count: int = Field(..., description="Total number of missions")


# Safety Models

class GeofenceRequest(BaseModel):
    """Request to set geofence boundaries."""
    min_x: float = Field(-100.0, description="Minimum X coordinate")
    max_x: float = Field(100.0, description="Maximum X coordinate")
    min_y: float = Field(-100.0, description="Minimum Y coordinate")
    max_y: float = Field(100.0, description="Maximum Y coordinate")
    min_altitude: float = Field(5.0, description="Minimum altitude", ge=1)
    max_altitude: float = Field(100.0, description="Maximum altitude", le=150)


class GeofenceResponse(BaseModel):
    """Response for geofence configuration."""
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_altitude: float
    max_altitude: float


class NoFlyZoneRequest(BaseModel):
    """Request to add a no-fly zone."""
    center_x: float = Field(..., description="Center X coordinate")
    center_y: float = Field(..., description="Center Y coordinate")
    radius: float = Field(..., description="Zone radius in meters", ge=5, le=100)
    name: str = Field("No-fly zone", description="Zone name for identification")


class NoFlyZoneResponse(BaseModel):
    """Response for no-fly zone."""
    id: int = Field(..., description="Zone ID")
    name: str = Field(..., description="Zone name")
    center: Dict[str, float] = Field(..., description="Zone center {x, y}")
    radius: float = Field(..., description="Zone radius")


class EmergencyResponse(BaseModel):
    """Response for emergency operations."""
    status: str = Field(..., description="Emergency status")
    drones: Optional[Dict[str, str]] = Field(None, description="Status per drone")
    timestamp: Optional[str] = Field(None, description="Timestamp")


class ValidationResponse(BaseModel):
    """Response for position validation."""
    position: Dict[str, float] = Field(..., description="Validated position")
    valid: bool = Field(..., description="Whether position is safe")
    issues: List[Dict[str, Any]] = Field(..., description="List of issues if any")
