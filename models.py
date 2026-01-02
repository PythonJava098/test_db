from sqlalchemy import Column, Integer, String, Float, Text
from database import Base

class UrbanResource(Base):
    __tablename__ = "urban_resources"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)  # <--- NEW: Tracks who owns this data
    name = Column(String, index=True)
    category = Column(String)   
    
    # Coordinates for Points
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Capacity / Range
    capacity = Column(Integer, default=50) 
    
    # Geometry Type ('point' or 'polygon')
    geom_type = Column(String, default="point")
    
    # Stores JSON coordinates for polygons
    shape_data = Column(Text, nullable=True)
