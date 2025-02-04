from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.config import DATABASE_URL
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Create Base class for models
Base = declarative_base()

# Ensure DATABASE_URL is set and properly formatted
if DATABASE_URL is None:
    raise ValueError("❌ DATABASE_URL is not set. Check your .env file!")

# Parse the URL and add default port if not specified
parsed = urlparse(DATABASE_URL)
if parsed.port is None:
    # Add default PostgreSQL port (5432) if not specified
    host_with_port = f"{parsed.hostname}:5432"
    DATABASE_URL = DATABASE_URL.replace(parsed.hostname, host_with_port)
    logger.info("Added default port 5432 to DATABASE_URL")

# Convert standard postgresql:// to postgresql+asyncpg:// if needed
if DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://', 1)
    logger.info("Converted DATABASE_URL to use asyncpg driver")

# Create async database engine with connection pooling
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Create session factory
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
