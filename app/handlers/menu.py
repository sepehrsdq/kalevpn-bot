from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import (
    APK_FILE_ID,
    BSC_WALLET,
    LTC_WALLET,
    SUPPORT_BOT,
    TON_WALLET,
    TRON_WALLET,
)
from app.database import get_db
from app.handlers.start import is_joined_channel
from app.keyboards import (
    admin_keyboard,
    back_keyboard,
    balance_admin_keyboard,
    main_menu_keyboard,
    panel_settings_keyboard,
    pricing_admin_keyboard,
)
from app.services.referrals import reward_referral_if_needed
from app.services.sync import sync_services_with_panel
from app.services.xui import XUIManager

from app.utils import (
    calculate_fixed_price,
    format_usage,
    generate_client_email,
    generate_deposit_id,
    generate_invoice_id,
    get_all_admins,
    get_float_setting,
    get_panel_inbound_id,
    get_panel_password,
    get_panel_sub_base_url,
    get_panel_url,
    get_panel_username,
    is_admin,
    mask_secret,
)


async def create_deposit_invoice(query, context, user_id, amount, network):
    network = str(network).lower()
    deposit_id = generate_deposit_id(network.upper())

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
        await query.edit_message_text(
            "❌ آدرس کیف پول این شبکه تنظیم نشده است.\n\n"
            "لطفاً از شبکه دیگری استفاده کنید یا به پشتیبانی پیام دهید.",
            reply_markup=back_keyboard("deposit_networks"),
        )
        return

    conn = get_db()
    conn.execute(
        """
        INSERT INTO deposits(deposit_id, user_id, amount, network, status)
        VALUES(?,?,?,?,?)
        """,
        (deposit_id, user_id, amount, network_name, "PENDING"),
    )
    conn.commit()
    conn.close()

    context.user_data["waiting_tx"] = True
    context.user_data["deposit_id"] = deposit_id

    await query.edit_message_text(
        "💳 اطلاعات پرداخت\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"🌐 شبکه:\n`{network_name}`\n\n"
        f"💰 مبلغ:\n`{amount:.2f}$`\n\n"
        f"🏦 آدرس کیف پول:\n`{wallet}`\n\n"
        f"🧾 شماره شارژ:\n`{deposit_id}`\n\n"
        "پس از پرداخت، TX Hash یا لینک تراکنش را همین‌جا ارسال کنید.\n\n"
        "برای لغو عملیات، روی بازگشت بزنید.",
        parse_mode="Markdown",
        reply_markup=back_keyboard("deposit_networks"),
    )


async def send_service_to_user(context, user_id, invoice_id, plan_text, service_data):
    sub_link = service_data.get("sub_link")
    vless_link = service_data.get("vless_link")

    text = (
        "🎉 سرویس شما آماده شد\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"🧾 شماره فاکتور:\n`{invoice_id}`\n\n"
        f"📦 پلن:\n`{plan_text}`\n\n"
        "🔗 لینک Subscription:\n"
        f"`{sub_link}`\n\n"
    )

    if vless_link:
        text += "📡 کانفیگ مستقیم:\n" f"`{vless_link}`\n\n"

    text += (
        "━━━━━━━━━━━━━━━\n\n"
        "📥 برنامه‌های پیشنهادی:\n\n"
        "🤖 Android:\n• NPV Tunnel\n\n"
        "🍎 iPhone:\n• HAPP\n• Streisand\n• NPV Tunnel\n\n"
        "⚠️ تنظیمات مهم:\n"
        "• Mux را روشن نکنید\n"
        "• Fragment را فعال نکنید\n"
        "• DNS برنامه را تغییر ندهید\n"
        "• لینک Subscription را Share نکنید\n\n"
        "💡 در صورت مشکل به پشتیبانی پیام دهید."
    )

    await context.bot.send_message(
        chat_id=user_id,
        text=text,
        parse_mode="Markdown",
    )


