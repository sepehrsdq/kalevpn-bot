from telegram.ext import ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from app.config import TON_WALLET, TRON_WALLET, BSC_WALLET, LTC_WALLET
from app.database import get_db

from app.keyboards import (
    admin_keyboard,
    balance_admin_keyboard,
    panel_settings_keyboard,
    pricing_admin_keyboard,
    back_keyboard,
)
from app.utils import (
    generate_deposit_id,
    get_all_admins,
    is_admin,
    mask_secret,
    set_setting,
)


async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    # =====================================================
    # ADMIN PRICE SETTINGS
    # =====================================================

    if context.user_data.get("waiting_price_key"):
        if not is_admin(user_id):
            return

        try:
            value = float(text)

            if value < 0:
                await update.message.reply_text(
                    "❌ مقدار نمی‌تواند منفی باشد."
                )
                return

            key = context.user_data.get("waiting_price_key")
            title = context.user_data.get(
                "waiting_price_title",
                "قیمت",
            )

            set_setting(key, value)

            context.user_data.pop("waiting_price_key", None)
            context.user_data.pop("waiting_price_title", None)

            await update.message.reply_text(
                f"✅ {title} بروزرسانی شد.\n\n"
                f"مقدار جدید:\n"
                f"`{value}$`",
                parse_mode="Markdown",
                reply_markup=pricing_admin_keyboard(),
            )

            return

        except Exception:
            await update.message.reply_text(
                "❌ فقط عدد وارد کنید.\n"
                "مثال:\n"
                "`0.25`",
                parse_mode="Markdown",
            )
            return

  # =====================================================
    # ADMIN BALANCE ADD / SUBTRACT
    # =====================================================

    if (
        context.user_data.get("admin_balance_add_mode")
        or context.user_data.get("admin_balance_sub_mode")
    ):
        if not is_admin(user_id):
            return

        try:
            target_id, amount = text.split()

            target_id = int(target_id)
            amount = abs(float(amount))

            is_sub = context.user_data.get("admin_balance_sub_mode")
            change_amount = -amount if is_sub else amount

            conn = get_db()

            row = conn.execute(
                """
                SELECT balance
                FROM users
                WHERE user_id=?
                """,
                (target_id,),
            ).fetchone()

            if not row:
                conn.close()
                await update.message.reply_text(
                    "❌ کاربر پیدا نشد."
                )
                return

            current_balance = float(row["balance"] or 0)

            if is_sub and current_balance < amount:
                conn.close()
                await update.message.reply_text(
                    "❌ موجودی کاربر کافی نیست.\n\n"
                    f"💰 موجودی فعلی کاربر: `{current_balance:.2f}$`",
                    parse_mode="Markdown",
                )
                return

            conn.execute(
                """
                UPDATE users
                SET balance = balance + ?
                WHERE user_id=?
                """,
                (
                    change_amount,
                    target_id,
                ),
            )

            new_balance = conn.execute(
                """
                SELECT balance
                FROM users
                WHERE user_id=?
                """,
                (target_id,),
            ).fetchone()["balance"]

            conn.commit()
            conn.close()

            if is_sub:
                user_msg = (
                    f"⚠️ مبلغ `{amount:.2f}$` از موجودی حساب شما کسر شد.\n"
                    f"💰 موجودی جدید: `{new_balance:.2f}$`"
                )

                admin_msg = (
                    "✅ موجودی کاربر کاهش یافت.\n\n"
                    f"👤 User ID: `{target_id}`\n"
                    f"➖ مبلغ کسر شده: `{amount:.2f}$`\n"
                    f"💰 موجودی جدید: `{new_balance:.2f}$`"
                )

            else:
                user_msg = (
                    f"✅ حساب شما `{amount:.2f}$` شارژ شد.\n"
                    f"💰 موجودی جدید: `{new_balance:.2f}$`"
                )

                admin_msg = (
                    "✅ موجودی کاربر افزایش یافت.\n\n"
                    f"👤 User ID: `{target_id}`\n"
                    f"➕ مبلغ اضافه شده: `{amount:.2f}$`\n"
                    f"💰 موجودی جدید: `{new_balance:.2f}$`"
                )

            try:
                await context.bot.send_message(
                    target_id,
                    user_msg,
                    parse_mode="Markdown",
                )
            except Exception:
                pass

            await update.message.reply_text(
                admin_msg,
                parse_mode="Markdown",
                reply_markup=balance_admin_keyboard(),
            )

            context.user_data.pop("admin_balance_add_mode", None)
            context.user_data.pop("admin_balance_sub_mode", None)

            return

        except Exception:
            await update.message.reply_text(
                "❌ فرمت اشتباه است.\n\n"
                "فرمت صحیح:\n"
                "`USER_ID AMOUNT`\n\n"
                "مثال:\n"
                "`951760796 5`",
                parse_mode="Markdown",
            )
            return


    # =====================================================
    # ADMIN PANEL SETTINGS
    # =====================================================

    if context.user_data.get("waiting_panel_setting_key"):
        if not is_admin(user_id):
            return

        try:
            key = context.user_data.get("waiting_panel_setting_key")
            title = context.user_data.get(
                "waiting_panel_setting_title",
                "تنظیمات پنل",
            )

            value = text

            if not value:
                await update.message.reply_text(
                    "❌ مقدار نمی‌تواند خالی باشد."
                )
                return

            if key in ["panel_url", "panel_sub_base_url"]:
                value = value.rstrip("/")

                if not (
                    value.startswith("http://")
                    or value.startswith("https://")
                ):
                    await update.message.reply_text(
                        "❌ آدرس باید با http:// یا https:// شروع شود.\n\n"
                        "مثال:\n"
                        "<code>https://panel.sq9.ir:2096/sq9x8K_92mP</code>",
                        parse_mode="HTML",
                    )
                    return

            if key == "panel_inbound_id":
                try:
                    int(value)
                except Exception:
                    await update.message.reply_text(
                        "❌ Inbound ID باید عدد باشد.\n\n"
                        "مثال:\n"
                        "<code>1</code>",
                        parse_mode="HTML",
                    )
                    return

            set_setting(key, value)

            context.user_data.pop("waiting_panel_setting_key", None)
            context.user_data.pop("waiting_panel_setting_title", None)

            shown_value = mask_secret(value) if key == "panel_password" else value

            await update.message.reply_text(
                f"✅ {title} بروزرسانی شد.\n\n"
                "مقدار جدید:\n"
                f"<code>{shown_value}</code>",
                parse_mode="HTML",
                reply_markup=panel_settings_keyboard(),
            )

            return

        except Exception as e:
            await update.message.reply_text(
                "❌ خطا در ذخیره تنظیمات پنل.\n\n"
                f"<code>{str(e)}</code>",
                parse_mode="HTML",
            )
            return

    # =====================================================
    # CUSTOM CHARGE AMOUNT
    # =====================================================

    if context.user_data.get("waiting_custom_amount"):

        try:

            amount = float(text)

            if amount <= 0:
                await update.message.reply_text(
                    "❌ مبلغ باید بیشتر از صفر باشد."
                )
                return

            if amount < 0.5:
                await update.message.reply_text(
                    "❌ حداقل مبلغ شارژ 0.5$ است."
                )
                return

            network = context.user_data.get("selected_network", "ton")
            network = str(network).lower()

            if network == "ton":
                wallet = TON_WALLET
                network_name = "TON"

            elif network == "usdt_ton":
                wallet = TON_WALLET
                network_name = "USDT - TON"

            elif network == "tron":
                wallet = TRON_WALLET
                network_name = "TRON"

            elif network == "usdt_tron":
                wallet = TRON_WALLET
                network_name = "USDT - TRC20"

            elif network == "usdt_bsc":
                wallet = BSC_WALLET
                network_name = "USDT - BEP20"

            elif network == "ltc":
                wallet = LTC_WALLET
                network_name = "Litecoin"

            else:
                wallet = TON_WALLET
                network_name = "TON"

            if not wallet:
                await update.message.reply_text(
                    "❌ آدرس کیف پول این شبکه تنظیم نشده است.\n\n"
                    "لطفاً از شبکه دیگری استفاده کنید یا به پشتیبانی پیام دهید."
                )
                return

            deposit_id = generate_deposit_id(network.upper())

            conn = get_db()

            conn.execute(
                """
                INSERT INTO deposits(
                    deposit_id,
                    user_id,
                    amount,
                    network,
                    status
                )
                VALUES(?,?,?,?,?)
                """,
                (
                    deposit_id,
                    user_id,
                    amount,
                    network_name,
                    "PENDING",
                ),
            )

            conn.commit()
            conn.close()

            context.user_data.pop("waiting_custom_amount", None)
            context.user_data["waiting_tx"] = True
            context.user_data["deposit_id"] = deposit_id

            await update.message.reply_text(
                "💳 اطلاعات پرداخت\n\n"
                "━━━━━━━━━━━━━━━\n\n"
                f"🌐 شبکه:\n"
                f"`{network_name}`\n\n"
                f"💰 مبلغ:\n"
                f"`{amount:.2f}$`\n\n"
                f"🏦 آدرس کیف پول:\n"
                f"`{wallet}`\n\n"
                f"🧾 شماره شارژ:\n"
                f"`{deposit_id}`\n\n"
                "📤 پس از پرداخت، TX Hash یا لینک تراکنش را ارسال کنید.\n\n"
                "❌ برای لغو عملیات، روی بازگشت بزنید.",
                parse_mode="Markdown",
                reply_markup=back_keyboard("deposit")
            )

            return

        except Exception:

            await update.message.reply_text(
                "❌ مبلغ را فقط به عدد وارد کنید.\n\n"
                "مثال:\n"
                "`2.5`",
                parse_mode="Markdown",
            )

            return

    # =====================================================
    # USER SENDS TX HASH
    # =====================================================

    if context.user_data.get("waiting_tx"):

        deposit_id = context.user_data.get("deposit_id")
        tx_hash = text

        if not deposit_id:
            context.user_data.pop("waiting_tx", None)
            await update.message.reply_text(
                "❌ درخواست شارژ پیدا نشد. دوباره تلاش کنید."
            )
            return

        if len(tx_hash) < 8:
            await update.message.reply_text(
                "❌ TX Hash یا لینک تراکنش معتبر نیست."
            )
            return

        conn = get_db()

        dep = conn.execute(
            """
            SELECT deposit_id, amount, network, status
            FROM deposits
            WHERE deposit_id=?
            """,
            (deposit_id,),
        ).fetchone()

        if not dep:
            conn.close()
            context.user_data.pop("waiting_tx", None)
            context.user_data.pop("deposit_id", None)

            await update.message.reply_text(
                "❌ درخواست شارژ پیدا نشد."
            )
            return

        if dep["status"] != "PENDING":
            conn.close()
            context.user_data.pop("waiting_tx", None)
            context.user_data.pop("deposit_id", None)

            await update.message.reply_text(
                "❌ این درخواست شارژ قبلاً بررسی شده است."
            )
            return

        duplicate = conn.execute(
            """
            SELECT deposit_id
            FROM deposits
            WHERE tx_hash=?
            AND tx_hash IS NOT NULL
            """,
            (tx_hash,),
        ).fetchone()

        if duplicate:
            conn.close()
            await update.message.reply_text(
                "❌ این TX Hash قبلاً ثبت شده است."
            )
            return

        conn.execute(
            """
            UPDATE deposits
            SET tx_hash=?
            WHERE deposit_id=?
            """,
            (
                tx_hash,
                deposit_id,
            ),
        )

        conn.commit()
        conn.close()

        context.user_data.pop("waiting_tx", None)
        context.user_data.pop("deposit_id", None)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ تایید شارژ",
                    callback_data=f"depapprove_{deposit_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ رد شارژ",
                    callback_data=f"depreject_{deposit_id}",
                )
            ],
        ])

        admin_msg = (
            "💳 درخواست شارژ جدید\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"👤 User ID:\n"
            f"`{user_id}`\n\n"
            f"🧾 شماره شارژ:\n"
            f"`{deposit_id}`\n\n"
            f"💰 مبلغ:\n"
            f"`{float(dep['amount']):.2f}$`\n\n"
            f"🌐 شبکه:\n"
            f"`{dep['network']}`\n\n"
            f"🔗 TX Hash / Link:\n"
            f"`{tx_hash}`"
        )

        for admin_id in get_all_admins():
            try:
                await context.bot.send_message(
                    admin_id,
                    admin_msg,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception:
                pass

        await update.message.reply_text(
            "✅ TX Hash ثبت شد.\n\n"
            "درخواست شما برای ادمین ارسال شد و پس از تایید، موجودی کیف پول شما افزایش می‌یابد.",
        )

        return


    # =====================================================
    # ADMIN FREE TEST ADD
    # =====================================================

    if context.user_data.get("waiting_test_vless"):
        if not is_admin(user_id):
            return

        context.user_data["new_test_vless"] = text
        context.user_data.pop("waiting_test_vless", None)
        context.user_data["waiting_test_limit"] = True

        await update.message.reply_text(
            "👥 ظرفیت تست را عددی وارد کنید.\n\n"
            "مثال:\n"
            "`20`",
            parse_mode="Markdown",
        )
        return

    if context.user_data.get("waiting_test_limit"):
        if not is_admin(user_id):
            return

        try:
            max_users = int(text)
            if max_users <= 0:
                await update.message.reply_text("❌ ظرفیت باید بیشتر از صفر باشد.")
                return

            vless = context.user_data.get("new_test_vless")
            if not vless:
                context.user_data.pop("waiting_test_limit", None)
                await update.message.reply_text("❌ کانفیگ تست پیدا نشد. دوباره تلاش کنید.")
                return

            conn = get_db()

            conn.execute("UPDATE free_test SET is_active=0")

            conn.execute(
                """
                INSERT INTO free_test(vless, max_users, used_users, is_active)
                VALUES(?,?,0,1)
                """,
                (vless, max_users),
            )

            conn.commit()
            conn.close()

            context.user_data.pop("waiting_test_limit", None)
            context.user_data.pop("new_test_vless", None)

            await update.message.reply_text(
                "✅ تست رایگان جدید فعال شد.",
                reply_markup=admin_keyboard(),
            )
            return

        except Exception:
            await update.message.reply_text(
                "❌ ظرفیت را فقط عدد وارد کنید.\n\n"
                "مثال:\n"
                "`20`",
                parse_mode="Markdown",
            )
            return

  
    # =====================================================
    # ADMIN ADD
    # =====================================================

    if context.user_data.get("admin_add_mode"):
        if not is_admin(user_id):
            return

        try:
            new_admin_id = int(text)

            conn = get_db()
            conn.execute(
                """
                INSERT OR IGNORE INTO admins(user_id)
                VALUES(?)
                """,
                (new_admin_id,),
            )
            conn.commit()
            conn.close()

            context.user_data.pop("admin_add_mode", None)

            await update.message.reply_text(
                "✅ ادمین جدید اضافه شد.",
                reply_markup=admin_keyboard(),
            )

            return

        except Exception:
            await update.message.reply_text(
                "❌ فقط آیدی عددی ارسال کنید."
            )
            return

    # =====================================================
    # ADMIN BAN / UNBAN
    # =====================================================

    if context.user_data.get("admin_ban_mode"):
        if not is_admin(user_id):
            return

        try:
            target_id, action = text.split()
            target_id = int(target_id)

            if action not in ["ban", "unban"]:
                await update.message.reply_text(
                    "❌ فقط ban یا unban مجاز است."
                )
                return

            banned_value = 1 if action == "ban" else 0

            conn = get_db()
            conn.execute(
                """
                UPDATE users
                SET is_banned=?
                WHERE user_id=?
                """,
                (
                    banned_value,
                    target_id,
                ),
            )
            conn.commit()
            conn.close()

            context.user_data.pop("admin_ban_mode", None)

            await update.message.reply_text(
                "✅ عملیات انجام شد.",
                reply_markup=admin_keyboard(),
            )

            return

        except Exception:
            await update.message.reply_text(
                "❌ فرمت اشتباه است.\n\n"
                "مثال:\n"
                "`951760796 ban`",
                parse_mode="Markdown",
            )
            return

    # =====================================================
    # BROADCAST
    # =====================================================

    if context.user_data.get("broadcast_mode"):
        if not is_admin(user_id):
            return

        conn = get_db()
        users = conn.execute(
            """
            SELECT user_id
            FROM users
            WHERE is_banned=0
            """
        ).fetchall()
        conn.close()

        sent = 0
        failed = 0

        for row in users:
            try:
                await context.bot.send_message(
                    row["user_id"],
                    text,
                )
                sent += 1
            except Exception:
                failed += 1

        context.user_data.pop("broadcast_mode", None)

        await update.message.reply_text(
            "✅ پیام همگانی ارسال شد.\n\n"
            f"📤 موفق: `{sent}`\n"
            f"❌ ناموفق: `{failed}`",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )

        return

    await update.message.reply_text(
        "پیام شما دریافت شد.\n\n"
        "برای استفاده از ربات از منوها استفاده کنید."
    )
