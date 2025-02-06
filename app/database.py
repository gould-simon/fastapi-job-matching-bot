import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import DATABASE_URL
import logging
from urllib.parse import urlparse, urlunparse
from sqlalchemy.sql import text
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy import event
from asyncpg.exceptions import ConnectionDoesNotExistError
import asyncio
import ssl
from app.logging_config import db_logger, log_error

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create Base class for models using SQLAlchemy 2.0 style
class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass

# Database configuration
def get_db_config():
    """Get database configuration with proper SSL and connection settings."""
    config = {
        "future": True,
        "echo": True,
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_pre_ping": True,
        "pool_recycle": 1800,  # Recycle connections after 30 minutes
        "poolclass": AsyncAdaptedQueuePool,
    }
    
    # Add SSL configuration for production
    if os.getenv("ENVIRONMENT") == "production":
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        config["connect_args"] = {"ssl": ssl_context}
    
    return config

# Database environment configuration
def get_environment_info():
    """Get information about the current environment."""
    env = os.getenv("ENVIRONMENT", "development")
    is_test = "pytest" in os.environ.get("PYTEST_CURRENT_TEST", "")
    is_production = env == "production"
    return {
        "environment": env,
        "is_test": is_test,
        "is_production": is_production,
        "database_type": "sqlite" if is_test else "postgresql"
    }

# Get database URL and configuration
def get_database_url():
    """Get the database URL with proper environment handling."""
    env_info = get_environment_info()
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    
    # Log database configuration
    db_logger.info("Database configuration", extra={
        'environment': env_info['environment'],
        'is_test': env_info['is_test'],
        'is_production': env_info['is_production'],
        'database_type': env_info['database_type'],
        'url_prefix': db_url.split("://")[0] if "://" in db_url else "unknown"
    })
    
    if env_info['is_test']:
        db_url = "sqlite+aiosqlite:///./test.db"
        db_logger.info("Using SQLite for testing")
    elif db_url.startswith("postgresql://"):
        parsed = urlparse(db_url)
        
        # Add default port if not specified
        if parsed.port is None:
            host_with_port = f"{parsed.hostname}:5432"
            db_url = db_url.replace(parsed.hostname, host_with_port)
        
        # Handle Render.com PostgreSQL
        if "dpg-" in db_url:
            parsed = urlparse(db_url)
            port = f":{parsed.port}" if parsed.port else ""
            render_hostname = f"{parsed.hostname}.oregon-postgres.render.com{port}"
            db_url = db_url.replace(f"{parsed.hostname}{port}", render_hostname)
        
        # Convert to async driver
        if not db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    return db_url

# Get database configuration
DATABASE_URL = get_database_url()
db_config = get_db_config()

# Create engine with retry logic
engine = create_async_engine(DATABASE_URL, **db_config)

# Add connection event listeners with enhanced logging
@event.listens_for(engine.sync_engine, "connect")
def connect(dbapi_connection, connection_record):
    db_logger.info("New database connection established", extra={
        'connection_id': id(dbapi_connection),
        'pool_id': id(connection_record)
    })

@event.listens_for(engine.sync_engine, "checkout")
def checkout(dbapi_connection, connection_record, connection_proxy):
    db_logger.debug("Database connection checked out from pool", extra={
        'connection_id': id(dbapi_connection),
        'pool_id': id(connection_record)
    })

@event.listens_for(engine.sync_engine, "checkin")
def checkin(dbapi_connection, connection_record):
    db_logger.debug("Database connection returned to pool", extra={
        'connection_id': id(dbapi_connection),
        'pool_id': id(connection_record)
    })

@event.listens_for(engine.sync_engine, "reset")
def reset(dbapi_connection, connection_record):
    db_logger.info("Database connection reset", extra={
        'connection_id': id(dbapi_connection),
        'pool_id': id(connection_record)
    })

# Add error handling for connection pool
@event.listens_for(engine.sync_engine, "invalidate")
def invalidate(dbapi_connection, connection_record, exception):
    log_error(db_logger, exception, context={
        'action': 'connection_invalidate',
        'connection_id': id(dbapi_connection),
        'pool_id': id(connection_record)
    })

