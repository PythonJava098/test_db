from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, text

# Import setup from your database.py file
from database import Base, engine, get_db

app = FastAPI()

# --- DEFINE A SIMPLE MODEL FOR TESTING ---
class HackathonTest(Base):
    __tablename__ = "hackathon_test"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(String)

# --- CREATE TABLES ON STARTUP ---
# This automatically creates the table in Turso if it doesn't exist
Base.metadata.create_all(bind=engine)

@app.get("/")
def home():
    return {"status": "Online", "message": "Go to /test-db to check Turso connection"}

@app.get("/test-db")
def test_database(db: Session = Depends(get_db)):
    try:
        # 1. Try to insert a row
        new_entry = HackathonTest(message="Hello from Render!")
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        
        # 2. Count how many rows we have
        count = db.query(HackathonTest).count()
        
        return {
            "status": "success",
            "database": "Connected to Turso",
            "last_inserted_id": new_entry.id,
            "total_rows": count
        }
    except Exception as e:
        return {"status": "error", "details": str(e)}

@app.get("/health")
def health_check():
    return {"status": "ok"}
