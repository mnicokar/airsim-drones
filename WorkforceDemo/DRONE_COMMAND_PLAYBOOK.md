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

There are 5 drones. The valid drone IDs are:

`Drone1`, `Drone2`, `Drone3`, `Drone4`, `Drone5`

**IMPORTANT — Drone ID formatting rules:**
- IDs are **one word, no spaces**. `Drone1` is correct. `Drone 1` is **wrong** and will fail.
- The API is case-insensitive: `drone1`, `DRONE1`, `Drone1` all work. The shorthand `d1`/`D1` also works.
- When the user says "drone 1", "Drone 1", "the first drone", or "d1", always send `Drone1` (no space).
- When the user says "all drones" or "every drone", use a fleet command instead of addressing drones individually.

### Default Values

Every optional parameter has a sensible default. If the user doesn't specify a value, **omit the parameter and the server will use the default**. Never ask the user for optional values — just use the defaults.

| Parameter | Default | Range | Unit |
|-----------|---------|-------|------|
| Takeoff altitude | **20** | 5 – 100 | meters |
| Flight speed (all movement) | **5.0** | 1 – 20 | m/s |
| Altitude change speed | **5.0** | 1 – 10 | m/s |
| View distance (goto-house) | **10.0** | 0 – 50 | meters |
| Formation type | **v** | v, line, diamond, echelon, column | — |
| Formation spacing | **8.0** | 3 – 20 | meters |
| Formation speed | **5.0** | 1 – 15 | m/s |

### Automatic Behaviors

1. **Auto-initialization** — Every individual drone command auto-initializes the drone if it hasn't been initialized yet. No manual init step required.
2. **Auto-takeoff on goto-house** — If a drone is landed/idle when you call `goto-house`, it automatically takes off first.
3. **Fleet auto-init** — Fleet commands (`/fleet/takeoff`, `/fleet/group-flight`) auto-initialize all drones if needed.

---

## 3. Action Name Reference

You have 20 available actions. Use this table to select the correct action and know which parameters to include.

### Quick Lookup

| Action Name | What It Does |
|-------------|-------------|
| `list_drones` | Discover which drones are available |
| `list_houses` | Get all 20 house locations (A-T) with coordinates |
| `get_drone_status` | Check a drone's position, state, heading, and current task |
| `get_fleet_status` | Check status of all drones at once (positions, states, emergency) |
| `takeoff_drone` | Launch a drone into the air |
| `land_drone` | Bring a drone down at its current position |
| `hover_drone` | Stop a drone and hover in place |
| `navigate_drone_to_house` | Send a drone to a house (auto-takes-off) — **preferred for house targets** |
| `move_drone_to_position` | Move a drone to arbitrary X,Y coordinates |
| `change_drone_altitude` | Raise or lower a drone without moving it horizontally |
| `rotate_drone` | Point a drone's camera in a compass direction |
| `capture_drone_photo` | Take a photo from a drone's camera |
| `fleet_initialize` | Initialize all drones for API control |
| `fleet_takeoff_all` | Take off all drones at once |
| `fleet_land_all` | Land every drone |
| `fleet_hover_all` | Hover all drones in place |
| `fleet_reset` | Return all drones to starting positions and land |
| `fleet_formation_flight` | Fly all 5 drones in formation to a house |
| `emergency_stop` | Immediately halt all drones |
| `fleet_clear_emergency` | Clear emergency status to resume operations |

### Detailed Action Descriptions

#### `list_drones`
Discover which drones exist in the simulation. Call this first if you don't know the fleet composition. Returns a list of drone IDs (e.g., ["Drone1", "Drone2", "Drone3", "Drone4", "Drone5"]). No parameters needed.

#### `list_houses`
Get all 20 house locations (A through T) with their X,Y coordinates. Use this to find valid navigation targets and plan routes. No parameters needed.

#### `get_drone_status`
Check a specific drone's current position, velocity, heading, altitude, state, and task. **Always call this before issuing commands** to understand what the drone is doing. Returns state values: `idle`, `taking_off`, `flying`, `hovering`, `landing`, `landed`, `emergency`.
- **Required:** `drone_id` (Drone1-Drone5)

