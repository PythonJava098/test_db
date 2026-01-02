// Init Map
const map = L.map('map').setView([20.5937, 78.9629], 5);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap & CartoDB'
}).addTo(map);

google.charts.load('current', {'packages':['corechart']});
google.charts.setOnLoadCallback(() => calculateCoverage()); // Load initial data

// Layers
let markerLayer = L.layerGroup().addTo(map);
let unionLayer = L.layerGroup().addTo(map); 
let projectAreaLayer = L.layerGroup().addTo(map);

let isBuildMode = false;
let selectedServiceType = null;

// --- 1. DENSITY CONTROLS SYNC ---
const slider = document.getElementById('densitySlider');
const input = document.getElementById('densityInput');

// Sync Slider -> Input
slider.addEventListener('input', function() {
    input.value = this.value;
});

// Sync Input -> Slider
input.addEventListener('input', function() {
    let val = parseInt(this.value);
    if(val > 5000) val = 5000;
    if(val < 100) val = 100;
    slider.value = val;
});

// --- 2. CALCULATE / HIDE ---
async function calculateCoverage() {
    const density = input.value;
    try {
        // Show loading state if needed
        const res = await fetch(`/api/resources?density=${density}`);
        const data = await res.json();
        updateVisuals(data, true); // true = show ranges
    } catch (err) { console.error(err); }
}

function clearCoverage() {
    unionLayer.clearLayers(); // Remove the blobs
    // We re-fetch data but tell visualizer to SKIP drawing ranges
    // This keeps markers but hides the confusing circles
    markerLayer.eachLayer(layer => {
        if (layer.options.className === 'range-circle') {
            map.removeLayer(layer);
        }
    });
}

// --- 3. VISUALIZER ---
function updateVisuals(data, showRanges) {
    markerLayer.clearLayers();
    unionLayer.clearLayers();
    projectAreaLayer.clearLayers();
    
    if (data.length === 0) return;

    // Draw Boundary
    const points = turf.featureCollection(data.map(d => turf.point([d.lon, d.lat])));
    if(points.features.length > 0) {
        const bbox = turf.bbox(points);
        L.geoJSON(turf.bboxPolygon(bbox), {
            style: { color: "#333", dashArray: "5, 5", fill: false, weight: 2 }
        }).addTo(projectAreaLayer);
    }

    // Group & Draw
    // Define colors for new services too
    const colors = {
        'hospital': '#e74c3c', 'school': '#f1c40f', 'atm': '#3498db',
        'bank': '#9b59b6', 'petrol_pump': '#2ecc71', 'police': '#34495e',
        'fire_station': '#d35400', 'park': '#27ae60'
    };

    // Get unique categories present in data
    const presentCategories = [...new Set(data.map(item => item.category))];
    
    presentCategories.forEach(cat => {
        const items = data.filter(d => d.category === cat);
        let color = colors[cat] || '#95a5a6'; // Default gray for unknown
        let polys = [];

        items.forEach(item => {
            // MARKER
            const customIcon = L.divIcon({
                className: 'custom-pin',
                html: `<div style="background-color:${color}; width:14px; height:14px; border-radius:50%; border:2px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.5);"></div>`,
                iconSize: [18, 18]
            });

            const marker = L.marker([item.lat, item.lon], {
                icon: customIcon, draggable: true
            }).bindPopup(createEditPopup(item)).addTo(markerLayer);

            marker.on('dragend', async (e) => {
                await updateService(item.id, { lat: e.target.getLatLng().lat, lon: e.target.getLatLng().lng });
            });

            // Prepare Range Polygon
            if (showRanges) {
                let circle = turf.circle([item.lon, item.lat], item.range, {steps: 64, units: 'kilometers'});
                polys.push(circle);
            }
        });

        // UNION POLYGON
        if (showRanges && polys.length > 0) {
            let merged = polys[0];
            for (let i = 1; i < polys.length; i++) merged = turf.union(merged, polys[i]);
            L.geoJSON(merged, {
                style: { color: color, fillColor: color, fillOpacity: 0.2, weight: 1 },
                interactive: false 
            }).addTo(unionLayer);
        }
    });

    drawChart(data);
}

