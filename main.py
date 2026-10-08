import os
import io
import re
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

# បញ្ជីពណ៌សម្រាប់ Inline Keyboard
COLOR_PALETTES = {
    "cyan": {"name": "🩵 Cyan", "fg": (0, 229, 255), "bg": (18, 24, 36)},
    "gold": {"name": "👑 Gold", "fg": (255, 215, 0), "bg": (20, 20, 20)},
    "purple": {"name": "💜 Purple", "fg": (186, 85, 211), "bg": (15, 10, 25)},
    "green": {"name": "💚 Green", "fg": (57, 255, 20), "bg": (10, 25, 15)},
}

# --- FUNCTION បង្កើត QR CODE (រៀបចំរៀង Dots និង Logo) ---
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

    # បញ្ចូល Logo បើមាន
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


# --- TELEGRAM BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # កំណត់ពណ៌ Default ប្រសិនបើមិនទាន់ជ្រើសរើស
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
        ],
        [
            InlineKeyboardButton("ℹ️ របៀបប្រើប្រាស់", callback_data="btn_help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        "👋 **ស្វាគមន៍មកកាន់ QRCodemakerBot!**\n\n"
        "🎨 **ជ្រើសរើសពណ៌ QR Code ខាងក្រោម៖**\n\n"
        "📌 **អ្នកអាចផ្ញើ៖**\n"
        "• **Link:** `https://example.com`\n"
        "• **Text ធម្មតា:** `ជម្រាបសួរ`\n"
        "• **លេខទូរស័ព្ទ:** `012345678` ឬ `tel:012345678`\n"
        "• **Wi-Fi:** `WIFI:S:MyNetwork;T:WPA;P:MyPassword;;`"
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
            f"✅ **អ្នកបានជ្រើសរើសពណ៌៖ {color_name}**\n\nសូមផ្ញើ Link, Text, លេខទូរស័ព្ទ ឬ ព័ត៌មាន Wi-Fi មកឥឡូវនេះ!",
            parse_mode="Markdown"
        )
    elif query.data == "btn_help":
        help_text = (
            "💡 **ការណែនាំអំពីទម្រង់ទិន្នន័យ៖**\n\n"
            "1. **Link/URL:** ផ្ញើ Link ផ្ទាល់ (ឧ. `https://google.com`)\n"
            "2. **PlainText:** ផ្ញើអត្ថបទធម្មតា\n"
            "3. **លេខទូរស័ព្ទ:** ផ្ញើលេខទូរស័ព្ទ (ឧ. `012345678`)\n"
            "4. **Wi-Fi Formats:** ផ្ញើតាមទម្រង់៖\n"
            "`WIFI:S:ឈ្មោះWiFi;T:WPA;P:លេខសម្ងាត់;;`"
        )
        await query.edit_message_text(help_text, parse_mode="Markdown")


async def generate_qr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip()
    
    # ចាប់យកជម្រើសពណ៌របស់អ្នកប្រើប្រាស់ (Default: cyan)
    color_key = context.user_data.get("selected_color", "cyan")
    palette = COLOR_PALETTES.get(color_key, COLOR_PALETTES["cyan"])

    # ដំណើរការទិន្នន័យ (រាប់បញ្ចូលទាំង PlainText / Phone / Wi-Fi / Link)[cite: 9]
    qr_data = raw_text
    data_type = "PlainText / ព័ត៌មាន"

    # ត្រួតពិនិត្យប្រភេទ Link
    if raw_text.lower().startswith("http://") or raw_text.lower().startswith("https://"):
        data_type = "🔗 Link / URL"
    # ត្រួតពិនិត្យប្រភេទ លេខទូរស័ព្ទ (បើជាលេខសុទ្ធ ឬមានទម្រង់ +855)
    elif re.match(r"^(\+?\d{8,15})$", raw_text):
        qr_data = f"tel:{raw_text}"
        data_type = "📞 លេខទូរស័ព្ទ"
    # ត្រួតពិនិត្យប្រភេទ Wi-Fi
    elif raw_text.upper().startswith("WIFI:"):
        data_type = "📶 ព័ត៌មាន Wi-Fi"

    await update.message.reply_chat_action("upload_photo")

    logo_file = "logo.png" if os.path.exists("logo.png") else None

    # បង្កើត QR Code
    photo_bytes = generate_custom_qr(
        data=qr_data,
        fg_color=palette["fg"],
        bg_color=palette["bg"],
        logo_path=logo_file
    )

    # ផ្ញើរូបភាពដោយផ្ទាល់ (គ្មាន Quoted Header)
    caption = (
        f"✨ **QR Code ត្រូវបានបង្កើតរួចរាល់!**\n"
    #     f"📌 **ប្រភេទ:** {data_type}\n"
    #    f"🎨 **ពណ៌:** {palette['name']}\n\n"
    #    f"📄 **ទិន្នន័យ:** `{raw_text}`"
    )

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=photo_bytes,
        caption=caption,
        parse_mode="Markdown"
    )


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
