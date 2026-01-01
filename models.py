from sqlalchemy import Column, Integer, String, Float
from database import Base

class UrbanResource(Base):
    __tablename__ = "urban_resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String)  # hospital, school, atm
    latitude = Column(Float)
    longitude = Column(Float)
    capacity = Column(Integer, default=50)
