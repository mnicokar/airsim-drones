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
