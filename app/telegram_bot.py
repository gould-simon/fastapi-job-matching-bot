from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
from dotenv import load_dotenv
import os
import logging
from app.ai_handler import get_ai_response, process_cv, extract_job_preferences
from app.database import SessionLocal, test_database_connection, list_all_tables
from app.models import User, UserSearch
import asyncio
from datetime import datetime
from logging.handlers import RotatingFileHandler
from sqlalchemy import text
import json

# Load environment variables
load_dotenv()

def setup_logging():
    """Configure logging with file cleanup on startup"""
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Clear existing log file
    log_file = 'logs/conversations.log'
    open(log_file, 'w').close()  # Truncate the file
    
    # Setup logging configuration
    logging.basicConfig(
        level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(
                log_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            ),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    # Set logging levels for specific modules
    logging.getLogger('httpx').setLevel(logging.WARNING)  # Reduce noise from httpx
    logging.getLogger('telegram').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)  # Ensure our logger captures everything
    logger.info("Logging setup complete - previous logs cleared")
    return logger

# Use this at the start of your bot
logger = setup_logging()

# Retrieve Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN is missing! Check your .env file.")

# Add environment identifier
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
logger.info(f"🚀 Starting bot in {ENVIRONMENT} environment using bot token: {TELEGRAM_BOT_TOKEN[:8]}...")

# Create temp directory if it doesn't exist
os.makedirs("temp", exist_ok=True)

# Create the application instance at module level
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Define conversation states
AWAITING_JOB_PREFERENCES = 1

# Define command handlers
async def start(update: Update, context: CallbackContext) -> None:
    try:
        # Log the incoming request
        logger.info(f"Start command received from user {update.effective_user.id}")
        
        # First send welcome message before database operations
        welcome_message = (
            "👋 Hello! I'm your AI-powered job-matching assistant for accounting professionals!\n\n"
            "Here's what I can help you with:\n"
            "🔍 /search_jobs - Search for accounting jobs\n"
            "📄 /upload_cv - Upload your CV for personalized matches\n"
            "🔔 /set_alerts - Set up job alerts\n"
            "💬 Or simply chat with me about your career goals!"
        )
        await update.message.reply_text(welcome_message)
        logger.info(f"Welcome message sent to user {update.effective_user.id}")
        
        # Then handle database operations
        try:
            async with SessionLocal() as db:
                # Check if user exists
                logger.debug("Checking if user exists in database...")
                result = await db.execute(
                    "SELECT * FROM users WHERE telegram_id = :telegram_id",
                    {"telegram_id": update.effective_user.id}
                )
                user = result.first()
                
                if not user:
                    # Create new user
                    logger.debug("Creating new user...")
                    new_user = User(
                        telegram_id=update.effective_user.id,
                        username=update.effective_user.username,
                        first_name=update.effective_user.first_name,
                        last_name=update.effective_user.last_name
                    )
                    db.add(new_user)
                    await db.commit()
                    logger.info(f"New user registered: {update.effective_user.id}")
        except Exception as db_error:
            logger.error(f"Database error in start command: {str(db_error)}", exc_info=True)
            # Don't return error to user since welcome message was already sent
            
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, I encountered an error. Please try again.")

async def handle_message(update: Update, context: CallbackContext) -> None:
    try:
        user = update.effective_user
        user_message = update.message.text
        
        # Log the incoming message
        logger.info(f"👤 User ({user.username or user.id}): {user_message}")
        
        # Get AI response
        response = await get_ai_response(user_message)
        
        # Log the bot's response
        logger.info(f"🤖 Bot: {response}")
        
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error in message handler: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, I encountered an error processing your message.")

async def search_jobs(update: Update, context: CallbackContext) -> int:
    """Initial handler for /search_jobs command"""
    await update.message.reply_text(
        "🔍 What kind of accounting job are you looking for?\n"
        "Please specify any preferences like:\n"
        "- Role (e.g., Tax Accountant, Audit Manager)\n"
        "- Location\n"
        "- Experience level\n"
        "- Salary range"
    )
    return AWAITING_JOB_PREFERENCES

