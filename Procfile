web: gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 
bot: python -m app.telegram_bot
streamlit: streamlit run app/admin_dashboard.py --server.port 8501 --server.address 0.0.0.0
