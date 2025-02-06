from app.database import AsyncSessionLocal, test_database_connection, list_all_tables, get_environment_info
from app.models import Job, JobEmbedding, AccountingFirm
import asyncio
from sqlalchemy import text
from app.logging_config import get_logger
import os
from datetime import datetime
from typing import Tuple

# Get logger for this script
logger = get_logger('db_check')

async def get_table_count(session, table_name: str, env_info: dict) -> Tuple[int, str]:
    """Get count of records in a table with proper quoting based on database type."""
    try:
        # SQLite doesn't support double quotes for identifiers
        if env_info['database_type'] == 'sqlite':
            result = await session.execute(text(f'SELECT COUNT(*) FROM {table_name}'))
        else:
            result = await session.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
        count = result.scalar()
        return count, None
    except Exception as e:
        error_msg = f"Error counting records in {table_name}: {str(e)}"
        logger.error(error_msg, extra={
            'table': table_name,
            'error': str(e),
            'error_type': type(e).__name__,
            'environment': env_info['environment'],
            'database_type': env_info['database_type']
        })
        return 0, error_msg

async def check_db():
    """Check database connection and table status."""
    try:
        # Get environment information
        env_info = get_environment_info()
        logger.info("Starting database check", extra={
            'environment': env_info['environment'],
            'database_type': env_info['database_type'],
            'is_test': env_info['is_test'],
            'timestamp': datetime.utcnow().isoformat()
        })

        async with AsyncSessionLocal() as session:
            try:
                # Test basic connection
                if env_info['database_type'] == 'sqlite':
                    await session.execute(text('SELECT sqlite_version()'))
                else:
                    await session.execute(text('SELECT version()'))
                logger.info("Database connection successful", extra={'database_type': env_info['database_type']})

                # Check tables
                tables_to_check = [
                    ('JobsApp_job', 'Jobs'),
                    ('JobsApp_accountingfirm', 'Firms'),
                    ('job_embeddings', 'Embeddings'),
                    ('users', 'Users'),
                    ('user_searches', 'Searches'),
                    ('user_conversations', 'Conversations'),
                    ('job_matches', 'Matches')
                ]

                counts = {}
                errors = []

                for table_name, display_name in tables_to_check:
                    count, error = await get_table_count(session, table_name, env_info)
                    counts[display_name] = count
                    if error:
                        errors.append(error)

                # Print summary
                print(f'\nDatabase Status ({env_info["environment"].upper()} Environment):')
                print(f'Database Type: {env_info["database_type"].upper()}')
                for display_name, count in counts.items():
                    print(f'{display_name}: {count}')

                if errors:
                    print("\n⚠️ Errors encountered:")
                    for error in errors:
                        print(f"  • {error}")

                # Check for potential issues
                if counts['Jobs'] == 0:
                    logger.warning("No jobs found in database", extra={
                        'table': 'JobsApp_job',
                        'action_needed': 'Run job scraper',
                        'environment': env_info['environment']
                    })
                    print("\n⚠️ No jobs found in the database. The job scraper needs to be run.")

                if counts['Embeddings'] == 0:
                    logger.warning("No job embeddings found", extra={
                        'table': 'job_embeddings',
                        'action_needed': 'Generate embeddings',
                        'environment': env_info['environment']
                    })
                    print("\n⚠️ No job embeddings found. The embedding generation process needs to be run.")

                if counts['Embeddings'] < counts['Jobs']:
                    missing = counts['Jobs'] - counts['Embeddings']
                    logger.warning("Missing embeddings for some jobs", extra={
                        'jobs': counts['Jobs'],
                        'embeddings': counts['Embeddings'],
                        'missing': missing,
                        'environment': env_info['environment']
                    })
                    print(f"\n⚠️ Missing embeddings for {missing} jobs.")

                # Check database connection and schema
                is_connected, message = await test_database_connection()
                if not is_connected:
                    logger.error("Database schema verification failed", extra={
                        'message': message,
                        'environment': env_info['environment'],
                        'database_type': env_info['database_type']
                    })
                    print(f"\n❌ {message}")
                else:
                    logger.info("Database schema verification successful", extra={
                        'environment': env_info['environment'],
                        'database_type': env_info['database_type']
                    })
                    print("\n✅ Database schema verification successful")

            except Exception as e:
                logger.error("Database query error", extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'environment': env_info['environment'],
                    'database_type': env_info['database_type']
                })
                print(f'\n❌ Error checking database: {str(e)}')
                raise

    except Exception as e:
        logger.error("Database connection error", extra={
            'error': str(e),
            'error_type': type(e).__name__,
            'environment': env_info['environment'],
            'database_type': env_info['database_type']
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