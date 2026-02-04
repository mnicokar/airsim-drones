/**
 * Drone Fleet Monitor - WebSocket client and map rendering
 */

// Configuration
const CONFIG = {
    wsUrl: `ws://${window.location.host}/status/ws`,
    apiUrl: `http://${window.location.host}`,
    updateInterval: 1000,  // 1 second
    mapPadding: 20,
    droneSize: 12,
    houseSize: 10,
    gridSpacing: 20,
};

// State
let canvas, ctx;
let drones = [];
let houses = {};
let selectedDrone = null;
let ws = null;
let isConnected = false;

// Camera feed state
let cameraInterval = null;
let cameraDroneId = null;
let cameraLoading = false;  // Prevent request pileup

// Map transformation
let mapScale = 1;
let mapOffsetX = 0;
let mapOffsetY = 0;
let minX = -100, maxX = 100, minY = -100, maxY = 100;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    canvas = document.getElementById('map-canvas');
    ctx = canvas.getContext('2d');

    // Handle resize
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    // Canvas interaction
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('click', handleClick);

    // Load initial data
    loadHouses();

    // Connect WebSocket
    connectWebSocket();

    // Setup camera controls
    setupCameraControls();

    // Load drones immediately (don't wait for WebSocket)
    refreshStatus();

    // Frequent polling for live position updates (500ms)
    setInterval(refreshStatus, 500);
});

function resizeCanvas() {
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = canvas.parentElement.clientHeight;
    calculateMapTransform();
    render();
}

function calculateMapTransform() {
    const padding = CONFIG.mapPadding * 2;
    const worldWidth = maxX - minX;
    const worldHeight = maxY - minY;

    const scaleX = (canvas.width - padding) / worldWidth;
    const scaleY = (canvas.height - padding) / worldHeight;
    mapScale = Math.min(scaleX, scaleY);

    mapOffsetX = canvas.width / 2;
    mapOffsetY = canvas.height / 2;
}

// Coordinate conversion
function worldToScreen(x, y) {
    return {
        x: mapOffsetX + x * mapScale,
        y: mapOffsetY - y * mapScale  // Flip Y axis
    };
}

function screenToWorld(screenX, screenY) {
    return {
        x: (screenX - mapOffsetX) / mapScale,
        y: -(screenY - mapOffsetY) / mapScale
    };
}

// WebSocket connection
function connectWebSocket() {
    try {
        ws = new WebSocket(CONFIG.wsUrl);

        ws.onopen = () => {
            isConnected = true;
            updateConnectionStatus(true);
            console.log('WebSocket connected');
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleStatusUpdate(data);
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };

        ws.onclose = () => {
            isConnected = false;
            updateConnectionStatus(false);
            console.log('WebSocket disconnected, reconnecting...');
            setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            isConnected = false;
            updateConnectionStatus(false);
        };
    } catch (e) {
        console.error('Failed to connect WebSocket:', e);
        updateConnectionStatus(false);
    }
}

function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');
    if (connected) {
        statusEl.textContent = 'Connected';
        statusEl.className = 'status connected';
    } else {
        statusEl.textContent = 'Disconnected';
        statusEl.className = 'status disconnected';
    }
}

// Data handling
function handleStatusUpdate(data) {
    if (data.drones) {
        drones = data.drones;
        updateFleetList();
        updateDroneCount();
        updateMapBounds();
        render();

        // Update detail panel if a drone is selected
        if (selectedDrone) {
            const drone = drones.find(d => d.drone_id === selectedDrone);
            if (drone) {
                updateDetailPanel(drone);
            }
        }
    }

    document.getElementById('update-time').textContent =
        `Last update: ${new Date().toLocaleTimeString()}`;
}

function updateMapBounds() {
    if (drones.length === 0 && Object.keys(houses).length === 0) return;

    let points = [];

    // Add drone positions
    drones.forEach(d => {
        if (d.position) {
            points.push({ x: d.position.x, y: d.position.y });
        }
    });

    // Add house positions
    Object.values(houses).forEach(h => {
        points.push({ x: h.x, y: h.y });
    });

    if (points.length === 0) return;

    const xs = points.map(p => p.x);
    const ys = points.map(p => p.y);

    const padding = 30;
    minX = Math.min(...xs) - padding;
    maxX = Math.max(...xs) + padding;
    minY = Math.min(...ys) - padding;
    maxY = Math.max(...ys) + padding;

    // Ensure minimum size
    if (maxX - minX < 100) {
        const center = (maxX + minX) / 2;
        minX = center - 50;
        maxX = center + 50;
    }
    if (maxY - minY < 100) {
        const center = (maxY + minY) / 2;
        minY = center - 50;
        maxY = center + 50;
    }

    calculateMapTransform();
}

