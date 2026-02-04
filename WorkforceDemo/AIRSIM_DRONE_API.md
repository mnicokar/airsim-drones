# AirSim Drone API Reference

Complete reference for controlling multirotors via the Python API.

---

## Connection & Setup

```python
import airsim

client = airsim.MultirotorClient()
```

| Method | Description |
|--------|-------------|
| `confirmConnection()` | Verify simulator is running (blocks until connected) |
| `ping()` | Check if connection is alive |
| `reset()` | Reset vehicle to starting state |
| `enableApiControl(True, vehicle_name="")` | Enable API control (required before commands) |
| `isApiControlEnabled(vehicle_name="")` | Check if API control is active |
| `armDisarm(True, vehicle_name="")` | Arm/disarm motors (required before takeoff) |

---

## Takeoff & Landing

| Method | Description |
|--------|-------------|
| `takeoffAsync(timeout_sec=20, vehicle_name="")` | Takeoff to ~3m above ground |
| `landAsync(timeout_sec=60, vehicle_name="")` | Land at current position |
| `goHomeAsync(timeout_sec=3e38, vehicle_name="")` | Return to home position and land |

**Example:**
```python
client.takeoffAsync().join()    # Blocking takeoff
client.landAsync().join()       # Blocking landing
```

---

## Movement Commands

### Position Control

```python
moveToPositionAsync(x, y, z, velocity,
                    timeout_sec=3e38,
                    drivetrain=MaxDegreeOfFreedom,
                    yaw_mode=YawMode(),
                    lookahead=-1,
                    adaptive_lookahead=1,
                    vehicle_name="")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `x, y, z` | float | Target position in NED coordinates |
| `velocity` | float | Speed in m/s |
| `timeout_sec` | float | Max time to reach target |
| `drivetrain` | DrivetrainType | Movement mode |
| `yaw_mode` | YawMode | How to handle rotation |

**Example:**
```python
# Move to position (10, 5, -5) at 5 m/s
client.moveToPositionAsync(10, 5, -5, 5).join()
```

---

### Velocity Control

```python
moveByVelocityAsync(vx, vy, vz, duration,
                    drivetrain=MaxDegreeOfFreedom,
                    yaw_mode=YawMode(),
                    vehicle_name="")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `vx, vy, vz` | float | Velocity vector in m/s (NED) |
| `duration` | float | How long to maintain velocity (seconds) |

**Example:**
```python
# Fly north at 5 m/s for 10 seconds
client.moveByVelocityAsync(5, 0, 0, 10).join()
```

---

### Velocity with Altitude Hold

```python
moveByVelocityZAsync(vx, vy, z, duration,
                     drivetrain=MaxDegreeOfFreedom,
                     yaw_mode=YawMode(),
                     vehicle_name="")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `vx, vy` | float | Horizontal velocity in m/s |
| `z` | float | Target altitude (NED, negative = up) |
| `duration` | float | Duration in seconds |

**Example:**
```python
# Fly east at 3 m/s while holding altitude at 10m
client.moveByVelocityZAsync(0, 3, -10, 5).join()
```

---

### Path Following

```python
moveOnPathAsync(path, velocity,
                timeout_sec=3e38,
                drivetrain=MaxDegreeOfFreedom,
                yaw_mode=YawMode(),
                lookahead=-1,
                adaptive_lookahead=1,
                vehicle_name="")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | list[Vector3r] | List of waypoints |
| `velocity` | float | Speed in m/s |

**Example:**
```python
path = [
    airsim.Vector3r(0, 0, -5),
    airsim.Vector3r(10, 0, -5),
    airsim.Vector3r(10, 10, -5),
    airsim.Vector3r(0, 10, -5),
    airsim.Vector3r(0, 0, -5),
]
client.moveOnPathAsync(path, 5).join()
```

---

### Altitude Control

```python
moveToZAsync(z, velocity,
             timeout_sec=3e38,
             yaw_mode=YawMode(),
             lookahead=-1,
             adaptive_lookahead=1,
             vehicle_name="")
```

**Example:**
```python
# Climb to 20m altitude at 3 m/s
client.moveToZAsync(-20, 3).join()
```

