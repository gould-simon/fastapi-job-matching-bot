import streamlit as st
import psycopg2
import os

DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM users")
total_users = cursor.fetchone()[0]

st.title("📊 Telegram Bot Admin Dashboard")
st.metric(label="Total Users", value=total_users)

cursor.close()
conn.close()
