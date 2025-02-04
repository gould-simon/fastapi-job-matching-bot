import streamlit as st
import psycopg2
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse
import logging
import sqlite3
import json

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
