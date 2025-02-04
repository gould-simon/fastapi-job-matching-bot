import os
from dotenv import load_dotenv

print("=== Environment Check ===")

# Print current directory
print("\n1. Current working directory:", os.getcwd())

# Check if .env file exists
env_path = os.path.join(os.getcwd(), '.env')
print("\n2. Checking .env file:")
print(f"   Path: {env_path}")
print(f"   Exists: {os.path.exists(env_path)}")

if os.path.exists(env_path):
    print("\n3. .env file contents (with byte representation):")
    with open(env_path, 'rb') as f:
        content = f.read()
        print(f"Raw bytes: {content}")
        print(f"Decoded: {content.decode('utf-8')}")

# Load .env file
print("\n4. Loading .env file...")
load_dotenv(override=True)

# Get DATABASE_URL
print("\n5. Reading DATABASE_URL:")
db_url = os.getenv("DATABASE_URL")
print(f"   Value: {db_url}")
print(f"   Type: {type(db_url)}")
print(f"   Length: {len(db_url) if db_url else 0}")

# Parse URL components if present
if db_url:
    from urllib.parse import urlparse
    parsed = urlparse(db_url)
    print("\n6. Parsed components:")
    print(f"   Scheme: {parsed.scheme}")
    print(f"   Username: {parsed.username}")
    print(f"   Password: {'*' * len(parsed.password) if parsed.password else None}")
    print(f"   Hostname: {parsed.hostname}")
    print(f"   Port: {parsed.port}")
    print(f"   Path: {parsed.path}")

print("\n=== End Environment Check ===") 