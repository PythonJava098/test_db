// Init Map
const map = L.map('map').setView([20.5937, 78.9629], 5);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap'
}).addTo(map);

google.charts.load('current', {'packages':['corechart']});
google.charts.setOnLoadCallback(() => calculateCoverage());

// Layers
let markerLayer = L.layerGroup().addTo(map);
let unionLayer = L.layerGroup().addTo(map);

// BOUNDARY LAYERS
// We use a FeatureGroup for the boundary because Leaflet.Draw needs it to be editable
let boundaryLayer = new L.FeatureGroup().addTo(map);
let drawControl = null; // Will hold the edit toolbar

let isBuildMode = false;
let selectedServiceType = null;
let currentBoundaryItem = null; // Stores the DB object of the saved boundary

// --- 1. FETCH & DRAW ---
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
    boundaryLayer.clearLayers();
    
    // Filter data
    const services = data.filter(d => d.category !== 'project_boundary');
    const boundary = data.find(d => d.category === 'project_boundary');
    currentBoundaryItem = boundary; // Save for later reference

    // 1. DRAW BOUNDARY
    if (boundary && boundary.shape_data) {
        // A. Use Saved Boundary
        const coords = boundary.shape_data; // JSON coords from DB
        const poly = L.polygon(coords, {
            color: "#333", dashArray: "10, 10", fill: false, weight: 2, className: 'project-border'
        });
        boundaryLayer.addLayer(poly);
        map.fitBounds(poly.getBounds(), {padding:[20,20]});
    } 
    else if (services.length > 0) {
        // B. Auto-Calculate Boundary from Points
        const points = turf.featureCollection(services.map(d => turf.point([d.lon, d.lat])));
        const bbox = turf.bbox(points); // [minX, minY, maxX, maxY]
        const bboxPoly = turf.bboxPolygon(bbox);
        
        // Convert Turf GeoJSON to Leaflet Layer
        const leafletPoly = L.geoJSON(bboxPoly, {
            style: { color: "#333", dashArray: "5, 5", fill: false, weight: 2, className: 'project-border' }
        });
        
        // We extract the shape so it can be added to the FeatureGroup for editing
        leafletPoly.eachLayer(layer => {
            boundaryLayer.addLayer(layer);
        });
        map.fitBounds(leafletPoly.getBounds(), {padding:[50,50]});
    }

    if (services.length === 0) return;

    // 2. DRAW SERVICES
    const categories = [...new Set(services.map(d => d.category))];
    categories.forEach(cat => {
        const items = services.filter(d => d.category === cat);
        const color = getColor(cat);
        let rangePolys = [];

        items.forEach(item => {
            // Marker
            const icon = L.divIcon({
                className: 'custom-pin',
                html: `<div style="background-color:${color}; width:12px; height:12px; border-radius:50%; border:2px solid white; box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>`
            });
            
            L.marker([item.lat, item.lon], { icon: icon, draggable: true })
                .bindPopup(createEditPopup(item))
                .on('dragend', (e) => updateService(item.id, {lat: e.target.getLatLng().lat, lon: e.target.getLatLng().lng}))
                .addTo(markerLayer);

            // Range
            if (showRanges) {
                rangePolys.push(turf.circle([item.lon, item.lat], item.range, {steps:32, units:'kilometers'}));
            }
        });

        // Union
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

// --- 2. BOUNDARY EDITING (LEAFLET DRAW) ---
function enableBoundaryEdit() {
    // 1. Toggle Buttons
    document.getElementById('btn-edit-boundary').style.display = 'none';
    document.getElementById('btn-save-boundary').style.display = 'flex';
    
    // 2. Change Boundary Style to indicate "Editable"
    boundaryLayer.eachLayer(layer => {
        layer.setStyle({ color: '#ef4444', dashArray: null, weight: 3 }); // Red solid line
        if (layer.editing) layer.editing.enable(); // Enable Dragging handles
    });
    
    // If no boundary exists yet, allow drawing a new rectangle
    if (boundaryLayer.getLayers().length === 0) {
        new L.Draw.Rectangle(map).enable();
        map.on(L.Draw.Event.CREATED, function (e) {
            boundaryLayer.addLayer(e.layer);
        });
    }
}

async function saveBoundary() {
    // 1. Get the shape
    if (boundaryLayer.getLayers().length === 0) return;
    const layer = boundaryLayer.getLayers()[0];
    
    // 2. Get Coords (Lat, Lon format)
    // Leaflet Polygon/Rectangle uses getLatLngs()
    let coords = layer.getLatLngs()[0]; // [[lat,lon], [lat,lon]...]
    
    // Convert to simple array format for JSON
    const jsonCoords = coords.map(p => [p.lat, p.lng]);
    
    // 3. API Call
    // If we already have a boundary item, update it. Else create new.
    const url = currentBoundaryItem ? `/api/update/${currentBoundaryItem.id}` : '/api/add';
    const method = currentBoundaryItem ? 'PUT' : 'POST';
    
    const payload = {
        name: "Project Boundary",
        category: "project_boundary",
        geom_type: "polygon",
        shape_data: jsonCoords // Helper func in backend handles this
    };
    
    // Special handling: PUT expects different structure than POST in our simplified backend? 
    // Let's standardise on the /api/boundary route in backend or just use Add/Update logic here.
    // For simplicity, we'll use a specific logic: Delete old boundary, Add new one.
    
    if (currentBoundaryItem) {
        await fetch(`/api/delete/${currentBoundaryItem.id}`, {method:'DELETE'});
    }
    
    await fetch('/api/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: "Project Boundary",
            category: "project_boundary",
            geom_type: "polygon",
            coordinates: jsonCoords // Note: Backend 'add' expects 'coordinates' key for polygons
        })
    });
    
    // 4. UI Reset
    document.getElementById('btn-edit-boundary').style.display = 'flex';
    document.getElementById('btn-save-boundary').style.display = 'none';
    calculateCoverage(); // Refresh to turn it back to dashed black line
}

