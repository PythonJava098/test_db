import os
import shutil
import json
import uuid
from fastapi import FastAPI, Request, Depends, UploadFile, File, Form, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from database import engine, Base, get_db
from models import UrbanResource
from utils import process_shapefile, calculate_dynamic_range

# Create tables (will add session_id column if dropping/recreating)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart City Allocator")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
os.makedirs("uploads", exist_ok=True)

# --- SESSION MANAGEMENT ---
def get_session_id(request: Request, response: Response):
    """
    Check if user has a session_id cookie. If not, generate a new UUID.
    """
    session_id = request.cookies.get("urban_session")
    if not session_id:
        session_id = str(uuid.uuid4())
        # We set the cookie on the response so the browser remembers it
        response.set_cookie(key="urban_session", value=session_id, max_age=86400) # 1 day
        request.state.session_id = session_id # Store for immediate use
    return session_id

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    # Just render the page; cookie will be set if missing by the browser or JS if needed, 
    # but strictly we handle cookies in API responses usually.
    # To be safe, we can manually ensure a cookie is set on the home load:
    response = templates.TemplateResponse("index.html", {"request": request})
    if not request.cookies.get("urban_session"):
        response.set_cookie(key="urban_session", value=str(uuid.uuid4()))
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    response = templates.TemplateResponse("dashboard.html", {"request": request})
    if not request.cookies.get("urban_session"):
        response.set_cookie(key="urban_session", value=str(uuid.uuid4()))
    return response

@app.post("/upload")
async def upload_file(
    response: Response,
    request: Request,
    category: str = Form(...), 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    # Get Session ID
    session_id = request.cookies.get("urban_session")
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie(key="urban_session", value=session_id)

    # 1. SCOPED DELETE: Only delete THIS user's data
    db.query(UrbanResource).filter(UrbanResource.session_id == session_id).delete()
    db.commit()

    # 2. Save and Process New File
    file_location = f"uploads/{session_id}_{file.filename}" # Prefix filename to avoid collisions
    with open(file_location, "wb+") as f:
        shutil.copyfileobj(file.file, f)
        
    # Pass session_id to utils
    process_shapefile(file_location, category, db, session_id)
    
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/api/resources")
def get_resources(request: Request, density: int = 1000, db: Session = Depends(get_db)):
    session_id = request.cookies.get("urban_session")
    if not session_id: return [] # No session, no data

    # FILTER: Only get my data
    resources = db.query(UrbanResource).filter(UrbanResource.session_id == session_id).all()
    
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
def add_service(request: Request, data: dict, db: Session = Depends(get_db)):
    session_id = request.cookies.get("urban_session")
    if not session_id: raise HTTPException(status_code=400, detail="No Session")

    if data.get("geom_type") == "polygon":
        coords_json = json.dumps(data.get("coordinates"))
        new_res = UrbanResource(
            session_id=session_id, # <--- TAG DATA
            name=data.get("name"), category=data["category"], 
            geom_type="polygon", shape_data=coords_json,
            capacity=data.get("capacity", 50)
        )
    else:
        new_res = UrbanResource(
            session_id=session_id, # <--- TAG DATA
            name=data.get("name"), category=data["category"], 
            geom_type="point", latitude=data["lat"], longitude=data["lon"],
            capacity=data.get("capacity", 50)
        )
    db.add(new_res)
    db.commit()
    return {"message": "Added"}

@app.put("/api/update/{resource_id}")
def update_service(resource_id: int, request: Request, data: dict, db: Session = Depends(get_db)):
    session_id = request.cookies.get("urban_session")
    # SECURITY: Ensure user owns this resource
    resource = db.query(UrbanResource).filter(UrbanResource.id == resource_id, UrbanResource.session_id == session_id).first()
    
    if not resource: raise HTTPException(status_code=404)
    
    if "name" in data: resource.name = data["name"]
    if "capacity" in data: resource.capacity = data["capacity"]
    if "lat" in data: resource.latitude = data["lat"]
    if "lon" in data: resource.longitude = data["lon"]
    
    db.commit()
    return {"message": "Updated"}

@app.delete("/api/delete/{resource_id}")
def delete_service(resource_id: int, request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("urban_session")
    # SECURITY: Ensure user owns this resource
    db.query(UrbanResource).filter(UrbanResource.id == resource_id, UrbanResource.session_id == session_id).delete()
    db.commit()
    return {"message": "Deleted"}

@app.get("/api/export")
def export_data(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("urban_session")
    # FILTER: Export only my data
    resources = db.query(UrbanResource).filter(UrbanResource.session_id == session_id).all()
    
    features = []
    for r in resources:
        if r.geom_type == 'polygon' and r.shape_data:
            latlon = json.loads(r.shape_data)
            lonlat = [[p[1], p[0]] for p in latlon]
            if lonlat[0] != lonlat[-1]: lonlat.append(lonlat[0])
            geo = {"type": "Polygon", "coordinates": [lonlat]}
        else:
            geo = {"type": "Point", "coordinates": [r.longitude, r.latitude]}
            
        features.append({
            "type": "Feature", "geometry": geo,
            "properties": {"name": r.name, "category": r.category, "capacity": r.capacity}
        })
    
    file_path = f"uploads/{session_id}_export.geojson"
    with open(file_path, "w") as f: json.dump({"type": "FeatureCollection", "features": features}, f)
    return FileResponse(file_path, filename="smart_city_plan.geojson")
