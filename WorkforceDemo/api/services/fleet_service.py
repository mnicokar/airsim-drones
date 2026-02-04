"""
Fleet Service - Fleet orchestration and formation flying.

Provides coordination for multiple drones including formations,
search patterns, and follow-the-leader mode.
"""

import math
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .drone_service import get_drone_service, DroneService, DroneState


class FormationType(Enum):
    """Available formation types."""
    LINE = "line"
    GRID = "grid"
    V_FORMATION = "v"
    CIRCLE = "circle"
    DIAMOND = "diamond"
    ECHELON = "echelon"


class SearchPattern(Enum):
    """Available search patterns."""
    PARALLEL_SWEEP = "parallel_sweep"
    EXPANDING_SQUARE = "expanding_square"
    SECTOR_SEARCH = "sector_search"
    CREEPING_LINE = "creeping_line"


@dataclass
class FormationConfig:
    """Configuration for a formation."""
    formation_type: FormationType
    spacing: float = 10.0  # meters between drones
    center_x: float = 0.0
    center_y: float = 0.0
    altitude: float = 20.0
    heading: float = 0.0  # degrees


@dataclass
class SearchConfig:
    """Configuration for a search pattern."""
    pattern: SearchPattern
    center_x: float
    center_y: float
    width: float  # search area width
    height: float  # search area height
    altitude: float = 20.0
    lane_spacing: float = 15.0  # spacing between search lanes
    speed: float = 5.0


