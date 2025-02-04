from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv
import os
import logging
from app.ai_handler import get_ai_response, process_cv
from app.database import SessionLocal
from app.models import User
import asyncio
from datetime import datetime
from logging.handlers import RotatingFileHandler

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
        level=logging.INFO,
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
    
    logger = logging.getLogger(__name__)
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

async def search_jobs(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "🔍 What kind of accounting job are you looking for?\n"
        "Please specify any preferences like:\n"
        "- Role (e.g., Tax Accountant, Audit Manager)\n"
        "- Location\n"
        "- Experience level\n"
        "- Salary range"
    )

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

async def main() -> None:
    try:
        logger.debug("Starting bot initialization...")
        logger.debug(f"Using token: {TELEGRAM_BOT_TOKEN[:5]}...")
        
        # Register command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("search_jobs", search_jobs))
        application.add_handler(CommandHandler("upload_cv", upload_cv))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.Document.ALL, upload_cv))
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
