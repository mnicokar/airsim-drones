"""
Drone Service - Core drone control logic.

Provides clean function interface for all drone operations that can be called
directly from Python or through the REST API.
"""

import airsim
import json
import logging
import math
import time
import os
import re
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DroneState(Enum):
    """Drone operational states."""
    IDLE = "idle"
    TAKING_OFF = "taking_off"
    FLYING = "flying"
    HOVERING = "hovering"
    LANDING = "landing"
    LANDED = "landed"
    EMERGENCY = "emergency"


@dataclass
class DroneStatus:
    """Status information for a single drone."""
    drone_id: str
    position: Tuple[float, float, float]  # x, y, z
    velocity: Tuple[float, float, float]  # vx, vy, vz
    heading: float  # degrees
    state: DroneState
    current_task: Optional[str] = None
    home_position: Optional[Tuple[float, float, float]] = None

    def to_dict(self) -> Dict:
        return {
            "drone_id": self.drone_id,
            "position": {"x": self.position[0], "y": self.position[1], "z": self.position[2]},
            "velocity": {"vx": self.velocity[0], "vy": self.velocity[1], "vz": self.velocity[2]},
            "heading": self.heading,
            "altitude": -self.position[2],  # Convert to positive altitude
            "state": self.state.value,
            "current_task": self.current_task,
            "home_position": {"x": self.home_position[0], "y": self.home_position[1], "z": self.home_position[2]} if self.home_position else None
        }