---

### Rotation Control

```python
rotateToYawAsync(yaw, timeout_sec=3e38, margin=5, vehicle_name="")
rotateByYawRateAsync(yaw_rate, duration, vehicle_name="")
```

| Method | Description |
|--------|-------------|
| `rotateToYawAsync(yaw)` | Rotate to absolute angle (degrees) |
| `rotateByYawRateAsync(yaw_rate, duration)` | Rotate at rate (deg/s) for duration |

**Example:**
```python
client.rotateToYawAsync(90).join()         # Face east
client.rotateByYawRateAsync(45, 4).join()  # Spin 180 degrees
```

---

### Hover

```python
hoverAsync(vehicle_name="")
```

Stops all movement and holds position.

---

## Low-Level Control

### Angle + Throttle

```python
moveByAngleRatesThrottleAsync(roll_rate, pitch_rate, yaw_rate, throttle, duration, vehicle_name="")
moveByAngleRatesZAsync(roll_rate, pitch_rate, yaw_rate, z, duration, vehicle_name="")
```

### Motor Control

```python
moveByMotorPWMsAsync(front_right_pwm, rear_left_pwm, front_left_pwm, rear_right_pwm, duration, vehicle_name="")
```

Direct PWM control (0.0 to 1.0) for each motor.

### RC-Style Control

```python
moveByRC(rcdata, vehicle_name="")
```

Simulates RC transmitter input.

---

## State & Sensors

### Get Multirotor State

```python
state = client.getMultirotorState(vehicle_name="")
```

Returns:
- `state.kinematics_estimated.position` - Vector3r (x, y, z)
- `state.kinematics_estimated.linear_velocity` - Vector3r
- `state.kinematics_estimated.angular_velocity` - Vector3r
- `state.kinematics_estimated.orientation` - Quaternionr (x, y, z, w)
- `state.gps_location` - GeoPoint (latitude, longitude, altitude)
- `state.timestamp` - nanoseconds
- `state.landed_state` - 0=Landed, 1=Flying
- `state.collision` - CollisionInfo

**Example:**
```python
state = client.getMultirotorState()
pos = state.kinematics_estimated.position
print(f"Position: ({pos.x_val}, {pos.y_val}, {pos.z_val})")
```

---

### Rotor States

```python
rotors = client.getRotorStates(vehicle_name="")
```

Returns thrust, torque, and speed for each rotor.

---

### IMU Data

```python
imu = client.getImuData(imu_name="", vehicle_name="")
```

Returns:
- `imu.angular_velocity` - Vector3r (rad/s)
- `imu.linear_acceleration` - Vector3r (m/s²)
- `imu.orientation` - Quaternionr

---

### Barometer

```python
baro = client.getBarometerData(barometer_name="", vehicle_name="")
```

Returns altitude and pressure readings.

---

### GPS

```python
gps = client.getGpsData(gps_name="", vehicle_name="")
```

Returns latitude, longitude, altitude, and velocity.

---

### Magnetometer

```python
mag = client.getMagnetometerData(magnetometer_name="", vehicle_name="")
```

Returns magnetic field vector.

---

### Distance Sensor

```python
dist = client.getDistanceSensorData(distance_sensor_name="", vehicle_name="")
```

Returns distance to nearest object.

---

## Camera & Images

### Get Images

```python
responses = client.simGetImages([
    airsim.ImageRequest("0", airsim.ImageType.Scene),
    airsim.ImageRequest("0", airsim.ImageType.DepthPlanar, True),
], vehicle_name="")
```

### Image Types

| Type | Description |
|------|-------------|
| `Scene` | RGB camera image |
| `DepthPlanar` | Depth map (planar) |
| `DepthPerspective` | Depth map (perspective) |
| `DepthVis` | Depth visualization |
| `DisparityNormalized` | Stereo disparity |
| `Segmentation` | Object segmentation |
| `SurfaceNormals` | Surface normal vectors |
| `Infrared` | Infrared image |

### Camera Pose

