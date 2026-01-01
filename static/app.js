// Init Map
const map = L.map('map').setView([20.5937, 78.9629], 5);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap & CartoDB'
}).addTo(map);

// Google Charts
google.charts.load('current', {'packages':['corechart']});
google.charts.setOnLoadCallback(fetchData);

// Layers
let markerLayer = L.layerGroup().addTo(map);
let unionLayer = L.layerGroup().addTo(map); // Stores the merged shapes
let projectAreaLayer = L.layerGroup().addTo(map); // Stores the boundary box

// State
let allocationMode = null;
let globalData = [];

// 1. Initial Load & Listeners
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

// 2. The Main Visualizer
function updateVisuals(data) {
    markerLayer.clearLayers();
    unionLayer.clearLayers();
    projectAreaLayer.clearLayers();
    
    if (data.length === 0) return;

    // A. Draw Project Boundary Box
    // Create a feature collection to calculate bounding box
    const points = turf.featureCollection(
        data.map(d => turf.point([d.lon, d.lat]))
    );
    const bbox = turf.bbox(points); // [minX, minY, maxX, maxY]
    const bboxPoly = turf.bboxPolygon(bbox);
    
    // Draw the bounding box (dashed line)
    L.geoJSON(bboxPoly, {
        style: { color: "#333", dashArray: "5, 5", fill: false, weight: 2 }
    }).addTo(projectAreaLayer);

    // Zoom map to fit the project area
    map.fitBounds([[bbox[1], bbox[0]], [bbox[3], bbox[2]]], {padding: [50, 50]});

    // B. Group Data by Category for Unioning
    const categories = ['hospital', 'school', 'atm', 'petrol_pump'];
    
    categories.forEach(cat => {
        const items = data.filter(d => d.category === cat);
        if (items.length === 0) return;

        let color = getColor(cat);
        let polys = [];

        // 1. Create individual markers & circles
        items.forEach(item => {
            // Marker
            L.circleMarker([item.lat, item.lon], {
                radius: 5, color: '#fff', fillColor: color, fillOpacity: 1, weight: 1
            }).bindPopup(createPopupContent(item)).addTo(markerLayer);

            // Create Circle Polygon for Turf.js (radius in km)
            let circle = turf.circle([item.lon, item.lat], item.range, {steps: 64, units: 'kilometers'});
            polys.push(circle);
        });

        // 2. UNION MAGIC (Merge overlapping circles)
        if (polys.length > 0) {
            let merged = polys[0];
            for (let i = 1; i < polys.length; i++) {
                merged = turf.union(merged, polys[i]);
            }

            // Draw the merged "Blob"
            L.geoJSON(merged, {
                style: {
                    color: color, 
                    fillColor: color, 
                    fillOpacity: 0.2, 
                    weight: 1 
                }
            }).addTo(unionLayer);
        }
    });

    drawChart(data);
}

// 3. Popup with "Update Capacity" Feature
function createPopupContent(item) {
    return `
        <div style="text-align:center">
            <b>${item.name}</b><br>
            <small>${item.category.toUpperCase()}</small><br>
            Current Cap: <b>${item.capacity}</b><br>
            Range: ${item.range} km<br>
            <hr style="margin:5px 0">
            <button onclick="updateCapacity(${item.id})" 
                style="background:#333; color:white; padding:4px; font-size:10px; width:100%">
                Edit Capacity
            </button>
        </div>
    `;
}

// 4. Update Capacity Logic
window.updateCapacity = async function(id) {
    const newCap = prompt("Enter new capacity (1-100):");
    if (!newCap) return;
    
    await fetch(`/api/update/${id}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ capacity: parseInt(newCap) })
    });
    fetchData(); // Refresh map
};

// 5. Add Service Logic (Map Click)
map.on('click', async function(e) {
    if (!allocationMode) return;

    const name = prompt(`Name for new ${allocationMode}?`, "New Facility");
    if (!name) return;
    
    const cap = prompt("Capacity (1-100)?", "50");

    await fetch('/api/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: name,
            category: allocationMode,
            lat: e.latlng.lat,
            lon: e.latlng.lng,
            capacity: parseInt(cap) || 50
        })
    });

    fetchData();
    setMode(null); // Reset mode
});

function setMode(mode) {
    allocationMode = mode;
    const status = document.getElementById('mode-status');
    if (mode) {
        status.innerHTML = `Build Mode: <b>${mode.toUpperCase()}</b> (Click map)`;
        status.style.color = "green";
        document.body.style.cursor = "crosshair";
    } else {
        status.innerHTML = "Status: View Only";
        status.style.color = "#666";
        document.body.style.cursor = "default";
    }
}

// 6. Export Logic
window.exportData = function() {
    window.location.href = "/api/export";
}

// Helpers
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
        legend: {position: 'bottom'}, chartArea: {width: '100%', height: '80%'}
    });
}
