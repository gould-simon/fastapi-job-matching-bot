from openai import AsyncOpenAI
import os
from typing import Optional
import pdfplumber  # For PDF files
from docx import Document  # For Word documents

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
        if file_path.endswith('.pdf'):
            with pdfplumber.open(file_path) as pdf:
                text = '\n'.join(page.extract_text() for page in pdf.pages)
        elif file_path.endswith(('.docx', '.doc')):
            doc = Document(file_path)
            text = '\n'.join(paragraph.text for paragraph in doc.paragraphs)
        
        # Use your existing AI processing logic
        response = await get_ai_response(
            text,
            context="Analyzing CV for job matching"
        )
        
        return response
        
    except Exception as e:
        return f"Error processing CV: {str(e)}"
    finally:
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path) 