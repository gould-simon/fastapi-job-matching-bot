import pytest
import asyncio
from app.ai_handler import extract_job_preferences, standardize_search_terms
import logging
from typing import Dict, Any
from app.embeddings import semantic_job_search, generate_job_embedding
from app.models import Job, AccountingFirm, JobEmbedding
from sqlalchemy import insert, select
import numpy as np
from datetime import datetime, UTC

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_extract_job_preferences():
    """Test that job preferences are correctly extracted from user input"""
    test_cases = [
        {
            "input": "audit manager in new york",
            "expected": {
                "role": "audit manager",
                "location": "new york",
                "experience": None,
                "salary": None,
                "search_type": "job_title"
            }
        },
        {
            "input": "audit technology roles in new york for manager or director level",
            "expected": {
                "role": "audit technology",
                "location": "new york",
                "experience": "manager or director",
                "salary": None,
                "search_type": "specialized"
            }
        },
        {
            "input": "senior level technology audit jobs in boston",
            "expected": {
                "role": "technology audit",
                "location": "boston",
                "experience": "senior",
                "salary": None,
                "search_type": "specialized"
            }
        }
    ]
    
    for case in test_cases:
        preferences = await extract_job_preferences(case["input"])
        for key, expected_value in case["expected"].items():
            if expected_value is not None:
                assert key in preferences, f"Key {key} not found in preferences"
                assert preferences[key].lower() == expected_value.lower(), \
                    f"Expected {key}='{expected_value}', got '{preferences[key]}'"

@pytest.mark.asyncio
async def test_standardize_search_terms():
    """Test that search terms are correctly standardized for semantic search"""
    test_cases = [
        {
            "input": {
                "role": "audit manager",
                "location": "NY",
                "experience": "manager level",
                "search_type": "job_title"
            },
            "expected": {
                "role": {
                    "standardized": "audit manager",
                    "search_variations": ["audit manager", "audit lead", "audit team manager", "auditing manager"]
                },
                "location": {
                    "standardized": "new york",
                    "search_variations": ["new york", "ny", "nyc"]
                },
                "experience": {
                    "standardized": "manager",
                    "search_variations": ["manager", "management", "managerial", "team lead"]
                }
            }
        },
        {
            "input": {
                "role": "technology audit",
                "location": "boston",
                "experience": "senior",
                "search_type": "specialized"
            },
            "expected": {
                "role": {
                    "standardized": "technology audit",
                    "search_variations": ["technology audit", "it audit", "tech audit", "information technology audit"]
                },
                "location": {
                    "standardized": "boston",
                    "search_variations": ["boston", "ma", "massachusetts"]
                },
                "experience": {
                    "standardized": "senior",
                    "search_variations": ["senior", "senior level", "experienced", "advanced"]
                }
            }
        }
    ]
    
    for case in test_cases:
        standardized = await standardize_search_terms(case["input"])
        assert isinstance(standardized, dict), "Standardized output should be a dictionary"
        
        # Check structure
        for key in ["role", "location", "experience"]:
            if key in case["expected"]:
                assert key in standardized, f"Missing key {key} in standardized output"
                assert "standardized" in standardized[key], f"Missing standardized value for {key}"
                assert "search_variations" in standardized[key], f"Missing search variations for {key}"
                
                # Check standardized value
                assert standardized[key]["standardized"].lower() == case["expected"][key]["standardized"].lower(), \
                    f"Incorrect standardized value for {key}"
                
                # Check that expected variations are included (but allow for additional variations)
                expected_variations = set(v.lower() for v in case["expected"][key]["search_variations"])
                actual_variations = set(v.lower() for v in standardized[key]["search_variations"])
                assert expected_variations.issubset(actual_variations), \
                    f"Missing expected variations for {key}. Expected {expected_variations} to be subset of {actual_variations}"

