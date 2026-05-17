"""
database.py
-----------
Database configuration module.
Supports PostgreSQL (primary) with automatic SQLite fallback.
Uses SQLAlchemy ORM for database-agnostic operations.
"""

import os
import logging
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# ─── Database URL Resolution ───────────────────────────────────────────────
# Priority: Environment variable > PostgreSQL > SQLite fallback
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./data_lineage.db"   # default: local SQLite for zero-config setup
)

# ─── Engine Configuration ──────────────────────────────────────────────────
if DATABASE_URL.startswith("sqlite"):
    # SQLite: enable WAL mode + foreign keys for better concurrency
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # needed for FastAPI async
        echo=False,  # set True to see SQL in terminal during debugging
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Enable foreign key enforcement and WAL journal mode for SQLite."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    logger.info("Using SQLite database: %s", DATABASE_URL)

else:
    # PostgreSQL: connection pool tuning for production loads
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,           # maintain 10 persistent connections
        max_overflow=20,        # allow up to 20 additional connections under load
        pool_pre_ping=True,     # validate connections before use (handles dropped connections)
        echo=False,
    )
    logger.info("Using PostgreSQL database")

# ─── Session Factory ───────────────────────────────────────────────────────
# Each request gets its own session; transactions are explicit
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ─── Declarative Base ─────────────────────────────────────────────────────
# All ORM models inherit from this base
Base = declarative_base()


# ─── Dependency Injection Helper ──────────────────────────────────────────
def get_db():
    """
    FastAPI dependency that provides a database session.
    Automatically closes the session after the request completes.

    Usage in routes:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database: create all tables defined via ORM models.
    Called once on application startup.
    """
    # Import models here to ensure they're registered with Base before create_all
    from models import db_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified successfully")
