import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import openai
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.models import Job, JobEmbedding
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key
        openai.api_key = openai_api_key

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a text using OpenAI's API"""
        try:
            response = await openai.Embedding.acreate(
                input=text, model="text-embedding-ada-002"
            )

            return response["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def _prepare_job_text(self, job: Job) -> str:
        """Prepare job text for embedding by combining relevant fields"""
        parts = [
            f"Title: {job.job_title}",
            f"Location: {job.location}",
            f"Seniority: {job.seniority}",
            f"Service: {job.service}",
            f"Industry: {job.industry}",
            f"Employment: {job.employment}",
            f"Salary: {job.salary}",
            f"Description: {job.description[:8000]}",
        ]
        return " | ".join([p for p in parts if p and not p.endswith(": None")])

    async def process_job(
        self, session: AsyncSession, job: Job
    ) -> Optional[JobEmbedding]:
        """Process a single job and generate its embedding"""
        try:
            logger.info("Start Process, %d", job.id)
            # Check if embedding exists and is recent
            existing_embedding = await session.execute(
                select(JobEmbedding).where(JobEmbedding.job_id == job.id)
            )
            logger.info("Got Embedding")
            existing_embedding = existing_embedding.scalar_one_or_none()
            logger.info("Scalar or None.")

            # If embedding exists and is less than 7 days old, skip
            if existing_embedding and existing_embedding.last_updated > datetime.now(
                timezone.utc
            ) - timedelta(days=7):
                return existing_embedding
            logger.info("After If")

            # Generate new embedding
            job_text = self._prepare_job_text(job)
            logger.info("Prepared Text")
            embedding_vector = await self._generate_embedding(job_text)
            logger.info("Embedding Generated")
            # Ensure embedding_vector is a list of floats
            if isinstance(embedding_vector, str):
                embedding_vector = json.loads(
                    embedding_vector
                )  # Convert string to list

            # Check if embedding_vector is a list of floats
            if not isinstance(embedding_vector, list) or not all(
                isinstance(entry, float) for entry in embedding_vector
            ):
                logger.error("Invalid embedding vector format: %s", embedding_vector)
                raise ValueError("Embedding vector must be a list of floats.")

            if existing_embedding:
                logger.info("If existing")
                # Update existing embedding
                existing_embedding.embedding = embedding_vector
                # existing_embedding.embedding = json.dumps(embedding_vector)
                logger.info("If existing 1")
                existing_embedding.embedding_vector = embedding_vector
                logger.info("If existing 2")
                existing_embedding.last_updated = datetime.now(timezone.utc)
                logger.info("If existing 3")
                with session.no_autoflush:
                    await session.merge(existing_embedding)
                logger.info("Complete Existing")
            else:
                logger.info("Else Existing")
                # Create new embedding
                new_embedding = JobEmbedding(
                    job_id=job.id,
                    embedding=embedding_vector,
                    embedding_vector=embedding_vector,
                    last_updated=datetime.utcnow(),
                )
                session.add(new_embedding)
                logger.info("Complete Else")

            logger.info("Before Commit ")
            await session.commit()
            logger.info("Await Commit ")
            return existing_embedding or new_embedding

        except Exception as e:
            logger.error(f"Error processing job {job.id}: {e}")
            await session.rollback()
            return None

    async def process_unembedded_jobs(self, batch_size: int = 50) -> int:
        """Process jobs that don't have embeddings or have outdated embeddings"""
        try:
            logger.info("Started Process")
            async with AsyncSessionLocal() as session:
                # Get jobs without embeddings or with old embeddings
                week_ago = datetime.utcnow() - timedelta(days=7)
                logger.info("Week Ago")

                query = (
                    select(Job)
                    .outerjoin(JobEmbedding)
                    .where(
                        and_(
                            Job.id.notin_(
                                select(JobEmbedding.job_id).where(
                                    JobEmbedding.last_updated > week_ago
                                )
                            )
                        )
                    )
                    .limit(batch_size)
                )
                logger.info("Query Done")

                result = await session.execute(query)

                logger.info("The result is : %s", result)
                jobs = result.scalars().all()
                logger.info("Jobs Scalars")

                processed_count = 0
                for job in jobs:
                    logger.info("Job Count: %d", processed_count)
                    if await self.process_job(session, job):
                        processed_count += 1

                logger.info("End Count %d", processed_count)

                return processed_count

        except Exception as e:
            logger.error(f"Error in batch processing jobs: {e}")
            return 0

    async def find_similar_jobs(
        self,
        session: AsyncSession,
        query_embedding: List[float],
        limit: int = 10,
        min_similarity: float = 0.7,
    ) -> List[tuple[Job, float]]:
        """Find jobs similar to the given embedding"""
        try:
            # Use pgvector's cosine similarity search
            query = text(
                """
                SELECT j.*, je.similarity_score
                FROM "JobsApp_job" j
                JOIN (
                    SELECT job_id, 
                           1 - (embedding_vector <=> :query_vector) as similarity_score
                    FROM job_embeddings
                    WHERE 1 - (embedding_vector <=> :query_vector) > :min_similarity
                    ORDER BY embedding_vector <=> :query_vector
                    LIMIT :limit
                ) je ON j.id = je.job_id
                ORDER BY je.similarity_score DESC
            """
            )

            result = await session.execute(
                query,
                {
                    "query_vector": query_embedding,
                    "limit": limit,
                    "min_similarity": min_similarity,
                },
            )

            similar_jobs = []
            for row in result:
                job = Job(
                    id=row.id,
                    job_title=row.job_title,
                    location=row.location,
                    seniority=row.seniority,
                    service=row.service,
                    industry=row.industry,
                    employment=row.employment,
                    salary=row.salary,
                    description=row.description,
                    link=row.link,
                    created_at=row.created_at,
                )
                similarity_score = row.similarity_score
                similar_jobs.append((job, similarity_score))

            return similar_jobs

        except Exception as e:
            logger.error(f"Error finding similar jobs: {e}")
            return []
