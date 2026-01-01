import os
import zipfile
import shutil
import math
import geopandas as gpd
from sqlalchemy.orm import Session
from models import UrbanResource

# --- DYNAMIC RANGE LOGIC ---
STANDARD_DENSITY = 1000  # people/km²
STANDARD_CAPACITY = 50   # Standard facility size

# Base range in km (if density is standard)
BASE_RANGES = {
    "hospital": 5.0,
    "school": 2.0,
    "atm": 1.0,
    "bank": 1.5,
    "petrol_pump": 3.0
}

def calculate_dynamic_range(category: str, capacity: int, density: int) -> float:
    """
    Calculates coverage radius.
    - High Density = Lower Range (Overcrowding)
    - High Capacity = Higher Range
    """
    base = BASE_RANGES.get(category.lower(), 2.0)
    density = max(int(density), 100) # Safety floor
    
    # Formula: Range ~ sqrt(1/density) * capacity
    density_factor = math.sqrt(STANDARD_DENSITY / density)
    capacity_factor = capacity / STANDARD_CAPACITY
    
    return round(base * density_factor * capacity_factor, 2)

# --- SHAPEFILE PROCESSOR ---
def process_shapefile(zip_path: str, category: str, db: Session):
    extract_folder = zip_path.replace(".zip", "")
    
    # 1. Unzip
    try:
        if os.path.exists(extract_folder): shutil.rmtree(extract_folder)
        os.makedirs(extract_folder)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
    except Exception as e:
        print(f"Zip Error: {e}")
        return 0

    # 2. Find .shp
    shp_file = None
    for root, _, files in os.walk(extract_folder):
        for file in files:
            if file.endswith(".shp"):
                shp_file = os.path.join(root, file)
                break
    
    if not shp_file:
        return 0

    # 3. Read & Parse
    try:
        gdf = gpd.read_file(shp_file)
        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326") # Convert to Lat/Lon
    except Exception as e:
        print(f"GeoPandas Error: {e}")
        return 0

    count = 0
    for _, row in gdf.iterrows():
        try:
            # Extract Geometry
            geo = row.geometry
            if geo.geom_type == 'Point':
                lat, lon = geo.y, geo.x
            else:
                lat, lon = geo.centroid.y, geo.centroid.x
            
            # Extract Name (Smart guess)
            name = "Unknown"
            for col in ['name', 'Name', 'NAME', 'facility', 'amenity']:
                if col in gdf.columns:
                    name = str(row[col])
                    break
            
            # Save to DB
            res = UrbanResource(
                name=name, category=category,
                latitude=lat, longitude=lon,
                capacity=50 # Default capacity
            )
            db.add(res)
            count += 1
        except:
            continue

    db.commit()
    
    # Cleanup
    try:
        shutil.rmtree(extract_folder)
        os.remove(zip_path)
    except:
        pass
        
    return count
