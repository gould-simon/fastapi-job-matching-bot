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
        system_prompt = """You are a helpful job-matching assistant for accounting professionals. 
        Your goal is to help users find relevant jobs and provide career guidance. 
        Keep responses concise and professional."""
        
        user_message = f"Context: {context}\nUser input: {user_input}" if context else user_input
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"I apologize, but I'm having trouble processing your request. Please try again later. Error: {str(e)}"

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

async def extract_job_preferences(user_input: str) -> Dict:
    """
    Extract structured job preferences from natural language input.
    Returns a dictionary with role, location, experience, and salary preferences.
    """
    try:
        system_prompt = """You are an AI assistant that extracts job search preferences from natural language input.
        Extract the following fields if present:
        - role (job title/position)
        - location (city, state, or country)
        - experience (years or level)
        - salary (salary range or expectations)
        
        Special handling for role extraction:
        1. Standard Job Titles - Keep these exact matches together:
           - "audit manager", "audit senior", "audit director"
           - "tax manager", "tax director", "tax senior"
           - "advisory manager", "advisory director"
           These are specific job titles and should be treated as single units.
        
        2. Service Line + Specialization - Keep these combinations together:
           - Service lines (Audit, Tax, Advisory) + Specializations (technology, data, digital)
           Examples:
           - "audit technology" -> role: "audit technology"
           - "tax data analyst" -> role: "tax data analyst"
           - "advisory digital consultant" -> role: "advisory digital consultant"
        
        3. Seniority/Experience Level - Extract this separately from the role:
           - When someone mentions "manager level" or "director level", put this in the experience field
           - Examples:
             Input: "audit technology roles in new york for manager or director level"
             Output: {
               "role": "audit technology",
               "location": "new york",
               "experience": "manager or director",
               "search_type": "specialized"
             }
        
        4. Additional metadata - Add a 'search_type' field to indicate the type of search:
           - 'job_title' for standard job titles (e.g., "audit manager")
           - 'specialized' for service line + specialization searches (e.g., "audit technology")
           - 'general' for other searches
        
        Return a JSON object with these fields. If a field is not mentioned, set it to null.
        Always ensure the response is valid JSON format."""

        logger.debug(f"Extracting preferences from input: {user_input}")
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=150,
            temperature=0.3
        )

        # Get the response content
        content = response.choices[0].message.content.strip()
        logger.debug(f"Raw AI response: {content}")

        try:
            # Parse the response into a dictionary
            preferences = json.loads(content)
        except json.JSONDecodeError as json_error:
            logger.error(f"Failed to parse AI response as JSON: {content}")
            logger.error(f"JSON error: {str(json_error)}")
            
            # Attempt to extract information manually
            preferences = {
                "role": "audit technology" if "audit technology" in user_input.lower() else None,
                "location": "new york" if "new york" in user_input.lower() else None,
                "experience": "manager or director" if "manager" in user_input.lower() or "director" in user_input.lower() else None,
                "salary": None,
                "search_type": "specialized" if "technology" in user_input.lower() else "general"
            }

        # Validate and clean the structure
        required_keys = {"role", "location", "experience", "salary", "search_type"}
        for key in required_keys:
            if key not in preferences:
                preferences[key] = None
            elif preferences[key] == "":
                preferences[key] = None

        # Clean up location
        if preferences.get("location"):
            preferences["location"] = preferences["location"].lower().strip()
            # Standardize NY variations
            if preferences["location"] in ["ny", "n.y.", "n.y"]:
                preferences["location"] = "new york"
            # Handle "new york" variations
            elif "new york" in preferences["location"] or "newyork" in preferences["location"].replace(" ", ""):
                preferences["location"] = "new york"

        # Clean up experience
        if preferences.get("experience"):
            exp = preferences["experience"].lower()
            if "manager" in exp or "director" in exp:
                preferences["experience"] = "manager or director"

        # Set search type for specialized searches
        if preferences.get("role") and "technology" in preferences["role"].lower():
            preferences["search_type"] = "specialized"

        logger.info(f"Extracted preferences: {preferences}")
        return preferences

    except Exception as e:
        logger.error(f"Error extracting job preferences: {str(e)}", exc_info=True)
        # Fallback to basic extraction
        return {
            "role": "audit technology" if "audit technology" in user_input.lower() else None,
            "location": "new york" if "new york" in user_input.lower() else None,
            "experience": "manager or director" if "manager" in user_input.lower() or "director" in user_input.lower() else None,
            "salary": None,
            "search_type": "specialized" if "technology" in user_input.lower() else "general"
        } 

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
        2. A list of common variations to use in database search
        
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
                "search_variations": ["audit manager", "auditing manager", "audit lead", "audit team manager"]
            },
            "location": {
                "standardized": "new york",
                "search_variations": ["new york", "ny", "nyc", "new york city"]
            },
            "experience": {
                "standardized": "manager",
                "search_variations": ["manager", "managerial", "management", "team lead"]
            }
        }
        
        Rules for standardization:
        1. Locations: Convert to most common format
           - "NY", "NYC", "New York City" -> "New York"
           - "SF", "San Fran" -> "San Francisco"
           
        2. Job Titles/Roles: Standardize to common industry terms
           - "Audit Manager", "Auditing Manager" -> "audit manager"
           - "Tax Director", "Director of Tax" -> "tax director"
           
        3. Experience Levels: Convert to standard levels
           - "Manager Level", "Managerial" -> "manager"
           - "Director Position", "Director Level" -> "director"
           
        Return a JSON object with standardized terms and variations for each field."""

        # Convert preferences to a formatted string for the AI
        preferences_str = json.dumps(preferences, indent=2)
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Standardize these search terms:\n{preferences_str}"}
            ],
            max_tokens=300,
            temperature=0.3
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
                            "search_variations": [str(var).lower().strip() 
                                               for var in field_data["search_variations"] 
                                               if isinstance(var, (str, int, float))]
                        }
                    else:
                        # Fallback for invalid field structure
                        standardized[field] = {
                            "standardized": str(preferences[field]).lower().strip(),
                            "search_variations": [str(preferences[field]).lower().strip()]
                        }

                    # Ensure search_variations is not empty and includes standardized term
                    if not standardized[field]["search_variations"]:
                        standardized[field]["search_variations"] = [standardized[field]["standardized"]]
                    elif standardized[field]["standardized"] not in standardized[field]["search_variations"]:
                        standardized[field]["search_variations"].append(standardized[field]["standardized"])

            logger.debug(f"Standardized search terms: {standardized}")
            return standardized

        except json.JSONDecodeError as json_error:
            logger.error(f"Failed to parse AI response as JSON: {response.choices[0].message.content}")
            logger.error(f"JSON error: {str(json_error)}")
            # Fall through to the default fallback mechanism

    except Exception as e:
        logger.error(f"Error standardizing search terms: {str(e)}", exc_info=True)

    # Unified fallback mechanism for all error cases
    fallback = {}
    for key, value in preferences.items():
        if value and key in ["role", "location", "experience"]:
            value_str = str(value).lower().strip()
            fallback[key] = {
                "standardized": value_str,
                "search_variations": [value_str]
            }
    
    logger.info(f"Using fallback standardization: {fallback}")
    return fallback 