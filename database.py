import os
import libsql_experimental as libsql
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

print("------------------------------------------------")
if TURSO_URL and TURSO_TOKEN:
    print(f"🔌 CONNECTING TO TURSO: {TURSO_URL}")
    
    # --- THE FIX IS HERE ---
    def get_conn():
        """
        Creates a Turso connection and patches it to look like a standard
        SQLite connection so SQLAlchemy doesn't crash.
        """
        conn = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
        
        # Patch: SQLAlchemy tries to call create_function, which libsql lacks.
        # We add a dummy function to bypass the error.
        if not hasattr(conn, "create_function"):
            conn.create_function = lambda *args, **kwargs: None
            
        return conn
    
    # Use standard sqlite dialect but inject our patched connection
    DATABASE_URL = "sqlite://"
    engine = create_engine(DATABASE_URL, creator=get_conn, connect_args={"check_same_thread": False})
else:
    print("⚠️  TURSO VARS NOT FOUND. USING LOCAL SQLITE.")
    DATABASE_URL = "sqlite:///./local_city.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
print("------------------------------------------------")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
