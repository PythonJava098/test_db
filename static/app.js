// Init Map
const map = L.map('map').setView([20.5937, 78.9629], 5);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { attribution: '© OpenStreetMap' }).addTo(map);

google.charts.load('current', {'packages':['corechart']});
google.charts.setOnLoadCallback(() => calculateCoverage());

// Layers
let markerLayer = L.layerGroup().addTo(map);
let unionLayer = L.layerGroup().addTo(map);
let polyLayer = L.layerGroup().addTo(map); // For Custom Shapes

// Drawing State
let mode = null; // 'point' or 'polygon'
let selectedType = null;
let tempPolyPoints = []; // Stores clicks for polygon
let tempPolyLine = null; // Visual guide line

// --- COLOR GENERATOR ---
function getColor(cat) {
    const map = {
        'hospital': '#e74c3c', 'school': '#f1c40f', 'atm': '#3498db',
        'bank': '#9b59b6', 'park': '#27ae60', 'commercial': '#e67e22',
        'residential': '#95a5a6', 'police': '#34495e'
    };
    // Return mapped color OR generate a consistent hash color for unknown types
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
    markerLayer.clearLayers();
    unionLayer.clearLayers();
    polyLayer.clearLayers();
    
    if (data.length === 0) return;

    // Group by category to handle colors & unions
    const categories = [...new Set(data.map(d => d.category))];

    categories.forEach(cat => {
        const items = data.filter(d => d.category === cat);
        const color = getColor(cat);
        let rangePolys = [];

        items.forEach(item => {
            // 1. HANDLE POLYGONS (Custom Areas)
            if (item.geom_type === 'polygon') {
                L.polygon(item.shape_data, {
                    color: color, fillColor: color, fillOpacity: 0.4, weight: 2
                }).bindPopup(`<b>${item.name}</b><br>${cat.toUpperCase()}<br><button onclick="deleteService(${item.id})">Delete</button>`).addTo(polyLayer);
            } 
            // 2. HANDLE POINTS (Standard Services)
            else {
                // Marker
                const icon = L.divIcon({
                    className: 'custom-pin',
                    html: `<div style="background-color:${color}; width:12px; height:12px; border-radius:50%; border:2px solid white; box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>`
                });
                
                L.marker([item.lat, item.lon], { icon: icon, draggable: true })
                    .bindPopup(createEditPopup(item))
                    .on('dragend', (e) => updateService(item.id, {lat: e.target.getLatLng().lat, lon: e.target.getLatLng().lng}))
                    .addTo(markerLayer);

                // Range Circle (only for points)
                if (showRanges) {
                    rangePolys.push(turf.circle([item.lon, item.lat], item.range, {steps:32, units:'kilometers'}));
                }
            }
        });

        // Union Logic for Points
        if (showRanges && rangePolys.length > 0) {
            try {
                let merged = rangePolys[0];
                for(let i=1; i<rangePolys.length; i++) merged = turf.union(merged, rangePolys[i]);
                L.geoJSON(merged, {
                    style: { color: color, fillColor: color, fillOpacity: 0.15, weight: 1 },
                    interactive: false
                }).addTo(unionLayer);
            } catch(e) { console.log("Union error", e); }
        }
    });

    drawChart(data);
}

// --- BUILDER MODES ---

// 1. Point Mode
function toggleBuildMode() {
    resetModes();
    const sel = document.getElementById('builderService');
    if(!sel.value) { alert("Select type first"); return; }
    
    mode = 'point';
    selectedType = sel.value;
    updateStatus(`Click map to place <b>${selectedType}</b>`);
    document.getElementById('map').style.cursor = 'crosshair';
}

// 2. Polygon Mode
function togglePolyMode() {
    resetModes();
    const sel = document.getElementById('builderService');
    if(!sel.value) { alert("Select type first"); return; }
    
    mode = 'polygon';
    selectedType = sel.value;
    tempPolyPoints = [];
    updateStatus(`Click to add points. <b>Double-Click</b> to finish.`);
    document.getElementById('map').style.cursor = 'crosshair';
}

function resetModes() {
    mode = null; selectedType = null; tempPolyPoints = [];
    if(tempPolyLine) map.removeLayer(tempPolyLine);
    document.getElementById('map').style.cursor = 'default';
    updateStatus("View Only");
}

function updateStatus(msg) {
    document.getElementById('mode-status').innerHTML = msg;
}

// Map Interactions
map.on('click', async function(e) {
    if (!mode) return;

    if (mode === 'point') {
        // ADD POINT
        const name = prompt("Facility Name?", "New " + selectedType);
        if(!name) return;
        
        await apiAdd({
            name: name, category: selectedType, geom_type: 'point',
            lat: e.latlng.lat, lon: e.latlng.lng
        });
        resetModes();
    } 
    else if (mode === 'polygon') {
        // ADD POLYGON VERTEX
        tempPolyPoints.push([e.latlng.lat, e.latlng.lng]);
        
        // Draw visual guide
        if(tempPolyLine) map.removeLayer(tempPolyLine);
        tempPolyLine = L.polygon(tempPolyPoints, {color: 'red', dashArray: '5,5'}).addTo(map);
    }
});

map.on('dblclick', async function(e) {
    if (mode === 'polygon' && tempPolyPoints.length > 2) {
        // FINISH POLYGON
        map.dragging.disable(); // Prevent zoom on dblclick
        setTimeout(() => map.dragging.enable(), 500);
        
        const name = prompt("Zone Name?", "New Zone");
        if(name) {
            await apiAdd({
                name: name, category: selectedType, geom_type: 'polygon',
                coordinates: tempPolyPoints
            });
        }
        resetModes();
    }
});

// --- API HELPERS ---
async function apiAdd(payload) {
    await fetch('/api/add', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    calculateCoverage();
}

function createEditPopup(item) {
    return `<div style="text-align:center"><b>${item.name}</b><br>${item.category}<br>
    <button onclick="deleteService(${item.id})" style="background:#ef4444;color:white;border:none;padding:5px;">Delete</button></div>`;
}

window.deleteService = async function(id) {
    if(confirm("Delete?")) {
        await fetch(`/api/delete/${id}`, {method: 'DELETE'});
        calculateCoverage();
    }
}

// Chart & Input Sync (Same as before)
document.getElementById('densitySlider').addEventListener('input', function() { document.getElementById('densityInput').value = this.value; });
document.getElementById('densityInput').addEventListener('input', function() { document.getElementById('densitySlider').value = this.value; });

function drawChart(data) {
    let counts = {};
    data.forEach(d => counts[d.category] = (counts[d.category]||0)+1);
    let chartData = [['Category', 'Count']];
    for (let [k,v] of Object.entries(counts)) chartData.push([k,v]);
    var chart = new google.visualization.PieChart(document.getElementById('chart_div'));
    chart.draw(google.visualization.arrayToDataTable(chartData), { pieHole: 0.4, legend: 'none', chartArea:{width:'90%',height:'90%'} });
}
