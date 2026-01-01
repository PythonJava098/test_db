import os
import libsql_experimental as libsql
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

print("------------------------------------------------")
if TURSO_URL and TURSO_TOKEN:
    print(f"🔌 CONNECTING TO TURSO: {TURSO_URL}")
    
    # We use a custom creator to bypass the 'sqlite+libsql' dialect issue
    def get_conn():
        return libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
    
    # Use standard sqlite dialect but inject our custom connection
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
