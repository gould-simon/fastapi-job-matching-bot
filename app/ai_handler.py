from openai import AsyncOpenAI
import os
from typing import Optional
import pdfplumber  # For PDF files
from docx import Document  # For Word documents
import logging

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
        
        # Create a specific prompt for CV analysis
        system_prompt = """You are an expert CV analyzer for accounting professionals. 
        Analyze the CV and provide:
        1. A summary of key skills and experience
        2. Suggested job roles that match their profile
        3. Any suggestions for improving their CV
        Keep the response concise and professional."""
        
        # Get AI analysis of the CV
        logger.debug("Sending CV text to OpenAI for analysis")
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this CV:\n\n{text}"}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        logger.debug("Successfully received analysis from OpenAI")
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error in process_cv: {str(e)}", exc_info=True)
        return f"I apologize, but I encountered an error while analyzing your CV: {str(e)}. Please try again or contact support."
    finally:
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path) 