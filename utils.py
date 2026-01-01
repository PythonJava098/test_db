import os
import zipfile
import geopandas as gpd
from sqlalchemy.orm import Session
from models import UrbanResource
import shutil

# Dynamic Logic from previous steps
import math
STANDARD_DENSITY = 1000
STANDARD_CAPACITY = 50
BASE_RANGES = {"hospital": 5.0, "atm": 1.0, "bank": 2.0, "petrol_pump": 3.0}

def calculate_dynamic_range(category: str, capacity: int, density: int) -> float:
    base = BASE_RANGES.get(category, 2.0)
    density = max(density, 100)
    density_factor = math.sqrt(STANDARD_DENSITY / density)
    capacity_factor = capacity / STANDARD_CAPACITY
    return round(base * density_factor * capacity_factor, 2)

def process_shapefile(zip_path: str, category: str, db: Session):
    """
    1. Unzips the file.
    2. Finds the .shp file.
    3. Reads it with Geopandas.
    4. Saves points to Turso.
    """
    extract_folder = zip_path.replace(".zip", "")
    
    # 1. Unzip
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_folder)

    # 2. Find .shp file
    shp_file = None
    for root, dirs, files in os.walk(extract_folder):
        for file in files:
            if file.endswith(".shp"):
                shp_file = os.path.join(root, file)
                break
    
    if not shp_file:
        return 0

    # 3. Read with Geopandas
    gdf = gpd.read_file(shp_file)
    
    # Convert to standard lat/lon (EPSG:4326) if it isn't already
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    count = 0
    for _, row in gdf.iterrows():
        # Handle Geometry
        geo = row.geometry
        if geo.geom_type == 'Point':
            lat, lon = geo.y, geo.x
        else:
            lat, lon = geo.centroid.y, geo.centroid.x

        # Handle Name (Try to find a name column, otherwise generic)
        name = "Unknown Facility"
        possible_names = ['name', 'Name', 'NAME', 'facility', 'type']
        for col in possible_names:
            if col in gdf.columns:
                name = str(row[col])
                break

        # Save to DB
        exists = db.query(UrbanResource).filter_by(latitude=lat, longitude=lon).first()
        if not exists:
            res = UrbanResource(
                name=name, 
                category=category, 
                latitude=lat, 
                longitude=lon, 
                capacity=50 # Default capacity
            )
            db.add(res)
            count += 1
            
    db.commit()
    
    # Cleanup
    shutil.rmtree(extract_folder)
    os.remove(zip_path)
    
    return count
