import airsim
import time

# --- CONFIG ---
SPEED_FAST = 8
ALTITUDE = -5

# --- CONNECT ---
print("🔌 Connecting...")
client = airsim.MultirotorClient()
client.confirmConnection()
client.enableApiControl(True, "Drone1")
client.enableApiControl(True, "Drone2")
client.armDisarm(True, "Drone1")
client.armDisarm(True, "Drone2")
print("✅ Connected. Starting in 3 seconds...")
time.sleep(3)

# --- HELPER: FIRE AND WAIT ---
# This replaces the broken .join() method
def move_swarm(x1, y1, z1, x2, y2, z2, duration):
    # Send commands to both drones immediately
    client.moveToPositionAsync(x1, y1, z1, SPEED_FAST, vehicle_name="Drone1")
    client.moveToPositionAsync(x2, y2, z2, SPEED_FAST, vehicle_name="Drone2")
    
    # Just wait for them to get there
    print(f"   ...Flying for {duration} seconds...")
    time.sleep(duration)

# --- THE SHOW ---

# 1. TAKEOFF
print("🛫 STAGE 1: Takeoff")
client.takeoffAsync(vehicle_name="Drone1")
client.takeoffAsync(vehicle_name="Drone2")
time.sleep(4) # Wait for takeoff to finish

# Move to start altitude
move_swarm(0, 0, ALTITUDE, 2, 0, ALTITUDE, 3)

# 2. THE CHARGE
print("⏩ STAGE 2: Charge Forward")
# Both fly 20m forward
move_swarm(20, 0, ALTITUDE, 22, 0, ALTITUDE, 4)

# 3. THE HAMMERHEAD
print("🔄 STAGE 3: Climb")
# Shoot UP 10 meters (Z = -15)
move_swarm(20, 0, -15, 22, 0, -15, 3)

print("   ...Spinning...")
client.rotateToYawAsync(180, vehicle_name="Drone1")
client.rotateToYawAsync(180, vehicle_name="Drone2")
time.sleep(2)

print("   ...Dive...")
# Dive back down
move_swarm(20, 0, ALTITUDE, 22, 0, ALTITUDE, 3)

# 4. THE SPLIT
print("↔️ STAGE 4: Split")
# Split Left/Right
move_swarm(20, -10, ALTITUDE, 22, 10, ALTITUDE, 3)
time.sleep(1)

# 5. RETURN TO BASE
print("🏠 STAGE 5: Return to Base")
move_swarm(0, 0, -2, 2, 0, -2, 5)

print("⬇️ Landing...")
client.landAsync(vehicle_name="Drone1")
client.landAsync(vehicle_name="Drone2")
time.sleep(5)

print("🏁 SHOW COMPLETE")