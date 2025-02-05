import asyncio
import logging
import os
from datetime import datetime

from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

async def update_job_embeddings():
    """Background task to update job embeddings"""
    embedding_service = EmbeddingService(os.getenv("OPENAI_API_KEY"))
    
    while True:
        try:
            logger.info("Starting job embedding update task")
            start_time = datetime.utcnow()
            
            # Process jobs in batches
            processed_count = await embedding_service.process_unembedded_jobs(batch_size=50)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Processed {processed_count} jobs in {duration:.2f} seconds")
            
            # Wait for 1 hour before next update
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Error in embedding update task: {e}")
            # Wait for 5 minutes before retrying on error
            await asyncio.sleep(300)

async def start_embedding_tasks():
    """Start background tasks for embedding updates"""
    asyncio.create_task(update_job_embeddings()) 