async function resetBoundary() {
    if(confirm("Reset boundary to auto-calculated?")) {
        if (currentBoundaryItem) {
            await fetch(`/api/delete/${currentBoundaryItem.id}`, {method:'DELETE'});
        }
        calculateCoverage();
    }
}


// --- 3. BUILDER MODE (Standard Points) ---
function toggleBuildMode() {
    const select = document.getElementById('builderService');
    const btn = document.getElementById('toggleBuildBtn');
    
    if (!isBuildMode) {
        if (!select.value) { alert("Select Service Type"); return; }
        isBuildMode = true;
        selectedServiceType = select.value;
        btn.innerText = "❌ Stop Building";
        btn.style.background = "#ef4444";
        document.getElementById('mode-status').innerHTML = `Placing: <b>${selectedServiceType}</b>`;
        L.DomUtil.addClass(map.getContainer(), 'crosshair-cursor-enabled');
    } else {
        isBuildMode = false;
        selectedServiceType = null;
        btn.innerText = "📍 Enable Build Mode";
        btn.style.background = "#111827";
        document.getElementById('mode-status').innerText = "Status: View Only";
        L.DomUtil.removeClass(map.getContainer(), 'crosshair-cursor-enabled');
    }
}

map.on('click', async function(e) {
    if (!isBuildMode) return;
    const name = prompt(`Name for new ${selectedServiceType}?`, "New Facility");
    if (!name) return;
    
    await fetch('/api/add', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: name, category: selectedServiceType, geom_type: 'point',
            lat: e.latlng.lat, lon: e.latlng.lng, capacity: 50
        })
    });
    calculateCoverage();
});

// --- HELPERS ---
function getColor(cat) {
    const colors = {'hospital':'#e74c3c', 'school':'#f1c40f', 'atm':'#3498db', 'bank':'#9b59b6', 'park':'#27ae60'};
    return colors[cat] || '#95a5a6';
}

function createEditPopup(item) {
    return `<div style="text-align:center"><b>${item.name}</b><br>${item.category}
    <br><button onclick="deleteService(${item.id})" style="background:#ef4444;color:white;border:none;padding:5px;margin-top:5px;border-radius:4px;">Delete</button></div>`;
}

window.deleteService = async function(id) {
    if(confirm("Delete?")) { await fetch(`/api/delete/${id}`, {method:'DELETE'}); calculateCoverage(); }
}

// Sliders and Charts
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
