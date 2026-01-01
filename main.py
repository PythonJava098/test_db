from fastapi import FastAPI, Request, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import engine, Base, get_db
from models import UrbanResource
from utils import fetch_osm_data, calculate_dynamic_range, haversine, Unit

# Init DB
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart City Allocator")

# Mount Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# --- DATA ENDPOINTS ---

@app.get("/api/resources")
def get_resources(density: int = 1000, db: Session = Depends(get_db)):
    """
    Returns resources with their calculated effective range 
    based on the provided population density.
    """
    resources = db.query(UrbanResource).all()
    
    response_data = []
    for r in resources:
        # Calculate how far this specific facility reaches
        eff_range = calculate_dynamic_range(r.category, r.capacity, density)
        
        response_data.append({
            "id": r.id,
            "name": r.name,
            "category": r.category,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "capacity": r.capacity,
            "effective_range_km": eff_range # <--- Sending this to frontend
        })
        
    return response_data

@app.post("/api/seed")
def seed_data(city: str, type: str, db: Session = Depends(get_db)):
    count = fetch_osm_data(city, type, db)
    return {"message": f"Imported {count} {type}s"}

@app.post("/api/allocate")
def allocate_resource(
    resource: dict, # Expected: {name, category, lat, lon, capacity}
    db: Session = Depends(get_db)
):
    new_res = UrbanResource(
        name=resource['name'],
        category=resource['category'],
        latitude=resource['lat'],
        longitude=resource['lon'],
        capacity=resource['capacity']
    )
    db.add(new_res)
    db.commit()
    return {"message": "Resource Allocated Successfully", "id": new_res.id}

@app.get("/api/analyze")
def analyze_coverage(
    lat: float, lon: float, 
    density: int = 1000, 
    db: Session = Depends(get_db)
):
    """
    Finds nearest services and calculates if the user is in their valid range
    considering the population density.
    """
    resources = db.query(UrbanResource).all()
    results = []
    
    for r in resources:
        dist = haversine((lat, lon), (r.latitude, r.longitude), unit=Unit.KILOMETERS)
        
        # Dynamic Range Calculation
        max_range = calculate_dynamic_range(r.category, r.capacity, density)
        
        in_range = dist <= max_range
        
        if dist < 10.0: # Only return relevant nearby items
            results.append({
                "name": r.name,
                "category": r.category,
                "distance": round(dist, 2),
                "max_range": max_range,
                "in_coverage": in_range
            })
            
    # Sort by distance
    results.sort(key=lambda x: x['distance'])
    
    # Coverage Status logic
    covered_by = [x['category'] for x in results if x['in_coverage']]
    is_desert = len(covered_by) == 0
    
    return {
        "is_desert": is_desert,
        "covered_services": list(set(covered_by)),
        "nearby_analysis": results[:5] # Top 5 nearest
    }
