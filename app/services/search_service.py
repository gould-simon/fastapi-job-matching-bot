import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, JobMatch, User, UserSearch
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service

    def _prepare_search_text(self, query: str, preferences: dict = None) -> str:
        """Prepare search text by combining query and preferences"""
        parts = [query]
        
        if preferences:
            if location := preferences.get('location'):
                parts.append(f"Location: {location}")
            if seniority := preferences.get('seniority'):
                parts.append(f"Seniority: {seniority}")
            if service := preferences.get('service'):
                parts.append(f"Service: {service}")
            if industry := preferences.get('industry'):
                parts.append(f"Industry: {industry}")
            if employment := preferences.get('employment'):
                parts.append(f"Employment Type: {employment}")
            if salary := preferences.get('salary'):
                parts.append(f"Salary Range: {salary}")
        
        return " | ".join(parts)

    async def search_jobs(
        self,
        session: AsyncSession,
        telegram_id: int,
        query: str,
        preferences: dict = None,
        limit: int = 10
    ) -> List[Tuple[Job, float]]:
        """Search for jobs using semantic search"""
        try:
            # Store the search query
            user = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = user.scalar_one_or_none()
            
            if not user:
                logger.error(f"User not found: {telegram_id}")
                return []
            
            search = UserSearch(
                telegram_id=telegram_id,
                search_query=query,
                structured_preferences=json.dumps(preferences) if preferences else None
            )
            session.add(search)
            
            # Generate embedding for the search query
            search_text = self._prepare_search_text(query, preferences)
            query_embedding = await self.embedding_service._generate_embedding(search_text)
            
            # Find similar jobs
            similar_jobs = await self.embedding_service.find_similar_jobs(
                session=session,
                query_embedding=query_embedding,
                limit=limit
            )
            
            # Store matches
            for job, score in similar_jobs:
                match = JobMatch(
                    telegram_id=telegram_id,
                    job_id=job.id,
                    similarity_score=score
                )
                session.add(match)
            
            await session.commit()
            return similar_jobs
            
        except Exception as e:
            logger.error(f"Error in job search: {e}")
            await session.rollback()
            return []

    async def get_recent_matches(
        self,
        session: AsyncSession,
        telegram_id: int,
        limit: int = 5
    ) -> List[Tuple[Job, float]]:
        """Get recent job matches for a user"""
        try:
            query = select(JobMatch, Job).join(Job).where(
                JobMatch.telegram_id == telegram_id
            ).order_by(
                JobMatch.created_at.desc()
            ).limit(limit)
            
            result = await session.execute(query)
            matches = [(row.Job, row.JobMatch.similarity_score) for row in result]
            return matches
            
        except Exception as e:
            logger.error(f"Error getting recent matches: {e}")
            return []

    async def get_job_by_id(
        self,
        session: AsyncSession,
        job_id: int
    ) -> Optional[Job]:
        """Get a specific job by ID"""
        try:
            query = select(Job).where(Job.id == job_id)
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return None 