import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update
from telegram.ext import ContextTypes
from app.telegram_bot import (
    start_command,
    help_command,
    upload_cv_command,
    search_jobs_command,
    set_preferences_command
)
from app.models import User, UserSearch, UserConversation
import logging
from sqlalchemy import select
import json
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
def mock_update():
    update = AsyncMock()
    update.effective_user = AsyncMock()
    update.effective_user.id = 12345
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.message = AsyncMock()
    update.message.text = ""
    return update

@pytest.fixture
def mock_context():
    return AsyncMock()

@pytest.mark.asyncio
async def test_start_command(mock_update, mock_context, db_session):
    """Test start command creates new user"""
    mock_update.effective_user.id = 11111
    mock_update.effective_user.username = "test_user_1"
    mock_update.effective_user.first_name = "Test"
    mock_update.effective_user.last_name = "User"

    await start_command(mock_update, mock_context)

    # Verify user was created
    result = await db_session.execute(
        select(User).where(User.telegram_id == 11111)
    )
    user = result.scalar_one()
    assert user.telegram_id == 11111
    assert user.username == "test_user_1"
    assert user.first_name == "Test"
    assert user.last_name == "User"

@pytest.mark.asyncio
async def test_help_command(mock_update, mock_context):
    """Test the /help command returns appropriate guidance"""
    await help_command(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()
    help_text = mock_update.message.reply_text.call_args[0][0]
    assert "commands" in help_text.lower()
    assert "/start" in help_text
    assert "/help" in help_text
    assert "/upload_cv" in help_text
    assert "/search" in help_text

@pytest.mark.asyncio
async def test_upload_cv_command(mock_update, mock_context, db_session, temp_dir):
    """Test CV upload and processing"""
    # Create test user
    user = User(
        telegram_id=22222,
        username="test_user_2",
        first_name="Test",
        last_name="User"
    )
    db_session.add(user)
    await db_session.commit()

    mock_update.effective_user.id = 22222
    mock_update.message.document = AsyncMock()
    mock_update.message.document.file_id = "test_file_id"
    mock_update.message.document.file_name = "test_cv.pdf"

    # Create a test PDF file
    test_file_path = temp_dir / "test_cv.pdf"
    c = canvas.Canvas(str(test_file_path))
    c.drawString(100, 750, "Test CV Content")
    c.save()

    # Mock file download
    mock_context.bot.get_file = AsyncMock()
    mock_file = AsyncMock()
    mock_file.download = AsyncMock()
    mock_context.bot.get_file.return_value = mock_file
    mock_file.download_to_drive = AsyncMock(return_value=str(test_file_path))

    await upload_cv_command(mock_update, mock_context)

    # Verify CV was processed
    result = await db_session.execute(
        select(User).where(User.telegram_id == 22222)
    )
    user = result.scalar_one()
    assert user.cv_text is not None
    assert isinstance(json.loads(user.cv_embedding), list)  # Verify embedding is stored as JSON string

@pytest.mark.asyncio
async def test_search_jobs_command(db_session):
    """Test searching for jobs"""
    # Create mock update and context
    update = MagicMock(spec=Update)
    update.message.text = "/search_jobs audit jobs"
    update.effective_user.id = 123456789
    update.message.reply_text = AsyncMock()
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # Create test user
    user = User(
        telegram_id=123456789,
        username="testuser",
        cv_embedding="[]"  # Empty list as JSON string
    )
    db_session.add(user)
    await db_session.commit()

    # Call the command
    await search_jobs_command(update, context)

    # Verify response
    update.message.reply_text.assert_called_once_with(
        "🔍 Searching for jobs matching your query...\n"
        "This feature is coming soon!"
    )

    # Verify search was recorded
    result = await db_session.execute(
        select(UserSearch).where(UserSearch.telegram_id == 123456789)
    )
    search = result.scalar_one()
    assert search.search_query == "audit jobs"

@pytest.mark.asyncio
async def test_set_preferences_command(db_session):
    """Test setting user preferences"""
    # Create mock update and context
    update = MagicMock(spec=Update)
    update.message.text = "/preferences location=New York role=Auditor"
    update.effective_user.id = 123456789
    update.message.reply_text = AsyncMock()
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # Create test user
    user = User(
        telegram_id=123456789,
        username="testuser"
    )
    db_session.add(user)
    await db_session.commit()

    # Call the command
    await set_preferences_command(update, context)

    # Verify preferences were set
    result = await db_session.execute(
        select(User).where(User.telegram_id == 123456789)
    )
    user = result.scalar_one()
    preferences = user.get_preferences()
    assert preferences == {
        "location": "New York",
        "role": "Auditor"
    }

    # Verify response
    update.message.reply_text.assert_called_once_with(
        "✅ Preferences updated successfully!\n"
        "Your current preferences:\n"
        '{\n  "location": "New York",\n  "role": "Auditor"\n}'
    )

@pytest.mark.asyncio
async def test_user_not_found(db_session):
    """Test handling of non-existent user"""
    # Create mock update and context
    update = MagicMock(spec=Update)
    update.message.text = "/search_jobs audit jobs"
    update.effective_user.id = 999999  # Non-existent user
    update.message.reply_text = AsyncMock()
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # Call the command
    await search_jobs_command(update, context)

    # Verify error response
    update.message.reply_text.assert_called_once_with(
        "❌ You need to start a conversation with /start first."
    )

@pytest.mark.asyncio
async def test_invalid_preferences_format(db_session):
    """Test handling of invalid preferences format"""
    # Create mock update and context
    update = MagicMock(spec=Update)
    update.message.text = "/preferences invalid format"
    update.effective_user.id = 123456789
    update.message.reply_text = AsyncMock()
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # Create test user
    user = User(
        telegram_id=123456789,
        username="testuser"
    )
    db_session.add(user)
    await db_session.commit()

    # Call the command
    await set_preferences_command(update, context)

    # Verify preferences were not set
    result = await db_session.execute(
        select(User).where(User.telegram_id == 123456789)
    )
    user = result.scalar_one()
    preferences = user.get_preferences()
    assert preferences == {}

    # Verify response
    update.message.reply_text.assert_called_once_with(
        "❌ Sorry, there was an error setting your preferences. Please try again later."
    ) 