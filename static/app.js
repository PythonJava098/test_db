// static/app.js

// Init Map
const map = L.map('map').setView([20.5937, 78.9629], 5);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap & CartoDB'
}).addTo(map);

// Google Charts
google.charts.load('current', {'packages':['corechart']});
google.charts.setOnLoadCallback(fetchData);

// Layers (Z-Index order matters!)
// 1. Union Layer (Bottom)
let unionLayer = L.layerGroup().addTo(map); 
// 2. Project Boundary
let projectAreaLayer = L.layerGroup().addTo(map); 
// 3. Markers (Top) - so they are always clickable
let markerLayer = L.layerGroup().addTo(map); 

let allocationMode = null;
let globalData = [];

// --- 1. FETCH DATA ---
document.getElementById('densitySlider').addEventListener('input', function(e) {
    document.getElementById('densityVal').innerText = e.target.value;
    fetchData(); 
});

async function fetchData() {
    const density = document.getElementById('densitySlider').value;
    try {
        const res = await fetch(`/api/resources?density=${density}`);
        globalData = await res.json();
        updateVisuals(globalData);
    } catch (err) { console.error(err); }
}

// --- 2. VISUALIZE ---
function updateVisuals(data) {
    markerLayer.clearLayers();
    unionLayer.clearLayers();
    projectAreaLayer.clearLayers();
    
    if (data.length === 0) return;

    // A. Draw Boundary
    const points = turf.featureCollection(data.map(d => turf.point([d.lon, d.lat])));
    const bbox = turf.bbox(points);
    const bboxPoly = turf.bboxPolygon(bbox);
    L.geoJSON(bboxPoly, {
        style: { color: "#333", dashArray: "5, 5", fill: false, weight: 2 }
    }).addTo(projectAreaLayer);

    // B. Group & Draw
    const categories = ['hospital', 'school', 'atm', 'petrol_pump'];
    
    categories.forEach(cat => {
        const items = data.filter(d => d.category === cat);
        if (items.length === 0) return;

        let color = getColor(cat);
        let polys = [];

        items.forEach(item => {
            // MARKER (Now Draggable!)
            const marker = L.circleMarker([item.lat, item.lon], {
                radius: 6, color: '#fff', fillColor: color, fillOpacity: 1, weight: 2
            });

            // Make it draggable by using a hidden larger hit-area or just handling drag events manually?
            // Leaflet CircleMarkers aren't naturally draggable. We swap to standard Marker for editing?
            // Better: We use a standard marker with a custom colored icon.
            
            const customIcon = L.divIcon({
                className: 'custom-pin',
                html: `<div style="background-color:${color}; width:12px; height:12px; border-radius:50%; border:2px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.5);"></div>`,
                iconSize: [16, 16]
            });

            const dragMarker = L.marker([item.lat, item.lon], {
                icon: customIcon,
                draggable: true // <--- ENABLE DRAGGING
            }).bindPopup(createEditPopup(item)).addTo(markerLayer);

            // Handle Drag End (Update Lat/Lon)
            dragMarker.on('dragend', async function(e) {
                const newLat = e.target.getLatLng().lat;
                const newLon = e.target.getLatLng().lng;
                await updateService(item.id, { lat: newLat, lon: newLon });
            });

            // Create Range Circle for Union
            let circle = turf.circle([item.lon, item.lat], item.range, {steps: 64, units: 'kilometers'});
            polys.push(circle);
        });

        // UNION POLYGON
        if (polys.length > 0) {
            let merged = polys[0];
            for (let i = 1; i < polys.length; i++) merged = turf.union(merged, polys[i]);

            L.geoJSON(merged, {
                style: { color: color, fillColor: color, fillOpacity: 0.2, weight: 1 },
                interactive: false // <--- CRITICAL FIX: Clicks pass through to markers
            }).addTo(unionLayer);
        }
    });

    drawChart(data);
}

// --- 3. CRUD POPUP ---
function createEditPopup(item) {
    // Returns a full HTML form inside the popup
    return `
        <div class="popup-form">
            <b>Edit Service</b>
            <label>Name:</label>
            <input type="text" id="name-${item.id}" value="${item.name}">
            
            <label>Capacity:</label>
            <input type="number" id="cap-${item.id}" value="${item.capacity}">
            
            <div class="coords">
                <small>Lat: ${item.lat.toFixed(4)}</small>
                <small>Lon: ${item.lon.toFixed(4)}</small>
            </div>

            <div class="popup-actions">
                <button onclick="saveEdit(${item.id})" class="btn-save">💾 Save</button>
                <button onclick="deleteService(${item.id})" class="btn-del">🗑️ Delete</button>
            </div>
            <small style="color:#888; font-size:10px;">(Drag marker to move)</small>
        </div>
    `;
}

// --- 4. API ACTIONS ---

// Save Updates (Name & Capacity)
window.saveEdit = async function(id) {
    const newName = document.getElementById(`name-${id}`).value;
    const newCap = document.getElementById(`cap-${id}`).value;
    
    await updateService(id, { name: newName, capacity: parseInt(newCap) });
};

// Generic Update Function
async function updateService(id, payload) {
    await fetch(`/api/update/${id}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    fetchData(); // Refresh UI
}

// Delete Service
window.deleteService = async function(id) {
    if(!confirm("Are you sure you want to delete this service?")) return;
    
    await fetch(`/api/delete/${id}`, { method: 'DELETE' });
    map.closePopup();
    fetchData();
};

// Add Service
map.on('click', async function(e) {
    if (!allocationMode) return;
    const name = prompt(`Name for new ${allocationMode}?`, "New Facility");
    if (!name) return;
    
    await fetch('/api/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: name, category: allocationMode,
            lat: e.latlng.lat, lon: e.latlng.lng, capacity: 50
        })
    });
    fetchData();
    setMode(null);
});

// --- HELPERS ---
function setMode(mode) {
    allocationMode = mode;
    const status = document.getElementById('mode-status');
    if (mode) {
        status.innerHTML = `Build Mode: <b>${mode.toUpperCase()}</b>`;
        status.style.color = "green";
        document.body.style.cursor = "crosshair";
    } else {
        status.innerHTML = "Status: View Only";
        status.style.color = "#666";
        document.body.style.cursor = "default";
    }
}

function getColor(cat) {
    if (cat === 'hospital') return '#e74c3c';
    if (cat === 'school') return '#f1c40f';
    if (cat === 'atm') return '#3498db';
    return '#2ecc71';
}

function drawChart(data) {
    let counts = {};
    data.forEach(d => counts[d.category] = (counts[d.category]||0)+1);
    let chartData = [['Category', 'Count']];
    for (let [k,v] of Object.entries(counts)) chartData.push([k,v]);
    
    let chart = new google.visualization.PieChart(document.getElementById('chart_div'));
    chart.draw(google.visualization.arrayToDataTable(chartData), {
        pieHole: 0.4, colors: ['#3498db', '#e74c3c', '#2ecc71', '#f1c40f'],
        legend: 'none', chartArea: {width: '90%', height: '90%'}
    });
}
window.exportData = function() { window.location.href = "/api/export"; }
