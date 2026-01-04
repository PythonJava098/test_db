import os
import libsql_experimental as libsql
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

# --- CUSTOM WRAPPER CLASS ---
class LibSQLConnectionWrapper:
    """
    Wraps the Turso (libsql) connection to add the missing 'create_function'
    method that SQLAlchemy expects.
    """
    def __init__(self, connection):
        self._conn = connection

    def create_function(self, *args, **kwargs):
        # SQLAlchemy calls this to register Regex functions. 
        # We silently ignore it because libsql doesn't support it yet.
        pass

    def __getattr__(self, name):
        # Forward all other calls (cursor, commit, close, etc.) to the real connection
        return getattr(self._conn, name)

print("------------------------------------------------")
if TURSO_URL and TURSO_TOKEN:
    print(f"🔌 CONNECTING TO TURSO: {TURSO_URL}")
    
    def get_conn():
        # 1. Connect to Turso
        raw_conn = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
        # 2. Wrap it in our custom class
        return LibSQLConnectionWrapper(raw_conn)
    
    # Use standard sqlite dialect + our wrapper
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