async def notify_admins(context, text):
    for admin_id in get_all_admins():
        try:
            await context.bot.send_message(
                admin_id,
                text,
                parse_mode="Markdown",
            )
        except Exception:
            pass


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Force join
    if data != "check_join":
        joined = await is_joined_channel(user_id, context.bot)
        if not joined:
            keyboard = [
                [InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/kale_vpn")],
                [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")],
            ]
            await query.message.reply_text(
                "❌ ابتدا در کانال عضو شوید.",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

    # Cancel pending deposit if user navigates away
    pending_dep = context.user_data.get("deposit_id")
    waiting_tx = context.user_data.get("waiting_tx")
    if pending_dep and waiting_tx and not data.startswith("charge_"):
        conn = get_db()
        conn.execute(
            """
            UPDATE deposits
            SET status='CANCELLED'
            WHERE deposit_id=? AND status='PENDING'
            """,
            (pending_dep,),
        )
        conn.commit()
        conn.close()
        context.user_data.pop("deposit_id", None)
        context.user_data.pop("waiting_tx", None)

    if data == "check_join":
        joined = await is_joined_channel(user_id, context.bot)
        if not joined:
            keyboard = [
                [InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/kale_vpn")],
                [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")],
            ]
            await query.edit_message_text(
                "❌ هنوز عضو کانال نشدید.\n\n"
                "لطفاً ابتدا عضو کانال شوید سپس روی «عضو شدم» بزنید.",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        pending_referrer_id = context.user_data.get("pending_referrer_id")
        if pending_referrer_id == user_id:
            pending_referrer_id = None

        conn = get_db()
        conn.execute(
            """
            INSERT OR IGNORE INTO users(user_id, username, referrer_id)
            VALUES(?,?,?)
            """,
            (user_id, query.from_user.username, pending_referrer_id),
        )
        conn.commit()
        conn.close()
        context.user_data.pop("pending_referrer_id", None)

        await query.edit_message_text(
            "✅ عضویت تایید شد.",
            reply_markup=main_menu_keyboard(user_id),
        )
        return

    if data == "main_menu":
        await query.message.reply_text(
            "🏠 منوی اصلی",
            reply_markup=main_menu_keyboard(user_id),
        )
        return

    # Admin
    if data == "admin_panel":
        if not is_admin(user_id):
            return
        await query.message.reply_text("👑 پنل مدیریت", reply_markup=admin_keyboard())
        return

    if data == "admin_stats":
        if not is_admin(user_id):
            return
        conn = get_db()
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        total_paid = conn.execute("SELECT COUNT(*) AS c FROM invoices").fetchone()["c"]
        total_income = conn.execute("SELECT SUM(amount) AS s FROM invoices").fetchone()["s"] or 0
        total_balance = conn.execute("SELECT SUM(balance) AS s FROM users").fetchone()["s"] or 0
        total_tests = conn.execute("SELECT COUNT(*) AS c FROM free_test").fetchone()["c"]
        conn.close()

        await query.edit_message_text(
            "📊 آمار ربات\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"👥 کاربران: `{total_users}`\n"
            f"🛒 خریدها: `{total_paid}`\n"
            f"💰 درآمد کل: `{round(total_income, 2)}$`\n"
            f"💳 مجموع موجودی کاربران: `{round(total_balance, 2)}$`\n"
            f"🆓 تست‌ها: `{total_tests}`",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )
        return

    if data == "admin_broadcast":
        if not is_admin(user_id):
            return
        context.user_data["broadcast_mode"] = True
        await query.edit_message_text(
            "📢 پیام همگانی را ارسال کنید.",
            reply_markup=admin_keyboard(),
        )
        return

    if data == "admin_prices":
        if not is_admin(user_id):
            return
        await query.edit_message_text(
            "💵 مدیریت قیمت‌ها\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"📦 قیمت هر گیگ حجمی: `{get_float_setting('fixed_price_per_gb', 0.90)}$`\n\n"
            f"⚡ قیمت هر گیگ مصرفی: `{get_float_setting('usage_price_per_gb', 0.20)}$`\n\n"
            f"💳 حداقل موجودی مصرفی: `{get_float_setting('usage_min_balance', 1.00)}$`\n\n"
            f"👥 جایزه رفرال: `{get_float_setting('referral_reward', 0.25)}$`\n\n"
            "برای تغییر، یکی از گزینه‌ها را انتخاب کنید.",
            parse_mode="Markdown",
            reply_markup=pricing_admin_keyboard(),
        )
        return

    if data in ["price_fixed_gb", "price_usage_gb", "price_usage_min", "price_referral"]:
        if not is_admin(user_id):
            return

        price_map = {
            "price_fixed_gb": ("fixed_price_per_gb", "📦 قیمت هر گیگ حجمی"),
            "price_usage_gb": ("usage_price_per_gb", "⚡ قیمت هر گیگ مصرفی"),
            "price_usage_min": ("usage_min_balance", "💳 حداقل موجودی مصرفی"),
            "price_referral": ("referral_reward", "👥 جایزه رفرال"),
        }

        setting_key, title = price_map[data]
        context.user_data["waiting_price_key"] = setting_key
        context.user_data["waiting_price_title"] = title

        await query.edit_message_text(
            f"{title}\n\n"
            "مقدار جدید را فقط به عدد دلار وارد کنید.\n\n"
            "مثال:\n`0.25`",
            parse_mode="Markdown",
            reply_markup=pricing_admin_keyboard(),
        )
        return

    if data == "admin_panel_settings":
        if not is_admin(user_id):
            return

        await query.edit_message_text(
            "⚙️ تنظیمات پنل سنایی\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"🌐 آدرس API پنل:\n<code>{get_panel_url() or 'تنظیم نشده'}</code>\n\n"
            f"👤 یوزرنیم:\n<code>{get_panel_username() or 'تنظیم نشده'}</code>\n\n"
            f"🔐 پسورد:\n<code>{mask_secret(get_panel_password())}</code>\n\n"
            f"📡 Inbound ID:\n<code>{get_panel_inbound_id() or 'تنظیم نشده'}</code>\n\n"
            f"🔗 آدرس پایه Subscription:\n<code>{get_panel_sub_base_url() or 'تنظیم نشده'}</code>\n\n"
            "برای تغییر هر مورد، یکی از گزینه‌ها را انتخاب کنید.",
            parse_mode="HTML",
            reply_markup=panel_settings_keyboard(),
        )
        return

    if data == "admin_panel_test":
        if not is_admin(user_id):
            return

        await query.edit_message_text("⏳ در حال تست اتصال به پنل سنایی...")

        try:
            xui = XUIManager()
            ok, msg, inbound_count = xui.test_connection()

            if ok:
                text = (
                    "✅ اتصال به پنل موفق بود.\n\n"
                    f"📡 تعداد Inbound ها: <code>{inbound_count}</code>\n"
                    f"🧾 Inbound ID: <code>{get_panel_inbound_id()}</code>\n"
                    f"🔗 آدرس ساب: <code>{get_panel_sub_base_url()}</code>"
                )
            else:
                text = (
                    "❌ اتصال به پنل ناموفق بود.\n\n"
                    f"خطا:\n<code>{msg}</code>"
                )

            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=panel_settings_keyboard(),
            )

        except Exception as e:
            await query.edit_message_text(
                "❌ خطای داخلی در تست اتصال پنل.\n\n"
                f"<code>{str(e)}</code>",
                parse_mode="HTML",
                reply_markup=panel_settings_keyboard(),
            )
        return

    if data in ["panel_set_url", "panel_set_username", "panel_set_password", "panel_set_inbound", "panel_set_sub_base"]:
        if not is_admin(user_id):
            return

        panel_map = {
            "panel_set_url": ("panel_url", "🌐 آدرس API پنل", "مثال:\n<code>https://panel.example.com:35816/path</code>"),
            "panel_set_username": ("panel_username", "👤 یوزرنیم پنل", "مثال:\n<code>admin</code>"),
            "panel_set_password": ("panel_password", "🔐 پسورد پنل", "پسورد جدید پنل را ارسال کنید."),
            "panel_set_inbound": ("panel_inbound_id", "📡 Inbound ID", "مثال:\n<code>1</code>"),
            "panel_set_sub_base": ("panel_sub_base_url", "🔗 آدرس پایه Subscription", "مثال:\n<code>https://panel.sq9.ir:2096/sq9x8K_92mP</code>"),
        }

        setting_key, title, example = panel_map[data]
        context.user_data["waiting_panel_setting_key"] = setting_key
        context.user_data["waiting_panel_setting_title"] = title

        await query.edit_message_text(
            f"{title}\n\nمقدار جدید را ارسال کنید.\n\n{example}",
            parse_mode="HTML",
            reply_markup=panel_settings_keyboard(),
        )
        return

    # Admin deposit approve/reject
    if data.startswith("depapprove_"):
        if not is_admin(user_id):
            return

        deposit_id = data.replace("depapprove_", "")
        conn = get_db()
        dep = conn.execute(
            "SELECT deposit_id, user_id, amount, status FROM deposits WHERE deposit_id=?",
            (deposit_id,),
        ).fetchone()

        if not dep:
            conn.close()
            await query.edit_message_text("❌ درخواست شارژ پیدا نشد.", reply_markup=admin_keyboard())
            return

        if dep["status"] != "PENDING":
            conn.close()
            await query.edit_message_text("❌ این شارژ قبلاً بررسی شده است.", reply_markup=admin_keyboard())
            return

        target_user_id = dep["user_id"]
        amount = float(dep["amount"] or 0)

        conn.execute("UPDATE deposits SET status='APPROVED' WHERE deposit_id=?", (deposit_id,))
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, target_user_id))
        new_balance = conn.execute(
            "SELECT balance FROM users WHERE user_id=?",
            (target_user_id,),
        ).fetchone()["balance"]
        conn.commit()
        conn.close()

        try:
            await context.bot.send_message(
                target_user_id,
                "✅ شارژ کیف پول شما تایید شد.\n\n"
                f"💰 مبلغ اضافه‌شده: `{amount:.2f}$`\n"
                f"💳 موجودی جدید: `{float(new_balance):.2f}$`",
                parse_mode="Markdown",
            )
        except Exception:
            pass

        await query.edit_message_text(
            "✅ شارژ تایید شد.\n\n"
            f"👤 User ID: `{target_user_id}`\n"
            f"💰 مبلغ: `{amount:.2f}$`\n"
            f"💳 موجودی جدید: `{float(new_balance):.2f}$`",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )
        return

    if data.startswith("depreject_"):
        if not is_admin(user_id):
            return

        deposit_id = data.replace("depreject_", "")
        conn = get_db()
        dep = conn.execute(
            "SELECT deposit_id, user_id, status FROM deposits WHERE deposit_id=?",
            (deposit_id,),
        ).fetchone()

        if not dep:
            conn.close()
            await query.edit_message_text("❌ درخواست شارژ پیدا نشد.", reply_markup=admin_keyboard())
            return

        if dep["status"] != "PENDING":
            conn.close()
            await query.edit_message_text("❌ این شارژ قبلاً بررسی شده است.", reply_markup=admin_keyboard())
            return

        target_user_id = dep["user_id"]
        conn.execute("UPDATE deposits SET status='REJECTED' WHERE deposit_id=?", (deposit_id,))
        conn.commit()
        conn.close()

        try:
            await context.bot.send_message(
                target_user_id,
                "❌ شارژ کیف پول شما رد شد.\n\n"
                "در صورت اشتباه بودن نتیجه، با پشتیبانی در ارتباط باشید.",
            )
        except Exception:
            pass

        await query.edit_message_text("❌ شارژ رد شد.", reply_markup=admin_keyboard())
        return

    # Shop
    if data == "shop":
        keyboard = [
            [InlineKeyboardButton("📦 سرویس حجمی ثابت", callback_data="shop_fixed")],
            [InlineKeyboardButton("⚡ سرویس مصرفی", callback_data="shop_usage")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")],
        ]
        await query.edit_message_text(
            "🚀 خرید سرویس KaleVPN\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            "📦 سرویس حجمی ثابت\n"
            "حجم و مدت مشخص دارد و بعد از پرداخت، لینک Subscription و کانفیگ به صورت خودکار ارسال می‌شود.\n\n"
            "⚡ سرویس مصرفی\n"
            "کیف پول را شارژ می‌کنید و هزینه بر اساس مصرف واقعی از موجودی شما کسر می‌شود.\n"
            "بعد از فعال‌سازی، لینک Subscription و کانفیگ به صورت خودکار ارسال می‌شود.\n\n"
            "نوع سرویس را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "shop_fixed":
        keyboard = [
            [
                InlineKeyboardButton("💎 1GB", callback_data="selectgb_1"),
                InlineKeyboardButton("💎 2GB", callback_data="selectgb_2"),
            ],
            [
                InlineKeyboardButton("🔥 5GB", callback_data="selectgb_5"),
                InlineKeyboardButton("🚀 10GB", callback_data="selectgb_10"),
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="shop")],
        ]
        await query.edit_message_text(
            "📦 سرویس حجمی ثابت\n\nحجم سرویس را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("selectgb_"):
        gb = float(data.split("_")[1])
        context.user_data["selected_gb"] = gb
        keyboard = [
            [InlineKeyboardButton("⚡ 1 روزه", callback_data="duration_1")],
            [InlineKeyboardButton("🔥 7 روزه", callback_data="duration_7")],
            [InlineKeyboardButton("🚀 30 روزه", callback_data="duration_30")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="shop_fixed")],
        ]
        await query.edit_message_text(
            f"📦 حجم انتخابی: `{gb}GB`\n\n⏳ مدت سرویس را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("duration_"):
        days = int(data.split("_")[1])
        gb = context.user_data.get("selected_gb")
        if not gb:
            await query.edit_message_text("❌ ابتدا حجم را انتخاب کنید.", reply_markup=back_keyboard("shop_fixed"))
            return

        price = calculate_fixed_price(gb, days)
        keyboard = [
            [InlineKeyboardButton("✅ تایید خرید", callback_data=f"buy_{gb}_{days}_{price}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="shop_fixed")],
        ]
        await query.edit_message_text(
            "🛒 تایید خرید\n\n"
            f"📦 حجم: `{gb}GB`\n"
            f"⏳ مدت: `{days} روز`\n"
            f"💰 مبلغ: `{price}$`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("buy_"):
        _, gb, days, price = data.split("_")
        keyboard = [
            [InlineKeyboardButton("✅ تایید قوانین و پرداخت", callback_data=f"acceptbuy_{gb}_{days}_{price}")],
            [InlineKeyboardButton("❌ لغو", callback_data="shop")],
        ]
        await query.edit_message_text(
            "📜 قوانین و شرایط استفاده KaleVPN\n\n"
            "1️⃣ سرویس‌ها شخصی هستند و اشتراک‌گذاری یا فروش مجدد ممنوع است.\n\n"
            "2️⃣ با توجه به شرایط اینترنت، احتمال اختلال یا قطعی موقت وجود دارد.\n\n"
            "3️⃣ هرگونه سوءاستفاده یا فعالیت مخرب باعث قطع سرویس بدون بازگشت وجه می‌شود.\n\n"
            "4️⃣ مسئولیت حفظ لینک و کانفیگ با کاربر است.\n\n"
            "در صورت موافقت، تایید کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("acceptbuy_"):
        _, gb, days, price = data.split("_")
        gb = float(gb)
        days = int(days)
        price = float(price)

        conn = get_db()
        row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        balance = float(row["balance"] or 0) if row else 0

        if balance < price:
            conn.close()
            await query.edit_message_text(
                "❌ موجودی شما کافی نیست.\n\n"
                f"💰 موجودی فعلی: `{balance:.2f}$`\n"
                f"💳 مبلغ لازم: `{price:.2f}$`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 شارژ کیف پول", callback_data="deposit")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="shop_fixed")],
                ]),
            )
            return

        invoice_id = generate_invoice_id()
        plan_text = f"{gb}GB | {days} Day"
        client_email = generate_client_email(user_id, invoice_id, "fixed")

        xui = XUIManager()
        ok, panel_msg, service_data = xui.add_client(
            email=client_email,
            limit_gb=gb,
            expiry_days=days,
            service_type="fixed",
        )

        if not ok:
            conn.close()
            await query.edit_message_text(
                "❌ ساخت سرویس ناموفق بود.\n\n"
                f"خطا:\n`{panel_msg}`",
                parse_mode="Markdown",
                reply_markup=back_keyboard("shop_fixed"),
            )
            return

        conn.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (price, user_id))
        conn.execute(
            """
            INSERT INTO invoices(
                invoice_id, user_id, amount, plan, delivered, service_type, status,
                sub_link, vless_link, client_uuid, client_email, sub_id
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                invoice_id,
                user_id,
                price,
                plan_text,
                1,
                "fixed",
                "DELIVERED",
                service_data.get("sub_link"),
                service_data.get("vless_link"),
                service_data.get("uuid"),
                service_data.get("email"),
                service_data.get("sub_id"),
            ),
        )
        conn.commit()
        conn.close()

        await send_service_to_user(context, user_id, invoice_id, plan_text, service_data)

        referral_reward = reward_referral_if_needed(user_id, invoice_id)
        if referral_reward:
            referrer_id, reward_amount = referral_reward
            try:
                await context.bot.send_message(
                    referrer_id,
                    "🎁 جایزه دعوت شما فعال شد.\n\n"
                    f"💰 مبلغ `{reward_amount:.2f}$` به کیف پول شما اضافه شد.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        await notify_admins(
            context,
            "✅ خرید حجمی جدید به صورت خودکار تحویل شد\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"🧾 Invoice: `{invoice_id}`\n"
            f"📦 Plan: `{plan_text}`\n"
            f"💰 Amount: `{price:.2f}$`",
        )

        await query.edit_message_text(
            "✅ خرید موفق بود.\n\n"
            f"🧾 شماره فاکتور: `{invoice_id}`\n\n"
            "لینک Subscription و کانفیگ برای شما ارسال شد.",
            parse_mode="Markdown",
            reply_markup=back_keyboard("main_menu"),
        )
        return

    elif data == "shop_usage":

        usage_price = get_float_setting("usage_price_per_gb", 0.20)
        min_balance = get_float_setting("usage_min_balance", 1.00)

        keyboard = [

            [
                InlineKeyboardButton(
                    "✅ درخواست فعال‌سازی",
                    callback_data="usage_rules"
                )
            ],

            [
                InlineKeyboardButton(
                    "💰 شارژ کیف پول",
                    callback_data="deposit"
                )
            ],

            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="shop"
                )
            ]
        ]

        msg = (
            "⚡ سرویس مصرفی KaleVPN\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            "در این سرویس، شما کیف پول خود را شارژ می‌کنید و هزینه فقط بر اساس مصرف واقعی کسر می‌شود.\n\n"
            "بعد از تایید قوانین و فعال‌سازی، لینک Subscription و کانفیگ به صورت خودکار برای شما ارسال می‌شود.\n\n"
            f"💵 تعرفه فعلی هر 1GB:\n"
            f"`{usage_price}$`\n\n"
            f"💳 حداقل موجودی برای فعال‌سازی:\n"
            f"`{min_balance}$`\n\n"
            "برای ادامه، روی درخواست فعال‌سازی بزنید."
        )

        await query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return


    elif data == "usage_rules":

        usage_price = get_float_setting("usage_price_per_gb", 0.20)
        min_balance = get_float_setting("usage_min_balance", 1.00)

        keyboard = [

            [
                InlineKeyboardButton(
                    "✅ تایید قوانین و فعال‌سازی",
                    callback_data="usage_activate"
                )
            ],

            [
                InlineKeyboardButton(
                    "❌ لغو",
                    callback_data="shop_usage"
                )
            ]
        ]

        msg = (
            "📜 قوانین سرویس مصرفی KaleVPN\n\n"
            "━━━━━━━━━━━━━━━\n\n"

            "1️⃣ سرویس مصرفی بر اساس مصرف واقعی اینترنت محاسبه می‌شود.\n\n"

            f"2️⃣ تعرفه فعلی هر 1GB مصرف:\n"
            f"`{usage_price}$`\n\n"

            f"3️⃣ حداقل موجودی لازم برای فعال‌سازی:\n"
            f"`{min_balance}$`\n\n"

            "4️⃣ هزینه مصرف به صورت دوره‌ای از کیف پول شما کسر می‌شود.\n\n"

            "5️⃣ اگر موجودی کیف پول شما تمام شود، سرویس به صورت خودکار غیرفعال می‌شود.\n\n"

            "6️⃣ اشتراک‌گذاری، فروش مجدد یا استفاده عمومی از لینک سرویس ممنوع است.\n\n"

            "7️⃣ با توجه به شرایط اینترنت، احتمال اختلال یا قطعی موقت وجود دارد و تضمین اتصال دائمی ۱۰۰٪ وجود ندارد.\n\n"

            "⚠️ در صورت موافقت، گزینه «تایید قوانین و فعال‌سازی» را انتخاب کنید."
        )

        await query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    if data == "usage_activate":
        min_balance = get_float_setting("usage_min_balance", 1.00)
        usage_price = get_float_setting("usage_price_per_gb", 0.20)

        conn = get_db()
        row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        balance = float(row["balance"] or 0) if row else 0

        if balance < min_balance:
            conn.close()
            await query.edit_message_text(
                "❌ موجودی شما برای فعال‌سازی سرویس مصرفی کافی نیست.\n\n"
                f"💰 موجودی فعلی: `{balance:.2f}$`\n"
                f"💳 حداقل موجودی لازم: `{min_balance:.2f}$`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 شارژ کیف پول", callback_data="deposit")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="shop_usage")],
                ]),
            )
            return

        invoice_id = generate_invoice_id()
        plan_text = f"Usage Based | {usage_price}$ per GB"
        client_email = generate_client_email(user_id, invoice_id, "usage")

        xui = XUIManager()
        ok, panel_msg, service_data = xui.add_client(
            email=client_email,
            limit_gb=0,
            expiry_days=0,
            service_type="usage",
        )

        if not ok:
            conn.close()
            await query.edit_message_text(
                "❌ ساخت سرویس مصرفی ناموفق بود.\n\n"
                f"خطا:\n`{panel_msg}`",
                parse_mode="Markdown",
                reply_markup=back_keyboard("shop_usage"),
            )
            return

        conn.execute(
            """
            INSERT INTO invoices(
                invoice_id, user_id, amount, plan, delivered, service_type, status,
                sub_link, vless_link, client_uuid, client_email, sub_id
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                invoice_id,
                user_id,
                0,
                plan_text,
                1,
                "usage",
                "DELIVERED",
                service_data.get("sub_link"),
                service_data.get("vless_link"),
                service_data.get("uuid"),
                service_data.get("email"),
                service_data.get("sub_id"),
            ),
        )
        conn.commit()
        conn.close()

        await send_service_to_user(context, user_id, invoice_id, plan_text, service_data)

        await notify_admins(
            context,
            "✅ سرویس مصرفی جدید به صورت خودکار فعال شد\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"🧾 Invoice: `{invoice_id}`\n"
            f"💰 Balance: `{balance:.2f}$`\n"
            f"💵 Rate: `{usage_price}$ / GB`",
        )

        await query.edit_message_text(
            "✅ سرویس مصرفی فعال شد.\n\n"
            f"🧾 شماره سرویس: `{invoice_id}`\n\n"
            "لینک Subscription و کانفیگ برای شما ارسال شد.",
            parse_mode="Markdown",
            reply_markup=back_keyboard("main_menu"),
        )
        return

    # My services
    if data == "my_services":
        sync_services_with_panel(user_id)

        conn = get_db()
        rows = conn.execute(
            """
            SELECT invoice_id, plan, amount, service_type, status, sub_link,
                   usage_total_bytes, usage_charged_amount, usage_disabled, created_at
            FROM invoices
            WHERE user_id=?
            AND status != 'PANEL_DELETED'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (user_id,),
        ).fetchall()
        conn.close()

        if not rows:
            await query.edit_message_text(
                "📦 اشتراک‌های من\n\nشما اشتراک فعالی ندارید.",
                reply_markup=main_menu_keyboard(user_id),
            )
            return

        text = "📦 اشتراک‌های من\n\n━━━━━━━━━━━━━━━\n\n"
        keyboard = []

        for row in rows:
            invoice_id = row["invoice_id"]
            service_type = row["service_type"]
            usage_disabled = int(row["usage_disabled"] or 0)
            status = row["status"]

            type_text = "⚡ مصرفی" if service_type == "usage" else "📦 حجمی ثابت"

            if usage_disabled == 1:
                status_text = "🚫 غیرفعال"
            elif status == "DELIVERED":
                status_text = "🟢 فعال"
            else:
                status_text = "🟡 در انتظار"

            text += (
                f"{type_text}\n"
                f"🧾 فاکتور: `{invoice_id}`\n"
                f"📌 پلن: `{row['plan']}`\n"
                f"📡 وضعیت: {status_text}\n"
            )

            if service_type == "usage":
                text += (
                    f"📊 مصرف ثبت‌شده: `{format_usage(row['usage_total_bytes'] or 0)}`\n"
                    f"💸 هزینه مصرف‌شده: `{float(row['usage_charged_amount'] or 0):.4f}$`\n"
                )
            else:
                text += f"💰 مبلغ پرداختی: `{float(row['amount'] or 0):.2f}$`\n"

            text += f"📅 تاریخ: `{row['created_at']}`\n━━━━━━━━━━━━━━━\n\n"

            keyboard.append([
                InlineKeyboardButton(
                    f"🔗 لینک سرویس {invoice_id}",
                    callback_data=f"service_detail_{invoice_id}",
                )
            ])

        keyboard.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")])

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("service_detail_"):
        invoice_id = data.replace("service_detail_", "")

        conn = get_db()
        row = conn.execute(
            """
            SELECT invoice_id, plan, amount, service_type, status, sub_link, vless_link,
                   usage_total_bytes, usage_charged_amount, usage_disabled, created_at
            FROM invoices
            WHERE invoice_id=? AND user_id=? AND status != 'PANEL_DELETED'
            """,
            (invoice_id, user_id),
        ).fetchone()
        conn.close()

        if not row:
            await query.edit_message_text(
                "❌ سرویس پیدا نشد.",
                reply_markup=back_keyboard("my_services"),
            )
            return

        service_type = row["service_type"]
        type_text = "⚡ مصرفی" if service_type == "usage" else "📦 حجمی ثابت"

        if int(row["usage_disabled"] or 0) == 1:
            status_text = "🚫 غیرفعال"
        elif row["status"] == "DELIVERED":
            status_text = "🟢 فعال"
        else:
            status_text = "🟡 در انتظار"

        text = (
            "🔗 جزئیات سرویس\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"🧾 فاکتور:\n`{row['invoice_id']}`\n\n"
            f"📌 نوع سرویس:\n{type_text}\n\n"
            f"📦 پلن:\n`{row['plan']}`\n\n"
            f"📡 وضعیت:\n{status_text}\n\n"
        )

        if service_type == "usage":
            text += (
                f"📊 مصرف ثبت‌شده:\n`{format_usage(row['usage_total_bytes'] or 0)}`\n\n"
                f"💸 هزینه مصرف‌شده:\n`{float(row['usage_charged_amount'] or 0):.4f}$`\n\n"
            )
        else:
            text += f"💰 مبلغ پرداختی:\n`{float(row['amount'] or 0):.2f}$`\n\n"

        text += f"🔗 لینک Subscription:\n`{row['sub_link']}`\n\n"

        if row["vless_link"]:
            text += f"📡 کانفیگ مستقیم:\n`{row['vless_link']}`\n\n"

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 برگشت به اشتراک‌های من", callback_data="my_services")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")],
            ]),
        )
        return

    # Wallet/deposit
    if data == "balance":
        conn = get_db()
        row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        conn.close()
        balance = float(row["balance"] or 0) if row else 0

        keyboard = [
            [InlineKeyboardButton("💵 شارژ حساب", callback_data="deposit")],
            [InlineKeyboardButton("📦 اشتراک‌های من", callback_data="my_services")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")],
        ]
        await query.edit_message_text(
            "💰 کیف پول شما\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"موجودی فعلی:\n`{balance:.2f}$`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    elif data == "deposit":

        keyboard = [

            [
                InlineKeyboardButton(
                    "✅ متوجه شدم",
                    callback_data="deposit_networks"
                )
            ],

            [
                InlineKeyboardButton(
                    "❌ انصراف",
                    callback_data="balance"
                )
            ]
        ]

        msg = (
            "📌 راهنمای شارژ کیف پول\n\n"

            "💡 برای شارژ حساب می‌توانید از صرافی‌هایی مثل:\n"
            "• نوبیتکس\n"
            "• بیت پین\n\n"

            "استفاده کنید.\n\n"

            "━━━━━━━━━━━━━━━\n\n"

            "⚠️ نکات مهم:\n\n"

            "• حتماً شبکه صحیح را انتخاب کنید.\n"
            "• مبلغ را دقیق ارسال کنید.\n"
            "• پس از پرداخت، TX Hash را ارسال کنید.\n"
            "• در صورت انتخاب شبکه اشتباه، پرداخت قابل بازیابی نیست.\n"
            "• توصیه می‌شود از شبکه TON استفاده کنید چون کارمزد بسیار کمتری دارد.\n\n"

            "━━━━━━━━━━━━━━━\n\n"

            "✅ پس از مطالعه، روی «متوجه شدم» بزنید."
        )

        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    elif data == "deposit_networks":

        keyboard = [

            [
                InlineKeyboardButton(
                    "💎 TON",
                    callback_data="net_ton"
                ),

                InlineKeyboardButton(
                    "💵 USDT (TON)",
                    callback_data="net_usdt_ton"
                )
            ],

            [
                InlineKeyboardButton(
                    "🔺 TRON",
                    callback_data="net_tron"
                ),

                InlineKeyboardButton(
                    "💵 USDT (TRC20)",
                    callback_data="net_usdt_tron"
                )
            ],

            [
                InlineKeyboardButton(
                    "💵 USDT (BEP20)",
                    callback_data="net_usdt_bsc"
                )
            ],

            [
                InlineKeyboardButton(
                    "🪙 Litecoin",
                    callback_data="net_ltc"
                )
            ],

            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="balance"
                )
            ]
        ]

        await query.edit_message_text(
            "💳 شبکه پرداخت را انتخاب کنید:\n\n"
            "💡 توصیه می‌شود از شبکه TON به دلیل کارمزد کمتر استفاده کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    if data.startswith("net_"):
        network = data.replace("net_", "")
        context.user_data["selected_network"] = network

        keyboard = [
            [
                InlineKeyboardButton("1$", callback_data="charge_1"),
                InlineKeyboardButton("5$", callback_data="charge_5"),
            ],
            [
                InlineKeyboardButton("10$", callback_data="charge_10"),
                InlineKeyboardButton("15$", callback_data="charge_15"),
            ],
            [InlineKeyboardButton("💵 مبلغ دلخواه", callback_data="custom_charge")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="deposit_networks")],
        ]
        await query.edit_message_text(
            "💰 مبلغ شارژ را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "custom_charge":
        context.user_data["waiting_custom_amount"] = True
        await query.edit_message_text(
            "💵 مبلغ دلخواه را وارد کنید.\n\n"
            "مثال:\n"
            "`2.5`",
            parse_mode="Markdown",
            reply_markup=back_keyboard("deposit")
        )

        return

    if data.startswith("charge_"):
        amount = float(data.split("_")[1])
        network = context.user_data.get("selected_network", "ton")
        await create_deposit_invoice(query, context, user_id, amount, network)
        return

    # Free test
    if data == "free_test":
        conn = get_db()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id, vless, max_users, used_users, is_active
                FROM free_test
                WHERE is_active=1
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

            if not row:
                conn.rollback()
                await query.edit_message_text("❌ تست رایگان فعال نیست.", reply_markup=back_keyboard())
                return

            test_id = row["id"]
            vless = row["vless"]
            max_users = int(row["max_users"] or 0)
            used_users = int(row["used_users"] or 0)

            already = conn.execute(
                "SELECT id FROM free_test_claims WHERE user_id=? AND test_id=?",
                (user_id, test_id),
            ).fetchone()

            if already:
                conn.rollback()
                await query.edit_message_text(
                    "❌ شما این اشتراک تست را قبلاً دریافت کرده‌اید.",
                    reply_markup=back_keyboard(),
                )
                return

            if used_users >= max_users:
                conn.execute("UPDATE free_test SET is_active=0 WHERE id=?", (test_id,))
                conn.commit()
                await query.edit_message_text("❌ ظرفیت تست رایگان تکمیل شده.", reply_markup=back_keyboard())
                return

            conn.execute(
                "INSERT INTO free_test_claims(user_id, test_id) VALUES(?,?)",
                (user_id, test_id),
            )
            new_used = used_users + 1
            conn.execute("UPDATE free_test SET used_users=? WHERE id=?", (new_used, test_id))
            if new_used >= max_users:
                conn.execute("UPDATE free_test SET is_active=0 WHERE id=?", (test_id,))

            conn.commit()

            await query.edit_message_text(
                "🆓 اشتراک تست رایگان\n\n"
                "━━━━━━━━━━━━━━━\n\n"
                f"📥 کانفیگ تست:\n\n`{vless}`\n\n"
                f"👥 ظرفیت باقی‌مانده: `{max_users - new_used}`",
                parse_mode="Markdown",
                reply_markup=back_keyboard(),
            )
            return

        except Exception as e:
            conn.rollback()
            print("FREE TEST ERROR:", e)
            await query.edit_message_text("❌ خطایی رخ داد.", reply_markup=back_keyboard())
            return
        finally:
            conn.close()

    if data == "admin_test":
        if not is_admin(user_id):
            return

        conn = get_db()
        tests = conn.execute(
            """
            SELECT id, max_users, used_users, is_active, created_at
            FROM free_test
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()
        conn.close()

        text = "🆓 مدیریت تست رایگان\n\n"
        if not tests:
            text += "❌ هیچ تستی ثبت نشده."
        else:
            for t in tests:
                status = "🟢 فعال" if int(t["is_active"] or 0) == 1 else "🔴 غیرفعال"
                text += (
                    f"🧾 ID: `{t['id']}`\n"
                    f"👥 کاربران: `{t['used_users']}/{t['max_users']}`\n"
                    f"📡 وضعیت: {status}\n\n"
                )

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ افزودن تست", callback_data="add_test")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")],
            ]),
        )
        return

    if data == "add_test":
        if not is_admin(user_id):
            return
        context.user_data["waiting_test_vless"] = True
        await query.edit_message_text("🆓 کانفیگ VLESS تست را ارسال کنید.")
        return

    # Tutorial/support
    if data == "tutorial":
        text = (
            "📚 مرکز آموزش KaleVPN\n\n"
            "1️⃣ برنامه مناسب را نصب کنید.\n"
            "2️⃣ لینک Subscription را داخل برنامه Import کنید.\n"
            "3️⃣ Update/Sync بزنید و Connect کنید.\n\n"
            "⚠️ Mux، Fragment و DNS اضافه را فعال نکنید."
        )
        await query.edit_message_text(text, reply_markup=back_keyboard())
        try:
            await context.bot.send_document(
                chat_id=user_id,
                document=APK_FILE_ID,
                caption="📥 دانلود NPV Tunnel برای Android",
            )
        except Exception:
            pass
        return

    if data == "support":
        keyboard = [
            [InlineKeyboardButton("💬 ارتباط با پشتیبانی", url=SUPPORT_BOT)],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")],
        ]
        await query.edit_message_text(
            "پشتیبانی:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # Admin balance/add/ban
    if data == "admin_balance":
        if not is_admin(user_id):
            return
        await query.edit_message_text(
            "💰 مدیریت موجودی کاربران\n\nیکی از عملیات زیر را انتخاب کنید:",
            reply_markup=balance_admin_keyboard(),
        )
        return

    if data == "admin_balance_add":
        if not is_admin(user_id):
            return
        context.user_data.pop("admin_balance_sub_mode", None)
        context.user_data.pop("waiting_panel_setting_key", None)
        context.user_data.pop("waiting_panel_setting_title", None)
        context.user_data.pop("waiting_price_key", None)
        context.user_data.pop("waiting_price_title", None)
        context.user_data.pop("waiting_custom_amount", None)
        context.user_data.pop("waiting_tx", None)
        context.user_data.pop("deposit_id", None)
        context.user_data["admin_balance_add_mode"] = True
        await query.edit_message_text(
            "➕ افزایش موجودی\n\nفرمت:\n`USER_ID AMOUNT`\n\nمثال:\n`951760796 5`",
            parse_mode="Markdown",
            reply_markup=balance_admin_keyboard(),
        )
        return

    if data == "admin_balance_sub":
        if not is_admin(user_id):
            return
        context.user_data.pop("admin_balance_add_mode", None)
        context.user_data.pop("waiting_panel_setting_key", None)
        context.user_data.pop("waiting_panel_setting_title", None)
        context.user_data.pop("waiting_price_key", None)
        context.user_data.pop("waiting_price_title", None)
        context.user_data.pop("waiting_custom_amount", None)
        context.user_data.pop("waiting_tx", None)
        context.user_data.pop("deposit_id", None)
        await query.edit_message_text(
            "➖ کاهش موجودی\n\nفرمت بدون منفی:\n`USER_ID AMOUNT`\n\nمثال:\n`951760796 0.5`",
            parse_mode="Markdown",
            reply_markup=balance_admin_keyboard(),
        )
        return

    if data == "admin_add":
        if not is_admin(user_id):
            return
        context.user_data["admin_add_mode"] = True
        await query.edit_message_text("👑 آیدی عددی ادمین جدید را ارسال کنید.", reply_markup=admin_keyboard())
        return

    if data == "admin_ban":
        if not is_admin(user_id):
            return
        context.user_data["admin_ban_mode"] = True
        await query.edit_message_text(
            "🚫 مدیریت بن کاربران\n\nفرمت:\n`USER_ID ban`\n\nیا:\n`USER_ID unban`",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )
        return
