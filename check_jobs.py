import asyncio
from sqlalchemy import text
from app.database import SessionLocal
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_jobs():
    async with SessionLocal() as db:
        try:
            # First, check if we have any jobs at all
            result = await db.execute(text("SELECT COUNT(*) FROM \"JobsApp_job\""))
            total_jobs = result.scalar()
            print(f"\nTotal jobs in database: {total_jobs}")

            # Check for audit technology roles in New York
            query = text("""
                SELECT DISTINCT
                    af.name as firm_name,
                    j.job_title,
                    j.seniority,
                    j.service,
                    j.location
                FROM "JobsApp_job" j
                JOIN "JobsApp_accountingfirm" af ON j.firm_id = af.id
                WHERE 
                    (
                        (LOWER(j.job_title) LIKE :tech_pattern AND LOWER(j.service) LIKE :audit_pattern)
                        OR
                        (LOWER(j.job_title) LIKE :audit_pattern AND LOWER(j.job_title) LIKE :tech_pattern)
                    )
                    AND (
                        LOWER(j.location) LIKE :location_pattern1 
                        OR LOWER(j.location) LIKE :location_pattern2
                    )
                    AND (
                        LOWER(j.seniority) LIKE :seniority_pattern1
                        OR LOWER(j.seniority) LIKE :seniority_pattern2
                    )
            """)
            
            params = {
                'tech_pattern': '%technology%',
                'audit_pattern': '%audit%',
                'location_pattern1': '%new york%',
                'location_pattern2': '%ny%',
                'seniority_pattern1': '%manager%',
                'seniority_pattern2': '%director%'
            }
            
            print("\nSearching for audit technology roles in New York (manager/director level)...")
            result = await db.execute(query, params)
            jobs = result.fetchall()
            
            if jobs:
                print(f"\nFound {len(jobs)} matching jobs:")
                for job in jobs:
                    print(f"\nFirm: {job.firm_name}")
                    print(f"Title: {job.job_title}")
                    print(f"Seniority: {job.seniority}")
                    print(f"Service: {job.service}")
                    print(f"Location: {job.location}")
                    print("---")
            else:
                print("\nNo exact matches found. Checking for similar roles...")
                
                # Try a broader search
                broader_query = text("""
                    SELECT DISTINCT
                        af.name as firm_name,
                        j.job_title,
                        j.seniority,
                        j.service,
                        j.location
                    FROM "JobsApp_job" j
                    JOIN "JobsApp_accountingfirm" af ON j.firm_id = af.id
                    WHERE 
                        (
                            LOWER(j.job_title) LIKE :audit_pattern
                            OR LOWER(j.service) LIKE :audit_pattern
                        )
                        AND (
                            LOWER(j.location) LIKE :location_pattern1 
                            OR LOWER(j.location) LIKE :location_pattern2
                        )
                        AND (
                            LOWER(j.seniority) LIKE :seniority_pattern1
                            OR LOWER(j.seniority) LIKE :seniority_pattern2
                        )
                    LIMIT 5
                """)
                
                result = await db.execute(broader_query, params)
                jobs = result.fetchall()
                
                if jobs:
                    print(f"\nFound {len(jobs)} similar audit roles:")
                    for job in jobs:
                        print(f"\nFirm: {job.firm_name}")
                        print(f"Title: {job.job_title}")
                        print(f"Seniority: {job.seniority}")
                        print(f"Service: {job.service}")
                        print(f"Location: {job.location}")
                        print("---")
                else:
                    print("\nNo similar roles found either.")

        except Exception as e:
            logger.error(f"Error querying database: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(check_jobs()) 