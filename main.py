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

import tempfile
import zipfile
import geopandas as gpd
from shapely.geometry import Point, Polygon
from fastapi.background import BackgroundTasks

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

def remove_file(path: str):
    try:
        if os.path.exists(path):
            if os.path.isdir(path): shutil.rmtree(path)
            else: os.remove(path)
    except Exception as e:
        print(f"Error removing file {path}: {e}")

@app.get("/api/export_shp")
def export_shapefile(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    session_id = request.cookies.get("urban_session")
    if not session_id: return Response(status_code=403)

    # 1. Fetch Data
    resources = db.query(UrbanResource).filter(UrbanResource.session_id == session_id).all()
    if not resources:
        return Response(content="No data to export", status_code=404)

    # 2. Convert to GeoPandas DataFrame
    data = []
    geometries = []
    
    for r in resources:
        # Create properties dict
        props = {
            "name": r.name or "Unknown",
            "category": r.category or "misc",
            "capacity": r.capacity
        }
        
        # Create Geometry
        if r.geom_type == 'polygon' and r.shape_data:
            try:
                # shape_data is "[[lat,lon], [lat,lon]...]"
                latlon = json.loads(r.shape_data)
                # Swap to [lon, lat] for GIS
                lonlat = [(p[1], p[0]) for p in latlon]
                geometries.append(Polygon(lonlat))
                data.append(props)
            except: pass
        else:
            # Point
            geometries.append(Point(r.longitude, r.latitude))
            data.append(props)

    if not data: return Response(content="No valid geometry found", status_code=400)

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(data, geometry=geometries, crs="EPSG:4326")

    # 3. Write to Temp Shapefile
    # We create a temporary directory to hold the .shp, .shx, .dbf, etc.
    tmp_dir = tempfile.mkdtemp()
    shp_path = os.path.join(tmp_dir, "urban_resources.shp")
    
    try:
        gdf.to_file(shp_path, driver="ESRI Shapefile")
    except Exception as e:
        shutil.rmtree(tmp_dir)
        return Response(content=f"Export failed: {e}", status_code=500)

    # 4. Zip the Shapefile components
    zip_filename = f"uploads/{session_id}_export.zip"
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for filename in os.listdir(tmp_dir):
            file_path = os.path.join(tmp_dir, filename)
            zipf.write(file_path, arcname=filename)

    # 5. Cleanup Temp Folder (we keep the zip to send it)
    shutil.rmtree(tmp_dir)

    # 6. Send File & Schedule Cleanup of Zip
    background_tasks.add_task(remove_file, zip_filename)
    return FileResponse(
        zip_filename, 
        media_type="application/zip", 
        filename="UrbanMind_Export.zip"
    )
