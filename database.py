import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Force reload of .env file
load_dotenv(override=True)

TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

print("------------------------------------------------")
if TURSO_URL and TURSO_TOKEN:
    print(f"🔌 CONNECTING TO TURSO: {TURSO_URL}")
    db_url = TURSO_URL.replace("libsql://", "sqlite+libsql://")
    DATABASE_URL = f"{db_url}?authToken={TURSO_TOKEN}"
else:
    print("⚠️  TURSO VARS NOT FOUND. USING LOCAL SQLITE.")
    print("   (Check your .env file or environment variables)")
    DATABASE_URL = "sqlite:///./local_city.db"
print("------------------------------------------------")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
