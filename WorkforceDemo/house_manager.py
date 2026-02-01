"""
House Manager - Fly to a house by letter.

Usage:
  python house_manager.py A              - Fly to House A (default speed)
  python house_manager.py A slow         - Fly slow (3 m/s)
  python house_manager.py A fast         - Fly fast (10 m/s)
  python house_manager.py A 15           - Fly at 15 m/s
  python house_manager.py list           - Show all houses
  python house_manager.py tour           - Tour all houses

After arriving, commands:
  circle    - Circle around the house
  photo     - Take photos (scene, depth, segmentation)
  land      - Land the drone
  (Ctrl+C)  - Exit and leave drone hovering
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


def load_labels():
    with open(LABELS_FILE, 'r') as f:
        return json.load(f)


def set_camera_pitch(client, pitch_degrees):
    """Tilt camera down (negative) or up (positive)."""
    pitch_rad = math.radians(pitch_degrees)
    q = airsim.to_quaternion(pitch_rad, 0, 0)
    camera_pose = airsim.Pose(airsim.Vector3r(0, 0, 0), q)
    client.simSetCameraPose("0", camera_pose)


def fly_to_view_house(client, house, name, speed):
    """Fly to offset position from house, facing it with camera tilted down."""
    hx, hy = house['x'], house['y']

    # Get current position to determine approach angle
    state = client.getMultirotorState()
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
    print(f"[ROTATING] Facing {name}...")
    client.rotateToYawAsync(yaw, timeout_sec=10).join()

    # Tilt camera down before flying so house is visible during approach
    set_camera_pitch(client, CAMERA_PITCH)

    print(f"[FLYING] Going to view {name} at {speed} m/s...")
    client.moveToPositionAsync(offset_x, offset_y, VIEW_HEIGHT, speed, timeout_sec=60).join()

    # Stabilize - stop all movement
    client.hoverAsync().join()

    # Store viewing position in house dict for later use
    house['view_x'] = offset_x
    house['view_y'] = offset_y

    print(f"[OK] Viewing {name} from ({offset_x:.1f}, {offset_y:.1f})")


def circle_house(client, house, laps=2):
    """Circle around the house for a set number of laps."""
    hx, hy = house['x'], house['y']

    print(f"[CIRCLE] Circling house {laps} times...")

    # Tilt camera down to keep house in view during circle
    set_camera_pitch(client, CAMERA_PITCH)

    # First move to edge of circle
    start_x = hx + CIRCLE_RADIUS
    start_y = hy
    client.moveToPositionAsync(start_x, start_y, VIEW_HEIGHT, CIRCLE_SPEED, timeout_sec=30).join()

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
                yaw_mode=airsim.YawMode(is_rate=False, yaw_or_rate=yaw)
            )

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[STOPPED] Circling interrupted")

    # Stop and return to viewing position
    client.moveByVelocityAsync(0, 0, 0, 1).join()

    # Return to offset viewing position (stored from fly_to_view_house)
    view_x = house.get('view_x', hx + CIRCLE_RADIUS)
    view_y = house.get('view_y', hy)
    client.moveToPositionAsync(view_x, view_y, VIEW_HEIGHT, CIRCLE_SPEED, timeout_sec=30).join()

    # Face the house again
    yaw = math.degrees(math.atan2(hy - view_y, hx - view_x))
    client.rotateToYawAsync(yaw, timeout_sec=10).join()

    print("[OK] Back at viewing position")


def take_photos(client, house_name):
    """Capture scene, depth, and segmentation images."""
    # Create photo directory if needed
    if not os.path.exists(PHOTO_DIR):
        os.makedirs(PHOTO_DIR)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    prefix = f"{PHOTO_DIR}/{house_name.replace(' ', '_')}_{timestamp}"

    print(f"[PHOTO] Capturing images for {house_name}...")

    # Scene (RGB) image
    responses = client.simGetImages([
        airsim.ImageRequest("0", airsim.ImageType.Scene, False, False)
    ])
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
    ])
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
    ])
    if responses and len(responses) > 0:
        response = responses[0]
        img1d = np.frombuffer(response.image_data_uint8, dtype=np.uint8)
        img = img1d.reshape(response.height, response.width, 3)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        filename = f"{prefix}_segmentation.png"
        cv2.imwrite(filename, img)
        print(f"  [SAVED] {filename}")

    print(f"[OK] Photos saved to {PHOTO_DIR}/")


def parse_speed(args):
    """Parse speed from arguments."""
    for arg in args:
        arg_lower = arg.lower()
        if arg_lower == 'slow':
            return 3
        elif arg_lower == 'fast':
            return 10
        elif arg_lower == 'vfast':
            return 20
        else:
            try:
                return float(arg)
            except:
                pass
    return 5  # Default speed


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    args = [a.upper() for a in sys.argv[1:]]
    labels = load_labels()

    # === LIST ===
    if args[0] == "LIST":
        print("\nAVAILABLE HOUSES:")
        print("-" * 40)
        for name in sorted(labels.keys()):
            h = labels[name]
            print(f"  {name:12} @ X:{h['x']:7.1f}  Y:{h['y']:7.1f}")
        print("-" * 40)
        return

    # Parse speed
    speed = parse_speed(sys.argv[2:]) if len(sys.argv) > 2 else 5

    # Connect and setup
    client = airsim.MultirotorClient()
    client.confirmConnection()
    client.enableApiControl(True)
    client.armDisarm(True)
    print("[OK] Connected and armed")

    print("[OK] Taking off...")
    client.takeoffAsync().join()
    client.moveToZAsync(VIEW_HEIGHT, speed).join()

    current_house = None
    current_house_name = None

    # === TOUR ===
    if args[0] == "TOUR":
        print(f"\n[TOUR] Visiting all {len(labels)} houses at {speed} m/s...\n")
        for i, (name, house) in enumerate(sorted(labels.items())):
            print(f"\n[{i+1}/{len(labels)}] {name}")
            fly_to_view_house(client, house, name, speed)
            current_house = house
            current_house_name = name
            time.sleep(2)
        print("\n[TOUR] Complete!")

    # === GO TO SPECIFIC HOUSE ===
    else:
        letter = args[0]
        search = f"House {letter}"
        if search not in labels:
            matches = [n for n in labels if letter in n.upper()]
            if matches:
                search = matches[0]
            else:
                print(f"[ERROR] House '{letter}' not found")
                print("Use 'python house_manager.py list' to see all houses")
                client.landAsync().join()
                return

        current_house = labels[search]
        current_house_name = search
        fly_to_view_house(client, current_house, search, speed)

    # Interactive command loop
    print("\n" + "=" * 45)
    print("COMMANDS:")
    print("  photo       - Take photos (scene/depth/seg)")
    print("  circle      - Circle this house (2 laps)")
    print("  circle 5    - Circle 5 laps")
    print("  go B        - Go to House B")
    print("  land        - Land the drone")
    print("  Ctrl+C      - Exit (drone keeps hovering)")
    print("=" * 45)

    try:
        while True:
            try:
                cmd = input("\nCommand: ").strip().lower()
            except EOFError:
                break

            parts = cmd.split()
            if not parts:
                continue

            action = parts[0]

            if action == "photo" and current_house:
                take_photos(client, current_house_name)

            elif action == "circle" and current_house:
                laps = int(parts[1]) if len(parts) > 1 else 2
                circle_house(client, current_house, laps)

            elif action == "go" and len(parts) > 1:
                letter = parts[1].upper()
                search = f"House {letter}"
                if search not in labels:
                    matches = [n for n in labels if letter in n.upper()]
                    if matches:
                        search = matches[0]
                    else:
                        print(f"  [!] House '{letter}' not found")
                        continue

                current_house = labels[search]
                current_house_name = search
                fly_to_view_house(client, current_house, search, speed)

            elif action == "land":
                print("[LANDING]...")
                # Reset camera to default orientation
                set_camera_pitch(client, 0)
                client.landAsync().join()
                client.armDisarm(False)
                client.enableApiControl(False)
                print("[DONE]")
                return

            else:
                print("  Commands: photo, circle, circle N, go X, land")

    except KeyboardInterrupt:
        print("\n[EXIT] Drone left hovering. Goodbye!")


if __name__ == "__main__":
    main()
