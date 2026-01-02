// Init Map
const map = L.map('map').setView([20.5937, 78.9629], 5);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { attribution: '© OpenStreetMap' }).addTo(map);

google.charts.load('current', {'packages':['corechart']});
google.charts.setOnLoadCallback(() => calculateCoverage());

// Layers
let markerLayer = L.layerGroup().addTo(map);
let unionLayer = L.layerGroup().addTo(map);
let polyLayer = L.layerGroup().addTo(map);
let boundaryLayer = new L.FeatureGroup().addTo(map);

// State
let mode = null; 
let selectedType = null;
let tempPolyPoints = []; 
let tempPolyLine = null;
let currentBoundaryItem = null;

// --- COLOR GENERATOR ---
function getColor(cat) {
    const map = {
        'hospital': '#e74c3c', 'school': '#f1c40f', 'atm': '#3498db',
        'bank': '#9b59b6', 'park': '#27ae60', 'commercial': '#e67e22',
        'residential': '#95a5a6', 'police': '#34495e', 'fire_station': '#d35400'
    };
    if(map[cat]) return map[cat];
    let hash = 0;
    for (let i = 0; i < cat.length; i++) hash = cat.charCodeAt(i) + ((hash << 5) - hash);
    const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
    return '#' + "00000".substring(0, 6 - c.length) + c;
}

// --- VISUALIZER ---
async function calculateCoverage() {
    const density = document.getElementById('densityInput').value;
    try {
        const res = await fetch(`/api/resources?density=${density}`);
        const data = await res.json();
        updateVisuals(data, true);
    } catch(e) { console.error(e); }
}

function updateVisuals(data, showRanges) {
    // 1. CLEAR LAYERS TO PREVENT DUPLICATES
    markerLayer.clearLayers();
    unionLayer.clearLayers();
    polyLayer.clearLayers();
    boundaryLayer.clearLayers();
    
    if (data.length === 0) return;

    // Separate Boundary from Services
    const services = data.filter(d => d.category !== 'project_boundary');
    const boundary = data.find(d => d.category === 'project_boundary');
    currentBoundaryItem = boundary;

    // Draw Boundary (Auto or Custom)
    if (boundary && boundary.shape_data) {
        const poly = L.polygon(boundary.shape_data, {
            color: "#333", dashArray: "10, 10", fill: false, weight: 2
        });
        boundaryLayer.addLayer(poly);
        map.fitBounds(poly.getBounds(), {padding:[20,20]});
    } else if (services.length > 0) {
        const points = turf.featureCollection(services.map(d => turf.point([d.lon, d.lat])));
        const bboxPoly = turf.bboxPolygon(turf.bbox(points));
        L.geoJSON(bboxPoly, {
            style: { color: "#333", dashArray: "5, 5", fill: false, weight: 2 }
        }).eachLayer(l => boundaryLayer.addLayer(l));
    }

    // Draw Services
    const categories = [...new Set(services.map(d => d.category))];
    categories.forEach(cat => {
        const items = services.filter(d => d.category === cat);
        const color = getColor(cat);
        let rangePolys = [];

        items.forEach(item => {
            if (item.geom_type === 'polygon') {
                L.polygon(item.shape_data, {
                    color: color, fillColor: color, fillOpacity: 0.4, weight: 2
                }).bindPopup(createEditPopup(item)).addTo(polyLayer);
            } else {
                // Marker
                const icon = L.divIcon({
                    className: 'custom-pin',
                    html: `<div style="background-color:${color}; width:12px; height:12px; border-radius:50%; border:2px solid white; box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>`
                });
                
                // DRAGGABLE MARKER LOGIC
                const marker = L.marker([item.lat, item.lon], { icon: icon, draggable: true })
                    .bindPopup(createEditPopup(item))
                    .addTo(markerLayer);

                // Handle Drag End - Update DB
                marker.on('dragend', async (e) => {
                    const newLat = e.target.getLatLng().lat;
                    const newLon = e.target.getLatLng().lng;
                    // We simply update backend. Next refresh will redraw it in new spot.
                    await updateService(item.id, { lat: newLat, lon: newLon });
                });

                if (showRanges) {
                    rangePolys.push(turf.circle([item.lon, item.lat], item.range, {steps:32, units:'kilometers'}));
                }
            }
        });

        // Union Logic
        if (showRanges && rangePolys.length > 0) {
            try {
                let merged = rangePolys[0];
                for(let i=1; i<rangePolys.length; i++) merged = turf.union(merged, rangePolys[i]);
                L.geoJSON(merged, {
                    style: { color: color, fillColor: color, fillOpacity: 0.15, weight: 1 },
                    interactive: false
                }).addTo(unionLayer);
            } catch(e) {}
        }
    });

    drawChart(services);
}

// --- BUILDER MODES ---
function toggleBuildMode() {
    resetModes();
    const sel = document.getElementById('builderService');
    if(!sel.value) { alert("Select type first"); return; }
    
    mode = 'point';
    selectedType = sel.value;
    updateStatus(`Click map to place <b>${selectedType}</b>`);
    L.DomUtil.addClass(map.getContainer(), 'crosshair-cursor-enabled');
}

