# AirSim Drones

Drone simulation project using Microsoft AirSim.

## Setup

### 1. Download AirSim Environment

Download the AirSimNH (Neighborhood) environment from the official AirSim releases:

https://github.com/Microsoft/AirSim/releases

Extract it to this directory so you have `AirSimNH/` folder alongside `WorkforceDemo/`.

### 2. Install Python Dependencies

The `airsim` package has build dependencies that must be installed first:

```bash
cd WorkforceDemo
python -m venv .venv
# Activate the virtual environment (choose your shell):
source .venv/Scripts/activate  # Git Bash
.venv\Scripts\activate.bat     # CMD
.venv\Scripts\Activate.ps1     # PowerShell

# Upgrade pip first
python -m pip install --upgrade pip

# Install build dependencies (required before airsim)
pip install numpy msgpack-rpc-python opencv-python backports.ssl_match_hostname

# Install airsim without build isolation
pip install --no-build-isolation airsim
```

**Note:** The `airsim` package doesn't properly declare its build dependencies, so they must be installed manually first. Using `--no-build-isolation` allows pip to use the already-installed packages during the build.

### 3. Run

1. Start `AirSimNH/WindowsNoEditor/AirSimNH.exe`
2. Run the Python scripts in `WorkforceDemo/`

## Scripts

### drone_controller.py

Multi-drone navigation and control. Allows you to command two drones independently to fly to different locations.

```bash
python drone_controller.py         # Start interactive mode
python drone_controller.py list    # Show all available house locations
```

**Interactive Commands:**

| Command | Description |
|---------|-------------|
| `drone 1` | Select Drone1 as active |
| `drone 2` | Select Drone2 as active |
| `go A` | Send active drone to House A |
| `send 1 A` | Send Drone1 to House A |
| `send 2 B` | Send Drone2 to House B |
| `photo` | Take photos (scene, depth, segmentation) |
| `circle` | Circle current house (2 laps) |
| `circle 5` | Circle 5 times |
| `status` | Show all drone positions |
| `land` | Land active drone |
| `land all` | Land all drones |
| `Ctrl+C` | Exit (drones keep hovering) |

**Example session:**
```
$ python drone_controller.py
[SETUP] Initializing drones...
[TAKEOFF] All drones taking off...
[OK] All drones ready!

[Drone1] Command: send 1 A
[Drone1][FLYING] Going to view House A...

[Drone1] Command: send 2 B
[Drone2][FLYING] Going to view House B...

[Drone1] Command: status
DRONE STATUS:
  Drone1: ( 125.0,  -45.0,  -20.0) - House A <-- active
  Drone2: (  80.0,   30.0,  -20.0) - House B

[Drone1] Command: drone 2
[OK] Active drone: Drone2 at House B

[Drone2] Command: photo
[Drone2][PHOTO] Capturing images...
```

### drone_fleet.py

Choreographed two-drone demonstration flight. Both drones perform synchronized maneuvers.

```bash
python drone_fleet.py
```

### camera_view.py

Single drone camera testing and visualization.

```bash
python camera_view.py
```
