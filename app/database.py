from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.config import DATABASE_URL
import logging
from urllib.parse import urlparse, urlunparse
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set to DEBUG for more detailed logs

# Create Base class for models
Base = declarative_base()

# Ensure DATABASE_URL is set and properly formatted
if DATABASE_URL is None:
    raise ValueError("❌ DATABASE_URL is not set. Check your .env file!")

# Parse the URL and add default port if not specified
parsed = urlparse(DATABASE_URL)
logger.debug(f"Initial database URL components: scheme={parsed.scheme}, hostname={parsed.hostname}, path={parsed.path}")

if parsed.port is None:
    # Add default PostgreSQL port (5432) if not specified
    host_with_port = f"{parsed.hostname}:5432"
    DATABASE_URL = DATABASE_URL.replace(parsed.hostname, host_with_port)
    logger.info("Added default port 5432 to DATABASE_URL")

# For Render's PostgreSQL, ensure we're using the correct hostname
if "dpg-" in DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    # Extract the port if it exists
    port = f":{parsed.port}" if parsed.port else ""
    # Use the full Render hostname
    render_hostname = f"{parsed.hostname}.oregon-postgres.render.com{port}"
    # Reconstruct the URL with the new hostname
    DATABASE_URL = DATABASE_URL.replace(f"{parsed.hostname}{port}", render_hostname)
    logger.info(f"Using Render PostgreSQL hostname: {render_hostname}")

# Convert standard postgresql:// to postgresql+asyncpg:// if needed
if DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://', 1)
    logger.info("Converted DATABASE_URL to use asyncpg driver")

# Log final database connection details (without credentials)
final_parsed = urlparse(DATABASE_URL)
safe_url = f"{final_parsed.scheme}://{final_parsed.hostname}:{final_parsed.port}{final_parsed.path}"
logger.info(f"Final database connection URL (without credentials): {safe_url}")

# Create async database engine with connection pooling
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    connect_args={
        "command_timeout": 30,  # 30 seconds command timeout
        "server_settings": {
            "application_name": "FastAPI Job Bot",
            "statement_timeout": "30000",  # 30 seconds statement timeout
            "idle_in_transaction_session_timeout": "30000"  # 30 seconds idle timeout
        }
    }
)

# Create session factory with proper configuration
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def list_all_tables():
    """List all tables in the database"""
    try:
        async with SessionLocal() as session:
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
    try:
        async with SessionLocal() as session:
            # Test basic connection
            await session.execute(text("SELECT 1"))
            logger.info("✅ Basic database connection successful")
            
            # List all tables first
            all_tables = await list_all_tables()
            logger.info(f"All tables in database: {all_tables}")
            
            # Check if required tables exist
            tables_query = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('JobsApp_job', 'JobsApp_accountingfirm', 'users', 'user_searches')
            """)
            result = await session.execute(tables_query)
            existing_tables = set(row[0] for row in result)
            required_tables = {'JobsApp_job', 'JobsApp_accountingfirm', 'users', 'user_searches'}
            missing_tables = required_tables - existing_tables
            
            if missing_tables:
                logger.error(f"❌ Missing required tables: {', '.join(missing_tables)}")
                logger.info(f"Found tables: {', '.join(existing_tables)}")
                return False, f"Missing required tables: {', '.join(missing_tables)}"
            
            logger.info(f"✅ All required tables exist: {', '.join(existing_tables)}")
            return True, "Database connection and schema verification successful"
            
    except Exception as e:
        error_message = str(e)
        logger.error(f"❌ Database connection test failed: {error_message}", exc_info=True)
        return False, f"Connection error: {error_message}"
