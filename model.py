from sqlalchemy import Column, Integer, String, Float
from database import Base

class Resource(Base):
    __tablename__ = "resources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String)  # e.g., "hospital", "atm", "school"
    lat = Column(Float)
    lon = Column(Float)