function updateFleetList() {
    const container = document.getElementById('fleet-list');
    if (drones.length === 0) {
        container.innerHTML = '<p style="color: #888; font-size: 0.9rem;">No drones connected</p>';
        return;
    }

    container.innerHTML = drones.map(d => {
        const isSelected = d.drone_id === selectedDrone ? 'selected' : '';
        return `
            <div class="drone-item ${isSelected}" onclick="selectDrone('${d.drone_id}')">
                <span class="drone-id">${d.drone_id}</span>
                <span class="drone-state ${d.state}">${d.state}</span>
            </div>
        `;
    }).join('');
}

function updateDroneCount() {
    const flying = drones.filter(d =>
        ['flying', 'taking_off', 'landing'].includes(d.state)
    ).length;
    document.getElementById('drone-count').textContent =
        `Drones: ${drones.length} (${flying} flying)`;
}

// API calls
async function loadHouses() {
    try {
        const response = await fetch(`${CONFIG.apiUrl}/drones/houses`);
        if (response.ok) {
            const data = await response.json();
            houses = {};
            data.houses.forEach(h => {
                houses[h.name] = { x: h.x, y: h.y };
            });
            updateHouseList();
            updateMapBounds();
            render();
        }
    } catch (e) {
        console.error('Failed to load houses:', e);
    }
}

function updateHouseList() {
    const container = document.getElementById('house-list');
    const houseNames = Object.keys(houses).sort();
    container.innerHTML = houseNames.map(name => {
        const letter = name.replace('House ', '');
        return `<div class="house-item" onclick="focusHouse('${name}')">${letter}</div>`;
    }).join('');
}

async function refreshStatus() {
    try {
        const response = await fetch(`${CONFIG.apiUrl}/status/fleet`);
        if (response.ok) {
            const data = await response.json();
            handleStatusUpdate(data);
        }
    } catch (e) {
        console.error('Failed to refresh status:', e);
    }
}

async function emergencyStop() {
    if (!confirm('Activate emergency stop for all drones?')) return;

    try {
        const response = await fetch(`${CONFIG.apiUrl}/fleet/emergency-stop`, {
            method: 'POST'
        });
        if (response.ok) {
            console.log('Emergency stop activated');
            refreshStatus();
        }
    } catch (e) {
        console.error('Failed to activate emergency stop:', e);
        alert('Failed to activate emergency stop!');
    }
}

async function clearEmergency() {
    try {
        const response = await fetch(`${CONFIG.apiUrl}/fleet/clear-emergency`, {
            method: 'POST'
        });
        if (response.ok) {
            console.log('Emergency cleared');
            refreshStatus();
        }
    } catch (e) {
        console.error('Failed to clear emergency:', e);
    }
}

// =========================================================================
// Camera Feed
// =========================================================================

function setupCameraControls() {
    const typeSelect = document.getElementById('camera-type');

    typeSelect.addEventListener('change', () => {
        if (cameraDroneId) {
            // Immediately fetch a new frame with the new type
            fetchCameraFrame();
        }
    });
}

function startCameraFeed(droneId) {
    // Stop any existing feed
    if (cameraInterval) {
        clearInterval(cameraInterval);
        cameraInterval = null;
    }

    cameraDroneId = droneId;

    // Show camera section and update label
    const cameraSection = document.getElementById('drone-camera-section');
    const cameraLabel = document.getElementById('camera-drone-label');

    cameraSection.classList.remove('hidden');
    cameraLabel.textContent = `Camera: ${droneId}`;

    // Fetch immediately
    fetchCameraFrame();

    // Then fetch every 100ms (10 fps target)
    cameraInterval = setInterval(fetchCameraFrame, 100);

    console.log(`Started camera feed for ${droneId}`);
}

