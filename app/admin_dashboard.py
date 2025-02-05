import streamlit as st
import psycopg2
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse
import logging
import sqlite3
import json
from fastapi import FastAPI, HTTPException, Query, APIRouter
from fastapi.responses import JSONResponse
from app.models import User, UserSearch, UserConversation, JobMatch
from app.database import get_db
import pandas as pd
from typing import List, Dict, Any, Optional
from sqlalchemy import func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select
from fastapi import Depends
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from app.database import engine

# At the top of the file, add logging
logger = logging.getLogger(__name__)

# Add this near the top of the file, after the imports
st.sidebar.text("Database URL Structure Check")
database_url = os.getenv("DATABASE_URL")
if database_url:
    parsed = urlparse(database_url)
    st.sidebar.text(f"""
    Hostname: {parsed.hostname}
    Port: {parsed.port}
    Path: {parsed.path}
    """)

# Modify the get_db_connection_string function
def get_db_connection_string():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    try:
        # Parse the URL to handle any special characters
        parsed = urlparse(database_url)
        
        # Set default port if none specified
        port = parsed.port or 5432
        
        # Convert asyncpg URL to psycopg2 compatible URL
        if 'postgresql+asyncpg://' in database_url:
            database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        
        # Handle special case for postgres:// URLs
        if 'postgres://' in database_url:
            database_url = database_url.replace('postgres://', 'postgresql://')
        
        # For Render.com PostgreSQL URLs, ensure proper formatting
        if parsed.hostname and 'dpg-' in parsed.hostname:
            # Reconstruct the URL with proper host formatting and explicit port
            database_url = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{port}/{parsed.path.lstrip('/')}"
            
        logger.debug(f"Processed database URL (showing structure): postgresql://user:****@{parsed.hostname}:{port}/{parsed.path.lstrip('/')}")
        return database_url
    except Exception as e:
        logger.error(f"Error parsing DATABASE_URL: {str(e)}")
        raise

# Modify the database connection functions to use connection pooling
from psycopg2 import pool

# Modify the connection pool creation
try:
    # Add connection timeout and TCP keepalive
    connection_pool = pool.SimpleConnectionPool(
        1, 20,
        get_db_connection_string(),
        connect_timeout=3,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )
    logger.info("Successfully created database connection pool")
except Exception as e:
    logger.error(f"Failed to create connection pool: {str(e)}")
    connection_pool = None

