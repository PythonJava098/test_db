import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Load variables
db_url = os.getenv("DATABASE_URL")
db_token = os.getenv("DATABASE_AUTH_TOKEN")

# 2. Fix the URL scheme for SQLAlchemy if needed
if db_url and db_url.startswith("libsql://"):
    db_url = db_url.replace("libsql://", "sqlite+libsql://")

# 3. Configure connection args (Token goes here)
connect_args = {"check_same_thread": False}
if db_token:
    connect_args["authToken"] = db_token

# 4. Create Engine
# Fallback to local file ONLY if no env var is found (prevents crash during local testing if vars missing)
if not db_url:
    print("WARNING: No DATABASE_URL found. Using local sqlite file.")
    db_url = "sqlite:///./smart_city_local.db"

engine = create_engine(
    db_url,
    connect_args=connect_args
)

# 5. Session & Base
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
