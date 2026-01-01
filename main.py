import os
import shutil
from fastapi import FastAPI, Request, Depends, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import engine, Base, get_db
from models import UrbanResource
from utils import process_shapefile, calculate_dynamic_range, haversine, Unit

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart City Allocator")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Ensure upload directory exists
os.makedirs("uploads", exist_ok=True)

# --- PAGES ---

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# --- API ---

@app.post("/upload")
async def upload_file(
    category: str = Form(...), 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """
    Receives a ZIP file containing Shapefile data
    """
    file_location = f"uploads/{file.filename}"
    
    # Save uploaded file to disk
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    # Process it
    try:
        count = process_shapefile(file_location, category, db)
        # Redirect to dashboard with success message (simplified)
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/resources")
def get_resources(density: int = 1000, db: Session = Depends(get_db)):
    resources = db.query(UrbanResource).all()
    data = []
    for r in resources:
        eff_range = calculate_dynamic_range(r.category, r.capacity, density)
        data.append({
            "name": r.name,
            "category": r.category,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "capacity": r.capacity,
            "range": eff_range
        })
    return data
