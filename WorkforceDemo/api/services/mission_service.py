"""
Mission Service - Mission planning and execution.

Provides mission types:
- Waypoint missions (fly through points with actions)
- Survey missions (area coverage with photos)
- Inspection missions (circle target, multi-angle photos)
- Search missions (coordinated search patterns)

Mission lifecycle: draft -> ready -> in_progress -> paused -> completed/aborted
"""

import math
import time
import threading
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .drone_service import get_drone_service, DroneService, DroneState
from .fleet_service import get_fleet_service, FleetService
from .safety_service import get_safety_service, SafetyService


class MissionStatus(Enum):
    """Mission lifecycle states."""
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


class MissionType(Enum):
    """Types of missions."""
    WAYPOINT = "waypoint"
    SURVEY = "survey"
    INSPECTION = "inspection"
    SEARCH = "search"


class WaypointAction(Enum):
    """Actions that can be performed at waypoints."""
    NONE = "none"
    HOVER = "hover"
    PHOTO = "photo"
    ROTATE = "rotate"
    FACE_TARGET = "face_target"


@dataclass
class Waypoint:
    """A single waypoint in a mission."""
    x: float
    y: float
    altitude: float
    action: WaypointAction = WaypointAction.NONE
    action_params: Dict = field(default_factory=dict)
    speed: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "x": self.x,
            "y": self.y,
            "altitude": self.altitude,
            "action": self.action.value,
            "action_params": self.action_params,
            "speed": self.speed
        }


@dataclass
class Mission:
    """A mission definition."""
    id: str
    name: str
    mission_type: MissionType
    drone_ids: List[str]
    status: MissionStatus = MissionStatus.DRAFT
    waypoints: List[Waypoint] = field(default_factory=list)
    params: Dict = field(default_factory=dict)
    progress: float = 0.0
    current_waypoint: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "mission_type": self.mission_type.value,
            "drone_ids": self.drone_ids,
            "status": self.status.value,
            "waypoints": [w.to_dict() for w in self.waypoints],
            "params": self.params,
            "progress": self.progress,
            "current_waypoint": self.current_waypoint,
            "total_waypoints": len(self.waypoints),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error
        }


