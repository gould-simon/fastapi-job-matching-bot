import asyncio
import os
from sqlalchemy import MetaData, Table, Column, Integer, String, DateTime, BigInteger, ForeignKey, Text, ARRAY, Float, JSON, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import create_async_engine
from datetime import datetime

# Load environment variables
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable is not set")

# Convert the DATABASE_URL to use asyncpg driver
if DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

async def create_tables():
    # Create async engine
    engine = create_async_engine(DATABASE_URL)
    
    metadata = MetaData()
    
    # Define tables
    jobsapp_job = Table(
        'jobsapp_job', metadata,
        Column('id', Integer, primary_key=True),
        extend_existing=True
    )
    
    users = Table(
        'users', metadata,
        Column('id', Integer, primary_key=True),
        Column('telegram_id', BigInteger, unique=True, nullable=False),
        Column('username', String, nullable=True),
        Column('first_name', String, nullable=True),
        Column('last_name', String, nullable=True),
        Column('cv_text', Text, nullable=True),
        Column('cv_embedding', ARRAY(Float), nullable=True),
        Column('preferences', JSONB, nullable=True),
        Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
        Column('updated_at', DateTime, nullable=False, default=datetime.utcnow)
    )
    
    user_searches = Table(
        'user_searches', metadata,
        Column('id', Integer, primary_key=True),
        Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
        Column('search_query', String, nullable=False),
        Column('created_at', DateTime, nullable=False, default=datetime.utcnow)
    )
    
    user_conversations = Table(
        'user_conversations', metadata,
        Column('id', Integer, primary_key=True),
        Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
        Column('message', String, nullable=False),
        Column('is_user', Boolean, nullable=False),
        Column('created_at', DateTime, nullable=False, default=datetime.utcnow)
    )
    
    job_matches = Table(
        'job_matches', metadata,
        Column('id', Integer, primary_key=True),
        Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
        Column('job_id', Integer, ForeignKey('jobsapp_job.id'), nullable=False),
        Column('score', Float, nullable=False),
        Column('created_at', DateTime, nullable=False, default=datetime.utcnow)
    )
    
    async with engine.begin() as conn:
        # Drop existing tables if they exist
        await conn.execute(text("DROP TABLE IF EXISTS job_matches CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS user_conversations CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS user_searches CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
        
        # Create tables
        await conn.run_sync(metadata.create_all)
        
        # Create indexes
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_searches_user_id ON user_searches (user_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_job_matches_user_id ON job_matches (user_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_job_matches_job_id ON job_matches (job_id);"))

if __name__ == "__main__":
    asyncio.run(create_tables()) 