import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Load Environment Variables
load_dotenv()

TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

# 2. Configure the Database URL
if TURSO_URL and TURSO_TOKEN:
    # Turso gives "libsql://...", but SQLAlchemy needs "sqlite+libsql://..."
    if TURSO_URL.startswith("libsql://"):
        TURSO_URL = TURSO_URL.replace("libsql://", "sqlite+libsql://")
    
    # Attach the token to the URL securely
    DATABASE_URL = f"{TURSO_URL}?authToken={TURSO_TOKEN}"
    
    # Create Engine for Turso (Remote)
    # Note: connect_args={"check_same_thread": False} is NOT needed for Turso/LibSQL
    engine = create_engine(DATABASE_URL)
    
    print("------------------------------------------------")
    print("✅  DATABASE CONNECTED: Using Turso Cloud ☁️")
    print("------------------------------------------------")

else:
    # Fallback to local file if no env vars found (Safety Net)
    DATABASE_URL = "sqlite:///./local_city.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    
    print("------------------------------------------------")
    print("⚠️  WARNING: Using LOCAL SQLite (No Turso Credentials Found)")
    print("------------------------------------------------")

# 3. Create Session and Base
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 4. Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
