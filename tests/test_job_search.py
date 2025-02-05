import pytest
import asyncio
from sqlalchemy import text
from app.database import SessionLocal
from app.ai_handler import extract_job_preferences, standardize_search_terms
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
async def db_session():
    async with SessionLocal() as session:
        yield session

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
                "salary": None
            }
        },
        {
            "input": "audit technology roles in new york for manager or director level",
            "expected": {
                "role": "audit technology",
                "location": "new york",
                "experience": "manager or director",
                "salary": None
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
    """Test that search terms are correctly standardized"""
    test_cases = [
        {
            "input": {
                "role": "audit manager",
                "location": "NY",
                "experience": "manager level"
            },
            "expected_keys": ["role", "location", "experience", "search_variations"]
        },
        {
            "input": {
                "role": "audit technology",
                "location": "new york city",
                "experience": "director"
            },
            "expected_keys": ["role", "location", "experience", "search_variations"]
        }
    ]
    
    for case in test_cases:
        standardized = await standardize_search_terms(case["input"])
        assert isinstance(standardized, dict), "Standardized output should be a dictionary"
        for key in case["expected_keys"]:
            assert any(k.get("search_variations") for k in standardized.values() if isinstance(k, dict)), \
                "Each term should have search variations"

@pytest.mark.asyncio
async def test_job_search_query(db_session):
    """Test that the job search query returns expected results"""
    test_cases = [
        {
            "input": "audit manager in new york",
            "min_expected_results": 1
        },
        {
            "input": "audit technology roles in new york for manager or director level",
            "min_expected_results": 1
        }
    ]
    
    for case in test_cases:
        # Extract and standardize preferences
        preferences = await extract_job_preferences(case["input"])
        standardized = await standardize_search_terms(preferences)
        
        # Prepare search parameters
        search_params = {
            "job_patterns": [f"%{pattern}%" for pattern in standardized.get('role', {}).get('search_variations', [])],
            "service_patterns": [f"%{pattern}%" for pattern in standardized.get('role', {}).get('search_variations', [])],
            "location_patterns": [f"%{pattern}%" for pattern in standardized.get('location', {}).get('search_variations', [])],
            "seniority_patterns": [f"%{pattern}%" for pattern in standardized.get('experience', {}).get('search_variations', [])],
            "location": standardized.get('location', {}).get('standardized'),
            "experience": standardized.get('experience', {}).get('standardized')
        }
        
        # Ensure we have at least one pattern for each field
        if not search_params["job_patterns"]:
            search_params["job_patterns"] = ["%"]
        if not search_params["service_patterns"]:
            search_params["service_patterns"] = ["%"]
        if not search_params["location_patterns"]:
            search_params["location_patterns"] = ["%"]
        if not search_params["seniority_patterns"]:
            search_params["seniority_patterns"] = ["%"]
        
        # Execute search query
        query = text("""
            SELECT DISTINCT
                af.name as firm_name,
                j.job_title,
                j.seniority,
                j.service,
                j.location
            FROM "JobsApp_job" j
            JOIN "JobsApp_accountingfirm" af ON j.firm_id = af.id
            WHERE 1=1
            AND (
                LOWER(j.job_title) LIKE ANY(:job_patterns)
                OR LOWER(j.service) LIKE ANY(:service_patterns)
            )
            AND (
                CASE WHEN :location IS NOT NULL AND :location != ''
                THEN LOWER(j.location) LIKE ANY(:location_patterns)
                ELSE TRUE END
            )
            AND (
                CASE WHEN :experience IS NOT NULL AND :experience != ''
                THEN LOWER(j.seniority) LIKE ANY(:seniority_patterns)
                ELSE TRUE END
            )
            ORDER BY j.date_published DESC NULLS LAST
            LIMIT 5
        """)
        
        result = await db_session.execute(query, search_params)
        jobs = result.fetchall()
        
        assert len(jobs) >= case["min_expected_results"], \
            f"Expected at least {case['min_expected_results']} results for '{case['input']}', got {len(jobs)}"
        
        # Verify job fields
        for job in jobs:
            assert job.firm_name, "Job should have a firm name"
            assert job.job_title, "Job should have a title"
            assert job.location, "Job should have a location" 