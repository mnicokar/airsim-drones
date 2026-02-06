# Drone Command Playbook

A comprehensive guide for an LLM to control a fleet of 5 drones via REST API in the AirSim Neighborhood simulation.

---

## 1. Environment Overview

### What is AirSim?

AirSim is a Microsoft open-source simulator for drones and autonomous vehicles built on Unreal Engine. This project uses the **Neighborhood** map — a suburban environment with 20 houses (labeled A through T) laid out on streets.

### Architecture

```
LLM  -->  REST API (FastAPI :8000)  -->  AirSim Python SDK  -->  Unreal Engine Simulator
```

- **REST API** runs at `http://localhost:8000`
- **Interactive docs** at `http://localhost:8000/docs`
- **Live 2D map** at `http://localhost:8000/`
- **WebSocket** at `ws://localhost:8000/status/ws` (1 Hz fleet updates)

All commands are **non-blocking by default** — they return immediately while the drone executes in the background. Add `"wait": true` to any request body to block until completion.

### Coordinate System

| Axis | Direction | Notes |
|------|-----------|-------|
| X | North (+) / South (-) | Primary axis |
| Y | East (+) / West (-) | Secondary axis |
| Z | Down (+) / Up (-) | AirSim convention (negative = higher altitude) |
| Altitude | Positive meters above ground | API abstracts Z away — use positive altitude values |
| Heading | 0-360 degrees | 0 = North, 90 = East, 180 = South, 270 = West |

---

## 2. Fleet Configuration

### Drones

| Drone ID | Aliases (case-insensitive) |
|----------|---------------------------|
| Drone1 | `drone1`, `DRONE1`, `d1`, `D1` |
| Drone2 | `drone2`, `DRONE2`, `d2`, `D2` |
| Drone3 | `drone3`, `DRONE3`, `d3`, `D3` |
| Drone4 | `drone4`, `DRONE4`, `d4`, `D4` |
| Drone5 | `drone5`, `DRONE5`, `d5`, `D5` |

### Default Values

| Parameter | Default | Range | Unit |
|-----------|---------|-------|------|
| Takeoff altitude | 20 | 5 – 100 | meters |
| Flight speed | 5.0 | 1 – 20 | m/s |
| Altitude change speed | — | 1 – 10 | m/s |
| Formation spacing | 8.0 | 3 – 20 | meters |
| Formation speed | 5.0 | 1 – 15 | m/s |
| View distance (goto-house) | 10.0 | 0 – 50 | meters |

### Automatic Behaviors

1. **Auto-initialization** — Every individual drone command auto-initializes the drone if it hasn't been initialized yet. No manual init step required.
2. **Auto-takeoff on goto-house** — If a drone is landed/idle when you call `goto-house`, it automatically takes off first.
3. **Fleet auto-init** — Fleet commands (`/fleet/takeoff`, `/fleet/group-flight`) auto-initialize all drones if needed.

---

## 3. Command Reference

### Discovery & Status

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| GET | `/drones` | — | List all available drone IDs |
| GET | `/drones/houses` | — | List all 20 houses with coordinates |
| GET | `/drones/{drone_id}` | — | Get detailed drone status (position, velocity, heading, state, task) |
| GET | `/status/fleet` | — | Get status of all drones + emergency flag |
| GET | `/status/positions` | — | Get simplified positions of all drones |
| GET | `/status/health` | — | API health check + AirSim connection status |
| WS | `/status/ws` | — | WebSocket: live 1 Hz fleet status updates |

### Individual Drone Commands

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/drones/{drone_id}/takeoff` | `{"altitude": 20, "wait": false}` | Take off to altitude (all fields optional) |
| POST | `/drones/{drone_id}/land` | — (query: `?wait=false`) | Land at current position |
| POST | `/drones/{drone_id}/hover` | — | Stop and hover in place |
| POST | `/drones/{drone_id}/goto-house` | `{"house": "A"}` | Navigate to house (auto-takeoff) |
| POST | `/drones/{drone_id}/move` | `{"x": 20, "y": -15}` | Move to X,Y coordinates |
| POST | `/drones/{drone_id}/altitude` | `{"altitude": 30}` | Change altitude only |
| POST | `/drones/{drone_id}/rotate` | `{"heading": 180}` | Rotate to compass heading |
| POST | `/drones/{drone_id}/photo` | `{}` or `{"image_types": ["scene"]}` | Capture photo(s) |
| GET | `/drones/{drone_id}/camera/frame` | — (query: `?type=scene`) | Get live JPEG camera frame |

### Fleet Commands

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/fleet/initialize` | — | Initialize all drones |
| POST | `/fleet/takeoff` | — | Take off all drones |
| POST | `/fleet/land` | — | Land all drones |
| POST | `/fleet/hover` | — | Hover all drones |
| POST | `/fleet/group-flight` | `{"leader": "drone1", "house": "A", "formation": "v"}` | Formation flight to house |
| POST | `/fleet/emergency-stop` | — | Emergency stop all drones immediately |
| POST | `/fleet/clear-emergency` | — | Clear emergency status, resume normal ops |

