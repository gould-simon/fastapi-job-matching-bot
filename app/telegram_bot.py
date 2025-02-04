from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv
import os
import logging
from app.ai_handler import get_ai_response, process_cv
from app.database import SessionLocal
from app.models import User

# Load environment variables
load_dotenv()

# Retrieve Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN is missing! Check your .env file.")

# Update the logging configuration
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create temp directory if it doesn't exist
os.makedirs("temp", exist_ok=True)

# Define command handlers
async def start(update: Update, context: CallbackContext) -> None:
    welcome_message = (
        "👋 Hello! I'm your AI-powered job-matching assistant for accounting professionals!\n\n"
        "Here's what I can help you with:\n"
        "🔍 /search_jobs - Search for accounting jobs\n"
        "📄 /upload_cv - Upload your CV for personalized matches\n"
        "🔔 /set_alerts - Set up job alerts\n"
        "💬 Or simply chat with me about your career goals!"
    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: CallbackContext) -> None:
    user_input = update.message.text
    
    # Show typing indicator
    await update.message.chat.send_action(action="typing")
    
    # Get AI response
    ai_response = await get_ai_response(
        user_input,
        context="User is looking for accounting job opportunities"
    )
    
    await update.message.reply_text(ai_response)

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

# Add debug logs in main()
def main():
    try:
        logger.debug("Starting bot initialization...")
        logger.debug(f"Using token: {TELEGRAM_BOT_TOKEN[:5]}...")
        
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        logger.debug("Application built successfully")

        # Register command handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("search_jobs", search_jobs))
        app.add_handler(CommandHandler("upload_cv", upload_cv))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.ALL, upload_cv))  # Handle file uploads
        logger.debug("Handlers registered successfully")

        # Start polling
        logger.info("🤖 Bot is now polling for messages...")
        app.run_polling()
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