#### `takeoff_drone`
Launch a drone and ascend to the specified altitude. Auto-initializes the drone if needed. **Use this before `move_drone_to_position` or `rotate_drone`**. Not needed before `navigate_drone_to_house` (which auto-takes-off).
- **Required:** `drone_id` (Drone1-Drone5)
- **Optional:** `altitude` — default **20m** (range 5-100m). If the user just says "take off", omit altitude.

#### `land_drone`
Safely bring a drone down at its current position. Use after completing a task or mission.
- **Required:** `drone_id` (Drone1-Drone5)

#### `navigate_drone_to_house`
Navigate a drone to view a specific house. The drone positions itself at a viewing distance facing the house, with the camera angled down. **Auto-takes-off if the drone is landed.** This is the preferred action for sending drones to houses — use this instead of `move_drone_to_position` whenever targeting a house.
- **Required:** `drone_id` (Drone1-Drone5), `house` (A-T)
- **Optional:** `speed` — default **5.0 m/s** (range 1-20). `view_distance` — default **10.0m** (range 0-50, 0 = directly above).

#### `move_drone_to_position`
Move a drone to arbitrary X,Y coordinates. Use this for precise positioning not tied to a house. **The drone must be airborne first** — call `takeoff_drone` or `navigate_drone_to_house` first.
- **Required:** `drone_id` (Drone1-Drone5), `x`, `y`
- **Optional:** `altitude` — keeps current altitude if omitted. `speed` — default **5.0 m/s** (range 1-20).

#### `change_drone_altitude`
Change a drone's altitude while staying at its current X,Y position. Use for altitude surveys or adjusting inspection height.
- **Required:** `drone_id` (Drone1-Drone5), `altitude` (1-100m)
- **Optional:** `speed` — default **5.0 m/s** (range 1-10).

#### `rotate_drone`
Rotate a drone to face a specific compass heading while hovering in place. Use this to aim the camera in a particular direction — for example, taking photos of a house from multiple angles.
- **Required:** `drone_id` (Drone1-Drone5), `heading` (0-360, where 0=North, 90=East, 180=South, 270=West)

#### `capture_drone_photo`
Capture photos from a drone's camera. Returns file paths to saved images. **Position and aim the drone first** using `navigate_drone_to_house` or `rotate_drone`.
- **Required:** `drone_id` (Drone1-Drone5)

#### `hover_drone`
Command a drone to stop all movement and hover in place at its current position. Use this to pause a drone mid-flight or stabilize it before taking a photo.
- **Required:** `drone_id` (Drone1-Drone5)

#### `get_fleet_status`
Get the current status of all drones at once, including positions, states, tasks, and whether an emergency is active. **Use this to monitor fleet progress** and check drone states before issuing commands. Returns `drones[]`, `total_count`, `flying_count`, and `emergency_active`. No parameters needed.

#### `fleet_initialize`
Discover and initialize all available drones for API control. Most commands auto-initialize, so this is only needed if you want to explicitly set up the fleet before issuing commands. No parameters needed.

#### `fleet_takeoff_all`
Command all drones to take off. Auto-initializes drones if needed. Use this to get the entire fleet airborne at once. No parameters needed.

#### `fleet_hover_all`
Command all drones to stop and hover in place at their current positions. Use this to pause the entire fleet. No parameters needed.

#### `fleet_reset`
Return all drones to their starting (home) positions and land them. Acts as a full fleet reset. Use this to start fresh or after completing a mission. No parameters needed.

#### `fleet_clear_emergency`
Clear emergency status and allow normal operations to resume. **Must be called after `emergency_stop`** before drones can accept new commands. No parameters needed.

#### `fleet_formation_flight`
Fly all 5 drones in formation to a house with a designated leader. All drones auto-initialize and auto-takeoff. Available formations: `v` (V-shape), `line` (side-by-side), `diamond`, `echelon` (diagonal), `column` (single file).
- **Required:** `leader` (Drone1-Drone5), `house` (A-T)
- **Optional:** `formation` (default "v"), `spacing` (3-20m, default 8m), `speed` (1-15 m/s, default 5)

#### `fleet_land_all`
Land every drone in the fleet at their current positions. Use to end a mission or bring all drones down. No parameters needed.

#### `emergency_stop`
Immediately stop all drones and command them to hover in place. **Use in any unsafe situation.** After calling this, normal operations are blocked until `fleet_clear_emergency` is called.

