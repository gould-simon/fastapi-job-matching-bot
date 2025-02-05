import pytest
import asyncio
import os
import tempfile
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import AccountingFirm, Job, JobEmbedding, User, UserSearch, UserConversation, JobMatch
from app.embeddings import update_job_embedding, generate_job_embedding, prepare_job_text
from sqlalchemy.sql import text
from datetime import datetime, UTC, timedelta
from typing import List, AsyncGenerator, Generator
import pytest_asyncio
import json
import logging
from pathlib import Path

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files.
    
    Returns:
        Path to temporary directory that will be cleaned up after tests
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)

@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def db_engine(temp_dir: Path):
    """Create a test database engine with SQLite.
    
    Args:
        temp_dir: Temporary directory for database file
        
    Returns:
        SQLAlchemy engine configured for testing
    """
    db_path = temp_dir / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    logger.info(f"Creating test database at {db_path}")

    # Configure SQLite with appropriate settings
    engine = create_async_engine(
        db_url,
        echo=True,  # Log all SQL
        future=True,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,  # Increase timeout for table creation
        }
    )
    
    try:
        # Create all tables in a single transaction
        async with engine.begin() as conn:
            # Enable foreign key support
            await conn.execute(text("PRAGMA foreign_keys = ON;"))
            
            logger.info("Dropping existing tables...")
            await conn.run_sync(Base.metadata.drop_all)
            
            # Create custom SQLite functions for array and JSON handling
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS jobsapp_accountingfirm (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(1000) NOT NULL,
                    slug VARCHAR(1000) NOT NULL,
                    link VARCHAR(1000) NOT NULL,
                    twitter_link VARCHAR(1000),
                    linkedin_link VARCHAR(1000),
                    location VARCHAR(10000),
                    ranking INTEGER,
                    about TEXT,
                    script VARCHAR(1000),
                    logo VARCHAR(1000),
                    country VARCHAR(100),
                    jobs_count INTEGER,
                    last_scraped TIMESTAMP,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))
            
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS jobsapp_job (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    firm_id INTEGER NOT NULL,
                    job_title VARCHAR(1000) NOT NULL,
                    seniority VARCHAR(1000),
                    service VARCHAR(1000),
                    industry VARCHAR(1000),
                    location VARCHAR(5000),
                    employment VARCHAR(1000),
                    salary VARCHAR(1000),
                    description TEXT,
                    link VARCHAR(400),
                    created_at TIMESTAMP,
                    date_published TIMESTAMP,
                    req_no VARCHAR(100),
                    FOREIGN KEY (firm_id) REFERENCES jobsapp_accountingfirm(id)
                )
            """))
            
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    cv_text TEXT,
                    cv_embedding TEXT,
                    preferences TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id BIGINT NOT NULL,
                    search_query TEXT NOT NULL,
                    structured_preferences TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
                )
            """))
            
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id BIGINT NOT NULL,
                    message TEXT NOT NULL,
                    is_user BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
                )
            """))
            
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS job_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id BIGINT NOT NULL,
                    job_id INTEGER NOT NULL,
                    similarity_score FLOAT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
                    FOREIGN KEY (job_id) REFERENCES jobsapp_job(id)
                )
            """))
            
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS job_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL UNIQUE,
                    embedding TEXT,
                    embedding_vector TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobsapp_job(id)
                )
            """))
            
            # Create indexes
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_job_matches_telegram_id ON job_matches(telegram_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_job_matches_job_id ON job_matches(job_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_job_embeddings_job_id ON job_embeddings(job_id)"))
            
            # Verify tables were created
            logging.info("Verifying table creation...")
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
            tables = {row[0] for row in result.fetchall()}
            expected_tables = {'jobsapp_accountingfirm', 'jobsapp_job', 'users', 'user_searches',
                             'user_conversations', 'job_matches', 'job_embeddings'}
            if not expected_tables.issubset(tables):
                missing_tables = expected_tables - tables
                raise Exception(f"Missing tables: {missing_tables}")
        
        yield engine
    
    finally:
        # Cleanup
        logger.info("Cleaning up test database...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
        logger.info("Test database cleanup complete")

@pytest_asyncio.fixture(scope="function")
async def db_session(temp_dir):
    """Create a clean test database for each test."""
    # Create test database
    test_db_path = temp_dir / "test.db"
    logging.info(f"Creating test database at {test_db_path}")
    
    # Create SQLite engine
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{test_db_path}",
        echo=True
    )

    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys = ON;"))
        
        # Drop existing tables
        logging.info("Dropping existing tables...")
        for table in ['jobsapp_accountingfirm', 'jobsapp_job', 'users', 'user_searches', 
                     'user_conversations', 'job_matches', 'job_embeddings']:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        
        # Create tables with SQLite-compatible types
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS jobsapp_accountingfirm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                link TEXT NOT NULL,
                twitter_link TEXT,
                linkedin_link TEXT,
                location TEXT,
                ranking INTEGER,
                about TEXT,
                script TEXT,
                logo TEXT,
                country TEXT,
                jobs_count INTEGER,
                last_scraped TIMESTAMP,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS jobsapp_job (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                firm_id INTEGER NOT NULL,
                job_title TEXT NOT NULL,
                seniority TEXT,
                service TEXT,
                industry TEXT,
                location TEXT,
                employment TEXT,
                salary TEXT,
                description TEXT,
                link TEXT,
                created_at TIMESTAMP,
                date_published TIMESTAMP,
                req_no TEXT,
                FOREIGN KEY (firm_id) REFERENCES jobsapp_accountingfirm(id)
            )
        """))
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                cv_text TEXT,
                cv_embedding TEXT,
                preferences TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                search_query TEXT NOT NULL,
                structured_preferences TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            )
        """))
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                is_user BOOLEAN NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            )
        """))
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS job_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                similarity_score REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
                FOREIGN KEY (job_id) REFERENCES jobsapp_job(id)
            )
        """))
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS job_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL UNIQUE,
                embedding TEXT,
                embedding_vector TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobsapp_job(id)
            )
        """))
        
        # Create indices
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_job_matches_telegram_id ON job_matches(telegram_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_job_matches_job_id ON job_matches(job_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_job_embeddings_job_id ON job_embeddings(job_id)"))
        
        # Verify tables were created
        logging.info("Verifying table creation...")
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        tables = {row[0] for row in result.fetchall()}
        logging.info(f"Created tables: {tables}")

    # Create session factory
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create and yield a session
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    # Cleanup
    logging.info("Cleaning up test database...")
    async with engine.begin() as conn:
        for table in reversed(['job_embeddings', 'job_matches', 'user_conversations', 
                             'user_searches', 'jobsapp_job', 'users', 'jobsapp_accountingfirm']):
            await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
    logging.info("Test database cleanup complete")

@pytest_asyncio.fixture
async def test_firm(db_session):
    """Create a test accounting firm."""
    firm = AccountingFirm(
        name="Test Firm",
        slug="test-firm",
        link="https://testfirm.com",
        twitter_link="https://twitter.com/testfirm",
        linkedin_link="https://linkedin.com/company/testfirm",
        location="New York, USA",
        ranking=1,
        about="Test Firm Description",
        script="testfirm.py",
        logo="testfirm.png",
        country="USA",
        jobs_count=0,
        last_scraped=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    db_session.add(firm)
    await db_session.commit()
    await db_session.refresh(firm)
    return firm

@pytest_asyncio.fixture
async def test_jobs(db_session, test_firm):
    """Create test job listings."""
    jobs = []
    for i in range(3):
        job = Job(
            firm_id=test_firm.id,
            job_title=f"Test Job {i}",
            seniority="Senior",
            service="Audit",
            industry="Financial Services",
            location="New York, USA",
            employment="Full-time",
            salary="$100,000 - $150,000",
            description=f"Test job description {i}",
            link=f"https://testfirm.com/jobs/{i}",
            created_at=datetime.now(UTC) - timedelta(days=i),
            date_published=datetime.now(UTC) - timedelta(days=i),
            req_no=f"REQ-{i}"
        )
        jobs.append(job)
    
    db_session.add_all(jobs)
    await db_session.commit()
    for job in jobs:
        await db_session.refresh(job)
    return jobs

@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        telegram_id=12345,
        username="test_user",
        first_name="Test",
        last_name="User",
        cv_text="Sample CV text"
    )
    # Set CV embedding and preferences using JSON strings for SQLite compatibility
    user.cv_embedding = json.dumps([0.1, 0.2, 0.3])
    user.preferences = json.dumps({"location": "New York", "role": "Auditor"})
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture
async def test_user_search(db_session, test_user):
    """Create a test user search."""
    search = UserSearch(
        telegram_id=test_user.telegram_id,
        search_query="Senior Auditor position",
        structured_preferences=json.dumps({"location": "New York", "seniority": "Senior"})
    )
    db_session.add(search)
    await db_session.commit()
    await db_session.refresh(search)
    return search

@pytest_asyncio.fixture
async def test_user_conversation(db_session, test_user):
    """Create test user conversations."""
    conversations = []
    messages = [
        ("Hi, I'm looking for a job", True),
        ("I can help you find a job. Please upload your CV.", False),
        ("Here's my CV", True),
        ("Thanks, I've processed your CV. What kind of job are you looking for?", False)
    ]
    
    for message, is_user in messages:
        conv = UserConversation(
            telegram_id=test_user.telegram_id,
            message=message,
            is_user=is_user,
            created_at=datetime.now(UTC)
        )
        conversations.append(conv)
    
    db_session.add_all(conversations)
    await db_session.commit()
    for conv in conversations:
        await db_session.refresh(conv)
    return conversations

@pytest_asyncio.fixture
async def test_job_matches(db_session, test_user, test_jobs):
    """Create test job matches."""
    matches = []
    for i, job in enumerate(test_jobs):
        match = JobMatch(
            telegram_id=test_user.telegram_id,
            job_id=job.id,
            similarity_score=0.8 - (i * 0.1)
        )
        matches.append(match)
    
    db_session.add_all(matches)
    await db_session.commit()
    for match in matches:
        await db_session.refresh(match)
    return matches 