class MissionService:
    """
    Mission planning and execution service.

    Manages mission lifecycle and coordinates with drone and fleet services.
    """

    def __init__(
        self,
        drone_service: Optional[DroneService] = None,
        fleet_service: Optional[FleetService] = None,
        safety_service: Optional[SafetyService] = None
    ):
        """Initialize mission service."""
        self._drone_service = drone_service or get_drone_service()
        self._fleet_service = fleet_service or get_fleet_service()
        self._safety_service = safety_service or get_safety_service()
        self._missions: Dict[str, Mission] = {}
        self._execution_threads: Dict[str, threading.Thread] = {}
        self._pause_flags: Dict[str, bool] = {}
        self._abort_flags: Dict[str, bool] = {}

    @property
    def drone_service(self) -> DroneService:
        return self._drone_service

    @property
    def fleet_service(self) -> FleetService:
        return self._fleet_service

    @property
    def safety_service(self) -> SafetyService:
        return self._safety_service

    # =========================================================================
    # Mission CRUD
    # =========================================================================

    def create_mission(
        self,
        name: str,
        mission_type: str,
        drone_ids: List[str],
        params: Optional[Dict] = None
    ) -> Mission:
        """
        Create a new mission.

        Args:
            name: Mission name
            mission_type: Type of mission (waypoint, survey, inspection, search)
            drone_ids: Drones to use for the mission
            params: Mission-specific parameters

        Returns:
            Created Mission object
        """
        mission_id = str(uuid.uuid4())[:8]

        try:
            m_type = MissionType(mission_type)
        except ValueError:
            m_type = MissionType.WAYPOINT

        mission = Mission(
            id=mission_id,
            name=name,
            mission_type=m_type,
            drone_ids=drone_ids,
            params=params or {}
        )

        self._missions[mission_id] = mission
        return mission

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        """Get a mission by ID."""
        return self._missions.get(mission_id)

    def get_all_missions(self) -> List[Mission]:
        """Get all missions."""
        return list(self._missions.values())

    def delete_mission(self, mission_id: str) -> bool:
        """Delete a mission."""
        if mission_id in self._missions:
            mission = self._missions[mission_id]
            if mission.status == MissionStatus.IN_PROGRESS:
                self.abort_mission(mission_id)
            del self._missions[mission_id]
            return True
        return False

    # =========================================================================
    # Mission Planning
    # =========================================================================

    def add_waypoint(
        self,
        mission_id: str,
        x: float,
        y: float,
        altitude: float,
        action: str = "none",
        action_params: Optional[Dict] = None,
        speed: Optional[float] = None
    ) -> Optional[Waypoint]:
        """Add a waypoint to a mission."""
        mission = self.get_mission(mission_id)
        if not mission or mission.status != MissionStatus.DRAFT:
            return None

        try:
            wp_action = WaypointAction(action)
        except ValueError:
            wp_action = WaypointAction.NONE

        waypoint = Waypoint(
            x=x, y=y, altitude=altitude,
            action=wp_action,
            action_params=action_params or {},
            speed=speed
        )
        mission.waypoints.append(waypoint)
        return waypoint

    def clear_waypoints(self, mission_id: str) -> bool:
        """Clear all waypoints from a mission."""
        mission = self.get_mission(mission_id)
        if not mission or mission.status != MissionStatus.DRAFT:
            return False
        mission.waypoints.clear()
        return True

    def plan_waypoint_mission(
        self,
        mission_id: str,
        waypoints: List[Dict]
    ) -> Optional[Mission]:
        """
        Plan a waypoint mission.

        Args:
            mission_id: ID of the mission
            waypoints: List of waypoint dicts with x, y, altitude, action, action_params

        Returns:
            Updated Mission or None if failed
        """
        mission = self.get_mission(mission_id)
        if not mission:
            return None

        mission.waypoints.clear()
        for wp_data in waypoints:
            self.add_waypoint(
                mission_id,
                wp_data.get("x", 0),
                wp_data.get("y", 0),
                wp_data.get("altitude", 20),
                wp_data.get("action", "none"),
                wp_data.get("action_params"),
                wp_data.get("speed")
            )

        if len(mission.waypoints) > 0:
            mission.status = MissionStatus.READY
        return mission

    def plan_survey_mission(
        self,
        mission_id: str,
        center_x: float,
        center_y: float,
        width: float,
        height: float,
        altitude: float = 20.0,
        lane_spacing: float = 15.0,
        take_photos: bool = True
    ) -> Optional[Mission]:
        """
        Plan a survey mission with systematic area coverage.

        Args:
            mission_id: ID of the mission
            center_x: Center X of survey area
            center_y: Center Y of survey area
            width: Survey area width
            height: Survey area height
            altitude: Survey altitude
            lane_spacing: Distance between parallel flight paths
            take_photos: Whether to take photos at each lane end

        Returns:
            Updated Mission or None if failed
        """
        mission = self.get_mission(mission_id)
        if not mission:
            return None

        mission.params.update({
            "center_x": center_x,
            "center_y": center_y,
            "width": width,
            "height": height,
            "lane_spacing": lane_spacing
        })

        mission.waypoints.clear()
        num_lanes = int(width / lane_spacing) + 1

        for i in range(num_lanes):
            lane_x = center_x - width / 2 + i * lane_spacing
            if i % 2 == 0:
                y_start = center_y - height / 2
                y_end = center_y + height / 2
            else:
                y_start = center_y + height / 2
                y_end = center_y - height / 2

            # Start of lane
            action = WaypointAction.PHOTO if take_photos else WaypointAction.NONE
            mission.waypoints.append(Waypoint(
                x=lane_x, y=y_start, altitude=altitude, action=action
            ))
            # End of lane
            mission.waypoints.append(Waypoint(
                x=lane_x, y=y_end, altitude=altitude, action=action
            ))

        mission.status = MissionStatus.READY
        return mission

    def plan_inspection_mission(
        self,
        mission_id: str,
        target_x: float,
        target_y: float,
        radius: float = 15.0,
        altitude: float = 20.0,
        num_angles: int = 8,
        take_photos: bool = True
    ) -> Optional[Mission]:
        """
        Plan an inspection mission that circles a target.

        Args:
            mission_id: ID of the mission
            target_x: Target X coordinate
            target_y: Target Y coordinate
            radius: Inspection circle radius
            altitude: Inspection altitude
            num_angles: Number of positions around the circle
            take_photos: Whether to take photos at each position

        Returns:
            Updated Mission or None if failed
        """
        mission = self.get_mission(mission_id)
        if not mission:
            return None

        mission.params.update({
            "target_x": target_x,
            "target_y": target_y,
            "radius": radius,
            "num_angles": num_angles
        })

        mission.waypoints.clear()

        for i in range(num_angles):
            angle = 2 * math.pi * i / num_angles
            wp_x = target_x + radius * math.cos(angle)
            wp_y = target_y + radius * math.sin(angle)

            action = WaypointAction.PHOTO if take_photos else WaypointAction.NONE
            mission.waypoints.append(Waypoint(
                x=wp_x, y=wp_y, altitude=altitude,
                action=WaypointAction.FACE_TARGET,
                action_params={"target_x": target_x, "target_y": target_y}
            ))
            if take_photos:
                mission.waypoints.append(Waypoint(
                    x=wp_x, y=wp_y, altitude=altitude,
                    action=WaypointAction.PHOTO
                ))

        mission.status = MissionStatus.READY
        return mission

    def plan_house_inspection(
        self,
        mission_id: str,
        house_identifier: str,
        radius: float = 15.0,
        altitude: float = 20.0,
        num_angles: int = 8
    ) -> Optional[Mission]:
        """
        Plan an inspection mission around a house.

        Args:
            mission_id: ID of the mission
            house_identifier: House letter (A-T) or name
            radius: Inspection circle radius
            altitude: Inspection altitude
            num_angles: Number of photo positions

        Returns:
            Updated Mission or None if failed
        """
        house_name, house = self.drone_service.find_house(house_identifier)
        if not house:
            return None

        mission = self.get_mission(mission_id)
        if mission:
            mission.params["house_name"] = house_name

        return self.plan_inspection_mission(
            mission_id,
            house["x"], house["y"],
            radius, altitude, num_angles
        )

    # =========================================================================
    # Mission Execution
    # =========================================================================

    def start_mission(self, mission_id: str) -> Dict:
        """
        Start executing a mission.

        Args:
            mission_id: ID of the mission to start

        Returns:
            Dict with start status
        """
        mission = self.get_mission(mission_id)
        if not mission:
            return {"error": "Mission not found"}

        if mission.status not in [MissionStatus.READY, MissionStatus.PAUSED]:
            return {"error": f"Mission cannot be started from status {mission.status.value}"}

        if len(mission.waypoints) == 0:
            return {"error": "Mission has no waypoints"}

        # Initialize flags
        self._pause_flags[mission_id] = False
        self._abort_flags[mission_id] = False

        # Start execution in background thread
        thread = threading.Thread(
            target=self._execute_mission,
            args=(mission_id,),
            daemon=True
        )
        self._execution_threads[mission_id] = thread

        mission.status = MissionStatus.IN_PROGRESS
        mission.started_at = datetime.now()

        thread.start()

        return {
            "mission_id": mission_id,
            "status": "started",
            "total_waypoints": len(mission.waypoints)
        }

    def _execute_mission(self, mission_id: str):
        """Execute mission in background thread."""
        mission = self.get_mission(mission_id)
        if not mission:
            return

        default_speed = mission.params.get("speed", 5.0)
        drone_id = mission.drone_ids[0] if mission.drone_ids else None

        if not drone_id:
            mission.status = MissionStatus.ABORTED
            mission.error = "No drone assigned"
            return

        try:
            total_waypoints = len(mission.waypoints)

            while mission.current_waypoint < total_waypoints:
                # Check for abort
                if self._abort_flags.get(mission_id, False):
                    mission.status = MissionStatus.ABORTED
                    self.drone_service.hover(drone_id)
                    return

                # Check for pause
                if self._pause_flags.get(mission_id, False):
                    mission.status = MissionStatus.PAUSED
                    self.drone_service.hover(drone_id)
                    while self._pause_flags.get(mission_id, False):
                        if self._abort_flags.get(mission_id, False):
                            mission.status = MissionStatus.ABORTED
                            return
                        time.sleep(0.5)
                    mission.status = MissionStatus.IN_PROGRESS

                waypoint = mission.waypoints[mission.current_waypoint]
                speed = waypoint.speed or default_speed
                z = -waypoint.altitude

                # Update task
                self.drone_service._drone_tasks[drone_id] = f"Mission: waypoint {mission.current_waypoint + 1}/{total_waypoints}"

                # Move to waypoint
                self.drone_service.client.moveToPositionAsync(
                    waypoint.x, waypoint.y, z, speed, vehicle_name=drone_id
                ).join()
                self.drone_service.client.hoverAsync(vehicle_name=drone_id).join()

                # Execute waypoint action
                self._execute_waypoint_action(drone_id, waypoint, mission)

                # Update progress
                mission.current_waypoint += 1
                mission.progress = mission.current_waypoint / total_waypoints * 100

            # Mission complete
            mission.status = MissionStatus.COMPLETED
            mission.completed_at = datetime.now()
            mission.progress = 100.0
            self.drone_service._drone_tasks[drone_id] = "Mission complete"
            self.drone_service._drone_states[drone_id] = DroneState.HOVERING

        except Exception as e:
            mission.status = MissionStatus.ABORTED
            mission.error = str(e)
            self.drone_service._drone_states[drone_id] = DroneState.HOVERING

    def _execute_waypoint_action(self, drone_id: str, waypoint: Waypoint, mission: Mission):
        """Execute the action at a waypoint."""
        if waypoint.action == WaypointAction.HOVER:
            duration = waypoint.action_params.get("duration", 3)
            time.sleep(duration)

        elif waypoint.action == WaypointAction.PHOTO:
            label = waypoint.action_params.get("label", f"mission_{mission.id}")
            self.drone_service.capture_photo(drone_id, label=label)

        elif waypoint.action == WaypointAction.ROTATE:
            heading = waypoint.action_params.get("heading", 0)
            self.drone_service.rotate_to_heading(drone_id, heading)

        elif waypoint.action == WaypointAction.FACE_TARGET:
            target_x = waypoint.action_params.get("target_x", 0)
            target_y = waypoint.action_params.get("target_y", 0)
            self.drone_service.face_target(drone_id, target_x, target_y)

    def pause_mission(self, mission_id: str) -> Dict:
        """Pause a running mission."""
        mission = self.get_mission(mission_id)
        if not mission:
            return {"error": "Mission not found"}

        if mission.status != MissionStatus.IN_PROGRESS:
            return {"error": f"Mission is not running (status: {mission.status.value})"}

        self._pause_flags[mission_id] = True
        return {"mission_id": mission_id, "status": "pausing"}

    def resume_mission(self, mission_id: str) -> Dict:
        """Resume a paused mission."""
        mission = self.get_mission(mission_id)
        if not mission:
            return {"error": "Mission not found"}

        if mission.status != MissionStatus.PAUSED:
            return {"error": f"Mission is not paused (status: {mission.status.value})"}

        self._pause_flags[mission_id] = False
        return {"mission_id": mission_id, "status": "resuming"}

    def abort_mission(self, mission_id: str) -> Dict:
        """Abort a running or paused mission."""
        mission = self.get_mission(mission_id)
        if not mission:
            return {"error": "Mission not found"}

        if mission.status not in [MissionStatus.IN_PROGRESS, MissionStatus.PAUSED]:
            return {"error": f"Mission cannot be aborted from status {mission.status.value}"}

        self._abort_flags[mission_id] = True
        self._pause_flags[mission_id] = False  # Unpause if paused to allow abort

        # Wait briefly for thread to respond
        time.sleep(0.5)

        return {"mission_id": mission_id, "status": "aborted"}

    # =========================================================================
    # Pre-built Mission Templates
    # =========================================================================

    def create_neighborhood_survey(
        self,
        name: str = "Neighborhood Survey",
        drone_id: str = "Drone1",
        altitude: float = 25.0
    ) -> Mission:
        """Create a mission to survey all houses in the neighborhood."""
        mission = self.create_mission(name, "survey", [drone_id])
        houses = self.drone_service.get_houses()

        mission.waypoints.clear()
        for house_name, house in houses.items():
            mission.waypoints.append(Waypoint(
                x=house["x"], y=house["y"], altitude=altitude,
                action=WaypointAction.PHOTO,
                action_params={"label": house_name.replace(" ", "_")}
            ))

        mission.status = MissionStatus.READY
        return mission

    def create_house_tour(
        self,
        house_letters: List[str],
        name: str = "House Tour",
        drone_id: str = "Drone1"
    ) -> Optional[Mission]:
        """Create a mission to tour specific houses."""
        mission = self.create_mission(name, "waypoint", [drone_id])

        for letter in house_letters:
            house_name, house = self.drone_service.find_house(letter)
            if house:
                mission.waypoints.append(Waypoint(
                    x=house["x"], y=house["y"], altitude=20,
                    action=WaypointAction.PHOTO,
                    action_params={"label": house_name.replace(" ", "_")}
                ))

        if len(mission.waypoints) > 0:
            mission.status = MissionStatus.READY
            return mission
        return None


# Singleton instance
_mission_service: Optional[MissionService] = None


def get_mission_service() -> MissionService:
    """Get or create the singleton MissionService instance."""
    global _mission_service
    if _mission_service is None:
        _mission_service = MissionService()
    return _mission_service
