import os
import logging
import json
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
import traceback
from typing import Dict, Any, Optional

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for logs."""
    def format(self, record):
        log_obj = {
            "message": record.getMessage(),
            "logger_name": record.name,
            "environment": os.getenv("ENVIRONMENT", "development"),
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "is_test": os.getenv("TESTING", "false").lower() == "true",
        }
        
        # Add extra fields if they exist
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        if hasattr(record, "path"):
            log_obj["path"] = record.path
        if hasattr(record, "method"):
            log_obj["method"] = record.method
        if hasattr(record, "duration"):
            log_obj["duration"] = record.duration
        if hasattr(record, "error_type"):
            log_obj["error_type"] = record.error_type
        
        # Add file and line information
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        
        if record.stack_info:
            log_obj["stack_info"] = self.formatStack(record.stack_info)
            
        log_obj["file"] = record.filename
        log_obj["line"] = record.lineno
        log_obj["function"] = record.funcName
        
        return json.dumps(log_obj)

class ErrorContextFilter(logging.Filter):
    """Filter that adds context to error logs."""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, 'error_context'):
            record.error_context = {}
        return True

def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # Only set up file logging in development
    if os.getenv("ENVIRONMENT", "development") != "production":
        try:
            # Create logs directory if it doesn't exist
            os.makedirs('logs', exist_ok=True)
            
            # Add file handler
            file_handler = logging.FileHandler(
                f"logs/{name}.log",
                mode='a',
                encoding='utf-8'
            )
            file_handler.setFormatter(JSONFormatter())
            logger.addHandler(file_handler)
            
        except Exception as e:
            # If file logging fails, log to console only
            logger.warning(
                f"Failed to set up file logging: {str(e)}. Using console logging only."
            )
    
    return logger

def log_error(logger: logging.Logger, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an error with enhanced context and formatting.
    
    Args:
        logger: The logger instance to use
        error: The exception to log
        context: Additional context to include in the log
    """
    error_context = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc()
    }
    
    if context:
        error_context.update(context)
    
    logger.error(
        f"{type(error).__name__}: {str(error)}",
        extra={
            'error_context': error_context,
            'environment': os.getenv('ENVIRONMENT', 'development')
        },
        exc_info=True
    )

# Initialize loggers
api_logger = get_logger("api")
bot_logger = get_logger("bot")
db_logger = get_logger("db") 