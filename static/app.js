// Init Map
const map = L.map('map').setView([19.0760, 72.8777], 11); // Default Mumbai
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

// Google Charts Init
google.charts.load('current', {'packages':['corechart']});
google.charts.setOnLoadCallback(drawChart);

// State
let allocationMode = null; // 'hospital', 'atm', etc.
let resources = [];

// 1. Load Resources
async function loadResources() {
    const res = await fetch('/api/resources');
    resources = await res.json();
    
    // Clear Map
    map.eachLayer((layer) => {
        if (!!layer.toGeoJSON) map.removeLayer(layer);
    });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

    // Plot Markers
    resources.forEach(r => {
        let color = r.category === 'hospital' ? 'red' : 'blue';
        L.circleMarker([r.latitude, r.longitude], {
            radius: 6, fillColor: color, color: '#fff', weight: 1, opacity: 1, fillOpacity: 0.8
        }).addTo(map).bindPopup(`<b>${r.name}</b><br>Cap: ${r.capacity}`);
    });

    drawChart(); // Update charts
}

// 2. Map Click Handler (Analysis OR Allocation)
map.on('click', async function(e) {
    const lat = e.latlng.lat;
    const lon = e.latlng.lng;

    // A. Allocation Logic
    if (allocationMode) {
        const name = prompt(`Name for new ${allocationMode}?`, "New Facility");
        if (!name) return;

        await fetch('/api/allocate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: name,
                category: allocationMode,
                lat: lat, lon: lon,
                capacity: 75 // Default high capacity for new builds
            })
        });
        loadResources(); // Refresh map
        setMode(null); // Reset mode
        return;
    }

    // B. Analysis Logic
    const density = document.getElementById('densitySlider').value;
    const res = await fetch(`/api/analyze?lat=${lat}&lon=${lon}&density=${density}`);
    const data = await res.json();

    document.getElementById('analysisPanel').style.display = 'block';
    
    let html = `<p><b>Density:</b> ${density} ppl/km²</p>`;
    if (data.is_desert) {
        html += `<p class="danger">⚠️ SERVICE DESERT</p>`;
        html += `<small>No services cover this area effectively at this density.</small>`;
    } else {
        html += `<p class="safe">✅ Covered By: ${data.covered_services.join(', ')}</p>`;
    }

    html += `<hr><b>Nearest:</b><br>`;
    data.nearby_analysis.forEach(n => {
        html += `<small>${n.name} (${n.distance}km) - Range: ${n.max_range}km</small><br>`;
    });

    document.getElementById('analysisContent').innerHTML = html;
});

// 3. Helper Functions
function updateDensityDisplay() {
    document.getElementById('densityValue').innerText = document.getElementById('densitySlider').value;
}

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
    alert("Fetching data... this may take 20 seconds.");
    await fetch(`/api/seed?city=${city}&type=${type}`, { method: 'POST' });
    loadResources();
    alert("Data Imported!");
}

// 4. Google Charts
function drawChart() {
    if(resources.length === 0) return;

    // Aggregate Data
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
