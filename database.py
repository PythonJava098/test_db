import os
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

# Construct the SQLAlchemy URL for Turso (libsql)
# Format: sqlite+libsql://dbname.turso.io?authToken=...
if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
    # Ensure URL starts with sqlite+libsql://
    db_url = TURSO_DATABASE_URL.replace("libsql://", "sqlite+libsql://")
    DATABASE_URL = f"{db_url}?authToken={TURSO_AUTH_TOKEN}"
else:
    # Fallback for local testing if env vars are missing
    DATABASE_URL = "sqlite:///./local_city.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
