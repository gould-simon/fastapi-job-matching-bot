from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Fetch environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Debugging output
print("Loaded DATABASE_URL:", DATABASE_URL)  # Should print the full database URL
