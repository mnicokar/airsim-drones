"""
Drone Camera Viewer
Shows live feed from the drone's camera.
Press 'Q' to quit, 'S' to save screenshot.
"""

import airsim
import cv2
import numpy as np
import time
import os

# Configuration
CAMERA_NAME = "0"           # Default front camera
IMAGE_TYPE = airsim.ImageType.Scene  # RGB image
SAVE_DIR = "screenshots"


def main():
    print("=" * 50)
    print("  DRONE CAMERA VIEWER")
    print("=" * 50)

    # Connect
    client = airsim.MultirotorClient()
    client.confirmConnection()
    print("[OK] Connected to AirSim")

    # Create screenshots directory
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    print("\nControls:")
    print("  Q - Quit")
    print("  S - Save screenshot")
    print("  1 - Scene (RGB) view")
    print("  2 - Depth view")
    print("  3 - Segmentation view")
    print("\nStarting camera feed...")

    current_type = IMAGE_TYPE
    screenshot_count = 0

    while True:
        # Get image from drone camera
        responses = client.simGetImages([
            airsim.ImageRequest(CAMERA_NAME, current_type, False, False)
        ])

        if responses and len(responses) > 0:
            response = responses[0]

            # Convert to numpy array
            if current_type == airsim.ImageType.Scene:
                # RGB image
                img1d = np.frombuffer(response.image_data_uint8, dtype=np.uint8)
                img = img1d.reshape(response.height, response.width, 3)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                window_title = "Drone Camera - Scene (RGB)"

            elif current_type == airsim.ImageType.DepthPerspective:
                # Depth image (need to request as float)
                responses = client.simGetImages([
                    airsim.ImageRequest(CAMERA_NAME, airsim.ImageType.DepthPerspective, True, False)
                ])
                if responses:
                    response = responses[0]
                    img = airsim.list_to_2d_float_array(response.image_data_float, response.width, response.height)
                    img = np.clip(img, 0, 100)  # Clip to 100m max
                    img = (img / 100 * 255).astype(np.uint8)
                    img = cv2.applyColorMap(img, cv2.COLORMAP_JET)
                    window_title = "Drone Camera - Depth"
                else:
                    continue

            elif current_type == airsim.ImageType.Segmentation:
                # Segmentation image
                img1d = np.frombuffer(response.image_data_uint8, dtype=np.uint8)
                img = img1d.reshape(response.height, response.width, 3)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                window_title = "Drone Camera - Segmentation"

            else:
                img1d = np.frombuffer(response.image_data_uint8, dtype=np.uint8)
                img = img1d.reshape(response.height, response.width, 3)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                window_title = "Drone Camera"

            # Get drone position for overlay
            state = client.getMultirotorState()
            pos = state.kinematics_estimated.position

            # Add position overlay
            text = f"X:{pos.x_val:.1f} Y:{pos.y_val:.1f} Alt:{-pos.z_val:.1f}m"
            cv2.putText(img, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Display
            cv2.imshow(window_title, img)

        # Handle key presses
        key = cv2.waitKey(50) & 0xFF

        if key == ord('q') or key == ord('Q'):
            print("\n[QUIT] Closing camera viewer...")
            break

        elif key == ord('s') or key == ord('S'):
            # Save screenshot
            filename = f"{SAVE_DIR}/screenshot_{screenshot_count:04d}.png"
            cv2.imwrite(filename, img)
            screenshot_count += 1
            print(f"[SAVED] {filename}")

        elif key == ord('1'):
            current_type = airsim.ImageType.Scene
            cv2.destroyAllWindows()
            print("[MODE] Scene (RGB)")

        elif key == ord('2'):
            current_type = airsim.ImageType.DepthPerspective
            cv2.destroyAllWindows()
            print("[MODE] Depth")

        elif key == ord('3'):
            current_type = airsim.ImageType.Segmentation
            cv2.destroyAllWindows()
            print("[MODE] Segmentation")

    cv2.destroyAllWindows()
    print("[DONE] Camera viewer closed")


if __name__ == "__main__":
    main()
