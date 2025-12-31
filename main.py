from fastapi import FastAPI,HTTPException,Depends
from typing import Annotated,List,Optional
from pydantic import BaseModel
from model import Pharmacy
import model
from database import engine,SessionLocal
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

app=FastAPI()
model.Base.metadata.create_all(bind=engine)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class pharmacycreate(BaseModel):
    
    name:str
    latitude:float
    longitude:float

class pharmacyreply(BaseModel):
    id:int
    class ConfigDict:
        from_attributes=True

class pharmacyupdate(BaseModel):
    ID:Optional[int]=None
    name:Optional[str]=None
    latitude:Optional[float]=None
    longitude:Optional[float]=None
    
def get_db():
    db=SessionLocal()
    try :
        yield db
    finally:
        db.close()

db_depend=Annotated[Session,Depends(get_db)]

@app.get("/")
def root():
    return {'message':'Smart City Resource Allocator'}

@app.get("/pharmacy")
def get_pharmacies(db: Session = Depends(get_db)):
    pharmacies = db.query(Pharmacy).all()
    return pharmacies


@app.post('/create')
def create_pharma(phar:pharmacycreate,db:Session=Depends(get_db)):
    db_phar=model.Pharmacy(name=phar.name,latitude=phar.latitude,longitude=phar.longitude)
    db.add(db_phar)
    db.commit()
    db.refresh(db_phar)

    return {
        'message':'pharmacy created succesfully',
        'id': db_phar.id
    }

@app.delete('/pharmacy/{id}')
def delete_pharma(phar_id:int,db:Session=Depends(get_db)):
    pharma=db.query(Pharmacy).filter(Pharmacy.id==phar_id).first()
    if not pharma:
        raise HTTPException(status_code=404,detail="Pharmacy not found")
    db.delete(pharma)
    db.commit()

    return {'message':'ID deleted'}

@app.put('/update/{phar_id}')
def update_pharma(data:pharmacyupdate,phar_id=int,db:Session=Depends(get_db)):
    pharmaupd=db.query(Pharmacy).filter(Pharmacy.id==phar_id).first()
    if not  pharmaupd:
        raise HTTPException(status_code=404,detail='Does not exist')
    if data.ID is not None:
        pharmaupd.id=data.ID
    if data.name is not None:
        pharmaupd.name=data.name
    if data.latitude is not None:
        pharmaupd.latitude=data.latitude
    if data.longitude is not None:
        pharmaupd.longitude=data.longitude

    db.commit()
    db.refresh(pharmaupd)
    
