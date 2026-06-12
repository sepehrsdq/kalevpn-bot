import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.database import get_db
from app.services.billing import charge_usage
from app.services.xui import XUIManager
from app.utils import get_float_setting

async def process_usage_billing(application):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT
            invoice_id,
            user_id,
            client_email,
            usage_last_bytes,
            usage_low_balance_warned
        FROM invoices
        WHERE service_type='usage'
        AND delivered=1
        AND status='DELIVERED'
        AND usage_disabled=0
        AND client_email IS NOT NULL
        """
    ).fetchall()
    conn.close()

    if not rows:
        return

    low_balance_threshold = get_float_setting("usage_low_balance_threshold", 0.25)
    xui = XUIManager()

    for row in rows:
        invoice_id = row["invoice_id"]
        user_id = row["user_id"]
        client_email = row["client_email"]
        last_bytes = int(row["usage_last_bytes"] or 0)
        low_warned = int(row["usage_low_balance_warned"] or 0)

        ok, msg, traffic = xui.get_client_traffic(client_email)

        if not ok or not traffic:
            print("USAGE TRAFFIC ERROR:", invoice_id, msg)

            if "پیدا نشد" in str(msg) or "not found" in str(msg).lower():
                conn = get_db()
                conn.execute(
                    """
                    UPDATE invoices
                    SET status='PANEL_DELETED',
                        usage_disabled=1
                    WHERE invoice_id=?
                    """,
                    (invoice_id,),
                )
                conn.commit()
                conn.close()

            continue

        current_bytes = int(traffic.get("total", 0) or 0)

        # First run: set baseline only.
        if last_bytes == 0:
            conn = get_db()
            conn.execute(
                """
                UPDATE invoices
                SET usage_last_bytes=?,
                    usage_total_bytes=?
                WHERE invoice_id=?
                """,
                (current_bytes, current_bytes, invoice_id),
            )
            conn.commit()
            conn.close()
            continue

        # Panel reset protection.
        if current_bytes < last_bytes:
            conn = get_db()
            conn.execute(
                """
                UPDATE invoices
                SET usage_last_bytes=?,
                    usage_total_bytes=?
                WHERE invoice_id=?
                """,
                (current_bytes, current_bytes, invoice_id),
            )
            conn.commit()
            conn.close()
            continue

        delta_bytes = current_bytes - last_bytes
        if delta_bytes <= 0:
            continue

        real_charge, balance_before, balance_after, should_disable = charge_usage(
            user_id,
            delta_bytes,
        )

        conn = get_db()
        conn.execute(
            """
            UPDATE invoices
            SET usage_last_bytes=?,
                usage_total_bytes=?,
                usage_charged_amount = usage_charged_amount + ?,
                usage_disabled=?
            WHERE invoice_id=?
            """,
            (
                current_bytes,
                current_bytes,
                real_charge,
                1 if should_disable else 0,
                invoice_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO usage_logs(
                invoice_id,
                user_id,
                client_email,
                old_bytes,
                new_bytes,
                delta_bytes,
                charged_amount,
                balance_before,
                balance_after
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                invoice_id,
                user_id,
                client_email,
                last_bytes,
                current_bytes,
                delta_bytes,
                real_charge,
                balance_before,
                balance_after,
            ),
        )

        if (
            balance_after <= low_balance_threshold
            and balance_after > 0
            and low_warned == 0
        ):
            conn.execute(
                """
                UPDATE invoices
                SET usage_low_balance_warned=1
                WHERE invoice_id=?
                """,
                (invoice_id,),
            )

            try:
                await application.bot.send_message(
                    user_id,
                    "⚠️ هشدار کمبود موجودی\n\n"
                    f"موجودی سرویس مصرفی شما کم شده است.\n\n"
                    f"💰 موجودی فعلی: `{balance_after:.2f}$`\n\n"
                    "برای جلوگیری از قطع سرویس، کیف پول خود را شارژ کنید.",
                    parse_mode="Markdown",
                )
            except Exception as e:
                print("LOW BALANCE MESSAGE ERROR:", e)

        conn.commit()
        conn.close()

        if should_disable:
            ok_disable, disable_msg = xui.disable_client(client_email)

            if ok_disable:
                try:
                    await application.bot.send_message(
                        user_id,
                        "🚫 سرویس مصرفی شما غیرفعال شد\n\n"
                        "موجودی کیف پول شما تمام شده است.\n\n"
                        f"🧾 شماره سرویس: `{invoice_id}`\n\n"
                        "برای فعال‌سازی مجدد، کیف پول خود را شارژ کنید و به پشتیبانی پیام دهید.",
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    print("DISABLE MESSAGE ERROR:", e)
            else:
                print("DISABLE CLIENT ERROR:", disable_msg)


async def process_trial_expiration(application):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, user_id, invoice_id, client_email, trial_minutes, trial_gb, bonus_expires_at
        FROM trial_services
        WHERE status='TRIAL_ACTIVE'
        AND expires_at IS NOT NULL
        AND datetime(expires_at) <= datetime('now')
        """
    ).fetchall()
    conn.close()

    if not rows:
        return

    xui = XUIManager()

    for row in rows:
        trial_id = row["id"]
        user_id = row["user_id"]
        invoice_id = row["invoice_id"]
        client_email = row["client_email"]

        ok_disable, disable_msg = xui.disable_client(client_email)
        if not ok_disable:
            print("TRIAL DISABLE ERROR:", invoice_id, disable_msg)

        conn = get_db()

        user_row = conn.execute(
            """
            SELECT balance
            FROM users
            WHERE user_id=?
            """,
            (user_id,),
        ).fetchone()

        balance = float(user_row["balance"] or 0) if user_row else 0

        conn.execute(
            """
            UPDATE trial_services
            SET status='TRIAL_EXPIRED'
            WHERE id=?
            """,
            (trial_id,),
        )

        conn.commit()
        conn.close()

        min_balance = get_float_setting("usage_min_balance", 1.00)
        bonus_amount = get_float_setting("trial_wallet_bonus", 0.10)
        bonus_window = int(get_float_setting("trial_bonus_window_minutes", 30))

        if balance >= min_balance:
            msg = (
                "⏳ تست رایگان شما تمام شد\n\n"
                "اگر اتصال و سرعت برایتان مناسب بود، می‌توانید سرویس اصلی خود را فعال کنید.\n\n"
                f"💰 موجودی فعلی کیف پول شما:\n"
                f"`{balance:.2f}$`\n\n"
                f"🎁 اگر تا {bonus_window} دقیقه آینده سرویس فعال کنید، "
                f"`{bonus_amount:.2f}$` اعتبار رایگان به کیف پول شما اضافه می‌شود.\n\n"
                "برای ادامه یکی از گزینه‌های زیر را انتخاب کنید."
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ فعال‌سازی سرویس مصرف واقعی", callback_data="shop_usage")],
                [InlineKeyboardButton("📦 خرید بسته حجمی", callback_data="shop_fixed")],
                [InlineKeyboardButton("💳 کیف پول", callback_data="balance")],
            ])

        else:
            msg = (
                "⏳ تست رایگان شما تمام شد\n\n"
                "اگر اتصال و سرعت برایتان مناسب بود، کیف پول خود را شارژ کنید و سرویس را فعال کنید.\n\n"
                f"💰 موجودی فعلی کیف پول شما:\n"
                f"`{balance:.2f}$`\n\n"
                f"🎁 اگر تا {bonus_window} دقیقه آینده کیف پول خود را شارژ یا سرویس فعال کنید، "
                f"`{bonus_amount:.2f}$` اعتبار رایگان دریافت می‌کنید.\n\n"
                "برای ادامه یکی از گزینه‌های زیر را انتخاب کنید."
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 شارژ کیف پول", callback_data="deposit")],
                [InlineKeyboardButton("⚡ سرویس مصرف واقعی", callback_data="shop_usage")],
                [InlineKeyboardButton("📦 بسته حجمی", callback_data="shop_fixed")],
            ])

        try:
            await application.bot.send_message(
                user_id,
                msg,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception as e:
            print("TRIAL EXPIRED MESSAGE ERROR:", e)

async def usage_monitor_loop(application):
    await asyncio.sleep(20)

    while True:
        try:
            await process_usage_billing(application)
        except Exception as e:
            print("USAGE MONITOR LOOP ERROR:", e)

        try:
            await process_trial_expiration(application)
        except Exception as e:
            print("TRIAL MONITOR LOOP ERROR:", e)

        interval = int(get_float_setting("usage_check_interval_seconds", 300))
        if interval < 60:
            interval = 60

        await asyncio.sleep(interval)


async def post_init(application):
    asyncio.create_task(usage_monitor_loop(application))
