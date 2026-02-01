"""
Drone Controller - Multi-drone navigation and control.

Control two drones independently, sending them to different locations,
taking photos, and performing maneuvers.

Usage:
  python drone_controller.py             - Start interactive mode with both drones
  python drone_controller.py list        - Show all available locations

Interactive commands:
  drone 1          - Select Drone1 as active
  drone 2          - Select Drone2 as active
  go A             - Send active drone to House A
  send 1 A         - Send Drone1 to House A
  send 2 B         - Send Drone2 to House B
  circle           - Circle current house with active drone
  circle 5         - Circle 5 times
  photo            - Take photos (scene, depth, segmentation)
  status           - Show all drone positions
  land             - Land active drone
  land all         - Land all drones
  Ctrl+C           - Exit and leave drones hovering
"""

import airsim
import json
import sys
import math
import time
import os
import cv2
import numpy as np

LABELS_FILE = "house_labels.json"
VIEW_HEIGHT = -20           # Altitude to view from (20m up)
VIEW_DISTANCE = 25          # Distance from house to hover
CAMERA_PITCH = -20          # Degrees to tilt camera down
CIRCLE_RADIUS = 15          # Radius for circling
CIRCLE_SPEED = 3            # Speed when circling
PHOTO_DIR = "house_photos"  # Directory for saved photos
DRONES = ["Drone1", "Drone2"]  # Available drones


def load_labels():
    with open(LABELS_FILE, 'r') as f:
        return json.load(f)


def set_camera_pitch(client, pitch_degrees, vehicle_name=""):
    """Tilt camera down (negative) or up (positive)."""
    pitch_rad = math.radians(pitch_degrees)
    q = airsim.to_quaternion(pitch_rad, 0, 0)
    camera_pose = airsim.Pose(airsim.Vector3r(0, 0, 0), q)
    client.simSetCameraPose("0", camera_pose, vehicle_name=vehicle_name)


def fly_to_view_house(client, house, name, speed, vehicle_name=""):
    """Fly to offset position from house, facing it with camera tilted down."""
    hx, hy = house['x'], house['y']
    drone_label = f"[{vehicle_name}]" if vehicle_name else ""

    # Get current position to determine approach angle
    state = client.getMultirotorState(vehicle_name=vehicle_name)
    pos = state.kinematics_estimated.position
    current_x, current_y = pos.x_val, pos.y_val

    # Calculate offset position (approach from current direction)
    dx = current_x - hx
    dy = current_y - hy
    dist = math.sqrt(dx * dx + dy * dy)

    if dist > 1:  # Normalize and scale to VIEW_DISTANCE
        offset_x = hx + (dx / dist) * VIEW_DISTANCE
        offset_y = hy + (dy / dist) * VIEW_DISTANCE
    else:  # Already close, default offset
        offset_x = hx + VIEW_DISTANCE
        offset_y = hy

    # Face the house before flying
    yaw = math.degrees(math.atan2(hy - current_y, hx - current_x))
    print(f"{drone_label}[ROTATING] Facing {name}...")
    client.rotateToYawAsync(yaw, timeout_sec=10, vehicle_name=vehicle_name).join()

    # Tilt camera down before flying so house is visible during approach
    set_camera_pitch(client, CAMERA_PITCH, vehicle_name=vehicle_name)

    print(f"{drone_label}[FLYING] Going to view {name} at {speed} m/s...")
    client.moveToPositionAsync(offset_x, offset_y, VIEW_HEIGHT, speed, timeout_sec=60, vehicle_name=vehicle_name).join()

    # Stabilize - stop all movement
    client.hoverAsync(vehicle_name=vehicle_name).join()

    print(f"{drone_label}[OK] Viewing {name} from ({offset_x:.1f}, {offset_y:.1f})")
    return {'x': offset_x, 'y': offset_y}


