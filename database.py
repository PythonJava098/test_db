from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base  # Updated import for newer SQLAlchemy versions
import os

# 1. Fetch variables from the environment
# Default to a local SQLite file if variables aren't set (for local testing)
DB_URL = os.environ.get("TURSO_DB_URL", "sqlite:///./smartcity.db")
DB_TOKEN = os.environ.get("TURSO_DB_AUTH_TOKEN")

# 2. Construct the connection string
# If we have a token, we must append it to the URL.
# Turso format: sqlite+libsql://<dbname>.turso.io?authToken=<token>
if "libsql" in DB_URL and DB_TOKEN:
    connection_string = f"{DB_URL}?authToken={DB_TOKEN}"
else:
    connection_string = DB_URL

# 3. Configure the Engine
# check_same_thread=False is needed ONLY for local SQLite files, not for Turso/libsql
connect_args = {}
if "sqlite" in connection_string and "libsql" not in connection_string:
    connect_args = {"check_same_thread": False}

engine = create_engine(
    connection_string,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
