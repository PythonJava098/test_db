import os
import shutil
from fastapi import FastAPI, Request, Depends, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
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
            "name": r.name,
            "category": r.category,
            "lat": r.latitude,
            "lon": r.longitude,
            "range": rng
        })
    return data
