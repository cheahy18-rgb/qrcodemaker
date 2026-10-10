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

COLOR_PALETTES = {
    "cyan": {"name": "🩵 Cyan", "fg": (0, 229, 255), "bg": (18, 24, 36)},
    "gold": {"name": "👑 Gold", "fg": (255, 215, 0), "bg": (20, 20, 20)},
    "purple": {"name": "💜 Purple", "fg": (186, 85, 211), "bg": (15, 10, 25)},
    "green": {"name": "💚 Green", "fg": (57, 255, 20), "bg": (10, 25, 15)},
}

def generate_custom_qr(
    data: str,
    fg_color=(0, 229, 255),
    bg_color=(18, 24, 36),
    logo_path: str = None
) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(back_color=bg_color, front_color=fg_color)
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
    if "selected_color" not in context.user_data:
        context.user_data["selected_color"] = "cyan"

    keyboard = [
        [
            InlineKeyboardButton("🩵 Cyan", callback_data="color_cyan"),
            InlineKeyboardButton("👑 Gold", callback_data="color_gold"),
        ],
        [
            InlineKeyboardButton("💜 Purple", callback_data="color_purple"),
            InlineKeyboardButton("💚 Green", callback_data="color_green"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        "👋 **ស្វាគមន៍មកកាន់ QRCodemakerBot!**\n\n"
        "🎨 **ជ្រើសរើសពណ៌ QR Code ខាងក្រោម៖**\n\n"
        "👉 **សូមផ្ញើ Link (ដែលផ្តើមដោយ http:// ឬ https://) មកកាន់ខ្ញុំ ខ្ញុំនឹងបង្កើត QR Code ជូនភ្លាមៗ!**"
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("color_"):
        color_key = query.data.replace("color_", "")
        context.user_data["selected_color"] = color_key
        color_name = COLOR_PALETTES[color_key]["name"]
        
        await query.edit_message_text(
            f"✅ **បានប្តូរពណ៌ជោគជ័យ៖ {color_name}**\n\nឥឡូវនេះសូមផ្ញើ Link មកដើម្បីបង្កើត QR Code!",
            parse_mode="Markdown"
        )

async def generate_qr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip()
    text_lower = raw_text.lower()

    # ត្រួតពិនិត្យផ្តាច់មុខ៖ ត្រូវតែចាប់ផ្តើមដោយ http:// ឬ https:// ប៉ុណ្ណោះ
    if text_lower.startswith("http://") or text_lower.startswith("https://"):
        color_key = context.user_data.get("selected_color", "cyan")
        palette = COLOR_PALETTES.get(color_key, COLOR_PALETTES["cyan"])

        await update.message.reply_chat_action("upload_photo")

        logo_file = "logo.png" if os.path.exists("logo.png") else None

        photo_bytes = generate_custom_qr(
            data=raw_text,
            fg_color=palette["fg"],
            bg_color=palette["bg"],
            logo_path=logo_file
        )

        caption = (
            f"✨ **QR Code ត្រូវបានបង្កើតរួចរាល់!**\n"
            f"🎨 **ពណ៌:** {palette['name']}\n\n"
            f"🔗 **Link:** `{raw_text}`"
        )

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=photo_bytes,
            caption=caption,
            parse_mode="Markdown"
        )
    else:
        # បើផ្ញើសារធម្មតាផ្សេងពី Link គឺ Bot មិនអើពើ (Ignore)
        return

bot_app = ApplicationBuilder().token(TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(button_click_handler))
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
