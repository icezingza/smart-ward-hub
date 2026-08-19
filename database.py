from pathlib import Path
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings


PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = settings.database_path


def init_wal_mode() -> None:
    """Enable SQLite settings required by the offline edge hub."""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(f"PRAGMA synchronous={settings.sqlite_synchronous};")
        conn.commit()
    finally:
        conn.close()


init_wal_mode()

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute(f"PRAGMA synchronous={settings.sqlite_synchronous};")
    cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms};")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
