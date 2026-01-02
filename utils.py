import os
import zipfile
import shutil
import math
import json
import geopandas as gpd
from sqlalchemy.orm import Session
from models import UrbanResource

# Standard Ranges
STANDARD_DENSITY = 1000
STANDARD_CAPACITY = 50
BASE_RANGES = {"hospital": 5.0, "school": 2.0, "atm": 1.0, "bank": 1.5, "petrol_pump": 3.0}

def calculate_dynamic_range(category: str, capacity: int, density: int) -> float:
    base = BASE_RANGES.get(category.lower(), 2.0)
    density = max(int(density), 100)
    density_factor = math.sqrt(STANDARD_DENSITY / density)
    capacity_factor = capacity / STANDARD_CAPACITY
    return round(base * density_factor * capacity_factor, 2)

def process_shapefile(zip_path: str, default_category: str, db: Session):
    extract_folder = zip_path.replace(".zip", "")
    
    try:
        if os.path.exists(extract_folder): shutil.rmtree(extract_folder)
        os.makedirs(extract_folder)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
            
        # Find .shp
        shp_file = next((os.path.join(r, f) for r, _, fs in os.walk(extract_folder) for f in fs if f.endswith(".shp")), None)
        if not shp_file: return 0

        gdf = gpd.read_file(shp_file)
        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        count = 0
        for _, row in gdf.iterrows():
            try:
                # 1. DYNAMIC CATEGORY DETECTION
                # If the file has a 'type' or 'amenity' column, use it. Otherwise use default.
                category = default_category
                for col in ['amenity', 'type', 'fclass', 'category', 'landuse']:
                    if col in gdf.columns and row[col]:
                        category = str(row[col]).lower()
                        break

                name = "Unknown"
                for col in ['name', 'Name', 'NAME', 'facility']:
                    if col in gdf.columns:
                        name = str(row[col])
                        break

                # 2. GEOMETRY HANDLING
                geo = row.geometry
                
                if geo.geom_type == 'Point':
                    # Save as Point
                    res = UrbanResource(
                        name=name, category=category, geom_type="point",
                        latitude=geo.y, longitude=geo.x, capacity=50
                    )
                    db.add(res)
                
                elif geo.geom_type in ['Polygon', 'MultiPolygon']:
                    # Save as Polygon (Extract coords)
                    # Simplify: Take the exterior of the first polygon
                    if geo.geom_type == 'MultiPolygon':
                        poly = geo.geoms[0]
                    else:
                        poly = geo
                    
                    # Convert coords to list of [lat, lon]
                    coords = [[p[1], p[0]] for p in poly.exterior.coords]
                    
                    res = UrbanResource(
                        name=name, category=category, geom_type="polygon",
                        shape_data=json.dumps(coords), capacity=50
                    )
                    db.add(res)
                
                count += 1
            except Exception as e:
                print(f"Skipping row: {e}")
                continue

        db.commit()
        return count
    except Exception as e:
        print(f"Process Error: {e}")
        return 0
    finally:
        try: shutil.rmtree(extract_folder)
        except: pass