@pytest.mark.asyncio
async def test_semantic_job_search(db_session):
    """Test that semantic job search works correctly"""
    # Create test firm and job
    firm = AccountingFirm(
        name="Test Firm",
        location="New York, USA",
        slug="test-firm",
        link="https://testfirm.com",
        twitter_link="https://twitter.com/testfirm",
        linkedin_link="https://linkedin.com/company/testfirm",
        ranking=1,
        about="A test accounting firm",
        script="test_script",
        logo="test_logo.png",
        country="USA",
        jobs_count=1,
        last_scraped=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    db_session.add(firm)
    
    job = Job(
        firm=firm,
        job_title="Senior Auditor",
        location="New York, USA",
        description="Looking for an experienced auditor...",
        seniority="Senior",
        service="Audit",
        industry="Accounting",
        employment="Full-time",
        salary="Competitive",
        link="https://testfirm.com/jobs/senior-auditor",
        created_at=datetime.now(UTC),
        date_published=datetime.now(UTC),
        req_no="JOB-001"
    )
    db_session.add(job)
    
    embedding = JobEmbedding(
        job=job,
        embedding_vector=[0.1] * 1536  # Mock embedding
    )
    db_session.add(embedding)
    
    await db_session.commit()
    
    # Test search
    results = await semantic_job_search(
        db_session,
        "experienced auditor in New York",
        limit=5
    )
    
    assert len(results) > 0
    assert results[0].job_title == "Senior Auditor"
    assert results[0].location == "New York, USA"

@pytest.mark.asyncio
async def test_location_filtering(db_session):
    """Test location-based filtering in job search"""
    # Create test firms and jobs
    firm1 = AccountingFirm(
        name="NY Firm",
        location="New York, USA",
        slug="ny-firm",
        link="https://nyfirm.com",
        twitter_link="https://twitter.com/nyfirm",
        linkedin_link="https://linkedin.com/company/nyfirm",
        ranking=1,
        about="A New York accounting firm",
        script="ny_script",
        logo="ny_logo.png",
        country="USA",
        jobs_count=1,
        last_scraped=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    firm2 = AccountingFirm(
        name="LA Firm",
        location="Los Angeles, USA",
        slug="la-firm",
        link="https://lafirm.com",
        twitter_link="https://twitter.com/lafirm",
        linkedin_link="https://linkedin.com/company/lafirm",
        ranking=2,
        about="A Los Angeles accounting firm",
        script="la_script",
        logo="la_logo.png",
        country="USA",
        jobs_count=1,
        last_scraped=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    db_session.add_all([firm1, firm2])
    
    job1 = Job(
        firm=firm1,
        job_title="Auditor",
        location="New York, USA",
        description="NY position",
        seniority="Mid-level",
        service="Audit",
        industry="Accounting",
        employment="Full-time",
        salary="Competitive",
        link="https://nyfirm.com/jobs/auditor",
        created_at=datetime.now(UTC),
        date_published=datetime.now(UTC),
        req_no="JOB-002"
    )
    job2 = Job(
        firm=firm2,
        job_title="Auditor",
        location="Los Angeles, USA",
        description="LA position",
        seniority="Mid-level",
        service="Audit",
        industry="Accounting",
        employment="Full-time",
        salary="Competitive",
        link="https://lafirm.com/jobs/auditor",
        created_at=datetime.now(UTC),
        date_published=datetime.now(UTC),
        req_no="JOB-003"
    )
    db_session.add_all([job1, job2])
    
    await db_session.commit()
    
    # Test NY search
    ny_results = await semantic_job_search(
        db_session,
        "auditor in New York",
        limit=5
    )
    assert len(ny_results) == 1
    assert ny_results[0].location == "New York, USA"
    
    # Test LA search
    la_results = await semantic_job_search(
        db_session,
        "auditor in Los Angeles",
        limit=5
    )
    assert len(la_results) == 1
    assert la_results[0].location == "Los Angeles, USA"

@pytest.mark.asyncio
async def test_sql_parameter_handling(db_session):
    """Test SQL injection prevention in job search"""
    # Create test data
    firm = AccountingFirm(
        name="Test Firm",
        location="New York, USA",
        slug="test-firm-2",
        link="https://testfirm2.com",
        twitter_link="https://twitter.com/testfirm2",
        linkedin_link="https://linkedin.com/company/testfirm2",
        ranking=3,
        about="Another test accounting firm",
        script="test_script_2",
        logo="test_logo_2.png",
        country="USA",
        jobs_count=1,
        last_scraped=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    db_session.add(firm)
    
    job = Job(
        firm=firm,
        job_title="Auditor",
        location="New York, USA",
        description="Test position",
        seniority="Mid-level",
        service="Audit",
        industry="Accounting",
        employment="Full-time",
        salary="Competitive",
        link="https://testfirm2.com/jobs/auditor",
        created_at=datetime.now(UTC),
        date_published=datetime.now(UTC),
        req_no="JOB-004"
    )
    db_session.add(job)
    
    await db_session.commit()
    
    # Test with potentially malicious input
    results = await semantic_job_search(
        db_session,
        "'; DROP TABLE jobs; --",
        limit=5
    )
    
    # Verify table still exists and no error occurred
    result = await db_session.execute(select(Job))
    assert result.scalar_one() is not None

@pytest.mark.asyncio
async def test_error_handling(db_session):
    """Test error handling in job search"""
    with pytest.raises(ValueError):
        await semantic_job_search(db_session, "", limit=5)
    
    with pytest.raises(ValueError):
        await semantic_job_search(db_session, "auditor", limit=0)
    
    with pytest.raises(ValueError):
        await semantic_job_search(db_session, "auditor", limit=-1) 