function stopCameraFeed() {
    if (cameraInterval) {
        clearInterval(cameraInterval);
        cameraInterval = null;
    }
    cameraDroneId = null;

    // Hide camera section
    const cameraSection = document.getElementById('drone-camera-section');
    const img = document.getElementById('camera-image');

    cameraSection.classList.add('hidden');
    img.src = '';

    console.log('Stopped camera feed');
}

function fetchCameraFrame() {
    if (!cameraDroneId) return;
    if (cameraLoading) return;  // Skip if previous request still loading

    cameraLoading = true;

    const typeSelect = document.getElementById('camera-type');
    const imageType = typeSelect.value;
    const img = document.getElementById('camera-image');

    // Add timestamp to prevent caching
    const timestamp = Date.now();
    const url = `${CONFIG.apiUrl}/drones/${cameraDroneId}/camera/frame?type=${imageType}&t=${timestamp}`;

    // Create a new image to load
    const newImg = new Image();
    newImg.onload = () => {
        img.src = newImg.src;
        cameraLoading = false;
    };
    newImg.onerror = (e) => {
        console.error('Failed to load camera frame from:', url, e);
        cameraLoading = false;
    };
    newImg.src = url;
}

// Selection and interaction
function selectDrone(droneId) {
    // If clicking the same drone, deselect it
    if (selectedDrone === droneId) {
        closeDetail();
        return;
    }

    selectedDrone = droneId;
    const drone = drones.find(d => d.drone_id === droneId);
    if (drone) {
        updateDetailPanel(drone);
        document.getElementById('drone-detail').classList.remove('hidden');
        // Start camera feed for selected drone
        startCameraFeed(droneId);
    }
    updateFleetList();  // Update to show selection highlight
    render();
}

function closeDetail() {
    selectedDrone = null;
    document.getElementById('drone-detail').classList.add('hidden');
    stopCameraFeed();
    updateFleetList();  // Update to remove selection highlight
    render();
}

function updateDetailPanel(drone) {
    document.getElementById('detail-drone-id').textContent = drone.drone_id;
    document.getElementById('detail-position').textContent =
        `X: ${drone.position.x.toFixed(1)}, Y: ${drone.position.y.toFixed(1)}`;
    document.getElementById('detail-altitude').textContent =
        `${drone.altitude.toFixed(1)} m`;
    document.getElementById('detail-heading').textContent =
        `${drone.heading.toFixed(0)}°`;
    document.getElementById('detail-state').textContent = drone.state;
    document.getElementById('detail-task').textContent =
        drone.current_task || 'None';
}

function focusHouse(name) {
    const house = houses[name];
    if (house) {
        // Could implement pan/zoom to house here
        console.log(`Focus on ${name} at (${house.x}, ${house.y})`);
    }
}

// Mouse interaction
function handleMouseMove(event) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    const tooltip = document.getElementById('map-tooltip');
    let found = false;

    // Check drones
    for (const drone of drones) {
        if (!drone.position) continue;
        const pos = worldToScreen(drone.position.x, drone.position.y);
        const dist = Math.sqrt((mouseX - pos.x) ** 2 + (mouseY - pos.y) ** 2);

        if (dist < CONFIG.droneSize + 5) {
            tooltip.innerHTML = `
                <strong>${drone.drone_id}</strong><br>
                State: ${drone.state}<br>
                Alt: ${drone.altitude.toFixed(1)}m
            `;
            tooltip.style.left = (event.clientX - rect.left + 15) + 'px';
            tooltip.style.top = (event.clientY - rect.top + 15) + 'px';
            tooltip.classList.add('visible');
            found = true;
            break;
        }
    }

    // Check houses
    if (!found) {
        for (const [name, house] of Object.entries(houses)) {
            const pos = worldToScreen(house.x, house.y);
            const dist = Math.sqrt((mouseX - pos.x) ** 2 + (mouseY - pos.y) ** 2);

            if (dist < CONFIG.houseSize + 5) {
                tooltip.innerHTML = `
                    <strong>${name}</strong><br>
                    X: ${house.x.toFixed(1)}, Y: ${house.y.toFixed(1)}
                `;
                tooltip.style.left = (event.clientX - rect.left + 15) + 'px';
                tooltip.style.top = (event.clientY - rect.top + 15) + 'px';
                tooltip.classList.add('visible');
                found = true;
                break;
            }
        }
    }

    if (!found) {
        tooltip.classList.remove('visible');
    }
}

