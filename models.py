from sqlalchemy import Column, Integer, String, Float, Text
from database import Base

class UrbanResource(Base):
    __tablename__ = "urban_resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String)  
    
    # Coordinates for Points
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Capacity / Range
    capacity = Column(Integer, default=50) 
    
    # NEW: Geometry Type ('point' or 'polygon')
    geom_type = Column(String, default="point")
    
    # NEW: Stores JSON coordinates for polygons (e.g., "[[lat,lon],[lat,lon]...]")
    shape_data = Column(Text, nullable=True)
