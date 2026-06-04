import asyncio

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


async def usage_monitor_loop(application):
    await asyncio.sleep(20)

    while True:
        try:
            await process_usage_billing(application)
        except Exception as e:
            print("USAGE MONITOR LOOP ERROR:", e)

        interval = int(get_float_setting("usage_check_interval_seconds", 300))
        if interval < 60:
            interval = 60

        await asyncio.sleep(interval)


async def post_init(application):
    asyncio.create_task(usage_monitor_loop(application))