async def process_job_preferences(update: Update, context: CallbackContext) -> int:
    """Process the user's job preferences and search for matching jobs"""
    try:
        user_input = update.message.text
        user_id = update.effective_user.id
        
        logger.debug(f"Starting job preference processing for user {user_id}")
        logger.info(f"Processing job preferences for user {user_id}: {user_input}")
        
        # Extract structured preferences using AI
        logger.debug("Calling extract_job_preferences")
        preferences = await extract_job_preferences(user_input)
        logger.info(f"Extracted preferences: {preferences}")
        
        # Store the search in database
        async with SessionLocal() as db:
            try:
                # Search for matching jobs
                query = text("""
                    SELECT DISTINCT
                        af.name as firm_name,
                        j.job_title,
                        j.seniority,
                        j.service,
                        j.location,
                        j.employment,
                        j.salary,
                        j.link
                    FROM "JobsApp_job" j
                    JOIN "JobsApp_accountingfirm" af ON j.firm_id = af.id
                    WHERE 1=1
                    AND (
                        CASE 
                            -- For standard job titles (e.g., "audit manager")
                            WHEN :search_type = 'job_title' THEN
                                (LOWER(j.job_title) LIKE :role_pattern
                                OR (LOWER(j.service) LIKE :service_pattern 
                                    AND LOWER(j.seniority) LIKE :position_pattern))
                            
                            -- For specialized searches (e.g., "audit technology")
                            WHEN :search_type = 'specialized' THEN
                                ((LOWER(j.job_title) LIKE :tech_pattern AND LOWER(j.service) LIKE :service_pattern)
                                OR (LOWER(j.job_title) LIKE :service_pattern AND LOWER(j.job_title) LIKE :tech_pattern))
                            
                            -- For general searches
                            ELSE (LOWER(j.job_title) LIKE :role_pattern 
                                OR LOWER(j.service) LIKE :role_pattern)
                        END
                    )
                    AND (
                        CASE WHEN :location IS NOT NULL AND :location != ''
                        THEN (LOWER(j.location) LIKE :location_pattern1 
                            OR LOWER(j.location) LIKE :location_pattern2)
                        ELSE TRUE END
                    )
                    AND (
                        CASE WHEN :experience IS NOT NULL AND :experience != ''
                        THEN (LOWER(j.seniority) LIKE :seniority_pattern1 
                            OR LOWER(j.seniority) LIKE :seniority_pattern2)
                        ELSE TRUE END
                    )
                    ORDER BY j.date_published DESC NULLS LAST
                    LIMIT 5
                """)
                
                # Prepare search patterns
                role = preferences.get("role", "").lower() if preferences.get("role") else ""
                search_type = preferences.get("search_type", "general")
                location = preferences.get("location", "").lower() if preferences.get("location") else ""
                experience = preferences.get("experience", "").lower() if preferences.get("experience") else ""
                
                # Split role into components based on search type
                role_parts = role.split() if role else []
                
                if search_type == "job_title":
                    # For "audit manager", service="audit", position="manager"
                    service_term = role_parts[0] if len(role_parts) > 0 else ""
                    position_term = role_parts[1] if len(role_parts) > 1 else ""
                    tech_pattern = "%technology%"  # Default tech pattern
                elif search_type == "specialized":
                    # For "audit technology", service="audit", tech="technology"
                    service_term = role_parts[0] if len(role_parts) > 0 else ""
                    position_term = ""
                    tech_pattern = f"%{role_parts[1]}%" if len(role_parts) > 1 else "%technology%"
                else:
                    service_term = role
                    position_term = ""
                    tech_pattern = "%technology%"
                
                # Handle seniority/experience level
                seniority_terms = ["manager", "director", "senior", "associate", "partner"]
                if any(term in experience.lower() for term in seniority_terms):
                    seniority_pattern1 = f"%{experience}%"
                    seniority_pattern2 = f"%{experience}%"
                else:
                    seniority_pattern1 = "%manager%"
                    seniority_pattern2 = "%director%"
                
                search_params = {
                    "role": role,
                    "role_pattern": f"%{role}%",
                    "search_type": search_type,
                    "service_pattern": f"%{service_term}%",
                    "position_pattern": f"%{position_term}%",
                    "tech_pattern": tech_pattern,
                    "location": location,
                    "location_pattern1": f"%{location}%",
                    "location_pattern2": f"%{location.replace('new york', 'ny')}%",
                    "experience": experience,
                    "seniority_pattern1": seniority_pattern1,
                    "seniority_pattern2": seniority_pattern2
                }
                
                logger.debug(f"Executing search with parameters: {search_params}")
                result = await db.execute(query, search_params)
                jobs = result.fetchall()
                logger.info(f"Found {len(jobs) if jobs else 0} matching jobs")
                
                if jobs:
                    response = "🎯 Here are some matching jobs:\n\n"
                    for job in jobs:
                        response += (
                            f"🏢 *{job.firm_name}*\n"
                            f"📋 {job.job_title}\n"
                        )
                        if job.seniority:
                            response += f"👔 {job.seniority}\n"
                        if job.service:
                            response += f"🔧 Service: {job.service}\n"
                        if job.location:
                            response += f"📍 {job.location}\n"
                        if job.employment:
                            response += f"⏰ {job.employment}\n"
                        if job.salary:
                            response += f"💰 {job.salary}\n"
                        if job.link:
                            response += f"🔗 {job.link}\n"
                        response += "\n"
                    
                    response += "Use /search_jobs to search for more jobs!"
                    
                    await update.message.reply_text(response, parse_mode='Markdown', disable_web_page_preview=True)
                    logger.info("Successfully sent job matches to user")
                else:
                    # Try a broader search by removing some constraints
                    broader_query = text("""
                        SELECT DISTINCT
                            af.name as firm_name,
                            j.job_title,
                            j.seniority,
                            j.service,
                            j.location,
                            j.employment,
                            j.salary,
                            j.link
                        FROM "JobsApp_job" j
                        JOIN "JobsApp_accountingfirm" af ON j.firm_id = af.id
                        WHERE 
                            (LOWER(j.job_title) LIKE :service_pattern
                            OR LOWER(j.service) LIKE :service_pattern)
                            AND (
                                LOWER(j.location) LIKE :location_pattern1 
                                OR LOWER(j.location) LIKE :location_pattern2
                            )
                            AND (
                                LOWER(j.seniority) LIKE :seniority_pattern1
                                OR LOWER(j.seniority) LIKE :seniority_pattern2
                            )
                        ORDER BY j.date_published DESC NULLS LAST
                        LIMIT 5
                    """)
                    
                    result = await db.execute(broader_query, search_params)
                    broader_jobs = result.fetchall()
                    
                    if broader_jobs:
                        response = "I found some similar roles that might interest you:\n\n"
                        for job in broader_jobs:
                            response += (
                                f"🏢 *{job.firm_name}*\n"
                                f"📋 {job.job_title}\n"
                            )
                            if job.seniority:
                                response += f"👔 {job.seniority}\n"
                            if job.service:
                                response += f"🔧 Service: {job.service}\n"
                            if job.location:
                                response += f"📍 {job.location}\n"
                            if job.employment:
                                response += f"⏰ {job.employment}\n"
                            if job.salary:
                                response += f"💰 {job.salary}\n"
                            if job.link:
                                response += f"🔗 {job.link}\n"
                            response += "\n"
                        
                        response += "Use /search_jobs to try a different search!"
                        
                        await update.message.reply_text(response, parse_mode='Markdown', disable_web_page_preview=True)
                        logger.info("Successfully sent broader job matches to user")
                    else:
                        logger.info("No matches found, sending alternative message")
                        await update.message.reply_text(
                            "😔 I couldn't find any exact matches for your preferences.\n\n"
                            "Try:\n"
                            "• Using more general terms\n"
                            "• Removing location requirements\n"
                            "• Searching for related roles\n\n"
                            "Use /search_jobs to try another search!"
                        )
                
            except Exception as db_error:
                logger.error(f"Database error details: {str(db_error)}", exc_info=True)
                await update.message.reply_text(
                    "Sorry, I encountered an error while searching for jobs. Please try again."
                )
                raise
            
    except Exception as e:
        logger.error(f"Error in process_job_preferences: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "Sorry, I encountered an error processing your request. Please try again."
        )
    
    return ConversationHandler.END

