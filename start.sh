#!/bin/bash

# Start the Streamlit app
streamlit run app/admin_dashboard.py --server.port 8501 --server.address 0.0.0.0 &

# Start the web server
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 &

# Start the Telegram bot
python -m app.telegram_bot &

# Wait for all background processes to finish
wait