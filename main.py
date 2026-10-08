import os
import io
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
import qrcode
from PIL import Image

from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

def generate_custom_qr_with_logo(
    url: str,
    logo_path: str = None,
    fg_color=(0, 229, 255),
    bg_color=(18, 24, 36)
) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    qr_img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=bg_color,
            front_color=fg_color
        )
    ).convert("RGBA")

    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            qr_width, qr_height = qr_img.size
            logo_size = int(qr_width * 0.2)
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
            qr_img.paste(logo, pos, mask=logo)
        except Exception as e:
            logging.error(f"Failed to embed logo: {e}")

    bio = io.BytesIO()
    bio.name = 'qrcode.png'
    qr_img.save(bio, 'PNG')
    bio.seek(0)
    return bio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✨ Custom Styling", callback_data="btn_style"),
            InlineKeyboardButton("❓ Help & Usage", callback_data="btn_help"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👋 **Welcome to QRCode Bot!**\n\nសូមផ្ញើ Link មកកាន់ខ្ញុំ ខ្ញុំនឹងបង្កើត QR Code ជូនអ្នកភ្លាមៗ។",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "btn_style":
        await query.edit_message_text("🎨 ផ្ញើ Link មកដើម្បីទទួលបាន QR Code ជាមួយ Styling!")
    elif query.data == "btn_help":
        await query.edit_message_text("❓ សូមផ្ញើ Link ដែលចាប់ផ្តើមដោយ http:// ឬ https://")

async def generate_qr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    text_lower = text.lower()  # បំប្លែងជាអក្សរតូចដើម្បីងាយស្រួលផ្ទៀងផ្ទាត់ (Case-insensitive)
    
    # ចាប់យក URL ទោះជាប្រើ Http:// ឬ HTTP:// ឬ https://
    if text_lower.startswith("http://") or text_lower.startswith("https://"):
        await update.message.reply_chat_action("upload_photo")
        
        logo_file = "logo.png" if os.path.exists("logo.png") else None

        photo_bytes = generate_custom_qr_with_logo(
            url=text,  # រក្សាទុក URL ដើមដែលផ្ញើមក
            logo_path=logo_file,
            fg_color=(0, 229, 255),
            bg_color=(18, 24, 36)
        )

        # ផ្ញើរូបភាពដោយផ្ទាល់ទៅកាន់ Chat ID
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=photo_bytes,
         #   caption=f"✨ **QR Code របស់អ្នកត្រូវបានបង្កើតរួចរាល់!**\n🔗 Link: {text}",
            parse_mode="Markdown"
        )

bot_app = ApplicationBuilder().token(TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(button_click_handler))

# ចាប់រាល់ Message ទាំងអស់ដែលមាន Text
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_qr_handler))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    logging.info("Telegram Bot started successfully.")
    
    yield
    
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(title="QRCode Bot Web Service", lifespan=lifespan)
application = app

@app.get("/")
def health_check():
    return {"status": "ok", "message": "QRCode Bot is running 24/7!"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
