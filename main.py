from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, Resource, init_db
from geo_utils import fetch_amenities, calculate_coverage_score
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Smart City Allocator")

# Initialize DB on startup
init_db()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Schemas ---
class LocationRequest(BaseModel):
    lat: float
    lon: float
    radius_meters: int = 2000 # Default search radius

class CoverageResponse(BaseModel):
    latitude: float
    longitude: float
    coverage_score: float
    nearest_resources: List[dict]
    missing_amenities: List[str]

# --- Endpoints ---

@app.post("/ingest-neighborhood")
def ingest_neighborhood_data(req: LocationRequest, db: Session = Depends(get_db)):
    """
    Scans a neighborhood for critical infrastructure (Hospitals, Pharmacies, Schools)
    and saves them to Turso.
    """
    # Define what we consider "Critical Resources"
    amenities_to_fetch = {
        "amenity": ["hospital", "pharmacy", "clinic", "doctors", "school"]
    }
    
    print(f"Fetching data for {req.lat}, {req.lon}...")
    found_items = fetch_amenities(req.lat, req.lon, req.radius_meters, amenities_to_fetch)
    
    count = 0
    for item in found_items:
        # Simple deduplication check (optional but recommended)
        exists = db.query(Resource).filter(
            Resource.name == item['name'], 
            Resource.lat == item['lat']
        ).first()
        
        if not exists:
            db_res = Resource(**item)
            db.add(db_res)
            count += 1
            
    db.commit()
    return {"status": "success", "resources_added": count, "total_found": len(found_items)}


@app.get("/analyze-coverage", response_model=CoverageResponse)
def analyze_coverage(lat: float, lon: float, db: Session = Depends(get_db)):
    """
    Calculates how well-served a specific coordinate is.
    """
    # 1. Query all resources from Turso (Filtering in Python for MVP)
    # In a real app, you'd use a SQL WHERE clause for a rough bounding box first!
    all_resources = db.query(Resource).all()
    
    # 2. Filter strictly by distance (e.g., 5km) using Haversine
    nearby_resources = []
    for r in all_resources:
        dist = calculate_coverage_score(lat, lon, [r], max_dist_km=5.0)
        if dist > 0: # It's within range
            nearby_resources.append(r)

    # 3. specific checks
    hospitals = [r for r in nearby_resources if r.amenity_type == 'hospital']
    pharmacies = [r for r in nearby_resources if r.amenity_type == 'pharmacy']
    
    # 4. Calculate Scores
    hospital_score = calculate_coverage_score(lat, lon, hospitals)
    pharmacy_score = calculate_coverage_score(lat, lon, pharmacies)
    
    avg_score = (hospital_score + pharmacy_score) / 2
    
    missing = []
    if not hospitals: missing.append("Critical: No Hospital nearby")
    if not pharmacies: missing.append("Warning: No Pharmacy nearby")

    return {
        "latitude": lat,
        "longitude": lon,
        "coverage_score": avg_score,
        "nearest_resources": [{"name": r.name, "type": r.amenity_type} for r in nearby_resources[:5]],
        "missing_amenities": missing
    }