---

## 4. Scenario Playbooks

Each scenario provides exact API calls in order. Replace `BASE` with `http://localhost:8000`.

---

### Scenario 1: First Flight

**Goal:** Take off one drone, let it hover, then land it.

```
Step 1 — Take off Drone1
POST /drones/drone1/takeoff
Body: {"altitude": 20, "wait": true}
Expected: {"status": "airborne", "drone_id": "Drone1"}

Step 2 — Check status
GET /drones/drone1
Expected: state = "hovering", altitude ≈ 20

Step 3 — Land
POST /drones/drone1/land?wait=true
Expected: {"status": "landed", "drone_id": "Drone1"}
```

---

### Scenario 2: Fleet Startup & Shutdown

**Goal:** Initialize, take off, and land all 5 drones.

```
Step 1 — Initialize fleet
POST /fleet/initialize
Expected: {"status": "initialized", "count": 5}

Step 2 — Take off all
POST /fleet/takeoff
Expected: {"status": "airborne", "count": 5}

Step 3 — Verify fleet
GET /status/fleet
Expected: flying_count = 5, emergency_active = false

Step 4 — Land all
POST /fleet/land
Expected: {"status": "landed", "count": 5}
```

---

### Scenario 3: Emergency Stop & Recovery

**Goal:** Stop all drones immediately, then resume operations.

```
Step 1 — Trigger emergency stop
POST /fleet/emergency-stop
Expected: {"status": "emergency_stopped", ...}

Step 2 — Verify emergency active
GET /status/fleet
Expected: emergency_active = true

Step 3 — Clear emergency
POST /fleet/clear-emergency
Expected: {"status": "emergency_cleared", ...}

Step 4 — Resume — take off again
POST /fleet/takeoff
```

---

### Scenario 4: Send Drone to a House

**Goal:** Send Drone1 to House C. No need to take off first — `goto-house` handles it.

```
Step 1 — Navigate to house (auto-takeoff included)
POST /drones/drone1/goto-house
Body: {"house": "C", "wait": true}
Expected: {"house_name": "House C", "house_position": {"x": 20.9, "y": 25.4}, "viewing_position": {...}}

Step 2 — Confirm arrival
GET /drones/drone1
Expected: state = "hovering", current_task = "Viewing House C"
```

---

### Scenario 5: Move Drone to Coordinates

**Goal:** Move Drone2 to a specific X, Y position at custom altitude and speed.

```
Step 1 — Take off
POST /drones/drone2/takeoff
Body: {"altitude": 25, "wait": true}

Step 2 — Move to coordinates
POST /drones/drone2/move
Body: {"x": 30.0, "y": -20.0, "altitude": 25.0, "speed": 8.0, "wait": true}
Expected: {"status": "moved", "drone_id": "Drone2", "position": {"x": 30.0, "y": -20.0, "altitude": 25.0}}
```

---

### Scenario 6: Multi-Drone Parallel Dispatch

**Goal:** Send 3 drones to 3 different houses simultaneously.

```
Step 1 — Fire all three commands (non-blocking, send in rapid succession)
POST /drones/drone1/goto-house
Body: {"house": "A"}

POST /drones/drone2/goto-house
Body: {"house": "F"}

POST /drones/drone3/goto-house
Body: {"house": "L"}

All three return immediately. Drones auto-takeoff and fly in parallel.

Step 2 — Monitor progress
GET /status/fleet
Check each drone's state and current_task until all show "hovering".
```

---

### Scenario 7: V-Formation Flight

**Goal:** Fly all 5 drones in V-formation to House J with Drone1 as leader.

```
Step 1 — Execute formation flight
POST /fleet/group-flight
Body: {"leader": "drone1", "house": "J", "formation": "v", "spacing": 8.0, "speed": 5.0}
Expected: {
  "status": "formation_flight_started",
  "formation": "v",
  "leader": "Drone1",
  "destination": "House J",
  "drones": [
    {"drone_id": "Drone1", "role": "leader", ...},
    {"drone_id": "Drone2", "role": "follower", ...},
    ...
  ]
}

Step 2 — Monitor arrival
GET /status/fleet
Wait until all drones show state = "hovering".
```

---

### Scenario 8: Formation Comparison

