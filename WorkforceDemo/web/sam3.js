// SAM3 Segmentation Test - Frontend Logic

let currentFile = null;
let currentTab = 'upload';

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    fetchModelStatus();
    fetchDroneList();
});

async function fetchModelStatus() {
    const badge = document.getElementById('model-status');
    try {
        const res = await fetch('/api/sam3/status');
        const data = await res.json();
        if (data.loaded) {
            badge.textContent = 'Model: Ready';
            badge.className = 'status connected';
        } else {
            badge.textContent = 'Model: Not Loaded (loads on first use)';
            badge.className = 'status disconnected';
        }
    } catch (e) {
        badge.textContent = 'Model: Error';
        badge.className = 'status disconnected';
    }
}

async function fetchDroneList() {
    const select = document.getElementById('drone-select');
    try {
        const res = await fetch('/status/fleet');
        const data = await res.json();
        select.innerHTML = '';
        const drones = data.drones || [];
        if (drones.length === 0) {
            select.innerHTML = '<option value="">No drones available</option>';
            return;
        }
        drones.forEach(d => {
            const opt = document.createElement('option');
            const id = d.drone_id || d.id || d.name;
            opt.value = id;
            opt.textContent = id;
            select.appendChild(opt);
        });
    } catch (e) {
        select.innerHTML = '<option value="">Failed to load drones</option>';
    }
}

function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[data-tab="${tab}"]`).classList.add('active');
    document.getElementById(`tab-${tab}`).classList.add('active');
}

function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    currentFile = file;

    const reader = new FileReader();
    reader.onload = (e) => {
        const preview = document.getElementById('source-preview');
        preview.src = e.target.result;
        preview.style.display = 'block';
        document.getElementById('no-source').style.display = 'none';
    };
    reader.readAsDataURL(file);
}

async function grabDroneFrame() {
    const droneId = document.getElementById('drone-select').value;
    if (!droneId) {
        alert('Please select a drone');
        return;
    }

    try {
        const res = await fetch(`/drones/${droneId}/camera/frame`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        currentFile = new File([blob], 'drone_frame.jpg', { type: 'image/jpeg' });

        const preview = document.getElementById('source-preview');
        preview.src = URL.createObjectURL(blob);
        preview.style.display = 'block';
        document.getElementById('no-source').style.display = 'none';
    } catch (e) {
        alert(`Failed to grab drone frame: ${e.message}`);
    }
}

async function runSegmentation() {
    const prompt = document.getElementById('prompt-input').value.trim();
    if (!prompt) {
        alert('Please enter a text prompt');
        return;
    }

    // Show loading
    document.getElementById('loading-spinner').style.display = 'flex';
    document.getElementById('result-content').style.display = 'none';
    document.getElementById('no-result').style.display = 'none';
    document.getElementById('run-btn').disabled = true;

    try {
        let res;
        if (currentTab === 'drone') {
            const droneId = document.getElementById('drone-select').value;
            if (!droneId) {
                alert('Please select a drone');
                return;
            }
            const formData = new FormData();
            formData.append('drone_id', droneId);
            formData.append('prompt', prompt);
            res = await fetch('/api/sam3/segment/drone', { method: 'POST', body: formData });
        } else {
            if (!currentFile) {
                alert('Please select an image first');
                return;
            }
            const formData = new FormData();
            formData.append('file', currentFile);
            formData.append('prompt', prompt);
            res = await fetch('/api/sam3/segment/upload', { method: 'POST', body: formData });
        }

        if (!res.ok) {
            const errText = await res.text();
            throw new Error(errText || `HTTP ${res.status}`);
        }

        // Display result image
        const blob = await res.blob();
        const resultImg = document.getElementById('result-image');
        resultImg.src = URL.createObjectURL(blob);

        // Parse detection metadata from headers
        const numMasks = res.headers.get('X-SAM3-Num-Masks') || '0';
        const detectionsJson = res.headers.get('X-SAM3-Detections') || '[]';
        const detections = JSON.parse(detectionsJson);

        displayDetections(parseInt(numMasks), detections);

        document.getElementById('result-content').style.display = 'block';

        // Refresh model status
        fetchModelStatus();
    } catch (e) {
        alert(`Segmentation failed: ${e.message}`);
        document.getElementById('no-result').style.display = 'block';
    } finally {
        document.getElementById('loading-spinner').style.display = 'none';
        document.getElementById('run-btn').disabled = false;
    }
}

function displayDetections(numMasks, detections) {
    document.getElementById('detection-summary').textContent =
        `Found ${numMasks} mask${numMasks !== 1 ? 's' : ''}`;

    const tbody = document.getElementById('detections-body');
    tbody.innerHTML = '';

    detections.forEach(d => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>#${d.mask_index}</td>
            <td>${d.score.toFixed(4)}</td>
            <td>${d.area.toLocaleString()}</td>
        `;
        tbody.appendChild(row);
    });
}
