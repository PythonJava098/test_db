import osmnx as ox
from haversine import haversine, Unit

def fetch_amenities(lat: float, lon: float, radius: int, tags: dict):
    """
    Uses OSMnx to find amenities within a radius (meters).
    Returns a list of dicts: [{'name': '...', 'lat': ..., 'lon': ...}, ...]
    """
    try:
        # Fetch geometries from OSM
        gdf = ox.features.features_from_point(
            (lat, lon), 
            tags=tags, 
            dist=radius
        )
        
        results = []
        if gdf.empty:
            return results

        # Process the GeoDataFrame
        for _, row in gdf.iterrows():
            # Handle naming (OSM data can be messy)
            name = row.get('name', 'Unknown')
            amenity = row.get('amenity', 'unknown')
            
            # Get centroid for lat/lon (buildings are polygons, we need points)
            centroid = row.geometry.centroid
            
            results.append({
                "name": name,
                "amenity_type": amenity,
                "lat": centroid.y,
                "lon": centroid.x
            })
        return results
    except Exception as e:
        print(f"Error fetching OSM data: {e}")
        return []

def calculate_coverage_score(user_lat, user_lon, resources, max_dist_km=2.0):
    """
    Calculates a simple 'Coverage Score' (0-100) based on proximity.
    """
    if not resources:
        return 0
    
    # Find distance to closest resource
    distances = [haversine((user_lat, user_lon), (r.lat, r.lon), unit=Unit.KILOMETERS) for r in resources]
    closest_dist = min(distances)
    
    if closest_dist > max_dist_km:
        return 0
    
    # Linear decay: Score 100 at 0km, Score 0 at max_dist_km
    score = max(0, 100 * (1 - (closest_dist / max_dist_km)))
    return round(score, 1)
