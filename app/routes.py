from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import SessionLocal

router = APIRouter()

async def get_db():
    async with SessionLocal() as session:
        yield session

@router.get("/jobs")
async def get_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute("SELECT * FROM jobs LIMIT 10")
    return result.fetchall()