class FleetService:
    """
    Fleet orchestration service.

    Manages coordination of multiple drones for formations,
    search patterns, and coordinated movements.
    """

    def __init__(self, drone_service: Optional[DroneService] = None):
        """Initialize fleet service."""
        self._drone_service = drone_service or get_drone_service()
        self._leader_drone: Optional[str] = None
        self._follower_offsets: Dict[str, Tuple[float, float, float]] = {}
        self._follow_mode_active = False

    @property
    def drone_service(self) -> DroneService:
        return self._drone_service

    # =========================================================================
    # Formation Flying
    # =========================================================================

    def calculate_formation_positions(
        self,
        formation_type: FormationType,
        num_drones: int,
        center_x: float = 0.0,
        center_y: float = 0.0,
        spacing: float = 10.0,
        heading: float = 0.0
    ) -> List[Tuple[float, float]]:
        """
        Calculate positions for a formation.

        Args:
            formation_type: Type of formation
            num_drones: Number of drones in formation
            center_x: Center X coordinate
            center_y: Center Y coordinate
            spacing: Distance between drones
            heading: Formation heading in degrees

        Returns:
            List of (x, y) positions for each drone
        """
        positions = []
        heading_rad = math.radians(heading)

        if formation_type == FormationType.LINE:
            # Side-by-side line perpendicular to heading
            start = -(num_drones - 1) * spacing / 2
            for i in range(num_drones):
                offset_y = start + i * spacing
                # Rotate by heading
                x = center_x - offset_y * math.sin(heading_rad)
                y = center_y + offset_y * math.cos(heading_rad)
                positions.append((x, y))

        elif formation_type == FormationType.GRID:
            # Rectangular grid
            cols = math.ceil(math.sqrt(num_drones))
            rows = math.ceil(num_drones / cols)
            idx = 0
            for row in range(rows):
                for col in range(cols):
                    if idx >= num_drones:
                        break
                    offset_x = (col - (cols - 1) / 2) * spacing
                    offset_y = (row - (rows - 1) / 2) * spacing
                    # Rotate by heading
                    x = center_x + offset_x * math.cos(heading_rad) - offset_y * math.sin(heading_rad)
                    y = center_y + offset_x * math.sin(heading_rad) + offset_y * math.cos(heading_rad)
                    positions.append((x, y))
                    idx += 1

        elif formation_type == FormationType.V_FORMATION:
            # V-shape with leader at front
            angle = math.radians(30)  # V angle from centerline
            positions.append((center_x, center_y))  # Leader at center

            for i in range(1, num_drones):
                side = i % 2  # Alternate left/right
                pos_in_arm = (i + 1) // 2
                offset_forward = -pos_in_arm * spacing * math.cos(angle)
                offset_side = pos_in_arm * spacing * math.sin(angle) * (1 if side == 0 else -1)

                # Rotate by heading
                x = center_x + offset_forward * math.cos(heading_rad) - offset_side * math.sin(heading_rad)
                y = center_y + offset_forward * math.sin(heading_rad) + offset_side * math.cos(heading_rad)
                positions.append((x, y))

        elif formation_type == FormationType.CIRCLE:
            # Circle around center point
            for i in range(num_drones):
                angle = 2 * math.pi * i / num_drones + heading_rad
                x = center_x + spacing * math.cos(angle)
                y = center_y + spacing * math.sin(angle)
                positions.append((x, y))

        elif formation_type == FormationType.DIAMOND:
            # Diamond shape
            if num_drones >= 1:
                positions.append((center_x + spacing, center_y))  # Front
            if num_drones >= 2:
                positions.append((center_x, center_y + spacing))  # Right
            if num_drones >= 3:
                positions.append((center_x - spacing, center_y))  # Back
            if num_drones >= 4:
                positions.append((center_x, center_y - spacing))  # Left
            # Additional drones form inner ring
            for i in range(4, num_drones):
                angle = 2 * math.pi * (i - 4) / max(1, num_drones - 4) + math.pi / 4
                x = center_x + (spacing / 2) * math.cos(angle)
                y = center_y + (spacing / 2) * math.sin(angle)
                positions.append((x, y))

        elif formation_type == FormationType.ECHELON:
            # Diagonal line (like geese)
            for i in range(num_drones):
                offset_x = -i * spacing * 0.7
                offset_y = i * spacing * 0.7
                # Rotate by heading
                x = center_x + offset_x * math.cos(heading_rad) - offset_y * math.sin(heading_rad)
                y = center_y + offset_x * math.sin(heading_rad) + offset_y * math.cos(heading_rad)
                positions.append((x, y))

        return positions

    def form_formation(
        self,
        formation_type: str,
        drone_ids: Optional[List[str]] = None,
        center_x: float = 0.0,
        center_y: float = 0.0,
        altitude: float = 20.0,
        spacing: float = 10.0,
        heading: float = 0.0,
        speed: float = 5.0
    ) -> Dict:
        """
        Arrange drones into a formation.

        Args:
            formation_type: Type of formation (line, grid, v, circle, diamond, echelon)
            drone_ids: List of drones to include, or None for all
            center_x: Center X coordinate of formation
            center_y: Center Y coordinate of formation
            altitude: Formation altitude in meters
            spacing: Distance between drones
            heading: Formation heading in degrees
            speed: Movement speed

        Returns:
            Dict with formation details and assigned positions
        """
        if drone_ids is None:
            drone_ids = self.drone_service.get_available_drones()

        try:
            formation = FormationType(formation_type)
        except ValueError:
            return {"error": f"Unknown formation type: {formation_type}"}

        positions = self.calculate_formation_positions(
            formation, len(drone_ids), center_x, center_y, spacing, heading
        )

        z = -altitude  # AirSim coordinates
        assignments = {}

        # Send all drones to their positions concurrently
        for drone_id, (x, y) in zip(drone_ids, positions):
            self.drone_service._drone_states[drone_id] = DroneState.FLYING
            self.drone_service._drone_tasks[drone_id] = f"Moving to {formation_type} formation"
            self.drone_service.client.moveToPositionAsync(x, y, z, speed, vehicle_name=drone_id)
            assignments[drone_id] = {"x": x, "y": y, "z": z}

        # Wait for all to arrive
        time.sleep(max(5, len(drone_ids) * 2))

        # Hover all
        for drone_id in drone_ids:
            self.drone_service.client.hoverAsync(vehicle_name=drone_id)
            self.drone_service._drone_states[drone_id] = DroneState.HOVERING
            self.drone_service._drone_tasks[drone_id] = f"In {formation_type} formation"

        return {
            "formation": formation_type,
            "center": {"x": center_x, "y": center_y},
            "altitude": altitude,
            "spacing": spacing,
            "heading": heading,
            "assignments": assignments
        }

    def form_line(self, drone_ids: Optional[List[str]] = None, **kwargs) -> Dict:
        """Form a line formation."""
        return self.form_formation("line", drone_ids, **kwargs)

    def form_grid(self, drone_ids: Optional[List[str]] = None, **kwargs) -> Dict:
        """Form a grid formation."""
        return self.form_formation("grid", drone_ids, **kwargs)

    def form_v(self, drone_ids: Optional[List[str]] = None, **kwargs) -> Dict:
        """Form a V-formation."""
        return self.form_formation("v", drone_ids, **kwargs)

    def form_circle(self, drone_ids: Optional[List[str]] = None, **kwargs) -> Dict:
        """Form a circle formation around a point."""
        return self.form_formation("circle", drone_ids, **kwargs)

    # =========================================================================
    # Search Patterns
    # =========================================================================

    def calculate_parallel_sweep_waypoints(
        self,
        num_drones: int,
        center_x: float,
        center_y: float,
        width: float,
        height: float,
        lane_spacing: float
    ) -> List[List[Tuple[float, float]]]:
        """Calculate waypoints for parallel sweep search pattern."""
        waypoints_per_drone = []
        total_lanes = int(width / lane_spacing) + 1

        # Distribute lanes among drones
        lanes_per_drone = max(1, total_lanes // num_drones)

        for i in range(num_drones):
            drone_waypoints = []
            start_lane = i * lanes_per_drone
            end_lane = min(start_lane + lanes_per_drone, total_lanes)

            for lane in range(start_lane, end_lane):
                lane_x = center_x - width / 2 + lane * lane_spacing
                # Alternate direction for each lane
                if (lane - start_lane) % 2 == 0:
                    drone_waypoints.append((lane_x, center_y - height / 2))
                    drone_waypoints.append((lane_x, center_y + height / 2))
                else:
                    drone_waypoints.append((lane_x, center_y + height / 2))
                    drone_waypoints.append((lane_x, center_y - height / 2))

            waypoints_per_drone.append(drone_waypoints)

        return waypoints_per_drone

    def calculate_expanding_square_waypoints(
        self,
        center_x: float,
        center_y: float,
        max_size: float,
        step_size: float
    ) -> List[Tuple[float, float]]:
        """Calculate waypoints for expanding square search pattern."""
        waypoints = [(center_x, center_y)]
        current_size = step_size
        x, y = center_x, center_y
        direction = 0  # 0=right, 1=up, 2=left, 3=down

        while current_size < max_size:
            for _ in range(2):  # Two legs per size increase
                if direction == 0:
                    x += current_size
                elif direction == 1:
                    y += current_size
                elif direction == 2:
                    x -= current_size
                else:
                    y -= current_size
                waypoints.append((x, y))
                direction = (direction + 1) % 4

            current_size += step_size

        return waypoints

    def calculate_sector_search_waypoints(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        num_sectors: int
    ) -> List[List[Tuple[float, float]]]:
        """Calculate waypoints for sector search (radial lines from center)."""
        waypoints_per_sector = []

        for i in range(num_sectors):
            angle = 2 * math.pi * i / num_sectors
            end_x = center_x + radius * math.cos(angle)
            end_y = center_y + radius * math.sin(angle)
            waypoints_per_sector.append([
                (center_x, center_y),
                (end_x, end_y),
                (center_x, center_y)
            ])

        return waypoints_per_sector

    def execute_search(
        self,
        pattern: str,
        drone_ids: Optional[List[str]] = None,
        center_x: float = 0.0,
        center_y: float = 0.0,
        width: float = 100.0,
        height: float = 100.0,
        altitude: float = 20.0,
        lane_spacing: float = 15.0,
        speed: float = 5.0
    ) -> Dict:
        """
        Execute a coordinated search pattern.

        Args:
            pattern: Search pattern type (parallel_sweep, expanding_square, sector_search)
            drone_ids: List of drones to use
            center_x: Center X of search area
            center_y: Center Y of search area
            width: Search area width
            height: Search area height
            altitude: Search altitude
            lane_spacing: Spacing between search lanes
            speed: Search speed

        Returns:
            Dict with search pattern details
        """
        if drone_ids is None:
            drone_ids = self.drone_service.get_available_drones()

        z = -altitude

        if pattern == "parallel_sweep":
            waypoints = self.calculate_parallel_sweep_waypoints(
                len(drone_ids), center_x, center_y, width, height, lane_spacing
            )

            # Execute search for each drone
            for i, drone_id in enumerate(drone_ids):
                if i < len(waypoints):
                    self.drone_service._drone_states[drone_id] = DroneState.FLYING
                    self.drone_service._drone_tasks[drone_id] = "Executing parallel sweep"

                    # Fly through waypoints
                    for wx, wy in waypoints[i]:
                        self.drone_service.client.moveToPositionAsync(
                            wx, wy, z, speed, vehicle_name=drone_id
                        ).join()

                    self.drone_service._drone_states[drone_id] = DroneState.HOVERING
                    self.drone_service._drone_tasks[drone_id] = "Search complete"

        elif pattern == "expanding_square":
            # Only one drone does expanding square
            waypoints = self.calculate_expanding_square_waypoints(
                center_x, center_y, max(width, height), lane_spacing
            )
            drone_id = drone_ids[0]
            self.drone_service._drone_states[drone_id] = DroneState.FLYING
            self.drone_service._drone_tasks[drone_id] = "Executing expanding square"

            for wx, wy in waypoints:
                self.drone_service.client.moveToPositionAsync(
                    wx, wy, z, speed, vehicle_name=drone_id
                ).join()

            self.drone_service._drone_states[drone_id] = DroneState.HOVERING
            self.drone_service._drone_tasks[drone_id] = "Search complete"

        elif pattern == "sector_search":
            radius = max(width, height) / 2
            sector_waypoints = self.calculate_sector_search_waypoints(
                center_x, center_y, radius, len(drone_ids)
            )

            for i, drone_id in enumerate(drone_ids):
                if i < len(sector_waypoints):
                    self.drone_service._drone_states[drone_id] = DroneState.FLYING
                    self.drone_service._drone_tasks[drone_id] = f"Searching sector {i + 1}"

                    for wx, wy in sector_waypoints[i]:
                        self.drone_service.client.moveToPositionAsync(
                            wx, wy, z, speed, vehicle_name=drone_id
                        ).join()

                    self.drone_service._drone_states[drone_id] = DroneState.HOVERING
                    self.drone_service._drone_tasks[drone_id] = "Search complete"

        return {
            "pattern": pattern,
            "area": {"center_x": center_x, "center_y": center_y, "width": width, "height": height},
            "drones_used": drone_ids,
            "status": "completed"
        }

    # =========================================================================
    # Follow-the-Leader Mode
    # =========================================================================

    def set_leader(self, leader_id: str, follower_ids: Optional[List[str]] = None) -> Dict:
        """
        Set up follow-the-leader mode.

        Args:
            leader_id: ID of the leader drone
            follower_ids: IDs of follower drones, or None for all except leader

        Returns:
            Dict with leader/follower configuration
        """
        all_drones = self.drone_service.get_available_drones()

        if leader_id not in all_drones:
            return {"error": f"Leader drone {leader_id} not found"}

        if follower_ids is None:
            follower_ids = [d for d in all_drones if d != leader_id]

        self._leader_drone = leader_id
        leader_pos = self.drone_service.get_drone_position(leader_id)

        # Calculate offsets for followers based on V-formation
        self._follower_offsets = {}
        for i, follower_id in enumerate(follower_ids):
            side = i % 2
            pos_in_arm = (i + 1) // 2 + 1
            offset_x = -pos_in_arm * 8  # Behind leader
            offset_y = pos_in_arm * 5 * (1 if side == 0 else -1)  # Left/right
            self._follower_offsets[follower_id] = (offset_x, offset_y, 0)

        return {
            "leader": leader_id,
            "followers": follower_ids,
            "offsets": {k: {"x": v[0], "y": v[1], "z": v[2]} for k, v in self._follower_offsets.items()}
        }

    def update_followers(self, speed: float = 5.0):
        """
        Update follower positions based on leader position.
        Call this periodically to maintain formation.
        """
        if not self._leader_drone or not self._follower_offsets:
            return

        leader_pos = self.drone_service.get_drone_position(self._leader_drone)
        leader_heading = self.drone_service.get_drone_heading(self._leader_drone)
        heading_rad = math.radians(leader_heading)

        for follower_id, (off_x, off_y, off_z) in self._follower_offsets.items():
            # Rotate offset by leader heading
            rot_x = off_x * math.cos(heading_rad) - off_y * math.sin(heading_rad)
            rot_y = off_x * math.sin(heading_rad) + off_y * math.cos(heading_rad)

            target_x = leader_pos[0] + rot_x
            target_y = leader_pos[1] + rot_y
            target_z = leader_pos[2] + off_z

            self.drone_service.client.moveToPositionAsync(
                target_x, target_y, target_z, speed,
                vehicle_name=follower_id
            )

    def start_follow_mode(self, leader_id: str, follower_ids: Optional[List[str]] = None, speed: float = 5.0) -> Dict:
        """Start follow-the-leader mode."""
        config = self.set_leader(leader_id, follower_ids)
        if "error" in config:
            return config

        self._follow_mode_active = True
        return {**config, "status": "active"}

    def stop_follow_mode(self):
        """Stop follow-the-leader mode."""
        self._follow_mode_active = False
        self._leader_drone = None
        self._follower_offsets = {}

        # Hover all drones
        self.drone_service.hover_all()

        return {"status": "stopped"}

    # =========================================================================
    # Fleet Movement
    # =========================================================================

    def move_fleet_to(
        self,
        x: float,
        y: float,
        altitude: float = 20.0,
        drone_ids: Optional[List[str]] = None,
        maintain_formation: bool = True,
        speed: float = 5.0
    ) -> Dict:
        """
        Move entire fleet to a new position.

        Args:
            x: Target X coordinate (center of fleet)
            y: Target Y coordinate (center of fleet)
            altitude: Target altitude
            drone_ids: Drones to move, or None for all
            maintain_formation: If True, maintain current relative positions
            speed: Movement speed

        Returns:
            Dict with movement details
        """
        if drone_ids is None:
            drone_ids = self.drone_service.get_available_drones()

        positions = self.drone_service.get_all_positions()
        z = -altitude

        if maintain_formation and len(drone_ids) > 1:
            # Calculate center of current formation
            center_x = sum(positions[d][0] for d in drone_ids) / len(drone_ids)
            center_y = sum(positions[d][1] for d in drone_ids) / len(drone_ids)

            # Move each drone maintaining relative position
            for drone_id in drone_ids:
                offset_x = positions[drone_id][0] - center_x
                offset_y = positions[drone_id][1] - center_y
                self.drone_service.client.moveToPositionAsync(
                    x + offset_x, y + offset_y, z, speed, vehicle_name=drone_id
                )
        else:
            # All drones go to same point
            for drone_id in drone_ids:
                self.drone_service.client.moveToPositionAsync(
                    x, y, z, speed, vehicle_name=drone_id
                )

        return {
            "target": {"x": x, "y": y, "altitude": altitude},
            "drones": drone_ids,
            "maintain_formation": maintain_formation
        }


# Singleton instance
_fleet_service: Optional[FleetService] = None


def get_fleet_service() -> FleetService:
    """Get or create the singleton FleetService instance."""
    global _fleet_service
    if _fleet_service is None:
        _fleet_service = FleetService()
    return _fleet_service