function handleClick(event) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    // Check drones
    for (const drone of drones) {
        if (!drone.position) continue;
        const pos = worldToScreen(drone.position.x, drone.position.y);
        const dist = Math.sqrt((mouseX - pos.x) ** 2 + (mouseY - pos.y) ** 2);

        if (dist < CONFIG.droneSize + 5) {
            selectDrone(drone.drone_id);
            return;
        }
    }

    // Click on empty space closes detail
    closeDetail();
}

// Rendering
function render() {
    if (!ctx) return;

    // Clear canvas
    ctx.fillStyle = '#0a0a1a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    drawGrid();
    drawHouses();
    drawDrones();
    drawCompass();
}

function drawGrid() {
    ctx.strokeStyle = '#1a1a3a';
    ctx.lineWidth = 1;

    // Vertical lines
    for (let x = Math.ceil(minX / CONFIG.gridSpacing) * CONFIG.gridSpacing;
         x <= maxX;
         x += CONFIG.gridSpacing) {
        const start = worldToScreen(x, minY);
        const end = worldToScreen(x, maxY);
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
    }

    // Horizontal lines
    for (let y = Math.ceil(minY / CONFIG.gridSpacing) * CONFIG.gridSpacing;
         y <= maxY;
         y += CONFIG.gridSpacing) {
        const start = worldToScreen(minX, y);
        const end = worldToScreen(maxX, y);
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
    }

    // Origin axes
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 2;

    // X axis
    let start = worldToScreen(minX, 0);
    let end = worldToScreen(maxX, 0);
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();

    // Y axis
    start = worldToScreen(0, minY);
    end = worldToScreen(0, maxY);
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();
}

function drawHouses() {
    const size = CONFIG.houseSize;

    for (const [name, house] of Object.entries(houses)) {
        const pos = worldToScreen(house.x, house.y);
        const letter = name.replace('House ', '');

        // House marker (square)
        ctx.fillStyle = '#e94560';
        ctx.fillRect(pos.x - size / 2, pos.y - size / 2, size, size);

        // Label
        ctx.fillStyle = '#fff';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(letter, pos.x, pos.y + size / 2 + 2);
    }
}

function drawDrones() {
    for (const drone of drones) {
        if (!drone.position) continue;

        const pos = worldToScreen(drone.position.x, drone.position.y);
        const size = CONFIG.droneSize;
        const isSelected = drone.drone_id === selectedDrone;

        // Drone color based on state
        let color;
        switch (drone.state) {
            case 'flying':
            case 'taking_off':
            case 'landing':
                color = '#2196f3';
                break;
            case 'emergency':
                color = '#f44336';
                break;
            default:
                color = '#4caf50';
        }

        // Selection highlight
        if (isSelected) {
            ctx.strokeStyle = '#00d9ff';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, size + 5, 0, Math.PI * 2);
            ctx.stroke();
        }

        // Drone body (circle)
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size, 0, Math.PI * 2);
        ctx.fill();

        // Drone ID label
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText(drone.drone_id.replace('Drone', 'D'), pos.x, pos.y - size - 2);
    }
}

function drawCompass() {
    const x = 50;
    const y = 50;
    const size = 30;

    // Background
    ctx.fillStyle = 'rgba(22, 33, 62, 0.8)';
    ctx.beginPath();
    ctx.arc(x, y, size + 5, 0, Math.PI * 2);
    ctx.fill();

    // Compass rose
    ctx.strokeStyle = '#666';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.stroke();

    // North indicator
    ctx.fillStyle = '#f44336';
    ctx.beginPath();
    ctx.moveTo(x, y - size + 5);
    ctx.lineTo(x - 5, y);
    ctx.lineTo(x + 5, y);
    ctx.closePath();
    ctx.fill();

    // South
    ctx.fillStyle = '#fff';
    ctx.beginPath();
    ctx.moveTo(x, y + size - 5);
    ctx.lineTo(x - 5, y);
    ctx.lineTo(x + 5, y);
    ctx.closePath();
    ctx.fill();

    // Labels
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 10px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', x, y - size - 10);
}
