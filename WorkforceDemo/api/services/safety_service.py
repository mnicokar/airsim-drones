"""
Safety Service - Geofencing and emergency controls.

Provides safety features including:
- Geofencing (operational boundaries)
- Emergency stop
- Return to home
- Collision avoidance considerations
"""

import math
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .drone_service import get_drone_service, DroneService, DroneState


@dataclass
class Geofence:
    """Geofence boundary definition."""
    min_x: float = -100.0
    max_x: float = 100.0
    min_y: float = -100.0
    max_y: float = 100.0
    min_altitude: float = 5.0
    max_altitude: float = 100.0


@dataclass
class NoFlyZone:
    """No-fly zone definition."""
    center_x: float
    center_y: float
    radius: float
    name: str = "No-fly zone"


class SafetyService:
    """
    Safety management service.

    Provides geofencing, emergency controls, and collision avoidance.
    """

    # Default minimum spacing between drones
    MIN_DRONE_SPACING = 5.0  # meters

    def __init__(self, drone_service: Optional[DroneService] = None):
        """Initialize safety service."""
        self._drone_service = drone_service or get_drone_service()
        self._geofence = Geofence()
        self._no_fly_zones: List[NoFlyZone] = []
        self._emergency_active = False

    @property
    def drone_service(self) -> DroneService:
        return self._drone_service

    # =========================================================================
    # Geofencing
    # =========================================================================

    def set_geofence(
        self,
        min_x: float = -100.0,
        max_x: float = 100.0,
        min_y: float = -100.0,
        max_y: float = 100.0,
        min_altitude: float = 5.0,
        max_altitude: float = 100.0
    ) -> Dict:
        """
        Set operational boundary geofence.

        Args:
            min_x: Minimum X coordinate
            max_x: Maximum X coordinate
            min_y: Minimum Y coordinate
            max_y: Maximum Y coordinate
            min_altitude: Minimum altitude in meters
            max_altitude: Maximum altitude in meters

        Returns:
            Dict with geofence configuration
        """
        self._geofence = Geofence(
            min_x=min_x, max_x=max_x,
            min_y=min_y, max_y=max_y,
            min_altitude=min_altitude, max_altitude=max_altitude
        )
        return {
            "min_x": min_x, "max_x": max_x,
            "min_y": min_y, "max_y": max_y,
            "min_altitude": min_altitude, "max_altitude": max_altitude
        }

    def get_geofence(self) -> Dict:
        """Get current geofence configuration."""
        return {
            "min_x": self._geofence.min_x,
            "max_x": self._geofence.max_x,
            "min_y": self._geofence.min_y,
            "max_y": self._geofence.max_y,
            "min_altitude": self._geofence.min_altitude,
            "max_altitude": self._geofence.max_altitude
        }

    def is_within_geofence(self, x: float, y: float, altitude: float) -> bool:
        """Check if a position is within the geofence."""
        return (
            self._geofence.min_x <= x <= self._geofence.max_x and
            self._geofence.min_y <= y <= self._geofence.max_y and
            self._geofence.min_altitude <= altitude <= self._geofence.max_altitude
        )

    def clamp_to_geofence(self, x: float, y: float, altitude: float) -> Tuple[float, float, float]:
        """Clamp a position to be within the geofence."""
        clamped_x = max(self._geofence.min_x, min(self._geofence.max_x, x))
        clamped_y = max(self._geofence.min_y, min(self._geofence.max_y, y))
        clamped_alt = max(self._geofence.min_altitude, min(self._geofence.max_altitude, altitude))
        return (clamped_x, clamped_y, clamped_alt)

    def check_drone_geofence(self, drone_id: str) -> Dict:
        """Check if a drone is within the geofence."""
        pos = self.drone_service.get_drone_position(drone_id)
        altitude = -pos[2]  # Convert to positive altitude

        within = self.is_within_geofence(pos[0], pos[1], altitude)

        return {
            "drone_id": drone_id,
            "position": {"x": pos[0], "y": pos[1], "altitude": altitude},
            "within_geofence": within,
            "violations": {
                "x_low": pos[0] < self._geofence.min_x,
                "x_high": pos[0] > self._geofence.max_x,
                "y_low": pos[1] < self._geofence.min_y,
                "y_high": pos[1] > self._geofence.max_y,
                "altitude_low": altitude < self._geofence.min_altitude,
                "altitude_high": altitude > self._geofence.max_altitude
            }
        }

    # =========================================================================
    # No-Fly Zones
    # =========================================================================

    def add_no_fly_zone(self, center_x: float, center_y: float, radius: float, name: str = "No-fly zone") -> Dict:
        """Add a no-fly zone."""
        zone = NoFlyZone(center_x=center_x, center_y=center_y, radius=radius, name=name)
        self._no_fly_zones.append(zone)
        return {
            "id": len(self._no_fly_zones) - 1,
            "name": name,
            "center": {"x": center_x, "y": center_y},
            "radius": radius
        }

    def remove_no_fly_zone(self, zone_id: int) -> bool:
        """Remove a no-fly zone by ID."""
        if 0 <= zone_id < len(self._no_fly_zones):
            del self._no_fly_zones[zone_id]
            return True
        return False

    def get_no_fly_zones(self) -> List[Dict]:
        """Get all no-fly zones."""
        return [
            {
                "id": i,
                "name": zone.name,
                "center": {"x": zone.center_x, "y": zone.center_y},
                "radius": zone.radius
            }
            for i, zone in enumerate(self._no_fly_zones)
        ]

    def is_in_no_fly_zone(self, x: float, y: float) -> Optional[Dict]:
        """Check if a position is in any no-fly zone."""
        for i, zone in enumerate(self._no_fly_zones):
            dist = math.sqrt((x - zone.center_x) ** 2 + (y - zone.center_y) ** 2)
            if dist < zone.radius:
                return {
                    "id": i,
                    "name": zone.name,
                    "center": {"x": zone.center_x, "y": zone.center_y},
                    "radius": zone.radius
                }
        return None

    # =========================================================================
    # Emergency Controls
    # =========================================================================

    def emergency_stop_all(self) -> Dict:
        """
        Immediately stop all drones and hover in place.

        Returns:
            Dict with status of all drones
        """
        self._emergency_active = True
        drone_ids = self.drone_service.get_available_drones()
        results = {}

        for drone_id in drone_ids:
            try:
                # Stop all movement and hover
                self.drone_service.client.cancelLastTask(vehicle_name=drone_id)
                self.drone_service.client.hoverAsync(vehicle_name=drone_id)
                self.drone_service._drone_states[drone_id] = DroneState.EMERGENCY
                self.drone_service._drone_tasks[drone_id] = "EMERGENCY STOP"
                results[drone_id] = "stopped"
            except Exception as e:
                results[drone_id] = f"error: {str(e)}"

        return {
            "status": "emergency_stop_activated",
            "drones": results,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def clear_emergency(self) -> Dict:
        """Clear emergency status and allow normal operations."""
        self._emergency_active = False
        drone_ids = self.drone_service.get_available_drones()

        for drone_id in drone_ids:
            if self.drone_service._drone_states.get(drone_id) == DroneState.EMERGENCY:
                self.drone_service._drone_states[drone_id] = DroneState.HOVERING
                self.drone_service._drone_tasks[drone_id] = None

        return {"status": "emergency_cleared"}

    def is_emergency_active(self) -> bool:
        """Check if emergency mode is active."""
        return self._emergency_active

    # =========================================================================
    # Return to Home
    # =========================================================================

    def return_home(self, drone_id: str, speed: float = 5.0, wait: bool = True) -> Dict:
        """
        Return a drone to its home position.

        Args:
            drone_id: ID of drone
            speed: Return speed
            wait: If True, wait for return to complete

        Returns:
            Dict with return status
        """
        home = self.drone_service._home_positions.get(drone_id)
        if home is None:
            return {"error": f"No home position stored for {drone_id}"}

        self.drone_service._drone_states[drone_id] = DroneState.FLYING
        self.drone_service._drone_tasks[drone_id] = "Returning home"

        # First go to safe altitude
        current_pos = self.drone_service.get_drone_position(drone_id)
        safe_z = min(current_pos[2], -10)  # At least 10m up

        future = self.drone_service.client.moveToPositionAsync(
            current_pos[0], current_pos[1], safe_z, speed, vehicle_name=drone_id
        )
        if wait:
            future.join()

        # Then go to home position
        future = self.drone_service.client.moveToPositionAsync(
            home[0], home[1], safe_z, speed, vehicle_name=drone_id
        )
        if wait:
            future.join()

        self.drone_service._drone_states[drone_id] = DroneState.HOVERING
        self.drone_service._drone_tasks[drone_id] = "At home position"

        return {
            "drone_id": drone_id,
            "home_position": {"x": home[0], "y": home[1], "z": home[2]},
            "status": "returned"
        }

    def return_all_home(self, speed: float = 5.0) -> Dict:
        """Return all drones to their home positions."""
        drone_ids = self.drone_service.get_available_drones()
        results = {}

        for drone_id in drone_ids:
            result = self.return_home(drone_id, speed, wait=False)
            results[drone_id] = result.get("status", result.get("error", "unknown"))

        # Wait for all to complete
        time.sleep(10)

        return {
            "status": "all_returning",
            "drones": results
        }

    # =========================================================================
    # Collision Avoidance
    # =========================================================================

    def get_drone_distances(self) -> Dict[str, Dict[str, float]]:
        """Get distances between all drones."""
        positions = self.drone_service.get_all_positions()
        drone_ids = list(positions.keys())
        distances = {}

        for i, drone1 in enumerate(drone_ids):
            distances[drone1] = {}
            for drone2 in drone_ids[i + 1:]:
                pos1 = positions[drone1]
                pos2 = positions[drone2]
                dist = math.sqrt(
                    (pos1[0] - pos2[0]) ** 2 +
                    (pos1[1] - pos2[1]) ** 2 +
                    (pos1[2] - pos2[2]) ** 2
                )
                distances[drone1][drone2] = dist
                if drone2 not in distances:
                    distances[drone2] = {}
                distances[drone2][drone1] = dist

        return distances

    def check_collision_risks(self) -> List[Dict]:
        """Check for potential collision risks between drones."""
        distances = self.get_drone_distances()
        risks = []

        for drone1, others in distances.items():
            for drone2, dist in others.items():
                if dist < self.MIN_DRONE_SPACING:
                    risks.append({
                        "drone1": drone1,
                        "drone2": drone2,
                        "distance": dist,
                        "min_required": self.MIN_DRONE_SPACING,
                        "severity": "critical" if dist < 2.0 else "warning"
                    })

        return risks

    def validate_position(self, x: float, y: float, altitude: float) -> Dict:
        """
        Validate if a position is safe to fly to.

        Checks:
        - Within geofence
        - Not in no-fly zone
        """
        issues = []

        # Check geofence
        if not self.is_within_geofence(x, y, altitude):
            clamped = self.clamp_to_geofence(x, y, altitude)
            issues.append({
                "type": "geofence_violation",
                "message": "Position outside geofence",
                "suggested_position": {"x": clamped[0], "y": clamped[1], "altitude": clamped[2]}
            })

        # Check no-fly zones
        nfz = self.is_in_no_fly_zone(x, y)
        if nfz:
            issues.append({
                "type": "no_fly_zone",
                "message": f"Position in no-fly zone: {nfz['name']}",
                "zone": nfz
            })

        return {
            "position": {"x": x, "y": y, "altitude": altitude},
            "valid": len(issues) == 0,
            "issues": issues
        }


# Singleton instance
_safety_service: Optional[SafetyService] = None


def get_safety_service() -> SafetyService:
    """Get or create the singleton SafetyService instance."""
    global _safety_service
    if _safety_service is None:
        _safety_service = SafetyService()
    return _safety_service
