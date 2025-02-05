import pytest
from fastapi.testclient import TestClient
from app.admin_dashboard import app
from app.models import User, UserSearch, UserConversation, JobMatch
from datetime import datetime, timedelta
import json
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

client = TestClient(app)

@pytest.fixture
async def sample_data(db_session):
    """Create sample data for testing"""
    # Create test users
    users = []
    for i in range(3):
        user = User(
            telegram_id=1000 + i,
            username=f"testuser{i}",
            first_name=f"Test{i}",
            last_name=f"User{i}",
            cv_text="Sample CV text",
            preferences={"location": "New York", "role": "Auditor"}
        )
        db_session.add(user)
        users.append(user)
    
    # Create test searches
    searches = []
    for user in users:
        search = UserSearch(
            telegram_id=user.telegram_id,
            search_query="audit jobs",
            structured_preferences=json.dumps({"role": "Auditor"})
        )
        db_session.add(search)
        searches.append(search)
    
    # Create test conversations
    conversations = []
    for user in users:
        conv = UserConversation(
            telegram_id=user.telegram_id,
            message="Test message",
            is_user=True
        )
        db_session.add(conv)
        conversations.append(conv)
    
    await db_session.commit()
    return users, searches, conversations

@pytest.mark.asyncio
async def test_dashboard_overview(sample_data):
    """Test dashboard overview endpoint"""
    await sample_data  # Ensure data is created
    response = client.get("/api/admin/overview")
    assert response.status_code == 200
    data = response.json()
    assert "total_users" in data
    assert "active_users_24h" in data
    assert "total_searches" in data
    assert "total_conversations" in data
    
    assert data["total_users"] >= 2
    assert data["total_searches"] >= 2
    assert data["total_conversations"] >= 2

@pytest.mark.asyncio
async def test_user_activity(sample_data):
    """Test user activity endpoint"""
    await sample_data  # Ensure data is created
    response = client.get("/api/admin/user-activity")
    assert response.status_code == 200
    data = response.json()
    assert "daily_active_users" in data
    assert "user_engagement" in data
    assert len(data["daily_active_users"]) > 0

@pytest.mark.asyncio
async def test_search_analytics(sample_data):
    """Test search analytics endpoint"""
    await sample_data  # Ensure data is created
    response = client.get("/api/admin/search-analytics")
    assert response.status_code == 200
    data = response.json()
    assert "popular_searches" in data
    assert "search_trends" in data
    assert len(data["popular_searches"]) > 0

@pytest.mark.asyncio
async def test_conversation_analytics(sample_data):
    """Test conversation analytics endpoint"""
    await sample_data  # Ensure data is created
    response = client.get("/api/admin/conversation-analytics")
    assert response.status_code == 200
    data = response.json()
    assert "conversation_trends" in data
    assert "user_messages" in data
    assert "bot_messages" in data
    assert len(data["conversation_trends"]) > 0

@pytest.mark.asyncio
async def test_user_details(sample_data):
    """Test user details endpoint"""
    users, _, _ = await sample_data
    
    # Test valid user
    response = client.get(f"/api/admin/users/{users[0].telegram_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == users[0].telegram_id
    assert data["username"] == users[0].username
    
    # Test invalid user
    response = client.get("/api/admin/users/999999")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in admin dashboard"""
    # Test invalid user ID
    response = client.get("/api/admin/users/999999")
    assert response.status_code == 404
    
    # Test invalid date range
    response = client.get("/api/admin/user-activity?start_date=invalid")
    assert response.status_code == 400
    
    # Test unauthorized access
    # This would need proper auth setup
    # response = client.get("/api/admin/overview", headers={})
    # assert response.status_code == 401 