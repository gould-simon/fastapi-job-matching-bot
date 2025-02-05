import asyncio
from sqlalchemy import text, String, Boolean
from app.database import SessionLocal
from app.ai_handler import extract_job_preferences
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.config import DATABASE_URL
from openai import AsyncOpenAI
from typing import List, Dict

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add timeout configuration
DATABASE_TIMEOUT = 30  # 30 seconds timeout

# Convert the database URL to use asyncpg
ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

# Create the database engine with timeout
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    connect_args={"command_timeout": DATABASE_TIMEOUT}
)

# Initialize OpenAI client
client = AsyncOpenAI()

async def analyze_job_match(job_seeker_preferences: dict, job_details: dict) -> float:
    """Use OpenAI to analyze how well a job matches the seeker's preferences."""
    try:
        prompt = f"""
        Analyze how well this job matches the job seeker's preferences. Consider:
        1. Role alignment
        2. Experience level match
        3. Location match
        4. Required skills match

        Job Seeker Preferences:
        - Desired Role: {job_seeker_preferences['role']}
        - Experience Level: {job_seeker_preferences['experience']}
        - Location: {job_seeker_preferences['location']}

        Job Details:
        - Title: {job_details['job_title']}
        - Service Line: {job_details['service']}
        - Location: {job_details['location']}
        - Seniority: {job_details['seniority']}

        Return a score between 0 and 1, where 1 is a perfect match.
        Only return the numerical score, nothing else.
        """

        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a job matching expert. Analyze job fit and return only a numerical score between 0 and 1."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=10
        )
        
        score = float(response.choices[0].message.content.strip())
        return min(max(score, 0), 1)  # Ensure score is between 0 and 1
    except Exception as e:
        logger.error(f"Error in AI job match analysis: {str(e)}")
        return 0.5  # Return neutral score on error

async def test_search(search_query: str):
    """Test a search query and display results"""
    try:
        logger.info(f"\n🔍 Testing search: '{search_query}'")
        
        # First, get AI-extracted preferences
        preferences = await extract_job_preferences(search_query)
        logger.info(f"📋 Extracted preferences: {preferences}")
        
        # Then perform the search
        async with AsyncSession(engine) as db:
            # Initial broad search
            query = text("""
                SELECT DISTINCT
                    af.name as firm_name,
                    j.job_title,
                    j.service,
                    j.location,
                    j.seniority,
                    j.description
                FROM "JobsApp_job" j
                JOIN "JobsApp_accountingfirm" af ON j.firm_id = af.id
                WHERE 
                    -- Basic text search on job title and description
                    (LOWER(j.job_title) LIKE :search_pattern 
                     OR LOWER(j.description) LIKE :search_pattern
                     OR LOWER(j.service) LIKE :search_pattern)
                    -- Location filter (if provided)
                    AND (CAST(:location AS text) IS NULL 
                         OR LOWER(j.location) LIKE :location_pattern)
                LIMIT 10  -- Get more results initially for AI ranking
            """)
            
            search_pattern = f"%{preferences['role'].lower()}%" if preferences['role'] else '%%'
            location = preferences['location']
            location_pattern = f"%{location.lower()}%" if location else '%%'
            
            params = {
                "search_pattern": search_pattern,
                "location": location,
                "location_pattern": location_pattern
            }
            
            result = await db.execute(query, params)
            jobs = result.fetchall()
            
            # Use AI to analyze and rank each job match
            job_matches = []
            for job in jobs:
                job_dict = {
                    'firm_name': job.firm_name,
                    'job_title': job.job_title,
                    'service': job.service,
                    'location': job.location,
                    'seniority': job.seniority,
                    'description': job.description
                }
                
                match_score = await analyze_job_match(preferences, job_dict)
                job_matches.append((match_score, job_dict))
            
            # Sort by match score and take top 5
            job_matches.sort(reverse=True, key=lambda x: x[0])
            top_matches = job_matches[:5]
            
            # Display results
            logger.info(f"📊 Found {len(top_matches)} matching jobs:")
            for score, job in top_matches:
                logger.info("")
                logger.info(f"🎯 Match Score: {score:.2f}")
                logger.info(f"🏢 {job['firm_name']}")
                logger.info(f"📋 {job['job_title']}")
                logger.info(f"🔧 Service: {job['service']}")
                logger.info(f"📍 {job['location']}")
                logger.info(f"👔 {job['seniority']}")
                logger.info("---")
    except Exception as e:
        logger.error(f"Error testing search '{search_query}': {str(e)}", exc_info=True)

async def run_tests():
    """Run a series of test searches"""
    # Test cases for different search types
    test_cases = [
        # Standard job titles
        "audit manager in new york",
        "tax senior in chicago",
        "advisory director in boston",
        
        # Specialized searches
        "audit technology roles in new york",
        "tax data analyst positions",
        "advisory digital consultant",
        
        # Mixed/complex searches
        "senior audit technology roles in new york",
        "experienced tax manager with data skills",
        "entry level audit position in boston",
        
        # General searches
        "accounting jobs in new york",
        "forensic accountant",
        "risk advisory"
    ]
    
    for test_case in test_cases:
        await test_search(test_case)
        print("\n" + "="*50 + "\n")  # Separator between tests

if __name__ == "__main__":
    asyncio.run(run_tests()) 