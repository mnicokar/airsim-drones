# AirSim Drones

Drone simulation project using Microsoft AirSim.

## Setup

### 1. Download AirSim Environment

Download the AirSimNH (Neighborhood) environment from the official AirSim releases:

https://github.com/Microsoft/AirSim/releases

Extract it to this directory so you have `AirSimNH/` folder alongside `WorkforceDemo/`.

### 2. Install Python Dependencies

```bash
cd WorkforceDemo
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install airsim
```

### 3. Run

1. Start `AirSimNH/WindowsNoEditor/AirSimNH.exe`
2. Run the Python scripts in `WorkforceDemo/`
