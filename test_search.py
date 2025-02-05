import asyncio
import os
import logging
from datetime import datetime

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import User, Job
from app.services.embedding_service import EmbeddingService
from app.services.search_service import SearchService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_search():
    """Test the job search functionality"""
    try:
        # Initialize services
        embedding_service = EmbeddingService(os.getenv("OPENAI_API_KEY"))
        search_service = SearchService(embedding_service)
        
        async with AsyncSessionLocal() as session:
            # Create a test user if doesn't exist
            test_user = await session.execute(
                select(User).where(User.telegram_id == 12345)
            )
            test_user = test_user.scalar_one_or_none()
            
            if not test_user:
                test_user = User(
                    telegram_id=12345,
                    username="test_user",
                    first_name="Test",
                    last_name="User",
                    cv_text="Experienced accountant with expertise in audit and tax.",
                    preferences={"location": "London", "seniority": "Senior", "service": "Accounting"}
                )
                session.add(test_user)
                await session.commit()
                logger.info("Created test user")
            
            # Process some jobs first
            logger.info("Processing jobs for embeddings...")
            processed = await embedding_service.process_unembedded_jobs(batch_size=10)
            logger.info(f"Processed {processed} jobs")
            
            # Test search
            search_query = "Senior Accountant in London"
            preferences = {
                "location": "London",
                "seniority": "Senior",
                "service": "Accounting"
            }
            
            logger.info(f"Searching for: {search_query}")
            results = await search_service.search_jobs(
                session=session,
                telegram_id=12345,
                query=search_query,
                preferences=preferences,
                limit=5
            )
            
            # Display results
            logger.info(f"Found {len(results)} matches:")
            for job, score in results:
                logger.info(f"\nJob: {job.job_title}")
                logger.info(f"Location: {job.location}")
                logger.info(f"Similarity: {score:.2f}")
                logger.info(f"Link: {job.link}")
                logger.info("-" * 50)
            
            # Test recent matches
            logger.info("\nTesting recent matches...")
            recent = await search_service.get_recent_matches(session, 12345, limit=3)
            logger.info(f"Found {len(recent)} recent matches")
            
    except Exception as e:
        logger.error(f"Error in test: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_search()) 