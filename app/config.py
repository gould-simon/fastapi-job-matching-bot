from dotenv import load_dotenv
import os
import logging

logger = logging.getLogger(__name__)

# Print current working directory
print("Current working directory:", os.getcwd())

# Force reload environment variables
load_dotenv(override=True)

# Fetch environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

if "username:password@host:port" in DATABASE_URL:
    raise ValueError("DATABASE_URL contains placeholder values. Please set the actual database URL in .env file")

# Debug output
logger.info(f"Environment file loaded: {os.path.exists('.env')}")
logger.info(f"DATABASE_URL type: {type(DATABASE_URL)}")
logger.info(f"DATABASE_URL starts with: {DATABASE_URL[:30]}...")  # Show just the start for security

# Debugging output
print("Loaded DATABASE_URL:", DATABASE_URL)  # Should print the full database URL
