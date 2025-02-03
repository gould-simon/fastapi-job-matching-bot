from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL  # ✅ Import from config.py

# Ensure DATABASE_URL is set
if DATABASE_URL is None:
    raise ValueError("❌ DATABASE_URL is not set. Check your .env file!")

# Create async database engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Create session factory
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
