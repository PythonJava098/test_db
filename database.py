import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Load variables
db_url = os.getenv("DATABASE_URL")
db_token = os.getenv("DATABASE_AUTH_TOKEN") # Ensure this matches your Env Var name

# 2. Fix the URL scheme for SQLAlchemy (libsql:// -> sqlite+libsql://)
if db_url and db_url.startswith("libsql://"):
    db_url = db_url.replace("libsql://", "sqlite+libsql://")

# 3. Configure connection args (pass the token here)
connect_args = {"check_same_thread": False}
if db_token:
    connect_args["authToken"] = db_token

# 4. Create the Engine
engine = create_engine(
    db_url,
    connect_args=connect_args
)

# 5. Create the Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 6. Define Base here (This fixes the circular import)
Base = declarative_base()