```python
# Get camera info
info = client.simGetCameraInfo("0", vehicle_name="")

# Set camera orientation
client.simSetCameraPose("0", airsim.Pose(position, orientation), vehicle_name="")
```

---

## Simulation Control

| Method | Description |
|--------|-------------|
| `simPause(True)` | Pause simulation |
| `simContinueForTime(seconds)` | Run for specified time then pause |
| `simSetTimeOfDay(True, "2024-06-21 12:00:00")` | Set time of day |
| `simSetWeatherParameter(param, value)` | Change weather |
| `simGetCollisionInfo(vehicle_name="")` | Get collision details |

---

## Vehicle Management

### Spawn New Vehicle

```python
pose = airsim.Pose(airsim.Vector3r(x, y, z), airsim.Quaternionr())
success = client.simAddVehicle("Drone3", "SimpleFlight", pose)
```

### List Vehicles

```python
vehicles = client.listVehicles()
```

### Get/Set Pose

```python
# Get current pose
pose = client.simGetVehiclePose(vehicle_name="")

# Teleport vehicle
client.simSetVehiclePose(pose, ignore_collision=True, vehicle_name="")
```

---

## Coordinate System (NED)

```
       +X (North)
         ^
         |
         |
+Y <-----+-----> -Y
(East)   |       (West)
         |
         v
       -X (South)

+Z = Down (below ground)
-Z = Up (altitude)
```

**Important:** Altitude is NEGATIVE Z. To fly at 10 meters altitude, use `z = -10`.

---

## Drivetrain Types

```python
airsim.DrivetrainType.ForwardOnly        # Front always faces movement direction
airsim.DrivetrainType.MaxDegreeOfFreedom # Can move any direction regardless of facing
```

---

## Yaw Modes

```python
# Fixed angle (degrees from north)
airsim.YawMode(is_rate=False, yaw_or_rate=90)   # Face east

# Angular velocity (degrees per second)
airsim.YawMode(is_rate=True, yaw_or_rate=30)    # Rotate 30 deg/s

# No yaw change
airsim.YawMode.Zero()
```

---

## Async Pattern

All movement commands are async and return `Future` objects:

```python
# Blocking - wait for completion
client.moveToPositionAsync(10, 0, -5, 5).join()

# Non-blocking - continue immediately
future = client.moveToPositionAsync(10, 0, -5, 5)
# ... do other stuff ...
future.join()  # Wait when needed

# Parallel movement (multiple drones)
f1 = client.moveToPositionAsync(10, 0, -5, 5, vehicle_name="Drone1")
f2 = client.moveToPositionAsync(10, 5, -5, 5, vehicle_name="Drone2")
f1.join()
f2.join()
```

**Note:** Sending a new command auto-cancels the previous async task for that vehicle.

---

## Data Types

### Vector3r

```python
v = airsim.Vector3r(x, y, z)
v.x_val, v.y_val, v.z_val
```

### Quaternionr

```python
q = airsim.Quaternionr(x, y, z, w)
q.x_val, q.y_val, q.z_val, q.w_val
```

### Pose

```python
pose = airsim.Pose(position_vector3r, orientation_quaternionr)
pose.position
pose.orientation
```

### Convert Quaternion to Euler

```python
pitch, roll, yaw = airsim.to_eularian_angles(quaternion)
```

### Convert Euler to Quaternion

```python
q = airsim.to_quaternion(pitch, roll, yaw)
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Connect | `client = airsim.MultirotorClient()` |
| Enable control | `client.enableApiControl(True)` |
| Arm | `client.armDisarm(True)` |
| Takeoff | `client.takeoffAsync().join()` |
| Move to point | `client.moveToPositionAsync(x, y, z, speed).join()` |
| Fly by velocity | `client.moveByVelocityAsync(vx, vy, vz, duration).join()` |
| Rotate | `client.rotateToYawAsync(degrees).join()` |
| Hover | `client.hoverAsync().join()` |
| Land | `client.landAsync().join()` |
| Disarm | `client.armDisarm(False)` |
| Get position | `client.getMultirotorState().kinematics_estimated.position` |
| Get image | `client.simGetImages([ImageRequest(...)])` |
