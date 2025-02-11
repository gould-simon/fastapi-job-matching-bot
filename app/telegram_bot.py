from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler,
    ContextTypes,
)
from telegram.constants import ParseMode
from dotenv import load_dotenv
import os
import logging
from app.ai_handler import (
    get_ai_response,
    process_cv,
    extract_job_preferences,
    standardize_search_terms,
)
from app.database import (
    AsyncSessionLocal,
    test_database_connection,
    list_all_tables,
    get_db,
)
from app.models import (
    User,
    UserSearch,
    UserConversation,
    Job,
    JobEmbedding,
    AccountingFirm,
)
import asyncio
from datetime import datetime
from logging.handlers import RotatingFileHandler
from sqlalchemy import text
import json
import time
from app.embeddings import semantic_job_search
from telegram.helpers import escape_markdown
from sqlalchemy.sql import select
from app.logging_config import get_logger
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func

# Load environment variables
load_dotenv()


def setup_logging():
    """Configure logging with file rotation"""
    # This function is now handled by logging_config.py
    pass


# Use this at the start of your bot
logger = get_logger(__name__)

# Retrieve Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN is missing! Check your .env file.")

# Add environment identifier
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
logger.info(
    f"🚀 Starting bot in {ENVIRONMENT} environment using bot token: {TELEGRAM_BOT_TOKEN[:8]}..."
)

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
            async with AsyncSessionLocal() as db:
                # Check if user exists
                logger.debug("Checking if user exists in database...")
                result = await db.execute(
                    text("SELECT * FROM users WHERE telegram_id = :telegram_id"),
                    {"telegram_id": update.effective_user.id},
                )
                user = result.first()

                if not user:
                    # Create new user
                    logger.debug("Creating new user...")
                    new_user = User(
                        telegram_id=update.effective_user.id,
                        username=update.effective_user.username,
                        first_name=update.effective_user.first_name,
                        last_name=update.effective_user.last_name,
                    )
                    db.add(new_user)
                    await db.commit()
                    logger.info(f"New user registered: {update.effective_user.id}")
        except Exception as db_error:
            logger.error(
                f"Database error in start command: {str(db_error)}", exc_info=True
            )
            # Don't return error to user since welcome message was already sent
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "Sorry, I encountered an error. Please try again."
        )


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
        await update.message.reply_text(
            "Sorry, I encountered an error processing your message."
        )


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
            error_msg = f"Error extracting preferences: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await update.message.reply_text(
                "I had trouble understanding your preferences. The error was:\n"
                f"_{escape_markdown(str(e))}_\n\n"
                "Please try again with clearer details about the role, location, and experience level."
            )
            return ConversationHandler.END

        # Store the search in database
        async with AsyncSessionLocal() as db:
            try:
                # Check database state before search
                logger.info("Checking database state before search...")
                jobs_count = await db.scalar(select(func.count()).select_from(Job))
                embeddings_count = await db.scalar(
                    select(func.count()).select_from(JobEmbedding)
                )
                firms_count = await db.scalar(
                    select(func.count()).select_from(AccountingFirm)
                )
                logger.info(
                    f"Database state: {jobs_count} jobs, {embeddings_count} embeddings, {firms_count} firms"
                )

                if jobs_count == 0:
                    await update.message.reply_text(
                        "I couldn't find any jobs in the database. This could be because:\n"
                        "• The job database hasn't been initialized yet\n"
                        "• The job scraper hasn't run recently\n"
                        "• There was an error during the last database update\n\n"
                        "Please try again later or contact support."
                    )
                    return ConversationHandler.END

                if embeddings_count == 0:
                    await update.message.reply_text(
                        "The job search system needs to be initialized. This could be because:\n"
                        "• The embeddings haven't been generated yet\n"
                        "• There was an error during embedding generation\n\n"
                        "Please try again later or contact support."
                    )
                    return ConversationHandler.END

                # Use semantic search
                matching_jobs = await semantic_job_search(
                    db=db,
                    query_text=user_input,
                    location=preferences.get("location"),
                    limit=5,
                )

                search_time = time.time() - start_time
                logger.info(f"Search completed in {search_time:.2f} seconds")
                logger.info(f"Found {len(matching_jobs)} matching jobs")

                if not matching_jobs:
                    await update.message.reply_text(
                        "I couldn't find any jobs matching your criteria. This could be because:\n"
                        "• There are no jobs in the database matching your location\n"
                        "• The job title or role you're looking for isn't currently available\n"
                        "• The search terms might be too specific\n\n"
                        "Try broadening your search or using different terms."
                    )
                    return ConversationHandler.END

                logger.debug("Job matches found:")
                for job in matching_jobs:
                    # Ensure all required fields exist and have valid values
                    job_title = job.get("job_title", "No title")
                    firm_name = job.get("firm_name", "Unknown firm")
                    location = job.get("location", "Location not specified")
                    similarity_score = job.get("similarity_score", 0.0)

                    logger.debug(
                        f"Match: {firm_name} - {job_title} (Score: {similarity_score:.2f})"
                    )

                response = "🎯 Here are some matching jobs:\n\n"
                for i, job in enumerate(matching_jobs, 1):
                    try:
                        # Safely escape and format each field
                        def safe_escape(text):
                            if not text:
                                return ""
                            # Convert string representation of list to actual list
                            text_str = str(text)
                            if text_str.startswith("[") and text_str.endswith("]"):
                                try:
                                    # Remove the brackets and split by comma
                                    items = text_str[1:-1].split(",")
                                    # Clean up each item
                                    items = [
                                        item.strip().strip("'").strip('"')
                                        for item in items
                                        if item.strip()
                                    ]
                                    if len(items) == 1:
                                        text_str = items[0]  # Single location
                                    else:
                                        text_str = ", ".join(
                                            items
                                        )  # Multiple locations
                                except Exception as e:
                                    logger.warning(f"Error parsing location list: {e}")

                            # Escape special characters for MarkdownV2
                            chars_to_escape = [
                                "_",
                                "*",
                                "[",
                                "]",
                                "(",
                                ")",
                                "~",
                                "`",
                                ">",
                                "#",
                                "+",
                                "-",
                                "=",
                                "|",
                                "{",
                                "}",
                                ".",
                                "!",
                            ]
                            for char in chars_to_escape:
                                text_str = text_str.replace(char, f"\\{char}")
                            return text_str

                        def format_salary(salary):
                            if not salary:
                                return "Not specified"
                            # Handle various salary formats
                            salary_str = str(salary)
                            if salary_str.isdigit() and len(salary_str) <= 2:
                                return "Competitive"  # Replace placeholder values
                            # Format salary ranges nicely
                            if " - " in salary_str:
                                try:
                                    min_sal, max_sal = salary_str.split(" - ")
                                    min_sal = int(min_sal)
                                    max_sal = int(max_sal)
                                    return f"${min_sal:,} - ${max_sal:,}"
                                except:
                                    pass
                            return salary_str

                        title = safe_escape(job.get("job_title", "No title"))
                        firm = safe_escape(job.get("firm_name", "Unknown firm"))
                        loc = safe_escape(job.get("location", "Location not specified"))
                        seniority = safe_escape(job.get("seniority", "Not specified"))
                        salary = safe_escape(
                            format_salary(job.get("salary", "Not specified"))
                        )
                        link = safe_escape(job.get("link", "No link available"))

                        job_entry = (
                            f"{i}\\. *{title}*\n"
                            f"   🏢 {firm}\n"
                            f"   📍 {loc}\n"
                            f"   💼 {seniority}\n"
                            f"   💰 {salary}\n"
                            f"   🔗 {link}\n\n"
                        )
                        response += job_entry

                    except Exception as e:
                        logger.error(
                            f"Error formatting job {i}: {str(e)}", exc_info=True
                        )
                        continue

                response += "Use /search\\_jobs to search for more jobs\\!"

                try:
                    # First try with MarkdownV2
                    await update.message.reply_text(
                        response,
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=True,
                    )
                except Exception as e:
                    logger.error(
                        f"Error sending markdown response: {str(e)}", exc_info=True
                    )
                    try:
                        # If markdown fails, try sending a simplified plain text version
                        plain_response = "🎯 Here are some matching jobs:\n\n"
                        for i, job in enumerate(matching_jobs, 1):
                            plain_response += (
                                f"{i}. {job.get('job_title', 'No title')}\n"
                                f"   Company: {job.get('firm_name', 'Unknown firm')}\n"
                                f"   Location: {job.get('location', 'Location not specified')}\n"
                                f"   Seniority: {job.get('seniority', 'Not specified')}\n"
                                f"   Salary: {job.get('salary', 'Not specified')}\n"
                                f"   Link: {job.get('link', 'No link available')}\n\n"
                            )
                        plain_response += "Use /search_jobs to search for more jobs!"

                        await update.message.reply_text(
                            plain_response, disable_web_page_preview=True
                        )
                    except Exception as e2:
                        logger.error(
                            f"Error sending plain text response: {str(e2)}",
                            exc_info=True,
                        )
                        await update.message.reply_text(
                            "I found some matching jobs but had trouble displaying them. "
                            "Please try searching again or contact support if the issue persists."
                        )
                return ConversationHandler.END

            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                logger.error(
                    f"Error in semantic search: {error_type} - {error_msg}",
                    exc_info=True,
                )

                # Provide more specific error messages based on the type of error
                if "OpenAI" in error_type:
                    await update.message.reply_text(
                        "Sorry, I'm having trouble connecting to the AI service. This might be due to:\n"
                        "• API key configuration issues\n"
                        "• Service availability\n"
                        "• Rate limiting\n\n"
                        "Please try again in a few moments."
                    )
                elif "DatabaseError" in error_type or "OperationalError" in error_type:
                    await update.message.reply_text(
                        "Sorry, I'm having trouble accessing the job database. This might be due to:\n"
                        "• Database connection issues\n"
                        "• Missing or incomplete job data\n"
                        "• Database maintenance\n\n"
                        "Please try again in a few moments."
                    )
                else:
                    await update.message.reply_text(
                        f"Sorry, I encountered an error while searching for jobs:\n"
                        f"_{escape_markdown(error_msg)}_\n\n"
                        "Please try again with different search terms or contact support if the issue persists."
                    )
                return ConversationHandler.END

    except Exception as e:
        logger.error(f"Unexpected error in job search: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "An unexpected error occurred while processing your request:\n"
            f"_{escape_markdown(str(e))}_\n\n"
            "Please try again or contact support if the issue persists."
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
        logger.debug(
            f"Received file: {doc.file_name} (type: {doc.mime_type}, size: {doc.file_size} bytes)"
        )

        # Validate file type
        if not doc.file_name.lower().endswith((".pdf", ".doc", ".docx")):
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
                logger.error(
                    f"Error during cleanup: {str(cleanup_error)}", exc_info=True
                )


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
            await update.message.reply_text(
                "⚠️ Sorry, this command is only available to admin users."
            )
            return

        # Send initial message
        status_message = await update.message.reply_text(
            "🔄 Testing database connection..."
        )

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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler - creates new user if not exists"""
    try:
        async with AsyncSessionLocal() as db:
            # Check if user exists using SQLAlchemy ORM
            result = await db.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            try:
                user = result.scalar_one()
                await update.message.reply_text(
                    f"Welcome back {user.username or user.first_name or 'there'}! 👋\n"
                    "I'm here to help you find your dream job in accounting.\n"
                    "Use /help to see available commands."
                )
            except NoResultFound:
                # Create new user
                user = User(
                    telegram_id=update.effective_user.id,
                    username=update.effective_user.username,
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name,
                )
                db.add(user)
                await db.commit()

                await update.message.reply_text(
                    f"Hello {user.username or user.first_name or 'there'}! 👋\n"
                    "I'm your personal job matching assistant.\n"
                    "I'll help you find the perfect accounting job.\n\n"
                    "Here's how to get started:\n"
                    "1. Upload your CV using /upload_cv\n"
                    "2. Set your preferences with /preferences\n"
                    "3. Search for jobs with /search_jobs\n\n"
                    "Use /help to see all available commands."
                )
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ Sorry, there was an error starting the conversation. Please try again."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command"""
    help_text = (
        "Here are the available commands:\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/upload_cv - Upload your CV (PDF or DOCX)\n"
        "/search - Search for jobs\n"
        "/preferences - Set your job preferences\n"
    )
    await update.message.reply_text(help_text)


async def upload_cv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle CV upload"""
    try:
        user_info = {
            "telegram_id": update.effective_user.id,
            "username": update.effective_user.username,
        }
        logger.info("CV upload initiated", extra={"user": user_info})

        if not update.message.document:
            logger.warning(
                "No document provided for CV upload", extra={"user": user_info}
            )
            await update.message.reply_text(
                "Please upload your CV as a PDF or Word document."
            )
            return

        file = update.message.document
        if not file.file_name.lower().endswith((".pdf", ".docx")):
            logger.warning(
                "Invalid file format",
                extra={"user": user_info, "file_name": file.file_name},
            )
            await update.message.reply_text(
                "Please upload your CV in PDF or Word (.docx) format only."
            )
            return

        # Download and process CV
        bot_file = await context.bot.get_file(file.file_id)
        file_path = f"temp/{update.effective_user.id}_{file.file_name}"
        await bot_file.download_to_drive(file_path)

        logger.info(
            "CV file downloaded",
            extra={
                "user": user_info,
                "file_path": file_path,
                "file_size": os.path.getsize(file_path),
            },
        )

        # Process CV
        cv_text, cv_embedding = await process_cv(file_path)

        # Update database
        async with AsyncSessionLocal() as session:
            user = await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            user = user.scalar_one()
            user.cv_text = cv_text
            user.cv_embedding = json.dumps(
                cv_embedding
            )  # Store as JSON string for SQLite
            await session.commit()

        logger.info("CV processed successfully", extra={"user": user_info})

        # Clean up
        os.remove(file_path)

        await update.message.reply_text(
            "✅ Your CV has been successfully processed! You can now:\n"
            "1. Search for jobs using /search\n"
            "2. Set your preferences using /preferences"
        )

    except Exception as e:
        logger.error(f"Error in upload_cv_command: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "Sorry, I encountered an error while processing your CV. Please try again later."
        )
        # Clean up on error
        if "file_path" in locals() and os.path.exists(file_path):
            os.remove(file_path)


async def search_jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for jobs command handler"""
    try:
        search_query = update.message.text.replace("/search_jobs", "").strip()
        if not search_query:
            await update.message.reply_text(
                "Please provide a search query. For example:\n"
                "/search_jobs audit jobs in New York"
            )
            return

        async with AsyncSessionLocal() as db:
            # Check if user exists using SQLAlchemy ORM
            result = await db.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            try:
                user = result.scalar_one()

                # Record the search
                search = UserSearch(
                    telegram_id=update.effective_user.id, search_query=search_query
                )
                db.add(search)
                await db.commit()

                # Get user's CV embedding
                cv_embedding = user.get_cv_embedding()

                # TODO: Implement job search logic
                await update.message.reply_text(
                    "🔍 Searching for jobs matching your query...\n"
                    "This feature is coming soon!"
                )

            except NoResultFound:
                logger.error(f"User not found: {update.effective_user.id}")
                await update.message.reply_text(
                    "❌ You need to start a conversation with /start first."
                )
                return

    except Exception as e:
        logger.error(f"Error in search_jobs_command: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ Sorry, there was an error processing your search. Please try again later."
        )


async def set_preferences_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user preferences command handler"""
    try:
        # Extract preferences from message text
        # Format should be: /preferences key1=value1 key2=value2
        preferences_text = update.message.text.replace("/preferences", "").strip()
        if not preferences_text:
            await update.message.reply_text(
                "Please provide your preferences in the format:\n"
                "/preferences location=New York role=Auditor"
            )
            return

        # Parse preferences into dictionary
        preferences = {}
        try:
            for pair in preferences_text.split():
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    preferences[key.strip()] = value.strip()
        except Exception:
            raise ValueError("Invalid preferences format")

        if not preferences:
            raise ValueError("No valid preferences provided")

        async with AsyncSessionLocal() as db:
            # Check if user exists using SQLAlchemy ORM
            result = await db.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            try:
                user = result.scalar_one()

                # Update preferences
                user.set_preferences(preferences)
                await db.commit()

                await update.message.reply_text(
                    "✅ Preferences updated successfully!\n"
                    "Your current preferences:\n"
                    f"{json.dumps(preferences, indent=2)}"
                )

            except NoResultFound:
                logger.error(f"User not found: {update.effective_user.id}")
                await update.message.reply_text(
                    "❌ You need to start a conversation with /start first."
                )
                return

    except ValueError as e:
        logger.error(f"Invalid preferences format: {str(e)}")
        await update.message.reply_text(
            "❌ Please provide preferences in the correct format:\n"
            "/preferences location=New York role=Auditor"
        )
    except Exception as e:
        logger.error(f"Error setting preferences: {str(e)}")
        await update.message.reply_text(
            "❌ Sorry, there was an error setting your preferences. Please try again later."
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
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, process_job_preferences
                    )
                ]
            },
            fallbacks=[
                CommandHandler("cancel", cancel),
                MessageHandler(filters.COMMAND, cancel),
            ],
            conversation_timeout=300,  # 5 minutes timeout
        )

        # Register handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(job_search_handler)  # Add the conversation handler
        application.add_handler(CommandHandler("upload_cv", upload_cv))
        application.add_handler(
            CommandHandler("test_db", test_db)
        )  # Add the test_db command
        application.add_handler(MessageHandler(filters.Document.ALL, upload_cv))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

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
