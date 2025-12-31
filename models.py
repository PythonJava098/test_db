from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import osmnx as ox
import models, database, utils
from pydantic import BaseModel

app = FastAPI(title="Smart City Resource Allocator")

# Create tables
models.Base.metadata.create_all(bind=database.engine)

# --- Pydantic Models ---
class LocationCheck(BaseModel):
    lat: float
    lon: float
    resource_type: str = "hospital"
    threshold_km: float = 5.0

# --- API Endpoints ---

@app.post("/ingest/{city_name}")
def ingest_data(city_name: str, resource: str = "hospital", db: Session = Depends(database.get_db)):
    """
    Fetches live data from OpenStreetMap and saves to Turso.
    Example resource: 'hospital', 'school', 'bank'
    """
    try:
        # 1. Use OSMnx to get data (Points of Interest)
        tags = {"amenity": resource}
        gdf = ox.features_from_place(city_name, tags=tags)
        
        # 2. Parse and save to DB
        count = 0
        for _, row in gdf.iterrows():
            # Handle geometry (Points vs Polygons)
            if row.geometry.geom_type == 'Point':
                lat, lon = row.geometry.y, row.geometry.x
            else:
                # Use centroid for buildings/polygons
                lat, lon = row.geometry.centroid.y, row.geometry.centroid.x
                
            name = row.get("name", "Unknown")
            
            # Simple check to avoid duplicates could go here
            new_resource = models.Resource(
                name=str(name),
                category=resource,
                lat=lat,
                lon=lon
            )
            db.add(new_resource)
            count += 1
            
        db.commit()
        return {"status": "success", "ingested_count": count, "city": city_name}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/desert")
def check_service_coverage(check: LocationCheck, db: Session = Depends(database.get_db)):
    """
    Determines if the provided location is in a 'Service Desert'
    based on the threshold distance.
    """
    # 1. Fetch all resources of the requested type
    # Optimization: In a real app, use a bounding box query here first to reduce list size
    resources = db.query(models.Resource).filter(models.Resource.category == check.resource_type).all()
    
    if not resources:
        return {"status": "error", "message": f"No data found for {check.resource_type}. Run /ingest first."}

    # 2. Find nearest resource using Haversine
    min_dist = float("inf")
    nearest_resource = None

    for res in resources:
        dist = utils.haversine(check.lat, check.lon, res.lat, res.lon)
        if dist < min_dist:
            min_dist = dist
            nearest_resource = res.name

    # 3. Determine status
    is_desert = min_dist > check.threshold_km
    
    return {
        "analysis": "Service Desert" if is_desert else "Well Covered",
        "nearest_resource": nearest_resource,
        "distance_km": round(min_dist, 2),
        "threshold_km": check.threshold_km,
        "is_desert": is_desert
    }

@app.get("/")
def home():
    return {"msg": "Smart City API is running. Go to /docs to test."}