function resetModes() {
    mode = null; selectedType = null;
    L.DomUtil.removeClass(map.getContainer(), 'crosshair-cursor-enabled');
    updateStatus("View Only");
}

function updateStatus(msg) { document.getElementById('mode-status').innerHTML = msg; }

// MAP CLICK HANDLER (BUILDER)
map.on('click', async function(e) {
    if (!mode) return;

    if (mode === 'point') {
        const name = prompt(`Name for new ${selectedType}?`, "New Facility");
        if(!name) return;
        
        // NEW: Ask for Capacity
        const capStr = prompt(`Capacity for ${name}? (Scale 1-100)`, "50");
        const cap = parseInt(capStr) || 50;
        
        await apiAdd({
            name: name, 
            category: selectedType, 
            geom_type: 'point',
            lat: e.latlng.lat, 
            lon: e.latlng.lng,
            capacity: cap // <--- SEND CAPACITY
        });
        resetModes();
    }
});

// --- BOUNDARY EDITING ---
function enableBoundaryEdit() {
    document.getElementById('btn-edit-boundary').style.display = 'none';
    document.getElementById('btn-save-boundary').style.display = 'flex';
    boundaryLayer.eachLayer(l => {
        l.setStyle({ color: '#ef4444', dashArray: null, weight: 3 });
        if(l.editing) l.editing.enable();
    });
    if (boundaryLayer.getLayers().length === 0) {
        new L.Draw.Rectangle(map).enable();
        map.on(L.Draw.Event.CREATED, e => boundaryLayer.addLayer(e.layer));
    }
}

async function saveBoundary() {
    if (boundaryLayer.getLayers().length === 0) return;
    const layer = boundaryLayer.getLayers()[0];
    const coords = layer.getLatLngs()[0].map(p => [p.lat, p.lng]);
    
    if (currentBoundaryItem) await fetch(`/api/delete/${currentBoundaryItem.id}`, {method:'DELETE'});
    
    await apiAdd({
        name: "Project Boundary", category: "project_boundary",
        geom_type: "polygon", coordinates: coords
    });
    
    document.getElementById('btn-edit-boundary').style.display = 'flex';
    document.getElementById('btn-save-boundary').style.display = 'none';
    calculateCoverage();
}

async function resetBoundary() {
    if(confirm("Reset boundary?")) {
        if (currentBoundaryItem) await fetch(`/api/delete/${currentBoundaryItem.id}`, {method:'DELETE'});
        calculateCoverage();
    }
}

// --- API HELPERS ---
async function apiAdd(payload) {
    await fetch('/api/add', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    calculateCoverage();
}

async function updateService(id, payload) {
    await fetch(`/api/update/${id}`, {
        method: 'PUT', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    // Note: We do NOT call calculateCoverage() here automatically if dragging 
    // to prevent jitter, but you can if you want instant range updates.
    calculateCoverage(); 
}

function createEditPopup(item) {
    return `
        <div class="popup-form">
            <b>${item.name}</b>
            <small>${item.category.toUpperCase()}</small>
            <label>Name:</label>
            <input type="text" id="name-${item.id}" value="${item.name}">
            <label>Capacity:</label>
            <input type="number" id="cap-${item.id}" value="${item.capacity}">
            <div class="popup-actions">
                <button onclick="saveEdit(${item.id})" class="btn-save">💾 Save</button>
                <button onclick="deleteService(${item.id})" class="btn-del">🗑️ Del</button>
            </div>
        </div>`;
}

window.saveEdit = async function(id) {
    const newName = document.getElementById(`name-${id}`).value;
    const newCap = document.getElementById(`cap-${id}`).value;
    await updateService(id, { name: newName, capacity: parseInt(newCap) });
};

window.deleteService = async function(id) {
    if(confirm("Delete?")) { await fetch(`/api/delete/${id}`, {method:'DELETE'}); calculateCoverage(); }
}

// --- SYNC & CHARTS ---
document.getElementById('densitySlider').addEventListener('input', function() { document.getElementById('densityInput').value = this.value; });
document.getElementById('densityInput').addEventListener('input', function() { document.getElementById('densitySlider').value = this.value; });
function clearCoverage() { markerLayer.clearLayers(); unionLayer.clearLayers(); boundaryLayer.clearLayers(); }
function drawChart(data) {
    let counts = {}; data.forEach(d => counts[d.category] = (counts[d.category]||0)+1);
    let chartData = [['Category', 'Count']]; for (let [k,v] of Object.entries(counts)) chartData.push([k,v]);
    var chart = new google.visualization.PieChart(document.getElementById('chart_div'));
    chart.draw(google.visualization.arrayToDataTable(chartData), { pieHole: 0.4, legend: 'none', chartArea:{width:'90%',height:'90%'} });
}
window.exportData = function() { window.location.href = "/api/export"; }
