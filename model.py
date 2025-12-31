from sqlalchemy import Integer,Float,String,Column,ForeignKey
from database import Base

class Pharmacy(Base):
    __tablename__="pharmacy"

    id=Column(Integer,primary_key=True,index=True)
    name=Column(String,nullable=False,index=True)
    latitude=Column(Float)
    longitude=Column(Float)