# Create session factory with custom retry logic
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session with retry logic."""
    retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(retries):
        try:
            async with AsyncSessionLocal() as session:
                try:
                    db_logger.debug("Database session created")
                    yield session
                    await session.commit()
                    db_logger.debug("Session committed successfully")
                except Exception as e:
                    await session.rollback()
                    log_error(db_logger, e, context={
                        'action': 'session_commit',
                        'attempt': attempt + 1
                    })
                    raise
                finally:
                    await session.close()
                    db_logger.debug("Session closed")
        except ConnectionDoesNotExistError as e:
            if attempt == retries - 1:
                log_error(db_logger, e, context={
                    'action': 'connection_retry',
                    'attempt': attempt + 1,
                    'max_retries': retries
                })
                raise
            db_logger.warning(
                f"Database connection failed, retrying in {retry_delay}s",
                extra={
                    'attempt': attempt + 1,
                    'retry_delay': retry_delay,
                    'error': str(e)
                }
            )
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
        except Exception as e:
            log_error(db_logger, e, context={
                'action': 'session_creation',
                'attempt': attempt + 1
            })
            raise

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Dependency to get DB session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session

async def list_all_tables():
    """List all tables in the database"""
    try:
        async with AsyncSessionLocal() as session:
            if DATABASE_URL.startswith("sqlite"):
                query = text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name;
                """)
            else:
                query = text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
            result = await session.execute(query)
            tables = [row[0] for row in result]
            logger.info(f"Found tables: {tables}")
            return tables
    except Exception as e:
        logger.error(f"Error listing tables: {str(e)}")
        return []

async def test_database_connection():
    """Test the database connection and verify schema"""
    env_info = get_environment_info()
    try:
        async with AsyncSessionLocal() as session:
            # Test basic connection
            await session.execute(text("SELECT 1"))
            db_logger.info("✅ Basic database connection successful", extra={
                'environment': env_info['environment'],
                'database_type': env_info['database_type']
            })
            
            # List all tables first
            all_tables = await list_all_tables()
            db_logger.info("Tables in database", extra={
                'tables': all_tables,
                'environment': env_info['environment']
            })
            
            # Check if required tables exist (case-insensitive)
            required_tables = {
                'users', 'jobsapp_job', 'jobsapp_accountingfirm', 
                'user_searches', 'user_conversations', 'job_matches',
                'job_embeddings'
            }
            existing_tables = {t.lower() for t in all_tables}
            missing_tables = required_tables - existing_tables
            
            if missing_tables:
                error_msg = f"Missing required tables: {', '.join(missing_tables)}"
                db_logger.error(error_msg, extra={
                    'existing_tables': list(existing_tables),
                    'missing_tables': list(missing_tables),
                    'environment': env_info['environment']
                })
                return False, error_msg
            
            db_logger.info("✅ All required tables exist", extra={
                'tables': list(existing_tables),
                'environment': env_info['environment']
            })
            return True, "Database connection and schema verification successful"
            
    except Exception as e:
        log_error(db_logger, e, context={
            'action': 'connection_test',
            'environment': env_info['environment'],
            'database_type': env_info['database_type'],
            'database_url': DATABASE_URL.replace(
                urlparse(DATABASE_URL).password, '****'
            ) if urlparse(DATABASE_URL).password else DATABASE_URL
        })
        return False, f"Connection error: {str(e)}"

# Database verification functions
async def verify_database_indexes():
    """Verify that all required indexes exist."""
    async with AsyncSessionLocal() as session:
        # Check and create indexes if needed
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_user_telegram_id ON users(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_job_matches_score ON job_matches(similarity_score)",
            "CREATE INDEX IF NOT EXISTS idx_job_location ON jobsapp_job(location)",
            "CREATE INDEX IF NOT EXISTS idx_job_title ON jobsapp_job(job_title)",
            "CREATE INDEX IF NOT EXISTS idx_user_last_active ON users(last_active)",
            "CREATE INDEX IF NOT EXISTS idx_conversation_created ON user_conversations(created_at)",
        ]
        
        for index in indexes:
            try:
                await session.execute(text(index))
            except Exception as e:
                logger.error(f"Failed to create index: {str(e)}")
                continue
        
        await session.commit()
        logger.info("Database indexes verified")
