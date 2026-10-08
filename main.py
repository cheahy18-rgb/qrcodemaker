import os
import io
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
import qrcode

# Import Modules សម្រាប់ការធ្វើ Styling លើ QR Code
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import (
    RoundedModuleDrawer,     # Dots ជ្រុងមូល
    CircleModuleDrawer,      # Dots រង្វង់មូល
    GappedSquareModuleDrawer # Dots ការ៉េមានចន្លោះ
)
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

# 1. កំណត់ Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# --- 2. FUNCTION បង្កើត STYLED QR CODE ---
def generate_custom_qr(
    url: str, 
    fg_color=(0, 229, 255),    # ពណ៌ Foreground (Cyan)
    bg_color=(18, 24, 36),     # ពណ៌ Background (Dark Slate)
    drawer_type="rounded"      # រូបរាង Dot ("rounded", "circle", "gapped")
) -> io.BytesIO:
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H, # កម្រិត error correction ខ្ពស់ ដើម្បីស្កេនបានស្រួល
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # ជ្រើសរើសរូបរាង Dot (Module Drawer)
    if drawer_type == "circle":
        module_drawer = CircleModuleDrawer()
    elif drawer_type == "gapped":
        module_drawer = GappedSquareModuleDrawer()
    else:
        module_drawer = RoundedModuleDrawer()

    # បង្កើត QR Code ជាមួយ Styling
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=module_drawer,
        color_mask=SolidFillColorMask(
            back_color=bg_color,
            front_color=fg_color
        )
    )

    bio = io.BytesIO()
    bio.name = 'styled_qrcode.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio


# --- 3. TELEGRAM BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✨ Custom Styling", callback_data="btn_style"),
            InlineKeyboardButton("❓ Help & Usage", callback_data="btn_help"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 **Welcome to QRCode Bot!**\n\nសូមផ្ញើ Link ឬ Hyperlink មកកាន់ខ្ញុំ ខ្ញុំនឹងបង្កើត QR Code Custom ជូនអ្នកភ្លាមៗ។",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "btn_style":
        await query.edit_message_text(
            "🎨 ** Styling Options Active**\n\nQR Code ដែលបង្កើតនឹងមាន៖\n• Background: Dark Slate\n• Foreground: Electric Cyan\n• Dot Shape: Rounded Corners\n\n👉 ផ្ញើ Link មកឥឡូវនេះដើម្បីសាកល្បង!"
        )
    elif query.data == "btn_help":
        await query.edit_message_text("❓ សូមផ្ញើ URL ដែលចាប់ផ្តើមដោយ `http://` ឬ `https://` (ឧទាហរណ៍៖ `https://google.com`)")

async def generate_qr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("http://") or text.startswith("https://"):
        await update.message.reply_chat_action("upload_photo")
        
        # បង្កើត Styled QR Code
        photo_bytes = generate_custom_qr(
            url=text,
            fg_color=(0, 229, 255),  # Electric Cyan
            bg_color=(18, 24, 36),    # Dark Charcoal
            drawer_type="rounded"     # Dots ជ្រុងមូល
        )

        # ផ្ញើរូបភាពដោយផ្ទាល់ទៅក្នុង Chat ដោយមិនបាច់ធ្វើការ Reply (ដើម្បីកុំឱ្យចេញផ្ទាំង Quoted Name)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=photo_bytes,
            #caption=f"✨ **QR Code របស់អ្នកត្រូវបានបង្កើតរួចរាល់!**\n🔗 Link: {text}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ សូមផ្ញើ Link ដែលត្រឹមត្រូវ (ឧទាហរណ៍៖ `https://example.com`)", parse_mode="Markdown")

# បង្កើត Telegram Application Instance
bot_app = ApplicationBuilder().token(TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(button_click_handler))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_qr_handler))


# --- 4. FASTAPI WEB SERVER SETUP ---
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

app = FastAPI(title="QRCode Bot Web Service", lifespan=lifespan)

# Alias សម្រាប់ការពារ Error លើ Render ប្រសិនបើ Start Command ប្រើ main:application
application = app

@app.get("/")
def health_check():
    return {"status": "ok", "message": "QRCode Bot is running 24/7!"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
