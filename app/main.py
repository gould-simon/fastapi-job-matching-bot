from fastapi import FastAPI, Request
from app.routes import router
from app.telegram_bot import application
import os

app = FastAPI()

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
