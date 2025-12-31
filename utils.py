import osmnx as ox
from haversine import haversine, Unit
from sqlalchemy.orm import Session
from models import UrbanResource

def fetch_and_seed_data(city_name: str, resource_type: str, db: Session):
    """
    Fetches POIs (Points of Interest) from OpenStreetMap via OSMnx
    and saves them to Turso.
    """
    print(f"Fetching {resource_type} data for {city_name}...")
    
    # Map common terms to OSM tags
    tags = {}
    if resource_type == "hospital":
        tags = {"amenity": "hospital"}
    elif resource_type == "atm":
        tags = {"amenity": "atm"}
    elif resource_type == "school":
        tags = {"amenity": "school"}
    else:
        tags = {"amenity": resource_type}

    # Fetch geometries
    try:
        gdf = ox.features_from_place(city_name, tags=tags)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return 0

    count = 0
    for _, row in gdf.iterrows():
        # Handle Points vs Polygons (use centroid for polygons)
        if row.geometry.geom_type == 'Point':
            lat = row.geometry.y
            lon = row.geometry.x
        else:
            lat = row.geometry.centroid.y
            lon = row.geometry.centroid.x
        
        # Simple name extraction
        name = row.get('name', 'Unknown')
        if not isinstance(name, str): name = "Unknown"

        # Check duplication (naive check by name + lat)
        exists = db.query(UrbanResource).filter(
            UrbanResource.name == name, 
            UrbanResource.latitude == lat
        ).first()

        if not exists:
            resource = UrbanResource(
                name=name,
                category=resource_type,
                latitude=lat,
                longitude=lon,
                address=str(row.get('addr:street', ''))
            )
            db.add(resource)
            count += 1
    
    db.commit()
    return count

def find_nearby(lat: float, lon: float, radius_km: float, db: Session):
    """
    Finds resources within a specific radius using Haversine formula.
    Note: Doing this in Python because basic SQLite lacks efficient spatial index.
    For massive datasets, this logic should move to PostGIS.
    """
    resources = db.query(UrbanResource).all()
    nearby_resources = []

    user_location = (lat, lon)

    for r in resources:
        resource_location = (r.latitude, r.longitude)
        distance = haversine(user_location, resource_location, unit=Unit.KILOMETERS)
        
        if distance <= radius_km:
            nearby_resources.append({
                "name": r.name,
                "category": r.category,
                "distance_km": round(distance, 2),
                "location": {"lat": r.latitude, "lon": r.longitude}
            })
            
    # Sort by distance
    nearby_resources.sort(key=lambda x: x['distance_km'])
    return nearby_resources
