from openai import AsyncOpenAI
import os
from typing import Optional, Dict
import pdfplumber  # For PDF files
from docx import Document  # For Word documents
import logging
import json

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logger = logging.getLogger(__name__)

async def get_ai_response(user_input: str, context: Optional[str] = None) -> str:
    try:
        system_prompt = """You are a knowledgeable job-matching assistant for accounting professionals, with expertise in audit, tax, and advisory roles.

        Your responsibilities:
        1. Provide specific, actionable job search advice
        2. Help users understand different accounting roles and career paths
        3. Give clear, concise responses that directly address the user's query
        4. If you don't know something, be honest and suggest alternatives

        Key areas of expertise:
        - Big 4 and mid-tier accounting firms
        - Audit, Tax, and Advisory service lines
        - Career progression in accounting
        - Professional qualifications (CPA, ACCA, etc.)
        
        Keep responses professional but friendly, and always end with a clear next step or call to action."""
        
        user_message = f"Context: {context}\nUser input: {user_input}" if context else user_input
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=500,  # Increased token limit for more detailed responses
            temperature=0.7
        )
        
        # Log the response for monitoring
        logger.debug(f"AI Response generated for input: {user_input[:50]}...")
        logger.debug(f"Response length: {len(response.choices[0].message.content)} chars")
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error in get_ai_response: {str(e)}", exc_info=True)
        return ("I apologize, but I'm having trouble processing your request right now. "
                "Please try:\n"
                "1. Using /search_jobs for job searches\n"
                "2. Being more specific in your question\n"
                "3. Breaking down complex queries into simpler ones")

async def process_cv(file_path: str) -> str:
    """Extract text from CV and process it"""
    text = ""
    
    try:
        logger.debug(f"Starting CV processing for file: {file_path}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return "Error: The CV file could not be found. Please try uploading again."

        # Extract text from CV
        if file_path.endswith('.pdf'):
            logger.debug("Processing PDF file")
            try:
                with pdfplumber.open(file_path) as pdf:
                    text = '\n'.join(page.extract_text() for page in pdf.pages if page.extract_text())
            except Exception as pdf_error:
                logger.error(f"PDF processing error: {str(pdf_error)}")
                raise Exception(f"Could not read PDF file: {str(pdf_error)}")
                
        elif file_path.endswith(('.docx', '.doc')):
            logger.debug("Processing Word document")
            try:
                doc = Document(file_path)
                text = '\n'.join(paragraph.text for paragraph in doc.paragraphs)
            except Exception as doc_error:
                logger.error(f"Word document processing error: {str(doc_error)}")
                raise Exception(f"Could not read Word document: {str(doc_error)}")
        else:
            logger.error(f"Unsupported file format: {file_path}")
            return "Error: Please upload your CV in PDF or Word (.docx) format."

        # Check if text was extracted successfully
        if not text.strip():
            logger.error("No text could be extracted from the CV")
            return "Error: Could not extract text from your CV. Please ensure the file is not empty or password protected."

        logger.debug(f"Successfully extracted {len(text)} characters from CV")
        
        # Create context and prompt for CV analysis
        context = """Analyze this CV as an expert CV analyzer for accounting professionals. 
        Provide:
        1. A summary of key skills and experience
        2. Suggested job roles that match their profile
        3. Any suggestions for improving their CV
        Keep the response concise and professional."""
        
        # Use the existing get_ai_response function for CV analysis
        logger.debug("Sending CV text to OpenAI for analysis")
        response = await get_ai_response(text, context=context)
        logger.debug("Successfully received analysis from OpenAI")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in process_cv: {str(e)}", exc_info=True)
        return f"I apologize, but I encountered an error while analyzing your CV: {str(e)}. Please try again or contact support."
    finally:
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

async def extract_job_preferences(user_input: str) -> Dict[str, Optional[str]]:
    """Extract job preferences from user input using OpenAI's API."""
    try:
        # Prepare the prompt for GPT
        prompt = f"""Extract job search preferences from the following user input:
"{user_input}"

Please extract the following fields:
- role (job title or function)
- location (city or region)
- experience (standardize to these exact terms):
  * "senior" for senior/experienced/senior level
  * "manager" for manager/managerial
  * "manager or director" for manager or director level
  * null if not specified
- salary (if mentioned)
- search_type (use these rules):
  * "job_title" when the input is a specific job title (e.g. "audit manager", "tax director")
  * "specialized" when the input describes a broader role or has multiple criteria (e.g. "audit technology roles", "senior level positions")

Format the response as a JSON object with these exact field names. If a field is not mentioned, set it to null.
For experience, use ONLY the standardized terms listed above.

Example outputs:
{{
    "role": "audit manager",
    "location": "new york",
    "experience": null,
    "salary": null,
    "search_type": "job_title"  # specific job title
}}

{{
    "role": "audit technology",
    "location": "boston",
    "experience": "senior",  # standardized from "senior level"
    "salary": null,
    "search_type": "specialized"  # broader role description
}}

{{
    "role": "tax director",
    "location": "chicago",
    "experience": "manager or director",  # standardized from "manager or director level"
    "salary": "150k+",
    "search_type": "job_title"  # specific job title
}}
"""

        # Call OpenAI API
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts job search preferences from user input. Use exact standardized terms for experience levels and be precise about search_type classification."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=150
        )

        # Parse the response
        preferences = json.loads(response.choices[0].message.content)
        
        # Ensure all required fields are present
        required_fields = ["role", "location", "experience", "salary", "search_type"]
        for field in required_fields:
            if field not in preferences:
                preferences[field] = None
        
        # Log the extracted preferences
        logger.info(f"Extracted preferences: {preferences}")
        
        return preferences

    except Exception as e:
        logger.error(f"Error extracting job preferences: {str(e)}")
        raise

