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

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Debug output
logger.info(f"Environment file loaded: {os.path.exists('.env')}")
logger.info(f"DATABASE_URL type: {type(DATABASE_URL)}")
logger.info(f"DATABASE_URL starts with: {DATABASE_URL[:30]}...")  # Show just the start for security

# Debugging output
print("Loaded DATABASE_URL:", DATABASE_URL)  # Should print the full database URL

# Configure logging based on environment
handlers = [
    logging.StreamHandler(),  # Always log to stdout/stderr
]

# Only add file logging in development
if os.getenv("ENVIRONMENT") != "production":
    try:
        os.makedirs('logs', exist_ok=True)
        handlers.append(
            logging.FileHandler('logs/conversations.log', mode='a', encoding='utf-8')
        )
    except Exception as e:
        print(f"Warning: Could not set up file logging: {e}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=handlers
)
