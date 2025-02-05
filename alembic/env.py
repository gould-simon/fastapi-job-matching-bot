from logging.config import fileConfig
from sqlalchemy import engine_from_config, MetaData
from sqlalchemy import pool
from alembic import context
from app.database import Base
from app.models import User, UserSearch, UserConversation, JobMatch, JobEmbedding  # Only bot-specific models
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Get database URL
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise ValueError("DATABASE_URL environment variable is not set")

# Convert asyncpg to psycopg2 for Alembic if needed
if "postgresql+asyncpg://" in db_url:
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

# Set the SQLAlchemy URL
config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Create a metadata object that only includes our bot-specific tables
def include_object(object, name, type_, reflected, compare_to):
    """Filter function to include only our bot-specific tables."""
    if type_ == "table":
        return name in {'users', 'user_searches', 'user_conversations', 'job_matches', 'job_embeddings'}
    return True

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Handle the connection with retries
    for i in range(3):  # Try 3 times
        try:
            connectable = engine_from_config(
                config.get_section(config.config_ini_section, {}),
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
            )

            with connectable.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    include_object=include_object
                )

                with context.begin_transaction():
                    context.run_migrations()
            break  # If successful, break the retry loop
        except Exception as e:
            if i == 2:  # Last attempt
                raise  # Re-raise the exception if all retries failed
            logging.warning(f"Migration attempt {i+1} failed: {str(e)}. Retrying...")

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
