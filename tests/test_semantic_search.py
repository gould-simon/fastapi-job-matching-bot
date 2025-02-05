import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from app.embeddings import (
    generate_job_embedding,
    prepare_job_text,
    update_job_embedding,
    semantic_job_search
)
from app.models import Job, AccountingFirm
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_generate_job_embedding():
    """Test that job embeddings are generated correctly."""
    test_text = "Senior Audit Manager with technology experience"
    embedding = await generate_job_embedding(test_text)
    
    assert isinstance(embedding, list), "Embedding should be a list"
    assert len(embedding) == 1536, "OpenAI ada-002 embeddings should be 1536-dimensional"
    assert all(isinstance(x, float) for x in embedding), "All embedding values should be floats"

@pytest.mark.asyncio
async def test_prepare_job_text():
    """Test that job text is prepared correctly for embedding."""
    test_job = Job(
        job_title="Senior Audit Manager",
        service="Audit",
        seniority="Senior Manager",
        description="Leading audit engagements for technology clients",
        industry="Technology"
    )
    
    job_text = prepare_job_text(test_job)
    
    assert "Title: Senior Audit Manager" in job_text
    assert "Service: Audit" in job_text
    assert "Level: Senior Manager" in job_text
    assert "Description: Leading audit engagements" in job_text
    assert "Industry: Technology" in job_text

@pytest.mark.asyncio
async def test_semantic_search(db_session: AsyncSession, test_jobs):
    """Test that semantic search returns relevant results."""
    session = await anext(db_session)
    query = "Senior Audit Manager in New York"
    results = await semantic_job_search(
        query_text=query,
        location="new york",
        limit=5,
        db=session
    )

    assert len(results) > 0
    assert any("audit" in result["job_title"].lower() for result in results)
    assert all("new york" in result["location"].lower() for result in results)

@pytest.mark.asyncio
async def test_location_filtering(db_session: AsyncSession, test_jobs):
    """Test that location filtering works correctly."""
    session = await anext(db_session)
    query = "audit position"

    # Without location filter
    results_no_location = await semantic_job_search(
        query_text=query,
        limit=5,
        db=session
    )

    # With location filter
    results_with_location = await semantic_job_search(
        query_text=query,
        location="boston",
        limit=5,
        db=session
    )

    assert len(results_no_location) > 0
    assert len(results_with_location) > 0
    assert all("boston" in result["location"].lower() for result in results_with_location)

@pytest.mark.asyncio
async def test_sql_parameter_handling(db_session: AsyncSession, test_jobs):
    """Test that SQL query parameters are handled correctly for various scenarios."""
    session = await anext(db_session)
    # Test with location filter
    results_with_location = await semantic_job_search(
        query_text="audit manager",
        location="new york",
        limit=5,
        db=session
    )

    # Test with NULL location
    results_no_location = await semantic_job_search(
        query_text="audit manager",
        limit=5,
        db=session
    )

    # Test with special characters in location
    results_special_chars = await semantic_job_search(
        query_text="audit manager",
        location="new york's%",
        limit=5,
        db=session
    )

    assert len(results_with_location) > 0
    assert len(results_no_location) > 0
    assert isinstance(results_special_chars, list)

@pytest.mark.asyncio
async def test_error_handling(db_session: AsyncSession, test_jobs):
    """Test that error cases are handled gracefully."""
    session = await anext(db_session)
    # Test with empty query
    with pytest.raises(ValueError, match="Query text cannot be empty"):
        await semantic_job_search(
            query_text="",
            limit=5,
            db=session
        )

    # Test with invalid limit
    with pytest.raises(ValueError, match="Limit must be positive"):
        await semantic_job_search(
            query_text="audit manager",
            limit=0,
            db=session
        )

    # Test with very long query
    long_query = "audit manager " * 1000
    results = await semantic_job_search(
        query_text=long_query,
        limit=5,
        db=session
    )
    assert isinstance(results, list) 