def circle_house(client, house, laps=2, vehicle_name="", view_pos=None):
    """Circle around the house for a set number of laps."""
    hx, hy = house['x'], house['y']
    drone_label = f"[{vehicle_name}]" if vehicle_name else ""

    print(f"{drone_label}[CIRCLE] Circling house {laps} times...")

    # Tilt camera down to keep house in view during circle
    set_camera_pitch(client, CAMERA_PITCH, vehicle_name=vehicle_name)

    # First move to edge of circle
    start_x = hx + CIRCLE_RADIUS
    start_y = hy
    client.moveToPositionAsync(start_x, start_y, VIEW_HEIGHT, CIRCLE_SPEED, timeout_sec=30, vehicle_name=vehicle_name).join()

    # Calculate angular velocity
    angular_velocity = CIRCLE_SPEED / CIRCLE_RADIUS
    start_time = time.time()
    total_angle = laps * 2 * math.pi
    last_lap = 0

    try:
        while True:
            elapsed = time.time() - start_time
            angle = angular_velocity * elapsed

            # Check if done
            if angle >= total_angle:
                print(f"  Completed {laps} laps!")
                break

            # Track laps
            current_lap = int(angle / (2 * math.pi)) + 1
            if current_lap > last_lap:
                print(f"  Lap {current_lap}/{laps}")
                last_lap = current_lap

            # Velocity tangent to circle
            vx = -CIRCLE_SPEED * math.sin(angle)
            vy = CIRCLE_SPEED * math.cos(angle)

            # Yaw to face the house (toward center)
            current_x = hx + CIRCLE_RADIUS * math.cos(angle)
            current_y = hy + CIRCLE_RADIUS * math.sin(angle)
            yaw = math.degrees(math.atan2(hy - current_y, hx - current_x))

            client.moveByVelocityAsync(
                vx, vy, 0,
                duration=0.5,
                drivetrain=airsim.DrivetrainType.MaxDegreeOfFreedom,
                yaw_mode=airsim.YawMode(is_rate=False, yaw_or_rate=yaw),
                vehicle_name=vehicle_name
            )

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[STOPPED] Circling interrupted")

    # Stop and return to viewing position
    client.moveByVelocityAsync(0, 0, 0, 1, vehicle_name=vehicle_name).join()

    # Return to offset viewing position
    view_x = view_pos['x'] if view_pos else hx + CIRCLE_RADIUS
    view_y = view_pos['y'] if view_pos else hy
    client.moveToPositionAsync(view_x, view_y, VIEW_HEIGHT, CIRCLE_SPEED, timeout_sec=30, vehicle_name=vehicle_name).join()

    # Face the house again
    yaw = math.degrees(math.atan2(hy - view_y, hx - view_x))
    client.rotateToYawAsync(yaw, timeout_sec=10, vehicle_name=vehicle_name).join()

    print(f"{drone_label}[OK] Back at viewing position")


def take_photos(client, house_name, vehicle_name=""):
    """Capture scene, depth, and segmentation images."""
    drone_label = f"[{vehicle_name}]" if vehicle_name else ""

    # Create photo directory if needed
    if not os.path.exists(PHOTO_DIR):
        os.makedirs(PHOTO_DIR)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    drone_suffix = f"_{vehicle_name}" if vehicle_name else ""
    prefix = f"{PHOTO_DIR}/{house_name.replace(' ', '_')}{drone_suffix}_{timestamp}"

    print(f"{drone_label}[PHOTO] Capturing images for {house_name}...")

    # Scene (RGB) image
    responses = client.simGetImages([
        airsim.ImageRequest("0", airsim.ImageType.Scene, False, False)
    ], vehicle_name=vehicle_name)
    if responses and len(responses) > 0:
        response = responses[0]
        img1d = np.frombuffer(response.image_data_uint8, dtype=np.uint8)
        img = img1d.reshape(response.height, response.width, 3)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        filename = f"{prefix}_scene.png"
        cv2.imwrite(filename, img)
        print(f"  [SAVED] {filename}")

    # Depth image
    responses = client.simGetImages([
        airsim.ImageRequest("0", airsim.ImageType.DepthPerspective, True, False)
    ], vehicle_name=vehicle_name)
    if responses and len(responses) > 0:
        response = responses[0]
        img = airsim.list_to_2d_float_array(response.image_data_float, response.width, response.height)
        img = np.clip(img, 0, 100)
        img = (img / 100 * 255).astype(np.uint8)
        img = cv2.applyColorMap(img, cv2.COLORMAP_JET)
        filename = f"{prefix}_depth.png"
        cv2.imwrite(filename, img)
        print(f"  [SAVED] {filename}")

    # Segmentation image
    responses = client.simGetImages([
        airsim.ImageRequest("0", airsim.ImageType.Segmentation, False, False)
    ], vehicle_name=vehicle_name)
    if responses and len(responses) > 0:
        response = responses[0]
        img1d = np.frombuffer(response.image_data_uint8, dtype=np.uint8)
        img = img1d.reshape(response.height, response.width, 3)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        filename = f"{prefix}_segmentation.png"
        cv2.imwrite(filename, img)
        print(f"  [SAVED] {filename}")

    print(f"{drone_label}[OK] Photos saved to {PHOTO_DIR}/")


def get_drone_status(client, vehicle_name):
    """Get position of a drone."""
    state = client.getMultirotorState(vehicle_name=vehicle_name)
    pos = state.kinematics_estimated.position
    return pos.x_val, pos.y_val, pos.z_val


def find_house(labels, letter):
    """Find a house by letter or partial name."""
    search = f"House {letter.upper()}"
    if search in labels:
        return search, labels[search]
    matches = [n for n in labels if letter.upper() in n.upper()]
    if matches:
        return matches[0], labels[matches[0]]
    return None, None