// --- 4. BUILDER MODE ---
function toggleBuildMode() {
    const select = document.getElementById('builderService');
    const btn = document.getElementById('toggleBuildBtn');
    const status = document.getElementById('mode-status');
    const mapContainer = document.getElementById('map');

    if (!isBuildMode) {
        // ENABLE
        if (!select.value) { alert("Please select a service type first!"); return; }
        
        isBuildMode = true;
        selectedServiceType = select.value;
        
        btn.innerText = "❌ Stop Building";
        btn.style.background = "#e74c3c";
        
        status.innerHTML = `Building: <b>${selectedServiceType.toUpperCase()}</b>`;
        status.style.color = "green";
        
        // Add custom cursor class
        L.DomUtil.addClass(mapContainer, 'crosshair-cursor-enabled');
        map.dragging.disable(); // Optional: Lock map drag to prevent accidental moves while clicking? 
        // Actually, usually better to keep drag enabled but change cursor.
        map.dragging.enable(); 

    } else {
        // DISABLE
        isBuildMode = false;
        selectedServiceType = null;
        
        btn.innerText = "Enable Build Mode";
        btn.style.background = "#2c3e50";
        status.innerText = "Status: View Only";
        status.style.color = "#666";
        
        L.DomUtil.removeClass(mapContainer, 'crosshair-cursor-enabled');
    }
}

// Map Click to Build
map.on('click', async function(e) {
    if (!isBuildMode) return;

    const name = prompt(`Name for new ${selectedServiceType}?`, "New Facility");
    if (!name) return;
    
    await fetch('/api/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: name, category: selectedServiceType,
            lat: e.latlng.lat, lon: e.latlng.lng, capacity: 50
        })
    });
    
    calculateCoverage(); // Refresh
});

// Update Dropdown Change
document.getElementById('builderService').addEventListener('change', function() {
    if (isBuildMode) {
        // Update the active type immediately if mode is already on
        selectedServiceType = this.value;
        document.getElementById('mode-status').innerHTML = `Building: <b>${selectedServiceType.toUpperCase()}</b>`;
    }
});


// --- 5. HELPERS (CRUD & Chart) ---
// (Same as previous code, just ensure they exist)
function createEditPopup(item) {
    return `
        <div class="popup-form">
            <b>${item.category.toUpperCase()}</b>
            <input type="text" id="name-${item.id}" value="${item.name}">
            <label>Capacity:</label>
            <input type="number" id="cap-${item.id}" value="${item.capacity}">
            <div class="popup-actions">
                <button onclick="saveEdit(${item.id})" class="btn-save">💾</button>
                <button onclick="deleteService(${item.id})" class="btn-del">🗑️</button>
            </div>
        </div>`;
}

window.saveEdit = async function(id) {
    const newName = document.getElementById(`name-${id}`).value;
    const newCap = document.getElementById(`cap-${id}`).value;
    await updateService(id, { name: newName, capacity: parseInt(newCap) });
};

async function updateService(id, payload) {
    await fetch(`/api/update/${id}`, {
        method: 'PUT', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    calculateCoverage();
}

window.deleteService = async function(id) {
    if(!confirm("Delete?")) return;
    await fetch(`/api/delete/${id}`, { method: 'DELETE' });
    map.closePopup();
    calculateCoverage();
};

function drawChart(data) {
    let counts = {};
    data.forEach(d => counts[d.category] = (counts[d.category]||0)+1);
    let chartData = [['Category', 'Count']];
    for (let [k,v] of Object.entries(counts)) chartData.push([k,v]);
    
    var chart = new google.visualization.PieChart(document.getElementById('chart_div'));
    chart.draw(google.visualization.arrayToDataTable(chartData), {
        pieHole: 0.4, legend: 'none', chartArea: {width: '90%', height: '90%'}
    });
}
window.exportData = function() { window.location.href = "/api/export"; }