### Decision Guide: Choosing the Right Action

| User Intent | Best Action | Why |
|-------------|------------|-----|
| "Go to House C" | `navigate_drone_to_house` | Auto-takeoff, auto-positions, faces the house |
| "Move to coordinates 30, -20" | `move_drone_to_position` | Arbitrary positioning (needs takeoff first) |
| "Take off" | `takeoff_drone` | Explicit launch |
| "Take off all drones" | `fleet_takeoff_all` | Launches entire fleet at once |
| "Land" / "Come down" | `land_drone` or `fleet_land_all` | Single drone vs. all drones |
| "Hover" / "Stay there" | `hover_drone` or `fleet_hover_all` | Single drone vs. all drones |
| "Take a photo" | `capture_drone_photo` | Position drone first |
| "Fly in formation" | `fleet_formation_flight` | Coordinates all 5 drones |
| "Stop!" / "Emergency" | `emergency_stop` | Halts everything immediately |
| "Resume" / "Clear emergency" | `fleet_clear_emergency` | Unblocks commands after emergency stop |
| "Reset" / "Go home" / "Start over" | `fleet_reset` | Returns all drones to start positions |
| "Where is Drone 2?" | `get_drone_status` | Returns full status |
| "Fleet status" / "What are the drones doing?" | `get_fleet_status` | Returns all drone states at once |
| "What houses are there?" | `list_houses` | Returns all 20 with coordinates |
| "Change height to 40m" | `change_drone_altitude` | Adjusts altitude in place |
| "Face south" / "Turn to 180" | `rotate_drone` | Rotates camera direction |
| "Initialize drones" | `fleet_initialize` | Explicit fleet setup (usually auto) |

---

## 4. Endpoint Reference

These are the endpoints available to you. Replace `{drone_id}` with a valid drone ID like `Drone1` (no spaces).

### Read Endpoints (GET)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/drones` | List all available drone IDs |
| GET | `/drones/houses` | List all 20 houses with coordinates |
| GET | `/drones/{drone_id}` | Get drone status (position, heading, state, task) |
| GET | `/status/fleet` | Get all drone statuses + flying count + emergency state |
| GET | `/status/positions` | Get simplified position data for all drones |
| GET | `/status/health` | Health check (API running, AirSim connected) |

### Individual Drone Commands (POST)

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/drones/{drone_id}/takeoff` | `{"altitude": 20}` | Take off (altitude optional, default 20m) |
| POST | `/drones/{drone_id}/land` | — | Land at current position |
| POST | `/drones/{drone_id}/hover` | — | Stop and hover in place |
| POST | `/drones/{drone_id}/goto-house` | `{"house": "A"}` | Navigate to house (auto-takeoff) |
| POST | `/drones/{drone_id}/move` | `{"x": 20, "y": -15}` | Move to X,Y coordinates |
| POST | `/drones/{drone_id}/altitude` | `{"altitude": 30}` | Change altitude only |
| POST | `/drones/{drone_id}/rotate` | `{"heading": 180}` | Rotate to compass heading |
| POST | `/drones/{drone_id}/photo` | `{}` | Capture photo from camera |

### Fleet Commands (POST)

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/fleet/initialize` | — | Initialize all drones for API control |
| POST | `/fleet/takeoff` | — | Take off all drones |
| POST | `/fleet/land` | — | Land all drones |
| POST | `/fleet/hover` | — | Hover all drones in place |
| POST | `/fleet/reset` | — | Return all drones to starting positions and land |
| POST | `/fleet/group-flight` | `{"leader": "Drone1", "house": "A", "formation": "v"}` | Formation flight to house |
| POST | `/fleet/emergency-stop` | — | Emergency stop all drones immediately |
| POST | `/fleet/clear-emergency` | — | Clear emergency status to resume operations |

---

## 5. Scenario Playbooks

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

### Scenario 13: Fleet Reset

**Goal:** Return all drones to their starting positions and land — a clean slate.

```
Step 1 — Reset fleet
POST /fleet/reset
Expected: {"status": "reset", "drones": ["Drone1", "Drone2", ...], "count": 5}

All drones fly back to their home positions and land automatically.

Step 2 — Verify reset complete
GET /status/fleet
Expected: all drones state = "landed", flying_count = 0
```

---

## 6. Best Practices

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

