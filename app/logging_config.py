import logging
import json
from datetime import datetime
from typing import Any, Dict
from fastapi import Request, Response
import time
from logging.handlers import RotatingFileHandler
import os
from pythonjsonlogger import jsonlogger

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

class CustomJSONFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name

def setup_api_logging():
    """Configure JSON logging for API monitoring"""
    logger = logging.getLogger("api")
    logger.setLevel(logging.INFO)
    
    # Create JSON formatter
    formatter = CustomJSONFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    
    # File handler for API logs
    file_handler = RotatingFileHandler(
        'logs/api.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create API logger instance
api_logger = setup_api_logging()

class APILoggingMiddleware:
    async def __call__(self, request: Request, call_next) -> Response:
        start_time = time.time()
        
        # Log request
        request_body = await self._get_request_body(request)
        api_logger.info(
            "API Request",
            extra={
                "request": {
                    "method": request.method,
                    "url": str(request.url),
                    "headers": dict(request.headers),
                    "body": request_body,
                    "client_ip": request.client.host if request.client else None,
                },
                "event_type": "api_request"
            }
        )
        
        # Process the request
        try:
            response = await call_next(request)
            response_body = await self._get_response_body(response)
            
            # Log response
            api_logger.info(
                "API Response",
                extra={
                    "response": {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": response_body,
                    },
                    "duration_ms": round((time.time() - start_time) * 1000, 2),
                    "event_type": "api_response"
                }
            )
            
            return response
            
        except Exception as e:
            api_logger.error(
                "API Error",
                extra={
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                    },
                    "duration_ms": round((time.time() - start_time) * 1000, 2),
                    "event_type": "api_error"
                },
                exc_info=True
            )
            raise
    
    async def _get_request_body(self, request: Request) -> Dict:
        """Safely get request body"""
        try:
            body = await request.json()
            return body
        except:
            return {}
    
    async def _get_response_body(self, response: Response) -> Dict:
        """Safely get response body"""
        try:
            body = response.body.decode()
            return json.loads(body)
        except:
            return {} 