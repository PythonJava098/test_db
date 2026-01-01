import os
import shutil
import json
from fastapi import FastAPI, Request, Depends, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from database import engine, Base, get_db
from models import UrbanResource
from utils import process_shapefile, calculate_dynamic_range

# Init DB
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart City Allocator")

# Mounts
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
os.makedirs("uploads", exist_ok=True)

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/upload")
async def upload_file(
    category: str = Form(...), 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    process_shapefile(file_location, category, db)
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/api/resources")
def get_resources(density: int = 1000, db: Session = Depends(get_db)):
    resources = db.query(UrbanResource).all()
    data = []
    for r in resources:
        rng = calculate_dynamic_range(r.category, r.capacity, density)
        data.append({
            "id": r.id,
            "name": r.name,
            "category": r.category,
            "lat": r.latitude,
            "lon": r.longitude,
            "capacity": r.capacity,
            "range": rng
        })
    return data

# --- NEW FEATURE 1: ADD SERVICE ---
@app.post("/api/add")
def add_service(
    data: dict, 
    db: Session = Depends(get_db)
):
    """Adds a new service point manually."""
    new_res = UrbanResource(
        name=data.get("name", "New Service"),
        category=data["category"],
        latitude=data["lat"],
        longitude=data["lon"],
        capacity=data.get("capacity", 50)
    )
    db.add(new_res)
    db.commit()
    return {"message": "Service added successfully"}

# --- UPDATE SERVICE (Expanded for Name, Lat, Lon, Capacity) ---
@app.put("/api/update/{resource_id}")
def update_service(
    resource_id: int, 
    data: dict, 
    db: Session = Depends(get_db)
):
    """Updates Name, Capacity, and Location."""
    resource = db.query(UrbanResource).filter(UrbanResource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    # Update fields if provided
    if "name" in data: resource.name = data["name"]
    if "capacity" in data: resource.capacity = data["capacity"]
    if "lat" in data: resource.latitude = data["lat"]
    if "lon" in data: resource.longitude = data["lon"]
    
    db.commit()
    return {"message": "Service updated successfully"}

# --- DELETE SERVICE (New) ---
@app.delete("/api/delete/{resource_id}")
def delete_service(
    resource_id: int, 
    db: Session = Depends(get_db)
):
    """Deletes a service permanently."""
    resource = db.query(UrbanResource).filter(UrbanResource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    db.delete(resource)
    db.commit()
    return {"message": "Service deleted"}

# --- NEW FEATURE 3: EXPORT DATA ---
@app.get("/api/export")
def export_data(db: Session = Depends(get_db)):
    """Generates a GeoJSON file of current data."""
    resources = db.query(UrbanResource).all()
    
    features = []
    for r in resources:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [r.longitude, r.latitude]
            },
            "properties": {
                "name": r.name,
                "category": r.category,
                "capacity": r.capacity
            }
        })
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    file_path = "uploads/smart_city_export.geojson"
    with open(file_path, "w") as f:
        json.dump(geojson, f)
        
    return FileResponse(file_path, filename="smart_city_plan.geojson")
