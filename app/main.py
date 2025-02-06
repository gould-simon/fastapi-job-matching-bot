import os
from typing import List
import uuid
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time
from sqlalchemy.sql import text
import psutil
from datetime import datetime

from app.database import get_db, test_database_connection
from app.services.embedding_service import EmbeddingService
from app.services.search_service import SearchService
from app.tasks.embedding_tasks import start_embedding_tasks
from app.logging_config import api_logger

# Initialize metrics
request_count = Counter('http_requests_total', 'Total HTTP requests')
request_latency = Histogram('http_request_duration_seconds', 'HTTP request duration')
error_count = Counter('http_errors_total', 'Total HTTP errors')

app = FastAPI(
    title="Job Matching Bot API",
    description="AI-powered job matching service with CV processing capabilities",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
embedding_service = EmbeddingService(os.getenv("OPENAI_API_KEY"))
search_service = SearchService(embedding_service)

@app.middleware("http")
async def add_request_tracking(request: Request, call_next):
    """Add request tracking and metrics."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Start timer and increment request counter
    start_time = time.time()
    request_count.inc()
    
    try:
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        # Record request duration
        duration = time.time() - start_time
        request_latency.observe(duration)
        
        return response
    except Exception as e:
        # Record error and duration
        error_count.inc()
        duration = time.time() - start_time
        request_latency.observe(duration)
        
        # Log error with context
        api_logger.error(
            f"Request failed: {str(e)}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "duration": duration,
            },
            exc_info=True
        )
        raise

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    error_count.inc()
    
    # Get request ID from state
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    # Log error with context
    api_logger.error(
        f"Unhandled error: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__
        },
        exc_info=True
    )
    
    # Return appropriate error response
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": request_id}
        )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id
        }
    )

@app.get("/")
async def root():
    """Root endpoint to check if the API is running"""
    return {"message": "Hello, FastAPI is working!"}

class SearchPreferences(BaseModel):
    location: str = None
    seniority: str = None
    service: str = None
    industry: str = None
    employment: str = None
    salary: str = None

class JobResponse(BaseModel):
    id: int
    job_title: str
    location: str
    seniority: str
    service: str
    industry: str
    employment: str
    salary: str
    description: str
    link: str
    similarity_score: float = None

    class Config:
        from_attributes = True

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup"""
    await start_embedding_tasks()

@app.post("/search/", response_model=List[JobResponse])
async def search_jobs(
    query: str,
    preferences: SearchPreferences = None,
    telegram_id: int = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Search for jobs using semantic search"""
    if not telegram_id:
        raise HTTPException(status_code=400, detail="telegram_id is required")
    
    jobs = await search_service.search_jobs(
        session=db,
        telegram_id=telegram_id,
        query=query,
        preferences=preferences.dict() if preferences else None,
        limit=limit
    )
    
    return [
        JobResponse(
            id=job.id,
            job_title=job.job_title,
            location=job.location,
            seniority=job.seniority,
            service=job.service,
            industry=job.industry,
            employment=job.employment,
            salary=job.salary,
            description=job.description,
            link=job.link,
            similarity_score=score
        )
        for job, score in jobs
    ]

@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific job by ID"""
    job = await search_service.get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse(
        id=job.id,
        job_title=job.job_title,
        location=job.location,
        seniority=job.seniority,
        service=job.service,
        industry=job.industry,
        employment=job.employment,
        salary=job.salary,
        description=job.description,
        link=job.link
    )

@app.get("/matches/{telegram_id}", response_model=List[JobResponse])
async def get_recent_matches(
    telegram_id: int,
    limit: int = 5,
    db: AsyncSession = Depends(get_db)
):
    """Get recent job matches for a user"""
    matches = await search_service.get_recent_matches(db, telegram_id, limit)
    
    return [
        JobResponse(
            id=job.id,
            job_title=job.job_title,
            location=job.location,
            seniority=job.seniority,
            service=job.service,
            industry=job.industry,
            employment=job.employment,
            salary=job.salary,
            description=job.description,
            link=job.link,
            similarity_score=score
        )
        for job, score in matches
    ]

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check database connection using the test function
        db_healthy, db_message = await test_database_connection()
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Prepare health check response
        health_status = {
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "message": db_message
            },
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent
            }
        }
        
        status_code = 200 if db_healthy else 503
        return JSONResponse(
            content=health_status,
            status_code=status_code
        )
        
    except Exception as e:
        api_logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return JSONResponse(
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            },
            status_code=503
        )

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
