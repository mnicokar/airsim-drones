# Drone Fleet API Documentation

Simple REST API for controlling drones in AirSim. Designed for LLM integration.

## Quick Start

```bash
# Start AirSim with drones first, then:
python run_api.py
```

**Access Points:**
- API Docs: http://localhost:8000/docs
- Web Map: http://localhost:8000/
- WebSocket: ws://localhost:8000/status/ws

---

## Key Features

- **5 drones available** (Drone1 - Drone5)
- **20 houses** (A - T) as navigation targets
- **Case-insensitive drone IDs** - `drone1`, `Drone1`, `d1` all work
- **Auto-initialization** - Drones initialize automatically on first command
- **Auto-takeoff** - `goto-house` automatically takes off if drone is landed
- **Non-blocking by default** - All commands return immediately (async)

---

## API Endpoints

### Drone Commands

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/drones` | GET | List all drones |
| `/drones/houses` | GET | List all houses (A-T) with coordinates |
| `/drones/{id}` | GET | Get drone status |
| `/drones/{id}/takeoff` | POST | Take off |
| `/drones/{id}/land` | POST | Land |
| `/drones/{id}/hover` | POST | Stop and hover |
| `/drones/{id}/move` | POST | Move to X,Y position |
| `/drones/{id}/altitude` | POST | Change altitude |
| `/drones/{id}/goto-house` | POST | Navigate to house A-T |
| `/drones/{id}/rotate` | POST | Rotate to heading |
| `/drones/{id}/photo` | POST | Capture photo |
| `/drones/{id}/camera/frame` | GET | Get live camera frame (JPEG) |

### Fleet Commands

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/fleet/initialize` | POST | Initialize all drones |
| `/fleet/takeoff` | POST | Take off all drones |
| `/fleet/land` | POST | Land all drones |
| `/fleet/hover` | POST | Hover all drones |
| `/fleet/emergency-stop` | POST | Emergency stop all |
| `/fleet/clear-emergency` | POST | Clear emergency status |

### Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status/fleet` | GET | Get all drone statuses |
| `/status/health` | GET | API health check |
| `/status/ws` | WebSocket | Live status updates |

---

## Common Operations

### Send Drone to House

```
POST /drones/drone1/goto-house
```
```json
{"house": "A"}
```

### Move Drone to Coordinates

```
POST /drones/drone1/move
```
```json
{"x": 20, "y": -15}
```

### Take Photo

```
POST /drones/drone1/photo
```
```json
{}
```

### Get Drone Status

```
GET /drones/drone1
```

Response:
```json
{
  "drone_id": "Drone1",
  "position": {"x": 20.1, "y": -17.2, "z": -20.0},
  "altitude": 20.0,
  "heading": 45.0,
  "state": "hovering",
  "current_task": "Viewing House A"
}
```

### Take Off All Drones

```
POST /fleet/takeoff
```

### Emergency Stop

```
POST /fleet/emergency-stop
```

---

## Parallel Commands

All commands are **non-blocking by default**. To send multiple drones simultaneously:

```
POST /drones/drone1/goto-house  {"house": "A"}
POST /drones/drone2/goto-house  {"house": "B"}
POST /drones/drone3/goto-house  {"house": "C"}
```

All three return immediately and drones fly in parallel.

To wait for completion, add `"wait": true`:
```json
{"house": "A", "wait": true}
```

---

## Request/Response Examples

### Navigate to House

**Request:**
```
POST /drones/drone1/goto-house
Content-Type: application/json

{"house": "C"}
```

**Response:**
```json
{
  "house_name": "House C",
  "house_position": {"x": 20.9, "y": 25.4},
  "viewing_position": {"x": 15.2, "y": 20.1, "z": -20.0}
}
```

### Move to Position

**Request:**
```
POST /drones/drone1/move
Content-Type: application/json

{
  "x": 30.0,
  "y": -20.0,
  "altitude": 25.0,
  "speed": 8.0
}
```

**Response:**
```json
{
  "status": "moved",
  "drone_id": "Drone1",
  "position": {"x": 30.0, "y": -20.0, "altitude": 25.0}
}
```

### Rotate to Heading

**Request:**
```
POST /drones/drone1/rotate
Content-Type: application/json

{"heading": 180}
```

**Response:**
```json
{
  "status": "rotated",
  "drone_id": "Drone1",
  "heading": 180
}
```

### Change Altitude

**Request:**
```
POST /drones/drone1/altitude
Content-Type: application/json

{"altitude": 30}
```

**Response:**
```json
{
  "status": "altitude_changed",
  "drone_id": "Drone1",
  "altitude": 30
}
```

---

## LLM Integration

### Natural Language Mapping

| User Says | API Call |
|-----------|----------|
| "Send Drone1 to House A" | `POST /drones/drone1/goto-house {"house": "A"}` |
| "Move drone to 20, 30" | `POST /drones/drone1/move {"x": 20, "y": 30}` |
| "Take a photo" | `POST /drones/drone1/photo {}` |
| "Where is Drone 2?" | `GET /drones/drone2` |
| "Land all drones" | `POST /fleet/land` |
| "Emergency stop!" | `POST /fleet/emergency-stop` |
| "List all houses" | `GET /drones/houses` |
| "What's the fleet status?" | `GET /status/fleet` |

### Tool Definition Example

```json
{
  "name": "send_drone_to_house",
  "description": "Navigate a drone to view a specific house",
  "parameters": {
    "drone_id": {
      "type": "string",
      "description": "Drone ID (drone1-drone5)"
    },
    "house": {
      "type": "string",
      "description": "House letter (A-T)"
    }
  },
  "endpoint": "POST /drones/{drone_id}/goto-house",
  "body": {"house": "{house}"}
}
```

---

## Houses Reference

| House | X | Y |
|-------|-----|-----|
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

---

## Error Handling

HTTP status codes:
- `200` - Success
- `400` - Bad request
- `404` - Not found (drone or house)
- `500` - Server error

Error response:
```json
{
  "detail": "House 'Z' not found"
}
```

---

## Web Interface

Open http://localhost:8000/ for a live 2D map showing:
- Drone positions (updated in real-time)
- House locations
- Camera feed from selected drone

Click a drone in the Fleet Status panel to view its camera.
