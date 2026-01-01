import osmnx as ox
from haversine import haversine, Unit
from sqlalchemy.orm import Session
from models import UrbanResource
import math

# Base ranges in km (Assuming standard density)
BASE_RANGES = {
    "hospital": 5.0,
    "atm": 1.0,
    "bank": 2.0,
    "petrol_pump": 3.0
}

STANDARD_DENSITY = 1000  # people per sq km (Reference baseline)
STANDARD_CAPACITY = 50   # Baseline capacity

def calculate_dynamic_range(category: str, capacity: int, density: int) -> float:
    """
    Calculates service range based on population density and facility capacity.
    - Higher Density -> Lower Range (Service gets crowded)
    - Higher Capacity -> Higher Range
    """
    base = BASE_RANGES.get(category, 2.0)
    
    # Avoid division by zero
    density = max(density, 100)
    
    # Logic: Range increases with capacity, decreases with sqrt of density ratio
    density_factor = math.sqrt(STANDARD_DENSITY / density)
    capacity_factor = capacity / STANDARD_CAPACITY
    
    return round(base * density_factor * capacity_factor, 2)

def fetch_osm_data(city: str, resource_type: str, db: Session):
    """Fetch real data from OpenStreetMap"""
    tags = {"amenity": resource_type}
    try:
        gdf = ox.features_from_place(city, tags=tags)
    except Exception:
        return 0

    count = 0
    for _, row in gdf.iterrows():
        # Get centroid if polygon
        geo = row.geometry
        lat = geo.y if geo.geom_type == 'Point' else geo.centroid.y
        lon = geo.x if geo.geom_type == 'Point' else geo.centroid.x
        
        name = str(row.get('name', 'Unknown'))
        
        # Naive duplication check
        exists = db.query(UrbanResource).filter_by(name=name, latitude=lat).first()
        if not exists:
            # Assign random capacity for existing real-world items (simulation)
            cap = 50 
            if resource_type == 'hospital': cap = 80
            
            res = UrbanResource(
                name=name, category=resource_type, 
                latitude=lat, longitude=lon, capacity=cap,
                address=str(row.get('addr:street', ''))
            )
            db.add(res)
            count += 1
    db.commit()
    return count