**Goal:** Try all 5 formation types to the same house so you can compare them.

```
Formation 1 — V
POST /fleet/group-flight
Body: {"leader": "drone1", "house": "A", "formation": "v", "wait": true}

Formation 2 — Line
POST /fleet/group-flight
Body: {"leader": "drone1", "house": "B", "formation": "line", "wait": true}

Formation 3 — Diamond
POST /fleet/group-flight
Body: {"leader": "drone1", "house": "C", "formation": "diamond", "wait": true}

Formation 4 — Echelon
POST /fleet/group-flight
Body: {"leader": "drone1", "house": "D", "formation": "echelon", "wait": true}

Formation 5 — Column
POST /fleet/group-flight
Body: {"leader": "drone1", "house": "E", "formation": "column", "wait": true}
```

---

### Scenario 9: House Inspection with Photos

**Goal:** Fly to a house and take photos from 4 angles (front, right, back, left).

```
Step 1 — Navigate to house
POST /drones/drone1/goto-house
Body: {"house": "F", "wait": true}

Step 2 — Photo from current angle (front)
POST /drones/drone1/photo
Body: {"label": "house_F_front"}

Step 3 — Rotate 90 degrees (East)
POST /drones/drone1/rotate
Body: {"heading": 90, "wait": true}

Step 4 — Photo (right side)
POST /drones/drone1/photo
Body: {"label": "house_F_right"}

Step 5 — Rotate 180 degrees (South)
POST /drones/drone1/rotate
Body: {"heading": 180, "wait": true}

Step 6 — Photo (back)
POST /drones/drone1/photo
Body: {"label": "house_F_back"}

Step 7 — Rotate 270 degrees (West)
POST /drones/drone1/rotate
Body: {"heading": 270, "wait": true}

Step 8 — Photo (left side)
POST /drones/drone1/photo
Body: {"label": "house_F_left"}
```

---

### Scenario 10: Altitude Survey

**Goal:** Hover over House A and take photos at 3 different altitudes.

```
Step 1 — Go to house at default altitude
POST /drones/drone1/goto-house
Body: {"house": "A", "wait": true}

Step 2 — Photo at default altitude (~20m)
POST /drones/drone1/photo
Body: {"label": "house_A_20m"}

Step 3 — Change to 40m altitude
POST /drones/drone1/altitude
Body: {"altitude": 40, "wait": true}

Step 4 — Photo at 40m
POST /drones/drone1/photo
Body: {"label": "house_A_40m"}

Step 5 — Change to 60m altitude
POST /drones/drone1/altitude
Body: {"altitude": 60, "wait": true}

Step 6 — Photo at 60m
POST /drones/drone1/photo
Body: {"label": "house_A_60m"}
```

---

### Scenario 11: Fleet Status Monitoring

**Goal:** Monitor fleet using both REST polling and WebSocket.

```
Option A — REST polling
GET /status/fleet
Response includes: drones[], total_count, flying_count, emergency_active

GET /status/positions
Response includes: positions { Drone1: {x, y, z, altitude}, ... }

GET /status/health
Response includes: status, airsim_connected, version

Option B — WebSocket (live 1 Hz)
Connect to: ws://localhost:8000/status/ws

Each message is JSON:
{
  "drones": [
    {
      "drone_id": "Drone1",
      "position": {"x": ..., "y": ..., "z": ...},
      "velocity": {"vx": ..., "vy": ..., "vz": ...},
      "heading": 45.0,
      "altitude": 20.0,
      "state": "hovering",
      "current_task": "Viewing House A"
    },
    ...
  ],
  "total_count": 5,
  "flying_count": 3,
  "emergency_active": false
}
```

---

### Scenario 12: Full Neighborhood Survey Mission

**Goal:** Systematically photograph all 20 houses using all 5 drones. Split houses into groups of 4 per drone.

