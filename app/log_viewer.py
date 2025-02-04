import streamlit as st
import os
from datetime import datetime
import re

st.title("🤖 Telegram Bot Conversation Logs")

# Function to parse log lines
def parse_log_line(line):
    try:
        # Extract timestamp and message
        timestamp_str = line[0:19]  # Assumes format: "2024-01-20 15:30:45"
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        
        # Check if it's a user or bot message
        if "👤 User" in line:
            message_type = "User"
            message = line.split("👤 User")[1]
        elif "🤖 Bot" in line:
            message_type = "Bot"
            message = line.split("🤖 Bot:")[1]
        else:
            return None
            
        return {
            'timestamp': timestamp,
            'type': message_type,
            'message': message.strip()
        }
    except:
        return None

# Read and display logs
if os.path.exists('logs/conversations.log'):
    with open('logs/conversations.log', 'r') as f:
        logs = f.readlines()
    
    # Parse logs
    conversations = []
    for line in logs:
        parsed = parse_log_line(line)
        if parsed:
            conversations.append(parsed)
    
    # Display filters
    st.sidebar.header("Filters")
    show_user = st.sidebar.checkbox("Show User Messages", True)
    show_bot = st.sidebar.checkbox("Show Bot Messages", True)
    
    # Display conversations
    for conv in reversed(conversations):  # Show newest first
        if (conv['type'] == "User" and show_user) or (conv['type'] == "Bot" and show_bot):
            with st.container():
                col1, col2 = st.columns([2, 8])
                with col1:
                    st.text(conv['timestamp'].strftime('%H:%M:%S'))
                    st.text(conv['type'])
                with col2:
                    if conv['type'] == "Bot":
                        st.info(conv['message'])
                    else:
                        st.success(conv['message'])
else:
    st.warning("No conversation logs found. Start chatting with the bot to generate logs!")

# Add auto-refresh button
if st.button("🔄 Refresh"):
    st.experimental_rerun()

# Add auto-refresh (every 30 seconds)
st.empty()
st.markdown("""
<meta http-equiv="refresh" content="30">
""", unsafe_allow_html=True) 