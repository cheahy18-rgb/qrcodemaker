import os
import io
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
import qrcode

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# 1. កំណត់ Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# 2. ទាញយក Bot Token ពី Environment Variables (ឬដាក់ Token ដោយផ្ទាល់សម្រាប់ Testing)
TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# --- TELEGRAM BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✨ Custom Styling", callback_data="btn_style"),
            InlineKeyboardButton("❓ Help & Usage", callback_data="btn_help"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 **Welcome to QRCode Bot!**\n\nសូមផ្ញើ Link ឬ Hyperlink មកកាន់ខ្ញុំ ខ្ញុំនឹងបង្កើត QR Code ជូនអ្នក។",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "btn_style":
        await query.edit_message_text("🎨 ផ្ញើ Link មកដើម្បីទទួលបាន QR Code!")
    elif query.data == "btn_help":
        await query.edit_message_text("❓ សូមផ្ញើ Link ដែលចាប់ផ្តើមដោយ http:// ឬ https://")

async def generate_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith("http://") or text.startswith("https://"):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        bio = io.BytesIO()
        bio.name = 'qrcode.png'
        img.save(bio, 'PNG')
        bio.seek(0)

        await update.message.reply_photo(photo=bio, caption=f"នេះជា QR Code សម្រាប់៖\n{text}")
    else:
        await update.message.reply_text("សូមផ្ញើ Link ដែលត្រឹមត្រូវ (ឧទាហរណ៍៖ https://example.com)")

# បង្កើត Telegram Application Instance
bot_app = ApplicationBuilder().token(TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(button_click_handler))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_qr))


# --- FASTAPI WEB SERVER SETUP ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ចាប់ផ្តើម Telegram Bot Polling ពេល Web Server ដំណើរការ
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    logging.info("Telegram Bot started successfully.")
    
    yield
    
    # បិទ Telegram Bot ពេល Web Server បិទ
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

# បង្កើត FastAPI Application Instance
app = FastAPI(title="QRCode Bot Web Service", lifespan=lifespan)

# បន្ថែម alias ឈ្មោះ "application" ដើម្បីកុំឱ្យមាន Error លើ Render ប្រសិនបើ Start Command ប្រើ main:application
application = app

@app.get("/")
def health_check():
    return {"status": "ok", "message": "QRCode Bot is running 24/7!"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)