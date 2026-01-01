from sqlalchemy import Column, Integer, String, Float
from database import Base

class UrbanResource(Base):
    __tablename__ = "urban_resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String)  # hospital, bank, atm, petrol_pump
    latitude = Column(Float)
    longitude = Column(Float)
    capacity = Column(Integer, default=50) # Scale 1-100 (100 = Major Hospital)
    address = Column(String, nullable=True)
