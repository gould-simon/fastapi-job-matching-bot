import asyncio
import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

async def add_columns():
    engine = create_async_engine(os.getenv('DATABASE_URL').replace('postgresql://', 'postgresql+asyncpg://'))
    async with engine.begin() as conn:
        await conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS cv_text TEXT'))
        await conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS cv_embedding FLOAT[]'))

if __name__ == '__main__':
    asyncio.run(add_columns()) 