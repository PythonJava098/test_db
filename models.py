from database import Base
from sqlalchemy import Column, Integer, String, Float

class UrbanResource(Base):
    __tablename__ = "urban_resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String)  # e.g., "hospital", "atm", "school"
    latitude = Column(Float)
    longitude = Column(Float)
    address = Column(String, nullable=True)
