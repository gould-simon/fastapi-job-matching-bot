import os
import logging
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
import traceback
from typing import Dict, Any, Optional

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp if not present
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add log level
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
            
        # Add file and line number
        log_record['file'] = record.filename
        log_record['line'] = record.lineno
        
        # Add exception info if present
        if record.exc_info:
            log_record['exc_info'] = self.formatException(record.exc_info)
            log_record['exc_type'] = record.exc_info[0].__name__
            
        # Add stack trace for errors
        if record.levelno >= logging.ERROR:
            log_record['stack_trace'] = traceback.format_stack()

class ErrorContextFilter(logging.Filter):
    """Filter that adds context to error logs."""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, 'error_context'):
            record.error_context = {}
        return True

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name and enhanced configuration."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:  # Only add handlers if they don't exist
        logger.setLevel(logging.DEBUG)
        
        # Create console handler with basic formatting
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # Create JSON file handler for detailed logging
        json_handler = RotatingFileHandler(
            'logs/app.json',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        json_handler.setLevel(logging.DEBUG)
        json_formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
        json_handler.setFormatter(json_formatter)
        
        # Create separate error log handler
        error_handler = RotatingFileHandler(
            'logs/error.log',
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(json_formatter)
        
        # Add handlers
        logger.addHandler(console_handler)
        logger.addHandler(json_handler)
        logger.addHandler(error_handler)
        
        # Add context filter
        logger.addFilter(ErrorContextFilter())
    
    return logger

def log_error(logger: logging.Logger, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an error with enhanced context and formatting.
    
    Args:
        logger: The logger instance to use
        error: The exception to log
        context: Additional context to include in the log
    """
    error_info = {
        'error_type': error.__class__.__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'context': context or {}
    }
    
    logger.error(
        f"Error occurred: {error}",
        extra={
            'error_context': error_info
        },
        exc_info=True
    )

# Create main application logger
api_logger = get_logger('api')
bot_logger = get_logger('bot')
db_logger = get_logger('db') 