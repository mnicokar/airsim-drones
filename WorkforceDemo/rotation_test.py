"""
Rotation Test - Drone faces direction of travel.
Tests rotating to face movement direction before flying.
"""

import airsim
import json
import math
import time

LABELS_FILE = "house_labels.json"
VIEW_HEIGHT = -30
FLIGHT_SPEED = 5


def load_labels():
    with open(LABELS_FILE, 'r') as f:
        return json.load(f)


def fly_to_house_facing_forward(client, house, name, speed):
    """Fly to house, rotating to face direction of travel first."""
    hx, hy = house['x'], house['y']

    # Get current position
    state = client.getMultirotorState()
    pos = state.kinematics_estimated.position
    current_x, current_y = pos.x_val, pos.y_val

    # Calculate yaw to face the target
    dx = hx - current_x
    dy = hy - current_y
    yaw = math.degrees(math.atan2(dy, dx))

    print(f"[ROTATING] Facing {name} (yaw: {yaw:.1f} degrees)...")
    client.rotateToYawAsync(yaw, timeout_sec=10).join()

    print(f"[FLYING] Going to {name} at {speed} m/s...")
    client.moveToPositionAsync(hx, hy, VIEW_HEIGHT, speed, timeout_sec=60).join()

    print(f"[OK] At {name} ({hx:.1f}, {hy:.1f})")


def main():
    labels = load_labels()

    # Connect
    client = airsim.MultirotorClient()
    client.confirmConnection()
    client.enableApiControl(True)
    client.armDisarm(True)
    print("[OK] Connected and armed")

    print("[OK] Taking off...")
    client.takeoffAsync().join()
    client.moveToZAsync(VIEW_HEIGHT, FLIGHT_SPEED).join()

    print("\n" + "=" * 45)
    print("ROTATION TEST")
    print("Drone will rotate to face target before flying")
    print("=" * 45)
    print("\nCommands: go <letter>, land, quit")

    while True:
        try:
            cmd = input("\nCommand: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[EXIT] Drone left hovering.")
            break

        parts = cmd.split()
        if not parts:
            continue

        action = parts[0]

        if action == "go" and len(parts) > 1:
            letter = parts[1].upper()
            search = f"House {letter}"
            if search not in labels:
                matches = [n for n in labels if letter in n.upper()]
                if matches:
                    search = matches[0]
                else:
                    print(f"  [!] House '{letter}' not found")
                    continue

            house = labels[search]
            fly_to_house_facing_forward(client, house, search, FLIGHT_SPEED)

        elif action == "land":
            print("[LANDING]...")
            client.landAsync().join()
            client.armDisarm(False)
            client.enableApiControl(False)
            print("[DONE]")
            return

        elif action in ["quit", "exit", "q"]:
            print("[EXIT] Drone left hovering.")
            break

        else:
            print("  Commands: go <letter>, land, quit")


if __name__ == "__main__":
    main()
