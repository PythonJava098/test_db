import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Get BOTH credentials from Environment Variables
# (You must add TURSO_DB_URL and TURSO_AUTH_TOKEN in Render Dashboard)
TURSO_DB_URL = os.environ.get("TURSO_DB_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

# 2. Construct the Secure URL
# Turso gives 'libsql://...', but SQLAlchemy needs 'sqlite+libsql://...'
if TURSO_DB_URL:
    db_url = TURSO_DB_URL.replace("libsql://", "sqlite+libsql://")
    if "?secure=true" not in db_url:
        db_url += "?secure=true"
else:
    # Fallback to a local file if variables are missing (prevents crash on local PC)
    print("⚠️ Warning: No Turso URL found. Using local sqlite file.")
    db_url = "sqlite:///./local_test.db"

# 3. Create the Engine
# We only pass the token if it exists (prevents errors with local sqlite)
connect_args = {'auth_token': TURSO_AUTH_TOKEN} if TURSO_AUTH_TOKEN else {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=True  # Set to False when you are done debugging
)

SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)
Base = declarative_base()
