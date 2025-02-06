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
            
        # Add environment information
        log_record['environment'] = os.getenv('ENVIRONMENT', 'development')
        log_record['is_test'] = 'pytest' in os.environ.get('PYTEST_CURRENT_TEST', '')
            
        # Add file and line number
        log_record['file'] = record.filename
        log_record['line'] = record.lineno
        log_record['function'] = record.funcName
        
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
    """Get a logger with the specified name and proper configuration."""
    logger = logging.getLogger(name)
    
    # Only configure if handlers haven't been added yet
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Create console handler with a higher log level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(CustomJsonFormatter())
        
        # Create file handler which logs even debug messages
        file_handler = RotatingFileHandler(
            filename=f'logs/{name}.json',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(CustomJsonFormatter())
        
        # Add the handlers to the logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        # Don't propagate to root logger
        logger.propagate = False
        
        # Log initial configuration
        logger.info(
            "Logger configured",
            extra={
                'logger_name': name,
                'handlers': ['console', 'file'],
                'environment': os.getenv('ENVIRONMENT', 'development')
            }
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

# Create main application logger
api_logger = get_logger('api')
bot_logger = get_logger('bot')
db_logger = get_logger('db') 