async def upload_cv(update: Update, context: CallbackContext) -> None:
    """Handle CV file uploads"""
    if not update.message.document:
        await update.message.reply_text(
            "Please send your CV as a document (PDF or Word format)."
        )
        return

    try:
        # Show typing indicator
        await update.message.chat.send_action(action="typing")
        
        # Get file information
        doc = update.message.document
        file = await context.bot.get_file(doc.file_id)
        
        # Log file details
        logger.debug(f"Received file: {doc.file_name} (type: {doc.mime_type}, size: {doc.file_size} bytes)")
        
        # Validate file type
        if not doc.file_name.lower().endswith(('.pdf', '.doc', '.docx')):
            await update.message.reply_text(
                "❌ Please upload your CV in PDF or Word (.doc/.docx) format only."
            )
            return

        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Download the file
        file_path = f"temp/{doc.file_name}"
        await file.download_to_drive(file_path)
        logger.debug(f"File downloaded to: {file_path}")

        # Send initial response
        processing_message = await update.message.reply_text(
            "✅ Thanks for sharing your CV! I'm analyzing it now..."
        )

        # Process the CV and get AI analysis
        cv_analysis = await process_cv(file_path)
        logger.debug("CV analysis completed")
        
        # Send detailed analysis
        await processing_message.edit_text(
            f"🎯 Here's my analysis of your CV:\n\n{cv_analysis}\n\n"
            "Would you like me to search for jobs matching your profile? "
            "Use /search_jobs to start looking!"
        )

    except Exception as e:
        logger.error(f"Error processing CV: {str(e)}", exc_info=True)
        error_message = (
            "❌ Sorry, I couldn't process your CV. The error was:\n"
            f"{str(e)}\n\n"
            "Please ensure:\n"
            "- The file is in PDF or Word format\n"
            "- The file is not password protected\n"
            "- The file is not corrupted\n"
            "Try uploading again or contact support if the issue persists."
        )
        await update.message.reply_text(error_message)

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "Search cancelled. You can start a new search anytime with /search_jobs"
    )
    return ConversationHandler.END

