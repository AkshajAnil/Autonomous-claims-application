from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def sqlalchemy_database_url() -> str:
    url = get_settings().database_url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(
    sqlalchemy_database_url(), 
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(120)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(160)"
        ]
        for statement in migrations:
            try:
                if engine.dialect.name != "postgresql":
                    statement = statement.replace(" IF NOT EXISTS", "")
                conn.execute(text(statement))
            except Exception:
                pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
