from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import engine, Base, get_db
from models import UrbanResource
from utils import fetch_and_seed_data, find_nearby

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart City Resource Allocator",
    description="Analyze urban resource coverage (Hospitals, ATMs, etc.)"
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Smart City API. Use /docs for documentation."}

@app.post("/seed-city/{city_name}")
def seed_city_data(
    city_name: str, 
    resource_type: str = Query(..., description="e.g., hospital, atm, school"),
    db: Session = Depends(get_db)
):
    """
    Ingests data from OpenStreetMap for a specific city and resource type.
    Example: city_name="Mumbai, India", resource_type="hospital"
    """
    try:
        count = fetch_and_seed_data(city_name, resource_type, db)
        return {"status": "success", "message": f"Added {count} {resource_type}s for {city_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/resources/")
def get_all_resources(db: Session = Depends(get_db)):
    """Return all stored resources."""
    return db.query(UrbanResource).all()

@app.get("/analyze/coverage")
def analyze_coverage(
    lat: float, 
    lon: float, 
    radius_km: float = 5.0, 
    db: Session = Depends(get_db)
):
    """
    Check if a specific location is within range of essential services.
    radius_km: Distance to check (default 5km)
    """
    nearby = find_nearby(lat, lon, radius_km, db)
    
    status = "Good Coverage" if nearby else "Resource Desert"
    
    return {
        "user_location": {"lat": lat, "lon": lon},
        "search_radius_km": radius_km,
        "status": status,
        "nearby_count": len(nearby),
        "nearest_resources": nearby
    }
