from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import FORCE_CHANNEL
from app.database import get_db
from app.keyboards import admin_keyboard, main_menu_keyboard
from app.utils import is_admin


async def is_joined_channel(user_id, bot):
    try:
        member = await bot.get_chat_member(
            chat_id=FORCE_CHANNEL,
            user_id=user_id,
        )

        return member.status not in [
            "left",
            "kicked",
        ]

    except Exception:
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    referrer_id = None

    if context.args:
        try:
            referrer_id = int(context.args[0])
        except Exception:
            referrer_id = None

    if referrer_id == user.id:
        referrer_id = None

    if referrer_id:
        context.user_data["pending_referrer_id"] = referrer_id

    joined = await is_joined_channel(
        user.id,
        context.bot,
    )

    if not joined:
        keyboard = [
            [
                InlineKeyboardButton(
                    "📢 عضویت در کانال",
                    url="https://t.me/kale_vpn",
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ عضو شدم",
                    callback_data="check_join",
                )
            ],
        ]

        await update.message.reply_text(
            "❌ برای استفاده از ربات ابتدا در کانال عضو شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return

    if not referrer_id:
        referrer_id = context.user_data.get("pending_referrer_id")

    conn = get_db()

    conn.execute(
        """
        INSERT OR IGNORE INTO users(
            user_id,
            username,
            referrer_id
        )
        VALUES(?,?,?)
        """,
        (
            user.id,
            user.username,
            referrer_id,
        ),
    )

    conn.commit()

    banned = conn.execute(
        """
        SELECT is_banned
        FROM users
        WHERE user_id=?
        """,
        (user.id,),
    ).fetchone()

    conn.close()

    if banned and banned["is_banned"] == 1:
        await update.message.reply_text(
            "🚫 حساب شما مسدود شده است."
        )
        return

    if is_admin(user.id):
        await update.message.reply_text(
            f"👑 سلام ادمین {user.first_name}",
            reply_markup=admin_keyboard(),
        )
        return

    await update.message.reply_text(
        f"سلام {user.first_name} 👋\n\nبه KaleVPN خوش اومدی.",
        reply_markup=main_menu_keyboard(user.id),
    )