async def standardize_search_terms(preferences: Dict) -> Dict:
    """
    Standardize search terms using OpenAI to match database format.
    Takes the extracted preferences and returns standardized versions.
    """
    try:
        system_prompt = """You are a search term standardizer for a job database.
        Your task is to convert user search terms into standardized database-friendly formats.
        
        For each term (role, location, experience), return:
        1. A standardized version of the term
        2. A comprehensive list of common variations to use in database search
        
        Example input:
        {
            "role": "audit manager",
            "location": "NY",
            "experience": "manager level"
        }
        
        Example output:
        {
            "role": {
                "standardized": "audit manager",
                "search_variations": ["audit manager", "auditing manager", "audit lead", "audit team manager", "audit department manager", "manager of audit"]
            },
            "location": {
                "standardized": "new york",
                "search_variations": ["new york", "ny", "nyc", "new york city", "manhattan"]
            },
            "experience": {
                "standardized": "manager",
                "search_variations": ["manager", "managerial", "management", "team lead", "team manager"]
            }
        }
        
        Rules for standardization:
        1. Locations: Convert to most common format and include ALL common variations
           - For "New York": include ["new york", "ny", "nyc", "manhattan"]
           - For "Boston": include ["boston", "ma", "massachusetts", "boston ma", "greater boston"]
           - For "San Francisco": include ["san francisco", "sf", "bay area", "silicon valley"]
           
        2. Job Titles/Roles: Include ALL common variations and combinations
           - For "Technology Audit": include ["technology audit", "it audit", "tech audit", "information technology audit", "technology assurance"]
           - For "Audit Manager": include ["audit manager", "auditing manager", "audit lead", "audit team manager", "manager of audit"]
           
        3. Experience Levels: Include ALL common variations and related terms
           - For "Manager": include ["manager", "management", "managerial", "team lead", "team manager"]
           - For "Senior": include ["senior", "senior level", "experienced", "advanced", "sr"]
           
        IMPORTANT: 
        - Include ALL common variations and synonyms
        - For locations, include city name, state abbreviation, and full state name
        - For roles, include different word orders and common industry terms
        - For experience, include both formal and informal variations
        
        Return a JSON object with standardized terms and variations for each field."""

        # Convert preferences to a formatted string for the AI
        preferences_str = json.dumps(preferences, indent=2)
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Standardize these search terms:\n{preferences_str}"}
            ],
            max_tokens=800,
            temperature=0.2
        )

        # Initialize standardized structure with default values
        standardized = {
            "role": {"standardized": None, "search_variations": []},
            "location": {"standardized": None, "search_variations": []},
            "experience": {"standardized": None, "search_variations": []}
        }

        try:
            # Parse and validate AI response
            ai_response = json.loads(response.choices[0].message.content)
            logger.debug(f"Raw AI response: {ai_response}")

            # Validate and process each field
            for field in ["role", "location", "experience"]:
                if field in preferences and preferences[field]:
                    field_data = ai_response.get(field, {})
                    
                    # Validate field structure
                    if (isinstance(field_data, dict) and 
                        "standardized" in field_data and 
                        "search_variations" in field_data and 
                        isinstance(field_data["search_variations"], list)):
                        
                        standardized[field] = {
                            "standardized": str(field_data["standardized"]).lower().strip(),
                            "search_variations": sorted(set(str(var).lower().strip() 
                                               for var in field_data["search_variations"]))
                        }

            return standardized

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error in standardize_search_terms: {str(e)}")
        raise 