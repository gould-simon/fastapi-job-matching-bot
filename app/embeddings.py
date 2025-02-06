from typing import List, Dict, Any, Optional, Union
import asyncio
from openai import OpenAI
from sqlalchemy import select, text, bindparam, func
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Job, JobEmbedding, AccountingFirm
from .database import get_db, AsyncSessionLocal
import logging
import json
from .config import OPENAI_API_KEY
import traceback
import time
from datetime import datetime, UTC
from sqlalchemy.types import ARRAY, Float, String, Integer
from pgvector.sqlalchemy import Vector
import os
import numpy as np
from functools import partial

logger = logging.getLogger(__name__)

async def generate_job_embedding(text: str) -> List[float]:
    """Generate embedding for job text using OpenAI's API"""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        # Run the synchronous OpenAI call in a thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.embeddings.create(
                model="text-embedding-ada-002",
                input=[text]  # API expects a list of strings
            )
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating job embedding: {str(e)}")
        raise

def prepare_job_text(job_or_title: Union[Job, str], description: str = None) -> str:
    """
    Prepare job text for embedding by combining relevant fields.
    Can accept either a Job object or title/description strings.
    """
    try:
        if isinstance(job_or_title, Job):
            job = job_or_title
            parts = []
            if job.job_title:
                parts.append(f"Title: {job.job_title}")
            if job.service:
                parts.append(f"Service: {job.service}")
            if job.seniority:
                parts.append(f"Level: {job.seniority}")
            if job.description:
                parts.append(f"Description: {job.description}")
            if job.industry:
                parts.append(f"Industry: {job.industry}")
        else:
            parts = []
            if job_or_title:  # title as string
                parts.append(f"Title: {job_or_title}")
            if description:
                parts.append(f"Description: {description}")
        
        job_text = " | ".join(parts)
        logger.debug(f"Prepared job text (length: {len(job_text)})")
        return job_text
    except Exception as e:
        error_context = {
            "job_id": getattr(job, 'id', None) if isinstance(job_or_title, Job) else None,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        logger.error(f"Error preparing job text: {json.dumps(error_context, indent=2)}")
        raise

async def update_job_embedding(job: Job) -> None:
    """Update embedding for a single job."""
    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"Updating embedding for job ID {job.id}")
            job_text = prepare_job_text(job)
            embedding_vector = await generate_job_embedding(job_text)
            
            # Create new embedding record
            job_embedding = JobEmbedding(
                job_id=job.id,
                embedding=embedding_vector,  # Store as double precision array
                embedding_vector=embedding_vector,
                last_updated=datetime.now(UTC)
            )
            db.add(job_embedding)
            await db.commit()
            logger.info(f"Successfully updated embedding for job ID {job.id}")
        except Exception as e:
            await db.rollback()
            error_context = {
                "job_id": getattr(job, 'id', None),
                "job_title": getattr(job, 'job_title', None),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            logger.error(f"Error updating job embedding: {json.dumps(error_context, indent=2)}")
            raise

async def update_all_job_embeddings(db: AsyncSession, batch_size: int = 50) -> None:
    """Update embeddings for all jobs in batches."""
    try:
        # Get jobs without embeddings using a left join
        query = select(Job).outerjoin(JobEmbedding).where(JobEmbedding.id.is_(None))
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        total_jobs = len(jobs)
        logger.info(f"Found {total_jobs} jobs needing embeddings")
        
        # Process in batches
        for i in range(0, total_jobs, batch_size):
            batch = jobs[i:i + batch_size]
            batch_start = i + 1
            batch_end = min(i + batch_size, total_jobs)
            
            logger.info(f"Processing batch {i//batch_size + 1} (jobs {batch_start}-{batch_end} of {total_jobs})")
            
            try:
                tasks = [update_job_embedding(job) for job in batch]
                await asyncio.gather(*tasks)
                logger.info(f"Successfully processed batch {i//batch_size + 1}")
            except Exception as batch_error:
                error_context = {
                    "batch_number": i//batch_size + 1,
                    "batch_start": batch_start,
                    "batch_end": batch_end,
                    "error_type": type(batch_error).__name__,
                    "error_message": str(batch_error),
                    "traceback": traceback.format_exc()
                }
                logger.error(f"Error processing batch: {json.dumps(error_context, indent=2)}")
                # Continue with next batch instead of failing completely
                continue
            
        logger.info(f"Finished updating all job embeddings. Processed {total_jobs} jobs.")
    except Exception as e:
        error_context = {
            "total_jobs": total_jobs if 'total_jobs' in locals() else None,
            "batch_size": batch_size,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        logger.error(f"Error in batch embedding update: {json.dumps(error_context, indent=2)}")
        raise

async def semantic_job_search(query_text: str, location: str = None, limit: int = 5, db: AsyncSession = None) -> List[Dict]:
    if not query_text:
        raise ValueError("Query text cannot be empty")
    if limit <= 0:
        raise ValueError("Limit must be positive")

    try:
        # Check if OpenAI API key is configured
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key is not configured")
            raise ValueError("OpenAI API key is not configured. Please check your environment variables.")

        # Verify database connection
        if not db or not db.is_active:
            logger.error("Database session is not active")
            raise RuntimeError("Database connection is not active. Please try again later.")

        # Generate query embedding
        try:
            logger.info(f"Generating embedding for query: {query_text}")
            query_embedding = await generate_job_embedding(query_text)
            logger.info("Successfully generated query embedding")
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}", exc_info=True)
            if "invalid api key" in str(e).lower():
                raise RuntimeError("Invalid OpenAI API key. Please check your configuration.")
            elif "rate limit" in str(e).lower():
                raise RuntimeError("OpenAI API rate limit exceeded. Please try again in a few moments.")
            else:
                raise RuntimeError(f"Failed to generate embedding: {str(e)}")

        location_pattern = f"%{location.lower()}%" if location else None

        # Check if job_embeddings table exists and has data
        try:
            logger.info("Checking job embeddings table...")
            count_query = select(func.count()).select_from(JobEmbedding)
            embedding_count = await db.scalar(count_query)
            logger.info(f"Found {embedding_count} job embeddings")
            
            if embedding_count == 0:
                raise RuntimeError("No job embeddings found in database. The system needs initialization.")
        except Exception as e:
            logger.error(f"Failed to check job embeddings: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to check job embeddings: {str(e)}")

        # Build query using sqlalchemy-pgvector
        query = select(
            Job.id,
            Job.job_title,
            Job.seniority,
            Job.service,
            Job.industry,
            Job.location,
            Job.employment,
            Job.salary,
            Job.description,
            Job.link,
            Job.created_at,
            AccountingFirm.name.label('firm_name'),
            func.l2_distance(JobEmbedding.embedding_vector, query_embedding).label('similarity')
        ).select_from(JobEmbedding).join(
            Job, JobEmbedding.job_id == Job.id
        ).join(
            AccountingFirm, Job.firm_id == AccountingFirm.id
        ).where(
            JobEmbedding.embedding_vector.is_not(None)
        ).order_by(
            'similarity'
        ).limit(limit)

        # Add location filter if provided
        if location_pattern:
            query = query.where(func.lower(Job.location).like(location_pattern))
            logger.info(f"Added location filter: {location}")

        logger.info("Starting semantic search with params: %s", json.dumps({
            "query_text": query_text,
            "location": location,
            "limit": limit,
            "query_length": len(query_text),
            "timestamp": datetime.now(UTC).isoformat()
        }, default=str))

        try:
            result = await db.execute(query)
            jobs = result.mappings().all()
            
            if not jobs:
                logger.info("No jobs found matching the search criteria")
                if location_pattern:
                    # Check if location is the limiting factor
                    location_count = await db.scalar(
                        select(func.count())
                        .select_from(Job)
                        .where(func.lower(Job.location).like(location_pattern))
                    )
                    if location_count == 0:
                        raise ValueError(f"No jobs found in location: {location}")
            
            logger.info(f"Found {len(jobs)} matching jobs")
            return [dict(job) for job in jobs]

        except Exception as e:
            logger.error(f"Failed to execute search query: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to execute search query: {str(e)}")

    except Exception as e:
        logger.error("Query execution error: %s", str(e.__class__.__name__) + ": " + str(e))
        logger.error("Error details: %s", traceback.format_exc())
        
        error_info = {
            "error_type": e.__class__.__name__,
            "error_message": str(e),
            "query_params": {
                "embedding_type": type(query_embedding).__name__ if 'query_embedding' in locals() else None,
                "embedding_length": len(query_embedding) if 'query_embedding' in locals() else None,
                "location_pattern": location_pattern if 'location_pattern' in locals() else None,
                "limit": limit,
                "query": str(query) if 'query' in locals() else None
            },
            "traceback": traceback.format_exc(),
            "database_info": {
                "session_class": db.__class__.__name__,
                "is_active": db.is_active if hasattr(db, 'is_active') else None
            }
        }
        logger.error("Query execution failed: %s", json.dumps(error_info, default=str, indent=2))
        raise 