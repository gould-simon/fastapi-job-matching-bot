from app.database import AsyncSessionLocal, test_database_connection, list_all_tables
from app.models import Job, JobEmbedding, AccountingFirm
import asyncio
from sqlalchemy import text
from app.logging_config import get_logger
import os
from datetime import datetime

# Get logger for this script
logger = get_logger('db_check')

async def check_db():
    """Check database connection and table status."""
    try:
        # Log environment information
        environment = os.getenv('ENVIRONMENT', 'development')
        logger.info("Starting database check", extra={
            'environment': environment,
            'timestamp': datetime.utcnow().isoformat()
        })

        async with AsyncSessionLocal() as session:
            try:
                # Test basic connection
                await session.execute(text('SELECT version()'))
                logger.info("Database connection successful")

                # Check jobs table
                jobs = await session.execute(text('SELECT COUNT(*) FROM "JobsApp_job"'))
                job_count = jobs.scalar()
                logger.info("Jobs table check", extra={'count': job_count})

                # Check firms table
                firms = await session.execute(text('SELECT COUNT(*) FROM "JobsApp_accountingfirm"'))
                firm_count = firms.scalar()
                logger.info("Firms table check", extra={'count': firm_count})

                # Check embeddings table
                embeddings = await session.execute(text('SELECT COUNT(*) FROM job_embeddings'))
                embedding_count = embeddings.scalar()
                logger.info("Embeddings table check", extra={'count': embedding_count})

                # Print summary
                print(f'\nDatabase Status ({environment.upper()} Environment):')
                print(f'Jobs: {job_count}')
                print(f'Firms: {firm_count}')
                print(f'Embeddings: {embedding_count}')

                # Check for potential issues
                if job_count == 0:
                    logger.warning("No jobs found in database", extra={
                        'table': 'JobsApp_job',
                        'action_needed': 'Run job scraper'
                    })
                    print("\n⚠️ No jobs found in the database. The job scraper needs to be run.")

                if embedding_count == 0:
                    logger.warning("No job embeddings found", extra={
                        'table': 'job_embeddings',
                        'action_needed': 'Generate embeddings'
                    })
                    print("\n⚠️ No job embeddings found. The embedding generation process needs to be run.")

                if embedding_count < job_count:
                    logger.warning("Missing embeddings for some jobs", extra={
                        'jobs': job_count,
                        'embeddings': embedding_count,
                        'missing': job_count - embedding_count
                    })
                    print(f"\n⚠️ Missing embeddings for {job_count - embedding_count} jobs.")

                # Check database connection and schema
                is_connected, message = await test_database_connection()
                if not is_connected:
                    logger.error("Database schema verification failed", extra={'message': message})
                    print(f"\n❌ {message}")
                else:
                    logger.info("Database schema verification successful")
                    print("\n✅ Database schema verification successful")

            except Exception as e:
                logger.error("Database query error", extra={
                    'error': str(e),
                    'error_type': type(e).__name__
                })
                print(f'\n❌ Error checking database: {str(e)}')
                raise

    except Exception as e:
        logger.error("Database connection error", extra={
            'error': str(e),
            'error_type': type(e).__name__,
            'environment': environment
        })
        print(f'\n❌ Error connecting to database: {str(e)}')
        raise

if __name__ == "__main__":
    try:
        asyncio.run(check_db())
    except KeyboardInterrupt:
        print("\nDatabase check interrupted by user.")
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        exit(1) 