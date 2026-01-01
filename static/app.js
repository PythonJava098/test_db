// Init Map
const map = L.map('map').setView([20.5937, 78.9629], 5); // Default View: India
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap & CartoDB'
}).addTo(map);

// Google Charts
google.charts.load('current', {'packages':['corechart']});
google.charts.setOnLoadCallback(fetchData);

let layerGroup = L.layerGroup().addTo(map);

// Slider Listener
document.getElementById('densitySlider').addEventListener('input', function(e) {
    document.getElementById('densityVal').innerText = e.target.value;
    fetchData(); // Refresh data on slider move
});

async function fetchData() {
    const density = document.getElementById('densitySlider').value;
    
    try {
        const res = await fetch(`/api/resources?density=${density}`);
        const data = await res.json();
        updateVisuals(data);
    } catch (err) {
        console.error(err);
    }
}

function updateVisuals(data) {
    layerGroup.clearLayers();
    
    if (data.length === 0) return;

    // 1. Draw Map Items
    data.forEach(item => {
        let color = '#3498db'; // Default Blue
        if (item.category === 'hospital') color = '#e74c3c'; // Red
        if (item.category === 'school') color = '#f1c40f';   // Yellow
        if (item.category === 'petrol_pump') color = '#2ecc71'; // Green

        // Center Point
        L.circleMarker([item.lat, item.lon], {
            radius: 4, color: '#fff', fillColor: color, fillOpacity: 1, weight: 1
        }).bindPopup(`<b>${item.name}</b><br>${item.category}`).addTo(layerGroup);

        // Range Circle
        L.circle([item.lat, item.lon], {
            radius: item.range * 1000, // km to meters
            color: color, fillColor: color, fillOpacity: 0.1, weight: 1
        }).addTo(layerGroup);
    });

    // 2. Draw Chart
    let counts = {};
    data.forEach(d => counts[d.category] = (counts[d.category]||0)+1);
    
    let chartData = [['Category', 'Count']];
    for (let [k,v] of Object.entries(counts)) chartData.push([k,v]);

    let chart = new google.visualization.PieChart(document.getElementById('chart_div'));
    chart.draw(google.visualization.arrayToDataTable(chartData), {
        pieHole: 0.4,
        colors: ['#e74c3c', '#f1c40f', '#3498db', '#2ecc71'],
        legend: {position: 'bottom'},
        chartArea: {width: '100%', height: '80%'}
    });
}
