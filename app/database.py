from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# CHANGE THESE VALUES
DB_USER = "postgres"
DB_PASSWORD = "9869"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "KaresaBari"

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Engine configuration
engine = create_engine(DATABASE_URL)

# Session maker for creating sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Declarative base for models
Base = declarative_base()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