class DroneService:
    """
    Core drone control service.

    Manages connection to AirSim and provides methods for controlling
    individual drones or the entire fleet.
    """

    # Default configuration
    DEFAULT_ALTITUDE = -20  # 20m up (negative Z is up in AirSim)
    DEFAULT_SPEED = 5
    CAMERA_PITCH = -20  # Degrees to tilt camera down
    PHOTO_DIR = "house_photos"

    def __init__(self, labels_file: str = "house_labels.json"):
        """Initialize drone service."""
        self._client: Optional[airsim.MultirotorClient] = None
        self._labels_file = labels_file
        self._houses: Dict[str, Dict] = {}
        self._drone_states: Dict[str, DroneState] = {}
        self._drone_tasks: Dict[str, str] = {}
        self._home_positions: Dict[str, Tuple[float, float, float]] = {}
        self._available_drones: List[str] = []
        self._connected = False
        self._yolo_model = None

    def _get_yolo_model(self):
        """Lazy-load the YOLO model on first use."""
        if self._yolo_model is None:
            try:
                from ultralytics import YOLO
                self._yolo_model = YOLO("yolov8n.pt")
                logger.info("YOLO model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load YOLO model: {e}")
                return None
        return self._yolo_model

    def _run_yolo_detection(self, img: np.ndarray) -> np.ndarray:
        """Run YOLO object detection and draw bounding boxes on the image."""
        model = self._get_yolo_model()
        if model is None:
            return img

        try:
            results = model.predict(img, conf=0.25, verbose=False)
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    class_name = model.names[cls_id]

                    # Color based on class id
                    colors = [
                        (0, 255, 0), (255, 0, 0), (0, 0, 255),
                        (255, 255, 0), (0, 255, 255), (255, 0, 255),
                    ]
                    color = colors[cls_id % len(colors)]

                    # Draw bounding box
                    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

                    # Draw label with background
                    label = f"{class_name} {conf:.0%}"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.5
                    thickness = 1
                    (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
                    cv2.rectangle(img, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
                    cv2.putText(img, label, (x1 + 2, y1 - 4), font, font_scale, (255, 255, 255), thickness)
        except Exception as e:
            logger.warning(f"YOLO detection failed: {e}")

        return img

    @property
    def client(self) -> airsim.MultirotorClient:
        """Get or create AirSim client connection."""
        if self._client is None:
            self._client = airsim.MultirotorClient()
            self._client.confirmConnection()
            self._connected = True
        return self._client

    @property
    def is_connected(self) -> bool:
        """Check if connected to AirSim."""
        return self._connected

    def connect(self) -> bool:
        """Establish connection to AirSim."""
        try:
            _ = self.client
            self._load_houses()
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from AirSim."""
        self._client = None
        self._connected = False

    def _load_houses(self):
        """Load house labels from JSON file."""
        try:
            labels_path = Path(__file__).parent.parent.parent / self._labels_file
            if not labels_path.exists():
                labels_path = Path(self._labels_file)
            with open(labels_path, 'r') as f:
                self._houses = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load house labels: {e}")
            self._houses = {}

    def get_houses(self) -> Dict[str, Dict]:
        """Get all house locations."""
        if not self._houses:
            self._load_houses()
        return self._houses

    def find_house(self, identifier: str) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Find a house by letter or partial name.

        Args:
            identifier: House letter (A-T) or partial name

        Returns:
            Tuple of (house_name, house_data) or (None, None) if not found
        """
        houses = self.get_houses()

        # Try exact match first
        search = f"House {identifier.upper()}"
        if search in houses:
            return search, houses[search]

        # Try partial match
        matches = [n for n in houses if identifier.upper() in n.upper()]
        if matches:
            return matches[0], houses[matches[0]]

        return None, None

    # =========================================================================
    # Drone Discovery and Initialization
    # =========================================================================

    def discover_drones(self, max_drones: int = 10) -> List[str]:
        """
        Discover available drones in the simulation.

        Args:
            max_drones: Maximum number of drones to check for

        Returns:
            List of available drone IDs
        """
        available = []
        for i in range(1, max_drones + 1):
            drone_id = f"Drone{i}"
            try:
                self.client.getMultirotorState(vehicle_name=drone_id)
                available.append(drone_id)
            except:
                break
        self._available_drones = available
        return available

    def get_available_drones(self) -> List[str]:
        """Get list of available drones."""
        if not self._available_drones:
            self.discover_drones()
        return self._available_drones

    def initialize_drone(self, drone_id: str) -> bool:
        """
        Initialize a single drone for API control.

        Args:
            drone_id: ID of drone to initialize

        Returns:
            True if successful
        """
        try:
            self.client.enableApiControl(True, drone_id)
            self.client.armDisarm(True, drone_id)
            self._drone_states[drone_id] = DroneState.LANDED

            # Store home position
            state = self.client.getMultirotorState(vehicle_name=drone_id)
            pos = state.kinematics_estimated.position
            self._home_positions[drone_id] = (pos.x_val, pos.y_val, pos.z_val)

            return True
        except Exception as e:
            print(f"Error initializing {drone_id}: {e}")
            return False

    def initialize_all_drones(self, drone_ids: Optional[List[str]] = None) -> List[str]:
        """
        Initialize all drones for API control.

        Args:
            drone_ids: List of drone IDs, or None to discover automatically

        Returns:
            List of successfully initialized drone IDs
        """
        if drone_ids is None:
            drone_ids = self.discover_drones()

        initialized = []
        for drone_id in drone_ids:
            if self.initialize_drone(drone_id):
                initialized.append(drone_id)

        return initialized

    def release_drone(self, drone_id: str):
        """Release API control of a drone."""
        try:
            self.client.armDisarm(False, drone_id)
            self.client.enableApiControl(False, drone_id)
            del self._drone_states[drone_id]
        except:
            pass

    # =========================================================================
    # Status and Position
    # =========================================================================

    def get_drone_position(self, drone_id: str) -> Tuple[float, float, float]:
        """
        Get current position of a drone.

        Returns:
            Tuple of (x, y, z) coordinates
        """
        state = self.client.getMultirotorState(vehicle_name=drone_id)
        pos = state.kinematics_estimated.position
        return (pos.x_val, pos.y_val, pos.z_val)

    def get_drone_velocity(self, drone_id: str) -> Tuple[float, float, float]:
        """Get current velocity of a drone."""
        state = self.client.getMultirotorState(vehicle_name=drone_id)
        vel = state.kinematics_estimated.linear_velocity
        return (vel.x_val, vel.y_val, vel.z_val)

    def get_drone_heading(self, drone_id: str) -> float:
        """Get current heading (yaw) of a drone in degrees."""
        state = self.client.getMultirotorState(vehicle_name=drone_id)
        orientation = state.kinematics_estimated.orientation
        # Convert quaternion to euler angles
        pitch, roll, yaw = airsim.to_eularian_angles(orientation)
        return math.degrees(yaw)

    def get_drone_status(self, drone_id: str) -> DroneStatus:
        """Get comprehensive status of a drone."""
        position = self.get_drone_position(drone_id)
        velocity = self.get_drone_velocity(drone_id)
        heading = self.get_drone_heading(drone_id)
        state = self._drone_states.get(drone_id, DroneState.IDLE)
        task = self._drone_tasks.get(drone_id)
        home = self._home_positions.get(drone_id)

        return DroneStatus(
            drone_id=drone_id,
            position=position,
            velocity=velocity,
            heading=heading,
            state=state,
            current_task=task,
            home_position=home
        )

    def get_all_positions(self) -> Dict[str, Tuple[float, float, float]]:
        """Get positions of all available drones."""
        positions = {}
        for drone_id in self.get_available_drones():
            positions[drone_id] = self.get_drone_position(drone_id)
        return positions

    def get_fleet_status(self) -> List[DroneStatus]:
        """Get status of all drones in the fleet."""
        statuses = []
        for drone_id in self.get_available_drones():
            try:
                statuses.append(self.get_drone_status(drone_id))
            except:
                pass
        return statuses

    # =========================================================================
    # Basic Movement Commands
    # =========================================================================

    def takeoff(self, drone_id: str, altitude: Optional[float] = None, wait: bool = True) -> bool:
        """
        Take off a drone to specified altitude.

        Args:
            drone_id: ID of drone
            altitude: Target altitude in meters (positive), defaults to DEFAULT_ALTITUDE
            wait: If True, wait for takeoff to complete

        Returns:
            True if successful
        """
        if altitude is None:
            altitude = -self.DEFAULT_ALTITUDE  # Convert to positive

        z = -altitude  # Convert to AirSim coordinates (negative Z is up)

        self._drone_states[drone_id] = DroneState.TAKING_OFF
        self._drone_tasks[drone_id] = f"Taking off to {altitude}m"

        try:
            future = self.client.takeoffAsync(vehicle_name=drone_id)
            if wait:
                future.join()
                # Move to target altitude
                self.client.moveToZAsync(z, self.DEFAULT_SPEED, vehicle_name=drone_id).join()

            self._drone_states[drone_id] = DroneState.HOVERING
            self._drone_tasks[drone_id] = None
            return True
        except Exception as e:
            print(f"Takeoff error for {drone_id}: {e}")
            return False

    def land(self, drone_id: str, wait: bool = True) -> bool:
        """
        Land a drone.

        Args:
            drone_id: ID of drone
            wait: If True, wait for landing to complete

        Returns:
            True if successful
        """
        self._drone_states[drone_id] = DroneState.LANDING
        self._drone_tasks[drone_id] = "Landing"

        try:
            # Reset camera pitch before landing
            self._set_camera_pitch(drone_id, 0)

            future = self.client.landAsync(vehicle_name=drone_id)
            if wait:
                future.join()

            self._drone_states[drone_id] = DroneState.LANDED
            self._drone_tasks[drone_id] = None
            return True
        except Exception as e:
            print(f"Landing error for {drone_id}: {e}")
            return False

    def hover(self, drone_id: str) -> bool:
        """
        Command drone to hover in place.

        Args:
            drone_id: ID of drone

        Returns:
            True if successful
        """
        try:
            self.client.hoverAsync(vehicle_name=drone_id).join()
            self._drone_states[drone_id] = DroneState.HOVERING
            self._drone_tasks[drone_id] = None
            return True
        except Exception as e:
            print(f"Hover error for {drone_id}: {e}")
            return False

    def move_to_position(
        self,
        drone_id: str,
        x: float,
        y: float,
        z: Optional[float] = None,
        speed: Optional[float] = None,
        wait: bool = True
    ) -> bool:
        """
        Move drone to a specific position.

        Args:
            drone_id: ID of drone
            x: Target X coordinate
            y: Target Y coordinate
            z: Target Z coordinate (negative is up), defaults to current altitude
            speed: Movement speed in m/s
            wait: If True, wait for movement to complete

        Returns:
            True if successful
        """
        if z is None:
            z = self.get_drone_position(drone_id)[2]
        if speed is None:
            speed = self.DEFAULT_SPEED

        self._drone_states[drone_id] = DroneState.FLYING
        self._drone_tasks[drone_id] = f"Moving to ({x:.1f}, {y:.1f}, {-z:.1f})"

        try:
            future = self.client.moveToPositionAsync(x, y, z, speed, vehicle_name=drone_id)
            if wait:
                future.join()
                self.client.hoverAsync(vehicle_name=drone_id).join()

            self._drone_states[drone_id] = DroneState.HOVERING
            self._drone_tasks[drone_id] = None
            return True
        except Exception as e:
            print(f"Move error for {drone_id}: {e}")
            return False

    def move_to_altitude(self, drone_id: str, altitude: float, speed: Optional[float] = None, wait: bool = True) -> bool:
        """
        Move drone to a specific altitude.

        Args:
            drone_id: ID of drone
            altitude: Target altitude in meters (positive)
            speed: Vertical speed in m/s
            wait: If True, wait for movement to complete

        Returns:
            True if successful
        """
        if speed is None:
            speed = self.DEFAULT_SPEED

        z = -altitude  # Convert to AirSim coordinates

        self._drone_states[drone_id] = DroneState.FLYING
        self._drone_tasks[drone_id] = f"Changing altitude to {altitude}m"

        try:
            future = self.client.moveToZAsync(z, speed, vehicle_name=drone_id)
            if wait:
                future.join()

            self._drone_states[drone_id] = DroneState.HOVERING
            self._drone_tasks[drone_id] = None
            return True
        except Exception as e:
            print(f"Altitude change error for {drone_id}: {e}")
            return False

    def goto_house(
        self,
        drone_id: str,
        house_identifier: str,
        speed: Optional[float] = None,
        view_distance: float = 10,
        wait: bool = True
    ) -> Optional[Dict]:
        """
        Navigate drone to view a specific house.

        Args:
            drone_id: ID of drone
            house_identifier: House letter (A-T) or name
            speed: Movement speed in m/s
            view_distance: Distance to hover from house (0 = directly above)
            wait: If True, wait for movement to complete

        Returns:
            Dict with house info and viewing position, or None if house not found
        """
        if speed is None:
            speed = self.DEFAULT_SPEED

        house_name, house = self.find_house(house_identifier)
        if house is None:
            return None

        hx, hy = house['x'], house['y']

        # Get current position to determine approach angle
        current_x, current_y, current_z = self.get_drone_position(drone_id)

        # Calculate offset position (approach from current direction)
        dx = current_x - hx
        dy = current_y - hy
        dist = math.sqrt(dx * dx + dy * dy)

        if dist > 1:
            offset_x = hx + (dx / dist) * view_distance
            offset_y = hy + (dy / dist) * view_distance
        else:
            offset_x = hx + view_distance
            offset_y = hy

        self._drone_states[drone_id] = DroneState.FLYING
        self._drone_tasks[drone_id] = f"Going to {house_name}"

        try:
            # Face the house
            yaw = math.degrees(math.atan2(hy - current_y, hx - current_x))
            self.client.rotateToYawAsync(yaw, timeout_sec=10, vehicle_name=drone_id).join()

            # Tilt camera down
            self._set_camera_pitch(drone_id, self.CAMERA_PITCH)

            # Fly to viewing position
            future = self.client.moveToPositionAsync(
                offset_x, offset_y, self.DEFAULT_ALTITUDE, speed,
                timeout_sec=60, vehicle_name=drone_id
            )
            if wait:
                future.join()
                self.client.hoverAsync(vehicle_name=drone_id).join()

            self._drone_states[drone_id] = DroneState.HOVERING
            self._drone_tasks[drone_id] = f"Viewing {house_name}"

            return {
                "house_name": house_name,
                "house_position": {"x": hx, "y": hy},
                "viewing_position": {"x": offset_x, "y": offset_y, "z": self.DEFAULT_ALTITUDE}
            }
        except Exception as e:
            print(f"Goto house error for {drone_id}: {e}")
            return None

    # =========================================================================
    # Rotation Commands
    # =========================================================================

    def rotate_to_heading(self, drone_id: str, heading: float, wait: bool = True) -> bool:
        """
        Rotate drone to face a specific heading.

        Args:
            drone_id: ID of drone
            heading: Target heading in degrees (0-360, 0=North, 90=East)
            wait: If True, wait for rotation to complete

        Returns:
            True if successful
        """
        try:
            future = self.client.rotateToYawAsync(heading, timeout_sec=10, vehicle_name=drone_id)
            if wait:
                future.join()
            return True
        except Exception as e:
            print(f"Rotation error for {drone_id}: {e}")
            return False

    def face_target(self, drone_id: str, target_x: float, target_y: float, wait: bool = True) -> bool:
        """
        Rotate drone to face a target position.

        Args:
            drone_id: ID of drone
            target_x: Target X coordinate
            target_y: Target Y coordinate
            wait: If True, wait for rotation to complete

        Returns:
            True if successful
        """
        current_x, current_y, _ = self.get_drone_position(drone_id)
        heading = math.degrees(math.atan2(target_y - current_y, target_x - current_x))
        return self.rotate_to_heading(drone_id, heading, wait)

    def _set_camera_pitch(self, drone_id: str, pitch_degrees: float):
        """Set camera pitch for a drone."""
        pitch_rad = math.radians(pitch_degrees)
        q = airsim.to_quaternion(pitch_rad, 0, 0)
        camera_pose = airsim.Pose(airsim.Vector3r(0, 0, 0), q)
        self.client.simSetCameraPose("0", camera_pose, vehicle_name=drone_id)

    # =========================================================================
    # Camera and Photo Commands
    # =========================================================================

    def capture_photo(
        self,
        drone_id: str,
        image_types: Optional[List[str]] = None,
        save_to_disk: bool = True,
        label: str = "photo"
    ) -> Dict[str, Any]:
        """
        Capture photos from drone camera.

        Args:
            drone_id: ID of drone
            image_types: List of image types to capture: "scene", "depth", "segmentation"
            save_to_disk: If True, save images to disk
            label: Label for saved files

        Returns:
            Dict with image data and file paths
        """
        if image_types is None:
            image_types = ["scene", "depth", "segmentation"]

        type_map = {
            "scene": airsim.ImageType.Scene,
            "depth": airsim.ImageType.DepthPerspective,
            "segmentation": airsim.ImageType.Segmentation
        }

        results = {"images": {}, "files": {}}

        timestamp = time.strftime("%Y%m%d_%H%M%S")

        if save_to_disk:
            os.makedirs(self.PHOTO_DIR, exist_ok=True)

        for img_type in image_types:
            if img_type not in type_map:
                continue

            is_float = (img_type == "depth")
            responses = self.client.simGetImages([
                airsim.ImageRequest("0", type_map[img_type], is_float, False)
            ], vehicle_name=drone_id)

            if not responses or len(responses) == 0:
                continue

            response = responses[0]

            if img_type == "depth":
                img = airsim.list_to_2d_float_array(response.image_data_float, response.width, response.height)
                img = np.clip(img, 0, 100)
                img = (img / 100 * 255).astype(np.uint8)
                img = cv2.applyColorMap(img, cv2.COLORMAP_JET)
            else:
                img1d = np.frombuffer(response.image_data_uint8, dtype=np.uint8)
                img = img1d.reshape(response.height, response.width, 3)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            results["images"][img_type] = img

            if save_to_disk:
                filename = f"{self.PHOTO_DIR}/{label}_{drone_id}_{timestamp}_{img_type}.png"
                cv2.imwrite(filename, img)
                results["files"][img_type] = filename

        return results

    def get_camera_frame(self, drone_id: str, image_type: str = "scene", max_width: int = 640) -> Optional[np.ndarray]:
        """
        Get a single camera frame from drone.

        Args:
            drone_id: ID of drone
            image_type: Type of image: "scene", "depth", "segmentation"
            max_width: Maximum width of returned image (for faster transfer)

        Returns:
            Image as numpy array, or None if failed
        """
        type_map = {
            "scene": airsim.ImageType.Scene,
            "depth": airsim.ImageType.DepthPerspective,
            "segmentation": airsim.ImageType.Segmentation
        }

        if image_type not in type_map:
            return None

        is_float = (image_type == "depth")
        responses = self.client.simGetImages([
            airsim.ImageRequest("0", type_map[image_type], is_float, False)
        ], vehicle_name=drone_id)

        if not responses or len(responses) == 0:
            return None

        response = responses[0]

        if image_type == "depth":
            img = airsim.list_to_2d_float_array(response.image_data_float, response.width, response.height)
            img = np.clip(img, 0, 100)
            img = (img / 100 * 255).astype(np.uint8)
            img = cv2.applyColorMap(img, cv2.COLORMAP_JET)
        else:
            img1d = np.frombuffer(response.image_data_uint8, dtype=np.uint8)
            img = img1d.reshape(response.height, response.width, 3)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        # Resize for faster transfer if image is larger than max_width
        if img.shape[1] > max_width:
            scale = max_width / img.shape[1]
            new_height = int(img.shape[0] * scale)
            img = cv2.resize(img, (max_width, new_height), interpolation=cv2.INTER_AREA)

        # Run YOLO object detection on scene images
        if image_type == "scene":
            img = self._run_yolo_detection(img)

        return img

    # =========================================================================
    # Multi-Drone Commands
    # =========================================================================

    def takeoff_all(self, drone_ids: Optional[List[str]] = None, altitude: Optional[float] = None) -> List[str]:
        """
        Take off all specified drones.

        Args:
            drone_ids: List of drone IDs, or None for all available
            altitude: Target altitude in meters

        Returns:
            List of drones that successfully took off
        """
        if drone_ids is None:
            drone_ids = self.get_available_drones()

        if altitude is None:
            altitude = -self.DEFAULT_ALTITUDE

        z = -altitude

        # Start all takeoffs
        for drone_id in drone_ids:
            self._drone_states[drone_id] = DroneState.TAKING_OFF
            self._drone_tasks[drone_id] = f"Taking off to {altitude}m"
            self.client.takeoffAsync(vehicle_name=drone_id)

        time.sleep(4)  # Wait for takeoffs

        # Move all to altitude
        for drone_id in drone_ids:
            self.client.moveToZAsync(z, self.DEFAULT_SPEED, vehicle_name=drone_id)

        time.sleep(3)  # Wait for altitude

        # Update states
        for drone_id in drone_ids:
            self._drone_states[drone_id] = DroneState.HOVERING
            self._drone_tasks[drone_id] = None

        return drone_ids

    def land_all(self, drone_ids: Optional[List[str]] = None) -> List[str]:
        """
        Land all specified drones.

        Args:
            drone_ids: List of drone IDs, or None for all available

        Returns:
            List of drones that started landing
        """
        if drone_ids is None:
            drone_ids = self.get_available_drones()

        # Start all landings
        for drone_id in drone_ids:
            self._drone_states[drone_id] = DroneState.LANDING
            self._drone_tasks[drone_id] = "Landing"
            self._set_camera_pitch(drone_id, 0)
            self.client.landAsync(vehicle_name=drone_id)

        time.sleep(5)  # Wait for landings

        # Update states
        for drone_id in drone_ids:
            self._drone_states[drone_id] = DroneState.LANDED
            self._drone_tasks[drone_id] = None

        return drone_ids

    def reset_all(self) -> List[str]:
        """
        Reset all drones to their original starting positions using AirSim's
        native reset. This returns drones to the positions defined in
        AirSim settings.json.

        Returns:
            List of drones that were reset
        """
        drone_ids = self.get_available_drones()

        # Use AirSim's native reset to return all vehicles to spawn positions
        self.client.reset()

        # Clear internal state
        self._drone_states.clear()
        self._drone_tasks.clear()
        self._home_positions.clear()

        time.sleep(2)  # Give AirSim a moment to finish resetting

        # Re-initialize all drones (re-enables API control, re-arms, captures true home positions)
        initialized = []
        for drone_id in drone_ids:
            if self.initialize_drone(drone_id):
                initialized.append(drone_id)

        return initialized

    def hover_all(self, drone_ids: Optional[List[str]] = None) -> List[str]:
        """
        Command all drones to hover in place.

        Args:
            drone_ids: List of drone IDs, or None for all available

        Returns:
            List of drones that are now hovering
        """
        if drone_ids is None:
            drone_ids = self.get_available_drones()

        for drone_id in drone_ids:
            self.client.hoverAsync(vehicle_name=drone_id)
            self._drone_states[drone_id] = DroneState.HOVERING
            self._drone_tasks[drone_id] = None

        return drone_ids

    # =========================================================================
    # Formation Flying
    # =========================================================================

    def get_formation_offsets(self, formation: str, num_drones: int, spacing: float = 8.0) -> List[Tuple[float, float]]:
        """
        Get position offsets for a formation.

        Args:
            formation: Formation type ("v", "line", "diamond", "echelon")
            num_drones: Number of drones in formation (including leader)
            spacing: Distance between drones in meters

        Returns:
            List of (x_offset, y_offset) tuples for each drone position
        """
        offsets = [(0.0, 0.0)]  # Leader at origin

        if formation == "v":
            # V-formation: leader at front, others trail back in V shape
            for i in range(1, num_drones):
                side = 1 if i % 2 == 1 else -1  # Alternate left/right
                row = (i + 1) // 2  # Row number (1, 1, 2, 2, 3, 3...)
                x_offset = -row * spacing  # Behind leader
                y_offset = side * row * spacing  # Left or right
                offsets.append((x_offset, y_offset))

        elif formation == "line":
            # Line formation: side by side
            for i in range(1, num_drones):
                side = 1 if i % 2 == 1 else -1
                pos = (i + 1) // 2
                offsets.append((0.0, side * pos * spacing))

        elif formation == "diamond":
            # Diamond formation
            positions = [
                (0, 0),           # Leader (front)
                (-spacing, -spacing),   # Back-left
                (-spacing, spacing),    # Back-right
                (-spacing * 2, 0),      # Rear
                (-spacing, 0),          # Middle
            ]
            offsets = positions[:num_drones]

        elif formation == "echelon":
            # Echelon formation: diagonal line
            for i in range(1, num_drones):
                offsets.append((-i * spacing, i * spacing))

        elif formation == "column":
            # Column formation: single file behind leader
            for i in range(1, num_drones):
                offsets.append((-i * spacing, 0.0))

        else:
            # Default to V if unknown
            return self.get_formation_offsets("v", num_drones, spacing)

        return offsets

    def group_flight(
        self,
        leader_id: str,
        house_identifier: str,
        formation: str = "v",
        spacing: float = 8.0,
        speed: float = 5.0,
        wait: bool = False
    ) -> Dict[str, Any]:
        """
        Fly all drones in formation to a house with a designated leader.

        Args:
            leader_id: ID of the leader drone
            house_identifier: House letter (A-T) to fly to
            formation: Formation type ("v", "line", "diamond", "echelon", "column")
            spacing: Distance between drones in meters
            speed: Flight speed in m/s
            wait: If True, wait for all drones to reach destination

        Returns:
            Dict with formation info and drone assignments
        """
        # Find the destination house
        house_name, house = self.find_house(house_identifier)
        if house is None:
            return {"error": f"House '{house_identifier}' not found"}

        target_x, target_y = house['x'], house['y']

        # Get all available drones
        all_drones = self.get_available_drones()
        if leader_id not in all_drones:
            return {"error": f"Leader drone '{leader_id}' not available"}

        # Order drones with leader first
        follower_drones = [d for d in all_drones if d != leader_id]
        formation_drones = [leader_id] + follower_drones
        num_drones = len(formation_drones)

        # Get formation offsets
        offsets = self.get_formation_offsets(formation, num_drones, spacing)

        # Calculate heading from formation center to house
        # Use leader's current position to determine approach angle
        leader_pos = self.get_drone_position(leader_id)
        dx = target_x - leader_pos[0]
        dy = target_y - leader_pos[1]
        heading = math.degrees(math.atan2(dy, dx))
        heading_rad = math.radians(heading)

        # Viewing position: offset from house towards the drones
        view_distance = 15 + (num_drones * spacing / 2)  # More drones = further back
        approach_x = target_x - view_distance * math.cos(heading_rad)
        approach_y = target_y - view_distance * math.sin(heading_rad)

        # Transform formation offsets based on heading
        # Rotate offsets so formation faces the house
        cos_h = math.cos(heading_rad)
        sin_h = math.sin(heading_rad)

        assignments = []
        futures = []

        # First, initialize and takeoff all drones
        for drone_id in formation_drones:
            # Initialize drone if not already done
            if drone_id not in self._drone_states:
                self.initialize_drone(drone_id)

            # Takeoff if landed
            current_state = self._drone_states.get(drone_id, DroneState.LANDED)
            if current_state == DroneState.LANDED:
                self._drone_states[drone_id] = DroneState.TAKING_OFF
                self._drone_tasks[drone_id] = "Taking off for formation"
                self.client.takeoffAsync(vehicle_name=drone_id)

        # Wait for all takeoffs to complete
        time.sleep(4)

        # Move all to formation altitude
        for drone_id in formation_drones:
            self.client.moveToZAsync(self.DEFAULT_ALTITUDE, self.DEFAULT_SPEED, vehicle_name=drone_id)

        time.sleep(3)

        # Now set up formation assignments and rotate to face house
        for i, drone_id in enumerate(formation_drones):
            offset_x, offset_y = offsets[i]

            # Rotate offset by heading
            rotated_x = offset_x * cos_h - offset_y * sin_h
            rotated_y = offset_x * sin_h + offset_y * cos_h

            # Final position
            final_x = approach_x + rotated_x
            final_y = approach_y + rotated_y

            # Update state
            role = "leader" if i == 0 else "follower"
            self._drone_states[drone_id] = DroneState.FLYING
            self._drone_tasks[drone_id] = f"Formation flight to {house_name} ({role})"

            assignments.append({
                "drone_id": drone_id,
                "role": role,
                "target": {"x": round(final_x, 1), "y": round(final_y, 1)},
                "offset": {"x": offset_x, "y": offset_y}
            })

            # Rotate to face the house
            self.client.rotateToYawAsync(heading, timeout_sec=5, vehicle_name=drone_id)

        # Small delay for rotations
        time.sleep(1)

        # Tilt cameras down and start movement
        for i, drone_id in enumerate(formation_drones):
            self._set_camera_pitch(drone_id, self.CAMERA_PITCH)

            offset_x, offset_y = offsets[i]
            rotated_x = offset_x * cos_h - offset_y * sin_h
            rotated_y = offset_x * sin_h + offset_y * cos_h
            final_x = approach_x + rotated_x
            final_y = approach_y + rotated_y

            future = self.client.moveToPositionAsync(
                final_x, final_y, self.DEFAULT_ALTITUDE, speed,
                vehicle_name=drone_id
            )
            futures.append((drone_id, future))

        if wait:
            for drone_id, future in futures:
                future.join()
                self.client.hoverAsync(vehicle_name=drone_id).join()
                self._drone_states[drone_id] = DroneState.HOVERING
                self._drone_tasks[drone_id] = f"Viewing {house_name}"

        return {
            "status": "formation_flight_started",
            "formation": formation,
            "leader": leader_id,
            "destination": house_name,
            "house_position": {"x": target_x, "y": target_y},
            "approach_heading": round(heading, 1),
            "drones": assignments
        }

    # =========================================================================
    # Scene Object Discovery
    # =========================================================================

    def list_scene_objects(self, pattern: str = ".*") -> List[str]:
        """
        List all objects in the scene matching a pattern.

        Args:
            pattern: Regex pattern to filter objects (default: all objects)

        Returns:
            List of object names
        """
        try:
            objects = self.client.simListSceneObjects(pattern)
            return sorted(objects)
        except Exception as e:
            print(f"Error listing scene objects: {e}")
            return []

    def get_object_pose(self, object_name: str) -> Optional[Dict]:
        """
        Get the pose (position and orientation) of a scene object.

        Args:
            object_name: Name of the object in the scene

        Returns:
            Dict with position (x, y, z) and orientation, or None if not found
        """
        try:
            pose = self.client.simGetObjectPose(object_name)
            if pose.containsNan():
                return None
            return {
                "object_name": object_name,
                "position": {
                    "x": pose.position.x_val,
                    "y": pose.position.y_val,
                    "z": pose.position.z_val
                },
                "orientation": {
                    "w": pose.orientation.w_val,
                    "x": pose.orientation.x_val,
                    "y": pose.orientation.y_val,
                    "z": pose.orientation.z_val
                }
            }
        except Exception as e:
            print(f"Error getting pose for {object_name}: {e}")
            return None

    def find_objects_by_type(self, object_type: str) -> List[Dict]:
        """
        Find objects by type and return their positions.

        Args:
            object_type: Type to search for (e.g., "house", "tree", "road")

        Returns:
            List of objects with their positions
        """
        # Common naming patterns in Unreal/AirSim
        type_patterns = {
            "house": r"(?i)(house|home|building|residence)",
            "tree": r"(?i)(tree|bush|plant|foliage)",
            "road": r"(?i)(road|street|pavement)",
            "vehicle": r"(?i)(car|vehicle|truck)",
            "light": r"(?i)(light|lamp|post)"
        }

        pattern = type_patterns.get(object_type.lower(), f"(?i){object_type}")

        all_objects = self.list_scene_objects()
        matching = [obj for obj in all_objects if re.search(pattern, obj)]

        results = []
        for obj_name in matching:
            pose = self.get_object_pose(obj_name)
            if pose:
                results.append(pose)

        return results

    def update_house_labels_from_scene(self, output_file: str = "house_labels.json") -> Dict:
        """
        Discover houses in the scene and update the house labels file.

        Returns:
            Dict of discovered houses with their coordinates
        """
        houses = self.find_objects_by_type("house")

        house_labels = {}
        for i, house in enumerate(houses):
            label = f"House {chr(65 + i)}" if i < 26 else f"House {i + 1}"
            house_labels[label] = {
                "x": round(house["position"]["x"], 1),
                "y": round(house["position"]["y"], 1),
                "object_name": house["object_name"]
            }

        # Save to file
        try:
            labels_path = Path(__file__).parent.parent.parent / output_file
            with open(labels_path, 'w') as f:
                json.dump(house_labels, f, indent=2)
            print(f"Saved {len(house_labels)} houses to {labels_path}")
        except Exception as e:
            print(f"Error saving house labels: {e}")

        return house_labels


# Singleton instance for API use
_drone_service: Optional[DroneService] = None


def get_drone_service() -> DroneService:
    """Get or create the singleton DroneService instance."""
    global _drone_service
    if _drone_service is None:
        _drone_service = DroneService()
    return _drone_service
