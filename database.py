import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Load Environment Variables (.env)
load_dotenv()

# 2. Get Turso Credentials
TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

# 3. Configure the Engine
if TURSO_URL and TURSO_TOKEN:
    print("------------------------------------------------")
    print("🚀  DETECTED TURSO CREDENTIALS")
    
    # Fix URL format: Turso gives "libsql://", SQLAlchemy needs "sqlite+libsql://"
    if TURSO_URL.startswith("libsql://"):
        TURSO_URL = TURSO_URL.replace("libsql://", "sqlite+libsql://")
    
    # Append the Auth Token
    DATABASE_URL = f"{TURSO_URL}?authToken={TURSO_TOKEN}"
    
    # Connect to Cloud (No check_same_thread needed for Turso)
    engine = create_engine(DATABASE_URL)
    print("✅  CONNECTED TO TURSO CLOUD")

else:
    # Fallback to Local File (for testing without internet/tokens)
    print("------------------------------------------------")
    print("⚠️  NO TURSO CREDENTIALS FOUND")
    DATABASE_URL = "sqlite:///./local_city.db"
    
    # SQLite file needs this argument
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    print("✅  CONNECTED TO LOCAL SQLITE FILE")

print("------------------------------------------------")

# 4. Standard SQLAlchemy Setup
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
