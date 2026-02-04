"""
Pydantic models for drone-related API requests and responses.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Position(BaseModel):
    """3D position model."""
    x: float = Field(..., description="X coordinate in meters")
    y: float = Field(..., description="Y coordinate in meters")
    z: Optional[float] = Field(None, description="Z coordinate (negative is up in AirSim)")


class Velocity(BaseModel):
    """3D velocity model."""
    vx: float = Field(..., description="X velocity in m/s")
    vy: float = Field(..., description="Y velocity in m/s")
    vz: float = Field(..., description="Z velocity in m/s")


class DroneStatusResponse(BaseModel):
    """Response model for drone status."""
    drone_id: str = Field(..., description="Drone identifier")
    position: Dict[str, float] = Field(..., description="Current position {x, y, z}")
    velocity: Dict[str, float] = Field(..., description="Current velocity {vx, vy, vz}")
    heading: float = Field(..., description="Current heading in degrees (0-360)")
    altitude: float = Field(..., description="Current altitude in meters (positive)")
    state: str = Field(..., description="Drone state: idle, taking_off, flying, hovering, landing, landed, emergency")
    current_task: Optional[str] = Field(None, description="Current task description")
    home_position: Optional[Dict[str, float]] = Field(None, description="Home position {x, y, z}")


class FleetStatusResponse(BaseModel):
    """Response model for fleet status."""
    drones: List[DroneStatusResponse] = Field(..., description="Status of all drones")
    total_count: int = Field(..., description="Total number of drones")
    flying_count: int = Field(..., description="Number of drones currently flying")
    emergency_active: bool = Field(..., description="Whether emergency mode is active")


# Request Models

class MoveRequest(BaseModel):
    """Request to move drone to a position."""
    x: float = Field(..., description="Target X coordinate")
    y: float = Field(..., description="Target Y coordinate")
    altitude: Optional[float] = Field(None, description="Target altitude in meters (positive). If not specified, maintains current altitude.")
    speed: Optional[float] = Field(None, description="Movement speed in m/s", ge=1, le=20)
    wait: bool = Field(False, description="Wait for movement to complete before responding (default: false for async)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "x": 20.0,
                    "y": -15.0,
                    "altitude": 20.0,
                    "speed": 5.0,
                    "wait": True
                }
            ]
        }
    }


class GotoHouseRequest(BaseModel):
    """Request to navigate drone to a house."""
    house: str = Field(..., description="House identifier (letter A-T or full name like 'House A')")
    speed: Optional[float] = Field(None, description="Movement speed in m/s", ge=1, le=20)
    view_distance: float = Field(10.0, description="Distance from house to hover at (0 = directly above)", ge=0, le=50)
    wait: bool = Field(False, description="Wait for navigation to complete (default: false for async)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "house": "A",
                    "speed": 5.0,
                    "view_distance": 10.0
                }
            ]
        }
    }


class GotoHouseResponse(BaseModel):
    """Response for goto-house operation."""
    house_name: str = Field(..., description="Full house name")
    house_position: Dict[str, float] = Field(..., description="House coordinates {x, y}")
    viewing_position: Dict[str, float] = Field(..., description="Drone viewing position {x, y, z}")


class RotateRequest(BaseModel):
    """Request to rotate drone to a heading."""
    heading: float = Field(..., description="Target heading in degrees (0-360, 0=North, 90=East)", ge=0, le=360)
    wait: bool = Field(False, description="Wait for rotation to complete (default: false for async)")


class FaceTargetRequest(BaseModel):
    """Request to rotate drone to face a target."""
    target_x: float = Field(..., description="Target X coordinate")
    target_y: float = Field(..., description="Target Y coordinate")
    wait: bool = Field(False, description="Wait for rotation to complete (default: false for async)")


class PhotoRequest(BaseModel):
    """Request to capture photos."""
    image_types: Optional[List[str]] = Field(
        None,
        description="Types of images to capture: 'scene', 'depth', 'segmentation'. Defaults to all."
    )
    save_to_disk: bool = Field(True, description="Save images to disk")
    label: str = Field("photo", description="Label for saved file names")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "image_types": ["scene", "depth"],
                    "save_to_disk": True,
                    "label": "house_inspection"
                }
            ]
        }
    }


class PhotoResponse(BaseModel):
    """Response for photo capture."""
    files: Dict[str, str] = Field(..., description="Paths to saved image files by type")
    captured_types: List[str] = Field(..., description="List of image types captured")


class TakeoffRequest(BaseModel):
    """Request for drone takeoff."""
    altitude: Optional[float] = Field(None, description="Target altitude in meters (positive)", ge=5, le=100)
    wait: bool = Field(False, description="Wait for takeoff to complete (default: false for async)")


class AltitudeRequest(BaseModel):
    """Request to change altitude."""
    altitude: float = Field(..., description="Target altitude in meters (positive)", ge=1, le=100)
    speed: Optional[float] = Field(None, description="Vertical speed in m/s", ge=1, le=10)
    wait: bool = Field(False, description="Wait for altitude change to complete (default: false for async)")


class HouseInfo(BaseModel):
    """Information about a house location."""
    name: str = Field(..., description="House name")
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")
    parts: Optional[int] = Field(None, description="Number of parts (for reference)")


class HousesResponse(BaseModel):
    """Response listing all houses."""
    houses: List[HouseInfo] = Field(..., description="List of all house locations")
    count: int = Field(..., description="Total number of houses")
