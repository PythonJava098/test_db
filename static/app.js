// Init Map
const map = L.map('map').setView([19.0760, 72.8777], 12); 
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
}).addTo(map);

// Google Charts Init
google.charts.load('current', {'packages':['corechart']});
google.charts.setOnLoadCallback(drawChart);

// State
let allocationMode = null;
let resources = [];
let resourceLayerGroup = L.layerGroup().addTo(map); // Layer to hold markers/circles

// 1. Load Resources (Triggered by slider or page load)
async function loadResources() {
    const density = document.getElementById('densitySlider').value;
    
    // Fetch data with the current density to get correct ranges
    const res = await fetch(`/api/resources?density=${density}`);
    resources = await res.json();
    
    renderMapObjects();
    drawChart(); 
}

// 2. Render Markers and Range Circles
function renderMapObjects() {
    resourceLayerGroup.clearLayers(); // Remove old circles/markers

    resources.forEach(r => {
        let color = 'blue';
        if (r.category === 'hospital') color = 'red';
        if (r.category === 'petrol_pump') color = 'orange';
        if (r.category === 'atm') color = 'green';

        // A. Draw the Center Point
        const marker = L.circleMarker([r.latitude, r.longitude], {
            radius: 5, fillColor: color, color: '#fff', weight: 1, opacity: 1, fillOpacity: 1
        }).bindPopup(`
            <b>${r.name}</b><br>
            Type: ${r.category}<br>
            Capacity: ${r.capacity}<br>
            Range: ${r.effective_range_km} km
        `);

        // B. Draw the Range Circle (The visual coverage area)
        const rangeCircle = L.circle([r.latitude, r.longitude], {
            radius: r.effective_range_km * 1000, // Convert km to meters for Leaflet
            color: color,
            fillColor: color,
            fillOpacity: 0.1, // Very transparent
            weight: 1 // Thin border
        });

        resourceLayerGroup.addLayer(marker);
        resourceLayerGroup.addLayer(rangeCircle);
    });
}

// 3. Map Click Handler (Analysis OR Allocation)
map.on('click', async function(e) {
    const lat = e.latlng.lat;
    const lon = e.latlng.lng;

    // A. Allocation Mode
    if (allocationMode) {
        const name = prompt(`Name for new ${allocationMode}?`, "New Facility");
        if (!name) return;

        // NEW: Ask for capacity
        const capacityStr = prompt(`Enter Capacity (1-100) for ${name}:`, "75");
        const capacity = parseInt(capacityStr) || 50; // Default to 50 if invalid

        await fetch('/api/allocate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: name,
                category: allocationMode,
                lat: lat, lon: lon,
                capacity: capacity 
            })
        });
        
        loadResources(); // Refresh map to show new item
        setMode(null); // Exit build mode
        return;
    }

    // B. Analysis Mode (Clicking to check a specific house/location)
    const density = document.getElementById('densitySlider').value;
    const res = await fetch(`/api/analyze?lat=${lat}&lon=${lon}&density=${density}`);
    const data = await res.json();

    document.getElementById('analysisPanel').style.display = 'block';
    
    let html = `<p><b>Density:</b> ${density} ppl/km²</p>`;
    
    if (data.is_desert) {
        html += `<p class="danger" style="color:red; font-weight:bold;">⚠️ SERVICE DESERT</p>`;
        html += `<small>You are outside the effective range of all services.</small>`;
    } else {
        html += `<p class="safe" style="color:green; font-weight:bold;">✅ COVERED</p>`;
        html += `Services: ${data.covered_services.join(', ')}`;
    }

    html += `<hr><b>Nearest Facilities:</b><br>`;
    data.nearby_analysis.forEach(n => {
        // Add checkmark if this specific facility covers the user
        const icon = n.in_coverage ? "✅" : "❌";
        html += `<small>${icon} <b>${n.name}</b> (${n.distance}km)</small><br>`;
    });

    document.getElementById('analysisContent').innerHTML = html;
});

// 4. Density Slider Listener
// When user drags slider, we immediately fetch new ranges and redraw circles
document.getElementById('densitySlider').addEventListener('input', function() {
    document.getElementById('densityValue').innerText = this.value;
    loadResources(); // This triggers the re-draw of circles
});

// Helper Functions
function setMode(mode) {
    allocationMode = mode;
    document.getElementById('modeStatus').innerText = mode ? `Mode: Build ${mode.toUpperCase()}` : "Mode: View Only";
}

function closePanel() {
    document.getElementById('analysisPanel').style.display = 'none';
}

async function seedData() {
    const city = document.getElementById('cityName').value;
    const type = document.getElementById('resourceType').value;
    alert("Fetching data... please wait.");
    await fetch(`/api/seed?city=${city}&type=${type}`, { method: 'POST' });
    loadResources();
    alert("Data Imported!");
}

function drawChart() {
    if(resources.length === 0) return;
    let counts = {};
    resources.forEach(r => { counts[r.category] = (counts[r.category] || 0) + 1; });
    let chartData = [['Category', 'Count']];
    for (const [key, value] of Object.entries(counts)) {
        chartData.push([key, value]);
    }
    var data = google.visualization.arrayToDataTable(chartData);
    var options = { title: 'Resource Distribution', pieHole: 0.4, legend: 'bottom' };
    var chart = new google.visualization.PieChart(document.getElementById('chart_div'));
    chart.draw(data, options);
}

// Initial Load
loadResources();
