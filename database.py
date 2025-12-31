import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Get secrets from Environment Variables (Set these in Render Dashboard)
TURSO_DB_URL = os.environ.get("TURSO_DB_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

# 2. Construct the Secure URL
# Turso gives 'libsql://...', but SQLAlchemy needs 'sqlite+libsql://...'
if TURSO_DB_URL:
    db_url = TURSO_DB_URL.replace("libsql://", "sqlite+libsql://")
    if "?secure=true" not in db_url:
        db_url += "?secure=true"
else:
    # Fallback for local testing if env vars are missing (prevents crash)
    db_url = "sqlite:///./test.db"

# 3. Create the Engine
connect_args = {'auth_token': TURSO_AUTH_TOKEN} if TURSO_AUTH_TOKEN else {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=True  # Logs SQL queries to console (great for debugging)
)

# 4. Create Session & Base
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 5. Dependency (Used in main.py to get a fresh DB session per request)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