async def timeout(update: Update, context: CallbackContext) -> int:
    """Handle conversation timeout."""
    await update.message.reply_text(
        "Search timed out. You can start a new search anytime with /search_jobs"
    )
    return ConversationHandler.END

async def test_db(update: Update, context: CallbackContext) -> None:
    """Handler for /test_db command to verify database connection"""
    try:
        # Only allow admin users to run this command
        admin_ids = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
        if not admin_ids or update.effective_user.id not in admin_ids:
            await update.message.reply_text("⚠️ Sorry, this command is only available to admin users.")
            return

        # Send initial message
        status_message = await update.message.reply_text("🔄 Testing database connection...")

        # Run connection test
        is_connected, message = await test_database_connection()
        
        if is_connected:
            await status_message.edit_text(
                "✅ Database connection successful!\n\n"
                f"{message}\n\n"
                "You can now use /search_jobs to search for jobs."
            )
        else:
            # Get list of all tables
            all_tables = await list_all_tables()
            tables_info = "\n• ".join(all_tables) if all_tables else "No tables found"
            
            await status_message.edit_text(
                f"❌ Database connection failed.\n\n"
                f"Error: {message}\n\n"
                f"All tables in database:\n• {tables_info}\n\n"
                "Please check:\n"
                "• Database schema is properly set up\n"
                "• All required tables are created\n"
                "• Database permissions are correct\n\n"
                "Check the logs for more details."
            )
    
    except Exception as e:
        logger.error(f"Error in test_db command: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred while testing the database connection. "
            "Please check the logs for details."
        )

async def main() -> None:
    try:
        logger.debug("Starting bot initialization...")
        logger.debug(f"Using token: {TELEGRAM_BOT_TOKEN[:5]}...")
        
        # Create conversation handler for job search
        job_search_handler = ConversationHandler(
            entry_points=[CommandHandler("search_jobs", search_jobs)],
            states={
                AWAITING_JOB_PREFERENCES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, process_job_preferences)
                ]
            },
            fallbacks=[
                CommandHandler("cancel", cancel),
                MessageHandler(filters.COMMAND, cancel)
            ],
            conversation_timeout=300  # 5 minutes timeout
        )
        
        # Register handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(job_search_handler)  # Add the conversation handler
        application.add_handler(CommandHandler("upload_cv", upload_cv))
        application.add_handler(CommandHandler("test_db", test_db))  # Add the test_db command
        application.add_handler(MessageHandler(filters.Document.ALL, upload_cv))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.debug("Handlers registered successfully")

        # Start polling
        logger.info("🤖 Bot is now polling for messages...")
        
        # Start the bot
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        logger.info("Bot is running. Press Ctrl+C to stop")
        
        # Keep the bot running until interrupted
        stop_signal = asyncio.Event()
        await stop_signal.wait()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}", exc_info=True)
        raise
    finally:
        # Only try to stop if the application was started
        if application.running:
            await application.stop()

if __name__ == "__main__":
    # Run the bot in polling mode for local development
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