def main():
    labels = load_labels()

    # Handle list command
    if len(sys.argv) > 1 and sys.argv[1].upper() == "LIST":
        print("\nAVAILABLE HOUSES:")
        print("-" * 40)
        for name in sorted(labels.keys()):
            h = labels[name]
            print(f"  {name:12} @ X:{h['x']:7.1f}  Y:{h['y']:7.1f}")
        print("-" * 40)
        return

    # Connect and setup all drones
    client = airsim.MultirotorClient()
    client.confirmConnection()

    print("[SETUP] Initializing drones...")
    for drone in DRONES:
        client.enableApiControl(True, drone)
        client.armDisarm(True, drone)
        print(f"  {drone}: Armed")

    print("[TAKEOFF] All drones taking off...")
    for drone in DRONES:
        client.takeoffAsync(vehicle_name=drone)
    time.sleep(4)  # Wait for takeoff

    for drone in DRONES:
        client.moveToZAsync(VIEW_HEIGHT, 5, vehicle_name=drone)
    time.sleep(3)

    print("[OK] All drones ready!")

    # Track state per drone
    speed = 5
    active_drone = DRONES[0]
    drone_state = {drone: {'house': None, 'house_name': None, 'view_pos': None} for drone in DRONES}

    # Interactive command loop
    print("\n" + "=" * 50)
    print("COMMANDS:")
    print("  drone 1/2       - Select active drone")
    print("  go A            - Send active drone to House A")
    print("  send 1 A        - Send Drone1 to House A")
    print("  send 2 B        - Send Drone2 to House B")
    print("  photo           - Take photos with active drone")
    print("  circle [N]      - Circle house N times (default 2)")
    print("  status          - Show all drone positions")
    print("  land            - Land active drone")
    print("  land all        - Land all drones")
    print("  Ctrl+C          - Exit (drones keep hovering)")
    print("=" * 50)
    print(f"\nActive drone: {active_drone}")

    try:
        while True:
            try:
                cmd = input(f"\n[{active_drone}] Command: ").strip().lower()
            except EOFError:
                break

            parts = cmd.split()
            if not parts:
                continue

            action = parts[0]

            # Select active drone
            if action == "drone" and len(parts) > 1:
                num = parts[1]
                if num in ["1", "2"]:
                    active_drone = f"Drone{num}"
                    state = drone_state[active_drone]
                    loc = f" at {state['house_name']}" if state['house_name'] else ""
                    print(f"[OK] Active drone: {active_drone}{loc}")
                else:
                    print("  Usage: drone 1 or drone 2")

            # Send specific drone to house
            elif action == "send" and len(parts) >= 3:
                num = parts[1]
                letter = parts[2]
                if num in ["1", "2"]:
                    drone = f"Drone{num}"
                    house_name, house = find_house(labels, letter)
                    if house:
                        view_pos = fly_to_view_house(client, house, house_name, speed, vehicle_name=drone)
                        drone_state[drone] = {'house': house, 'house_name': house_name, 'view_pos': view_pos}
                    else:
                        print(f"  [!] House '{letter}' not found")
                else:
                    print("  Usage: send 1 A or send 2 B")

            # Send active drone to house
            elif action == "go" and len(parts) > 1:
                letter = parts[1]
                house_name, house = find_house(labels, letter)
                if house:
                    view_pos = fly_to_view_house(client, house, house_name, speed, vehicle_name=active_drone)
                    drone_state[active_drone] = {'house': house, 'house_name': house_name, 'view_pos': view_pos}
                else:
                    print(f"  [!] House '{letter}' not found")

            # Take photos with active drone
            elif action == "photo":
                state = drone_state[active_drone]
                if state['house_name']:
                    take_photos(client, state['house_name'], vehicle_name=active_drone)
                else:
                    print("  [!] Drone not at a house. Use 'go X' first.")

            # Circle with active drone
            elif action == "circle":
                state = drone_state[active_drone]
                if state['house']:
                    laps = int(parts[1]) if len(parts) > 1 else 2
                    circle_house(client, state['house'], laps, vehicle_name=active_drone, view_pos=state['view_pos'])
                else:
                    print("  [!] Drone not at a house. Use 'go X' first.")

            # Show status
            elif action == "status":
                print("\nDRONE STATUS:")
                print("-" * 50)
                for drone in DRONES:
                    x, y, z = get_drone_status(client, drone)
                    state = drone_state[drone]
                    loc = state['house_name'] if state['house_name'] else "No house"
                    marker = " <-- active" if drone == active_drone else ""
                    print(f"  {drone}: ({x:6.1f}, {y:6.1f}, {z:6.1f}) - {loc}{marker}")
                print("-" * 50)

            # Land drone(s)
            elif action == "land":
                if len(parts) > 1 and parts[1] == "all":
                    print("[LANDING] All drones...")
                    for drone in DRONES:
                        set_camera_pitch(client, 0, vehicle_name=drone)
                        client.landAsync(vehicle_name=drone)
                    time.sleep(5)
                    for drone in DRONES:
                        client.armDisarm(False, drone)
                        client.enableApiControl(False, drone)
                    print("[DONE] All drones landed.")
                    return
                else:
                    print(f"[LANDING] {active_drone}...")
                    set_camera_pitch(client, 0, vehicle_name=active_drone)
                    client.landAsync(vehicle_name=active_drone).join()
                    client.armDisarm(False, active_drone)
                    client.enableApiControl(False, active_drone)
                    print(f"[DONE] {active_drone} landed.")

            else:
                print("  Commands: drone N, go X, send N X, photo, circle, status, land, land all")

    except KeyboardInterrupt:
        print("\n[EXIT] Drones left hovering. Goodbye!")


if __name__ == "__main__":
    main()
