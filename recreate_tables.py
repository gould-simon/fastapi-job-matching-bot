import asyncio
import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

async def recreate_tables():
    engine = create_async_engine(os.getenv('DATABASE_URL').replace('postgresql://', 'postgresql+asyncpg://'))
    async with engine.begin() as conn:
        # Drop existing tables
        await conn.execute(text('DROP TABLE IF EXISTS job_matches'))
        await conn.execute(text('DROP TABLE IF EXISTS user_conversations'))
        await conn.execute(text('DROP TABLE IF EXISTS user_searches'))
        await conn.execute(text('DROP TABLE IF EXISTS users'))

        # Create users table
        await conn.execute(text('''
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                cv_text TEXT,
                cv_embedding FLOAT[],
                preferences JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
            )
        '''))
        await conn.execute(text('CREATE INDEX ix_users_telegram_id ON users (telegram_id)'))

        # Create user_searches table
        await conn.execute(text('''
            CREATE TABLE user_searches (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
                search_query TEXT,
                structured_preferences TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
            )
        '''))
        await conn.execute(text('CREATE INDEX ix_user_searches_telegram_id ON user_searches (telegram_id)'))

        # Create user_conversations table
        await conn.execute(text('''
            CREATE TABLE user_conversations (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
                message TEXT NOT NULL,
                is_user BOOLEAN NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
            )
        '''))
        await conn.execute(text('CREATE INDEX ix_user_conversations_telegram_id ON user_conversations (telegram_id)'))

        # Create job_matches table
        await conn.execute(text('''
            CREATE TABLE job_matches (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
                job_id INTEGER NOT NULL REFERENCES JobsApp_job(id),
                similarity_score FLOAT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
            )
        '''))
        await conn.execute(text('CREATE INDEX ix_job_matches_telegram_id ON job_matches (telegram_id)'))
        await conn.execute(text('CREATE INDEX ix_job_matches_job_id ON job_matches (job_id)'))

if __name__ == '__main__':
    asyncio.run(recreate_tables()) 