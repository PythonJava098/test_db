import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# TURSO CONFIGURATION
TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

if TURSO_URL and TURSO_TOKEN:
    # Fix URL protocol for SQLAlchemy if needed
    db_url = TURSO_URL.replace("libsql://", "sqlite+libsql://")
    DATABASE_URL = f"{db_url}?authToken={TURSO_TOKEN}"
    connect_args = {"check_same_thread": False}
else:
    # Local fallback
    DATABASE_URL = "sqlite:///./local_city.db"
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
