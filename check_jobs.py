from app.database import AsyncSessionLocal
import asyncio
from sqlalchemy import text

async def check_jobs():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM \"JobsApp_job\""))
        count = result.scalar()
        print(f"Number of jobs in database: {count}")

async def main():
    await check_jobs()

asyncio.run(main())
