from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
from dotenv import load_dotenv
import os
import logging
from app.ai_handler import get_ai_response, process_cv, extract_job_preferences, standardize_search_terms
from app.database import SessionLocal, test_database_connection, list_all_tables
from app.models import User, UserSearch
import asyncio
from datetime import datetime
from logging.handlers import RotatingFileHandler
from sqlalchemy import text
import json
import time

# Load environment variables
load_dotenv()

def setup_logging():
    """Configure logging with file cleanup on startup"""
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Clear existing log file
    log_file = 'logs/conversations.log'
    open(log_file, 'w', encoding='utf-8').close()  # Truncate the file
    
    # Setup logging configuration
    logging.basicConfig(
        level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            RotatingFileHandler(
                log_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
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
        start_time = time.time()
        
        logger.debug(f"Starting job preference processing for user {user_id}")
        logger.info(f"Processing job preferences for user {user_id}: {user_input}")
        
        # Extract structured preferences using AI
        try:
            logger.debug("Calling extract_job_preferences")
            preferences = await extract_job_preferences(user_input)
            if not preferences:
                logger.warning(f"No preferences extracted from input: {user_input}")
                await update.message.reply_text(
                    "I couldn't understand your job preferences. Please try again with more specific details about:\n"
                    "• The role you're looking for\n"
                    "• Your preferred location\n"
                    "• Your experience level"
                )
                return ConversationHandler.END
            logger.info(f"Extracted preferences: {preferences}")
        except Exception as e:
            logger.error(f"Error extracting preferences: {str(e)}", exc_info=True)
            await update.message.reply_text(
                "Sorry, I had trouble understanding your preferences. Please try again with clearer details."
            )
            return ConversationHandler.END
        
        # Standardize search terms
        try:
            logger.debug("Standardizing search terms")
            standardized = await standardize_search_terms(preferences)
            if not standardized:
                logger.warning(f"Failed to standardize terms for preferences: {preferences}")
                await update.message.reply_text(
                    "I had trouble processing your search terms. Please try again with different wording."
                )
                return ConversationHandler.END
            logger.info(f"Standardized terms: {standardized}")
        except Exception as e:
            logger.error(f"Error standardizing search terms: {str(e)}", exc_info=True)
            await update.message.reply_text(
                "Sorry, I encountered an error processing your search terms. Please try again."
            )
            return ConversationHandler.END
        
        # Validate standardized terms
        if not any(
            standardized.get(key, {}).get('search_variations', [])
            for key in ['role', 'location', 'experience']
        ):
            logger.warning(f"No valid search variations generated for any field: {standardized}")
            await update.message.reply_text(
                "I couldn't generate valid search terms. Please try again with more specific details."
            )
            return ConversationHandler.END
        
        # Log the number of search variations
        for key, value in standardized.items():
            if isinstance(value, dict) and 'search_variations' in value:
                logger.debug(f"Number of {key} variations: {len(value['search_variations'])}")
                logger.debug(f"{key} variations: {value['search_variations']}")
        
        # Store the search in database
        async with SessionLocal() as db:
            try:
                # Prepare search parameters - simplified
                try:
                    search_params = {
                        "job_pattern": f"%{str(standardized.get('role', {}).get('standardized', '')).lower()}%",
                        "location_pattern": f"%{str(standardized.get('location', {}).get('standardized', '')).lower()}%",
                        "seniority_pattern": f"%{str(standardized.get('experience', {}).get('standardized', '')).lower()}%"
                    }
                    
                    logger.debug(f"Search parameters prepared: {json.dumps(search_params, indent=2)}")
                except Exception as e:
                    logger.error(f"Error preparing search parameters: {str(e)}", exc_info=True)
                    raise

                # Execute search query with simplified patterns
                query = text("""
                    SELECT DISTINCT
                        af.name as firm_name,
                        j.job_title,
                        j.seniority,
                        j.service,
                        j.location,
                        j.employment,
                        j.salary,
                        j.link,
                        j.date_published,
                        CASE 
                            WHEN LOWER(j.job_title) LIKE :job_pattern THEN 3
                            WHEN LOWER(j.service) LIKE :job_pattern THEN 2
                            ELSE 1
                        END as match_score
                    FROM "JobsApp_job" j
                    JOIN "JobsApp_accountingfirm" af ON j.firm_id = af.id
                    WHERE (
                        LOWER(j.job_title) LIKE :job_pattern
                        OR LOWER(j.service) LIKE :job_pattern
                    )
                    AND LOWER(j.location) LIKE :location_pattern
                    AND LOWER(j.seniority) LIKE :seniority_pattern
                    ORDER BY match_score DESC, j.date_published DESC NULLS LAST
                    LIMIT 5
                """)

                try:
                    # Execute the query
                    result = await db.execute(query, search_params)
                    jobs = result.fetchall()
                    search_time = time.time() - start_time
                    logger.info(f"Search completed in {search_time:.2f} seconds")
                    logger.info(f"Found {len(jobs) if jobs else 0} matching jobs")
                except Exception as e:
                    logger.error(f"Database query execution error: {str(e)}", exc_info=True)
                    logger.error(f"Failed query parameters: {search_params}")
                    raise
                
                if jobs:
                    logger.debug("Job matches found:")
                    for job in jobs:
                        logger.debug(f"Match: {job.firm_name} - {job.job_title} ({job.location})")
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
                    # Try a broader search by using more permissive patterns
                    broader_params = {
                        "job_pattern": f"%{str(standardized.get('role', {}).get('standardized', '')).split()[0].lower()}%",  # Use first word only
                        "location_pattern": "%%",  # Match any location
                        "seniority_pattern": "%%"  # Match any seniority
                    }
                    
                    logger.debug("No exact matches found, trying broader search with parameters:")
                    logger.debug(json.dumps(broader_params, indent=2))
                    
                    result = await db.execute(query, broader_params)
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
                            "😔 I couldn't find any matching jobs.\n\n"
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

    file_path = None
    processing_message = None

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
            "✅ Thanks for sharing your CV! I'm analyzing it now...\n"
            "This may take a few moments. I'll notify you when the analysis is complete."
        )

        # Define an async function to process the CV and update the user
        async def process_cv_and_update():
            try:
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
                logger.error(f"Error in CV processing task: {str(e)}", exc_info=True)
                await processing_message.edit_text(
                    "❌ Sorry, I encountered an error while analyzing your CV.\n"
                    "Please try uploading again or contact support if the issue persists."
                )
            finally:
                # Clean up the temporary file
                try:
                    os.remove(file_path)
                    logger.debug(f"Cleaned up temporary file: {file_path}")
                except Exception as e:
                    logger.error(f"Error cleaning up temporary file: {str(e)}")

        # Create background task for CV processing
        asyncio.create_task(process_cv_and_update())

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
        # Only send error message if we haven't already sent one via processing_message
        if not processing_message or not processing_message.edit_date:
            await update.message.reply_text(error_message)
            
        # Clean up the file if it exists
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.debug(f"Cleaned up temporary file after error: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {str(cleanup_error)}", exc_info=True)

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
