from fastapi import FastAPI, Request
from app.routes import router
from app.telegram_bot import application
from app.logging_config import APILoggingMiddleware
import os

app = FastAPI()

# Add logging middleware
app.middleware("http")(APILoggingMiddleware())

app.include_router(router)

@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI is working!"}

@app.post("/webhook")
async def webhook(request: Request):
    """Handle incoming Telegram webhook requests"""
    data = await request.json()
    await application.update_queue.put(data)
    return {"ok": True}

@app.get("/bot-status")
async def bot_status():
    try:
        bot_info = await application.bot.get_me()
        return {
            "status": "running",
            "bot_username": bot_info.username,
            "handlers_registered": len(application.handlers)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# Webhook setup (only run when deploying to production)
if __name__ == "__main__":
    import uvicorn
    app_url = "https://fastapi-job-matching-bot.fly.dev"  # Your fly.io URL
    
    # Set webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=8000,
        webhook_url=f"{app_url}/webhook",
        webhook_path="/webhook"
    )
