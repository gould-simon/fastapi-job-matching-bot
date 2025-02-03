from telegram.ext import Application
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def start(update, context):
    await update.message.reply_text("Hello!")

def main():
    try:
        app = Application.builder().token("YOUR_BOT_TOKEN").build()
        app.add_handler(CommandHandler("start", start))
        app.run_polling()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

if __name__ == "__main__":
    main() 