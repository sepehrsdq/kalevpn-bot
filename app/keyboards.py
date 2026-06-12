from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils import is_admin


def main_menu_keyboard(user_id=None):
    keyboard = [
        [
            InlineKeyboardButton(
                "🚀 خرید سرویس",
                callback_data="shop",
            )
        ],
        [
            InlineKeyboardButton(
                "📦 اشتراک‌های من",
                callback_data="my_services",
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 تست فوری رایگان",
                callback_data="free_test",
            ),
            InlineKeyboardButton(
                "💰 کیف پول",
                callback_data="balance",
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 دعوت دوستان",
                callback_data="referral",
            )
        ],
        [
            InlineKeyboardButton(
                "🎓 مرکز آموزش",
                callback_data="tutorial",
            )
        ],
        [
            InlineKeyboardButton(
                "🤖 پشتیبانی",
                callback_data="support",
            )
        ],
    ]

    if user_id and is_admin(user_id):
        keyboard.append([
            InlineKeyboardButton(
                "👑 پنل مدیریت",
                callback_data="admin_panel",
            )
        ])

    return InlineKeyboardMarkup(keyboard)


def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 آمار ربات",
                callback_data="admin_stats",
            )
        ],
        [
            InlineKeyboardButton(
                "📢 پیام همگانی",
                callback_data="admin_broadcast",
            )
        ],
        [
            InlineKeyboardButton(
                "💰 مدیریت موجودی",
                callback_data="admin_balance",
            )
        ],
        [
            InlineKeyboardButton(
                "💵 مدیریت قیمت‌ها",
                callback_data="admin_prices",
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ تنظیمات پنل سنایی",
                callback_data="admin_panel_settings",
            )
        ],
        [
            InlineKeyboardButton(
                "👑 افزودن ادمین",
                callback_data="admin_add",
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 مدیریت تست فوری",
                callback_data="admin_test",
            )
        ],
        [
            InlineKeyboardButton(
                "🚫 مدیریت بن کاربران",
                callback_data="admin_ban",
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 منوی کاربر",
                callback_data="main_menu",
            ),
            InlineKeyboardButton(
                "👑 پنل ادمین",
                callback_data="admin_panel",
            ),
        ],
    ])


def back_keyboard(target="main_menu"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data=target,
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="main_menu",
            )
        ],
    ])


def pricing_admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📦 قیمت هر گیگ حجمی",
                callback_data="price_fixed_gb",
            )
        ],
        [
            InlineKeyboardButton(
                "⚡ قیمت هر گیگ مصرفی",
                callback_data="price_usage_gb",
            )
        ],
        [
            InlineKeyboardButton(
                "💳 حداقل موجودی مصرفی",
                callback_data="price_usage_min",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 جایزه رفرال",
                callback_data="price_referral",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="admin_panel",
            )
        ],
    ])


def panel_settings_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🌐 تغییر آدرس API پنل",
                callback_data="panel_set_url",
            )
        ],
        [
            InlineKeyboardButton(
                "👤 تغییر یوزرنیم",
                callback_data="panel_set_username",
            )
        ],
        [
            InlineKeyboardButton(
                "🔐 تغییر پسورد",
                callback_data="panel_set_password",
            )
        ],
        [
            InlineKeyboardButton(
                "📡 تغییر Inbound ID",
                callback_data="panel_set_inbound",
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 تغییر آدرس ساب",
                callback_data="panel_set_sub_base",
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ تست اتصال پنل",
                callback_data="admin_panel_test",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="admin_panel",
            )
        ],
    ])


def balance_admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ افزایش موجودی",
                callback_data="admin_balance_add",
            )
        ],
        [
            InlineKeyboardButton(
                "➖ کاهش موجودی",
                callback_data="admin_balance_sub",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="admin_panel",
            )
        ],
    ])


def trial_admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🟢 فعال/غیرفعال تست فوری",
                callback_data="trial_toggle",
            )
        ],
        [
            InlineKeyboardButton(
                "⏳ مدت تست",
                callback_data="trial_set_minutes",
            ),
            InlineKeyboardButton(
                "📦 حجم تست",
                callback_data="trial_set_gb",
            ),
        ],
        [
            InlineKeyboardButton(
                "🎁 هدیه کیف پول",
                callback_data="trial_set_bonus",
            ),
            InlineKeyboardButton(
                "⏰ مهلت هدیه",
                callback_data="trial_set_bonus_window",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔁 تعداد مجاز تست",
                callback_data="trial_set_max",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="admin_panel",
            )
        ],
    ])
