from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 🔽 ADD THIS BLOCK
# Auto-create tables for local/dev unless you disable it
if os.getenv("DB_AUTO_CREATE", "1") == "1":
    try:
        # Import Base and models so metadata is populated
        from .models import Base  # noqa: F401

        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        # Don't crash in prod if something goes wrong
        print(f"[DB] Skipped auto-create tables: {e}")

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
