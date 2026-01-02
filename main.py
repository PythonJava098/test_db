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

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart City Allocator")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
os.makedirs("uploads", exist_ok=True)

# ... (Home & Dashboard routes same as before) ...
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/upload")
async def upload_file(category: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb+") as f: shutil.copyfileobj(file.file, f)
    process_shapefile(file_location, category, db)
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/api/resources")
def get_resources(density: int = 1000, db: Session = Depends(get_db)):
    resources = db.query(UrbanResource).all()
    data = []
    for r in resources:
        rng = 0
        if r.geom_type == 'point':
            rng = calculate_dynamic_range(r.category, r.capacity, density)
        
        data.append({
            "id": r.id,
            "name": r.name,
            "category": r.category,
            "geom_type": r.geom_type,
            "lat": r.latitude,
            "lon": r.longitude,
            "shape_data": json.loads(r.shape_data) if r.shape_data else None,
            "capacity": r.capacity,
            "range": rng
        })
    return data

@app.post("/api/add")
def add_service(data: dict, db: Session = Depends(get_db)):
    """Handles adding Points OR Polygons manually"""
    if data.get("geom_type") == "polygon":
        new_res = UrbanResource(
            name=data.get("name"), category=data["category"], 
            geom_type="polygon", shape_data=json.dumps(data["coordinates"]),
            capacity=data.get("capacity", 50)
        )
    else:
        new_res = UrbanResource(
            name=data.get("name"), category=data["category"], 
            geom_type="point", latitude=data["lat"], longitude=data["lon"],
            capacity=data.get("capacity", 50)
        )
    db.add(new_res)
    db.commit()
    return {"message": "Added"}

# ... (Update/Delete/Export routes same as previous, just ensure they exist) ...
@app.put("/api/update/{resource_id}")
def update_service(resource_id: int, data: dict, db: Session = Depends(get_db)):
    resource = db.query(UrbanResource).filter(UrbanResource.id == resource_id).first()
    if not resource: raise HTTPException(status_code=404)
    if "name" in data: resource.name = data["name"]
    if "capacity" in data: resource.capacity = data["capacity"]
    if "lat" in data: resource.latitude = data["lat"]
    if "lon" in data: resource.longitude = data["lon"]
    db.commit()
    return {"message": "Updated"}

@app.delete("/api/delete/{resource_id}")
def delete_service(resource_id: int, db: Session = Depends(get_db)):
    db.query(UrbanResource).filter(UrbanResource.id == resource_id).delete()
    db.commit()
    return {"message": "Deleted"}
    
@app.get("/api/export")
def export_data(db: Session = Depends(get_db)):
    resources = db.query(UrbanResource).all()
    features = []
    for r in resources:
        if r.geom_type == 'polygon' and r.shape_data:
            # For GeoJSON, coords are [lon, lat], but we stored [lat, lon], so swap back
            latlon = json.loads(r.shape_data)
            lonlat = [[p[1], p[0]] for p in latlon]
            # Ensure closed loop
            if lonlat[0] != lonlat[-1]: lonlat.append(lonlat[0])
            geo = {"type": "Polygon", "coordinates": [lonlat]}
        else:
            geo = {"type": "Point", "coordinates": [r.longitude, r.latitude]}
            
        features.append({
            "type": "Feature", "geometry": geo,
            "properties": {"name": r.name, "category": r.category, "capacity": r.capacity}
        })
    
    file_path = "uploads/export.geojson"
    with open(file_path, "w") as f: json.dump({"type": "FeatureCollection", "features": features}, f)
    return FileResponse(file_path, filename="smart_city.geojson")
