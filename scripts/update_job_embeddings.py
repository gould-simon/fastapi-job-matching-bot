import asyncio
import sys
import os
from pathlib import Path
import json
import time
import traceback

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.embeddings import update_all_job_embeddings
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Configure logging with structured output and rotation."""
    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    log_file = log_dir / "job_embeddings_update.log"
    
    # Setup logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup file handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Setup root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

async def main():
    """Update embeddings for all jobs in the database."""
    logger = setup_logging()
    start_time = time.time()
    
    try:
        logger.info("Starting job embeddings update process")
        
        # Log environment info
        env_info = {
            "python_version": sys.version,
            "platform": sys.platform,
            "script_path": __file__,
            "working_directory": os.getcwd()
        }
        logger.info(f"Environment information: {json.dumps(env_info, indent=2)}")
        
        async with SessionLocal() as db:
            try:
                await update_all_job_embeddings(db)
                
                # Log success metrics
                duration = time.time() - start_time
                metrics = {
                    "status": "success",
                    "duration_seconds": round(duration, 2),
                    "duration_formatted": f"{duration/60:.1f} minutes"
                }
                logger.info(f"Job embeddings update completed: {json.dumps(metrics, indent=2)}")
                
            except Exception as db_error:
                error_context = {
                    "error_type": type(db_error).__name__,
                    "error_message": str(db_error),
                    "traceback": traceback.format_exc(),
                    "duration_seconds": round(time.time() - start_time, 2)
                }
                logger.error(f"Database error during update: {json.dumps(error_context, indent=2)}")
                raise
                
    except Exception as e:
        error_context = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
            "duration_seconds": round(time.time() - start_time, 2)
        }
        logger.error(f"Critical error in update process: {json.dumps(error_context, indent=2)}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(1) 