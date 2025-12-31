from sqlalchemy import Column, Integer, String, Float
from database import Base

class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    amenity_type = Column(String)  # e.g., "hospital", "pharmacy"
    lat = Column(Float)
    lon = Column(Float)
    address = Column(String, nullable=True)
