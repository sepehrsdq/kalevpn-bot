# main.py
import asyncio
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters

from app.handlers.menu import button_handler
from app.handlers.messages import handle_messages
from app.handlers.start import start, is_joined_channel
from app.jobs.usage_monitor import post_init
from app.config import TOKEN

# =============================
# ساخت Application
# =============================
app = ApplicationBuilder().token(TOKEN).concurrent_updates(True).build()

# =============================
# Handlers
# =============================

# /start
app.add_handler(MessageHandler(filters.COMMAND & filters.Regex(r'^/start'), start))

# پیام‌های کاربر
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_messages))

# دکمه‌های منو
app.add_handler(CallbackQueryHandler(button_handler))

# =============================
# پس‌زمینه: مانیتور مصرف خودکار
# =============================
asyncio.get_event_loop().create_task(post_init(app))

# =============================
# اجرای بات
# =============================
print("🚀 Kale VPN Bot is running...")
app.run_polling()