def get_db_connection():
    if connection_pool:
        try:
            conn = connection_pool.getconn()
            # Test the connection
            with conn.cursor() as cursor:
                cursor.execute('SELECT 1')
            return conn
        except Exception as e:
            logger.error(f"Pool connection failed: {str(e)}")
            if conn:
                connection_pool.putconn(conn)
            # Fall back to direct connection
            return psycopg2.connect(
                get_db_connection_string(),
                connect_timeout=3,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
    else:
        # Direct connection with timeout and keepalive settings
        return psycopg2.connect(
            get_db_connection_string(),
            connect_timeout=3,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5
        )

# Update get_recent_interactions to use the new connection handling
def get_recent_interactions(days=7):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Get recent active users
        cursor.execute("""
            SELECT u.username, u.first_name, u.last_name, u.last_active, u.messages_sent 
            FROM users u 
            WHERE u.last_active >= NOW() - INTERVAL '%s days'
            ORDER BY u.last_active DESC
            LIMIT 50
        """, (days,))
        recent_users = cursor.fetchall()
        
        return total_users, recent_users
    
    except Exception as e:
        logger.error(f"Database error in get_recent_interactions: {str(e)}")
        st.error(f"Database connection error: {str(e)}")
        return 0, []
    finally:
        if cursor:
            cursor.close()
        if conn:
            if connection_pool:
                connection_pool.putconn(conn)
            else:
                conn.close()

# Similarly update get_search_count
def get_search_count():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as searches
            FROM user_searches
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """)
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"Error in get_search_count: {str(e)}")
        st.error(f"Error fetching search count: {str(e)}")
        return 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            if connection_pool:
                connection_pool.putconn(conn)
            else:
                conn.close()

# Add this function after other function definitions
def setup_logging_db():
    """Setup SQLite database for storing logs"""
    try:
        conn = sqlite3.connect('logs.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                level TEXT,
                message TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to setup logging database: {str(e)}")

# Add custom handler for logging to database
class DatabaseHandler(logging.Handler):
    def emit(self, record):
        try:
            conn = sqlite3.connect('logs.db')
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO logs (timestamp, level, message) VALUES (?, ?, ?)',
                (datetime.fromtimestamp(record.created), record.levelname, record.getMessage())
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to log to database: {str(e)}")

# Add this function after other function definitions
def get_recent_logs(limit=100):
    """Fetch recent logs from the database"""
    try:
        conn = sqlite3.connect('logs.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, level, message 
            FROM logs 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        logs = cursor.fetchall()
        conn.close()
        return logs
    except Exception as e:
        logger.error(f"Failed to fetch logs: {str(e)}")
        return []

def clear_logs():
    """Clear both the SQLite logs and conversation.log file"""
    try:
        # Clear SQLite logs
        conn = sqlite3.connect('logs.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM logs')
        conn.commit()
        conn.close()
        
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
        # Clear conversation.log
        open('logs/conversations.log', 'w').close()
        logger.info("Logs cleared successfully on server startup")
    except Exception as e:
        logger.error(f"Failed to clear logs: {str(e)}")

# Setup logging database and handler (add near the top after logger definition)
setup_logging_db()
clear_logs()  # Add this line to clear logs on startup
db_handler = DatabaseHandler()
db_handler.setLevel(logging.INFO)
logger.addHandler(db_handler)

try:
    st.title("📊 Telegram Bot Admin Dashboard")

    # Metrics
    with st.spinner("Loading metrics..."):
        total_users, recent_users = get_recent_interactions()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Total Users", value=total_users)
        with col2:
            st.metric(label="Active Users (Last 7 Days)", value=len(recent_users))
        with col3:
            search_count = get_search_count()
            st.metric(label="Job Searches (Last 7 Days)", value=search_count)

    # Recent Activity
    st.subheader("Recent User Activity (Last 7 Days)")
    if recent_users:
        import pandas as pd
        df = pd.DataFrame(
            recent_users,
            columns=['Username', 'First Name', 'Last Name', 'Last Active', 'Messages Sent']
        )
        st.dataframe(df)
    else:
        st.info("No recent user activity")

    # Add date filter
    days = st.slider("Show activity for last N days", 1, 30, 7)
    _, filtered_users = get_recent_interactions(days)

    # Add Logs Section
    st.subheader("📝 Recent System Logs")
    
    # Add log filter options
    col1, col2 = st.columns(2)
    with col1:
        log_limit = st.slider("Number of logs to show", 10, 500, 100)
    with col2:
        log_level_filter = st.multiselect(
            "Filter by log level",
            ["ERROR", "WARNING", "INFO", "DEBUG"],
            default=["ERROR", "WARNING", "INFO"]
        )

    # Fetch and display logs
    logs = get_recent_logs(log_limit)
    if logs:
        # Convert logs to DataFrame for better display
        log_df = pd.DataFrame(
            logs,
            columns=['Timestamp', 'Level', 'Message']
        )
        
        # Filter by selected log levels
        log_df = log_df[log_df['Level'].isin(log_level_filter)]
        
        # Style the dataframe
        def highlight_error(val):
            if val == 'ERROR':
                return 'background-color: #ffcdd2'
            elif val == 'WARNING':
                return 'background-color: #fff9c4'
            return ''
        
        # Display styled dataframe
        st.dataframe(
            log_df.style.applymap(highlight_error, subset=['Level']),
            height=400
        )
        
        # Add export option
        if st.button("Export Logs"):
            log_json = log_df.to_json(orient='records', date_format='iso')
            st.download_button(
                label="Download Logs as JSON",
                data=log_json,
                file_name=f"bot_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    else:
        st.info("No logs found")

except Exception as e:
    st.error(f"Dashboard error: {str(e)}")
    logger.error(f"Dashboard error: {str(e)}", exc_info=True)

app = FastAPI(title="Job Matching Bot Admin Dashboard")

router = APIRouter(prefix="/api/admin")

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Mount the router
app.include_router(router)

@router.get("/overview")
async def get_dashboard_overview():
    """Get overview statistics for the admin dashboard"""
    try:
        async with async_session_maker() as session:
            # Get total users
            result = await session.execute(text("SELECT count(telegram_id) FROM users"))
            total_users = result.scalar() or 0

            # Get active users in last 24h
            one_day_ago = datetime.now() - timedelta(days=1)
            result = await session.execute(
                text("SELECT count(DISTINCT telegram_id) FROM users WHERE last_active >= :date"),
                {"date": one_day_ago}
            )
            active_users_24h = result.scalar() or 0

            # Get recent searches
            result = await session.execute(
                text("SELECT count(*) FROM user_searches WHERE created_at >= :date"),
                {"date": one_day_ago}
            )
            recent_searches = result.scalar() or 0

            # Get recent conversations
            result = await session.execute(
                text("SELECT count(*) FROM user_conversations WHERE created_at >= :date"),
                {"date": one_day_ago}
            )
            recent_conversations = result.scalar() or 0

            # Get recent job matches
            result = await session.execute(
                text("SELECT count(*) FROM job_matches WHERE created_at >= :date"),
                {"date": one_day_ago}
            )
            recent_matches = result.scalar() or 0

            return {
                "total_users": total_users,
                "active_users_24h": active_users_24h,
                "recent_searches": recent_searches,
                "recent_conversations": recent_conversations,
                "recent_matches": recent_matches
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting dashboard overview: {str(e)}")

@router.get("/user-activity")
async def get_user_activity(
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format"),
    db: AsyncSession = Depends(get_db)
):
    """Get user activity metrics for a date range."""
    try:
        # Validate date parameters
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )

        # Rest of the function implementation
        query = text("""
            SELECT DATE(timestamp) as date,
                   COUNT(*) as total_actions,
                   COUNT(DISTINCT user_id) as unique_users
            FROM user_activity_log
            WHERE (:start_date IS NULL OR DATE(timestamp) >= DATE(:start_date))
            AND (:end_date IS NULL OR DATE(timestamp) <= DATE(:end_date))
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """)
        
        result = await db.execute(query, {"start_date": start_date, "end_date": end_date})
        activity_data = [dict(row) for row in result]
        
        return {
            "activity": activity_data,
            "total_actions": sum(day["total_actions"] for day in activity_data),
            "unique_users": len(set(day["unique_users"] for day in activity_data))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user activity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/search-analytics")
async def get_search_analytics(start_date: Optional[datetime] = None):
    """Get search analytics data"""
    try:
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)

        async with async_session_maker() as session:
            # Get popular search terms
            result = await session.execute(
                text("""
                    SELECT search_query, COUNT(*) as count
                    FROM user_searches
                    WHERE created_at >= :start_date
                    GROUP BY search_query
                    ORDER BY count DESC
                    LIMIT 10
                """),
                {"start_date": start_date}
            )
            rows = result.fetchall()
            
            return {
                "popular_searches": [
                    {"term": row[0], "count": row[1]} for row in rows
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting search analytics: {str(e)}")

@router.get("/conversation-analytics")
async def get_conversation_analytics(start_date: Optional[datetime] = None):
    """Get conversation analytics data"""
    try:
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)

        async with async_session_maker() as session:
            # Get total conversations
            result = await session.execute(
                text("""
                    SELECT COUNT(*) as total
                    FROM user_conversations
                    WHERE created_at >= :start_date
                """),
                {"start_date": start_date}
            )
            total_conversations = result.scalar() or 0

            # Get conversation volume over time
            result = await session.execute(
                text("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM user_conversations
                    WHERE created_at >= :start_date
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """),
                {"start_date": start_date}
            )
            rows = result.fetchall()
            
            return {
                "total_conversations": total_conversations,
                "conversation_trend": {
                    "dates": [row[0] for row in rows],
                    "counts": [row[1] for row in rows]
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting conversation analytics: {str(e)}")

@router.get("/users/{user_id}")
async def get_user_details(user_id: int):
    """Get detailed information about a specific user"""
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                text("SELECT * FROM users WHERE id = :user_id"),
                {"user_id": user_id}
            )
            user = result.fetchone()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Get user's recent activity
            searches_result = await session.execute(
                text("""
                    SELECT search_query, created_at
                    FROM user_searches
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT 5
                """),
                {"user_id": user_id}
            )
            recent_searches = searches_result.fetchall()
            
            conversations_result = await session.execute(
                text("""
                    SELECT message_text, created_at
                    FROM user_conversations
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT 5
                """),
                {"user_id": user_id}
            )
            recent_conversations = conversations_result.fetchall()
            
            return {
                "user_info": dict(user),
                "recent_searches": [
                    {"query": row[0], "timestamp": row[1]} 
                    for row in recent_searches
                ],
                "recent_conversations": [
                    {"message": row[0], "timestamp": row[1]}
                    for row in recent_conversations
                ]
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting user details: {str(e)}")