```
Assignment:
  Drone1 → Houses A, B, C, D
  Drone2 → Houses E, F, G, H
  Drone3 → Houses I, J, K, L
  Drone4 → Houses M, N, O, P
  Drone5 → Houses Q, R, S, T

Step 1 — Initialize and take off all
POST /fleet/takeoff

Step 2 — Round 1: Send all 5 drones to their first house (parallel)
POST /drones/drone1/goto-house  Body: {"house": "A"}
POST /drones/drone2/goto-house  Body: {"house": "E"}
POST /drones/drone3/goto-house  Body: {"house": "I"}
POST /drones/drone4/goto-house  Body: {"house": "M"}
POST /drones/drone5/goto-house  Body: {"house": "Q"}

Step 3 — Wait and monitor until all hovering
GET /status/fleet  (poll until flying_count = 0 or all states = "hovering")

Step 4 — Capture photos (parallel)
POST /drones/drone1/photo  Body: {"label": "survey_A"}
POST /drones/drone2/photo  Body: {"label": "survey_E"}
POST /drones/drone3/photo  Body: {"label": "survey_I"}
POST /drones/drone4/photo  Body: {"label": "survey_M"}
POST /drones/drone5/photo  Body: {"label": "survey_Q"}

Step 5 — Round 2: Next house per drone
POST /drones/drone1/goto-house  Body: {"house": "B"}
POST /drones/drone2/goto-house  Body: {"house": "F"}
POST /drones/drone3/goto-house  Body: {"house": "J"}
POST /drones/drone4/goto-house  Body: {"house": "N"}
POST /drones/drone5/goto-house  Body: {"house": "R"}

(Repeat wait → photo → next house pattern)

Step 6 — Round 3
POST /drones/drone1/goto-house  Body: {"house": "C"}
POST /drones/drone2/goto-house  Body: {"house": "G"}
POST /drones/drone3/goto-house  Body: {"house": "K"}
POST /drones/drone4/goto-house  Body: {"house": "O"}
POST /drones/drone5/goto-house  Body: {"house": "S"}

Step 7 — Round 4 (final)
POST /drones/drone1/goto-house  Body: {"house": "D"}
POST /drones/drone2/goto-house  Body: {"house": "H"}
POST /drones/drone3/goto-house  Body: {"house": "L"}
POST /drones/drone4/goto-house  Body: {"house": "P"}
POST /drones/drone5/goto-house  Body: {"house": "T"}

Step 8 — Final photos and land
(Capture photos for round 4, then:)
POST /fleet/land
```

---

## 5. Best Practices

### Before Every Mission
- **Check fleet status first** — `GET /status/fleet` to see what state drones are in.
- **Check for active emergencies** — If `emergency_active = true`, call `POST /fleet/clear-emergency` before issuing commands.

### Choosing the Right Command
- **Use `goto-house` over raw coordinates** whenever targeting a house — it auto-positions the drone at a good viewing angle and handles takeoff automatically.
- **Use `move` for arbitrary coordinates** when you need precise positioning not tied to a house.
- **Use formation flight** when moving the whole fleet — it handles coordination and spacing automatically.

### Speed and Altitude Guidelines
| Parameter | Safe Range | Recommended | Notes |
|-----------|-----------|-------------|-------|
| Altitude | 5 – 100 m | 15 – 30 m | Lower for close inspection, higher for survey |
| Speed | 1 – 20 m/s | 3 – 8 m/s | Slower near houses, faster for transit |
| Altitude speed | 1 – 10 m/s | 2 – 5 m/s | |
| Formation spacing | 3 – 20 m | 6 – 10 m | Tighter risks collision |
| Formation speed | 1 – 15 m/s | 3 – 7 m/s | |

### Non-Blocking vs Blocking
- **Default is non-blocking** (`wait: false`) — command returns immediately while the drone flies.
- **Use `wait: true`** when the next command depends on the drone being in position (e.g., take photo after arriving at house).
- **For parallel dispatch**, use non-blocking for all drones, then poll `GET /status/fleet` to track progress.

### Coordinate Bounds
The Neighborhood map houses span approximately:
- **X axis:** -76 to +61 meters
- **Y axis:** -66 to +69 meters

Stay within these bounds for meaningful navigation. Going far outside will put drones over featureless terrain.

### Error Handling
- `200` — Success
- `400` — Bad request (invalid parameters)
- `404` — Drone or house not found
- `500` — AirSim/server error

Check the `"detail"` field in error responses for a human-readable message.

---

## 6. Houses Reference

All 20 house locations in the Neighborhood map. Coordinates are in meters from the world origin.

| House | X | Y |
|-------|-------|-------|
| A | 20.1 | -17.2 |
| B | -20.6 | -19.5 |
| C | 20.9 | 25.4 |
| D | -24.4 | 29.5 |
| E | -34.7 | 20.9 |
| F | 33.4 | 23.5 |
| G | 20.9 | -36.9 |
| H | -20.9 | -39.1 |
| I | -22.6 | -49.0 |
| J | -35.3 | 41.9 |
| K | 20.9 | -54.4 |
| L | 25.1 | 53.2 |
| M | -61.3 | -19.0 |
| N | -27.0 | 60.0 |
| O | 60.5 | -33.4 |
| P | -37.2 | 58.4 |
| Q | -22.7 | -66.2 |
| R | -68.6 | -29.0 |
| S | 29.7 | 69.0 |
| T | -75.6 | -14.5 |
