import io
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import qrcode

# បើក Log សម្រាប់មើលព័ត៌មាន ឬ Error
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# មុខងារស្វាគមន៍ពេលអ្នកប្រើចុច /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ជំរាបសួរ! សូមផ្ញើ Link/Hyperlink មកកាន់ខ្ញុំ ខ្ញុំនឹងបង្កើត QR Code ជូនអ្នក។"
    )

# មុខងារបង្កើត QR Code ពី Link
async def generate_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # ពិនិត្យថាអត្ថបទជា Link ឬអត់ (តាមរយៈ http:// ឬ https://)
    if text.startswith("http://") or text.startswith("https://"):
        # បង្កើត QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # រក្សាទុកក្នុង Memory (In-Memory Bytes)
        bio = io.BytesIO()
        bio.name = 'qrcode.png'
        img.save(bio, 'PNG')
        bio.seek(0)

        # ផ្ញើរូបភាព QR Code ត្រឡប់ទៅ Telegram វិញ
        await update.message.reply_photo(photo=bio, caption=f"នេះជា QR Code សម្រាប់៖\n{text}")
    else:
        await update.message.reply_text("សូមផ្ញើ Link ដែលត្រឹមត្រូវ (ឧទាហរណ៍៖ https://example.com)")

if __name__ == '__main__':
    # ដាក់ Bot Token របស់អ្នកនៅត្រង់នេះ
    TOKEN = "8957616954:AAHIMDj92nBIoYyCGrdYprf_swyMXKh023E"

    app = ApplicationBuilder().token(TOKEN).build()

    # ភ្ជាប់ Command និង Message Handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_qr))

    print("Bot កំពុងដំណើរការ...")
    app.run_polling()