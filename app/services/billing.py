from app.database import get_db
from app.utils import bytes_to_gb, get_float_setting


def calculate_usage_charge(delta_bytes):
    usage_price = get_float_setting("usage_price_per_gb", 0.20)
    delta_gb = bytes_to_gb(delta_bytes)
    return round(delta_gb * usage_price, 6)


def charge_usage(user_id, delta_bytes):
    charge_amount = calculate_usage_charge(delta_bytes)

    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            "SELECT balance FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()

        if not row:
            conn.rollback()
            return 0, 0, 0, True

        balance_before = float(row["balance"] or 0)

        if balance_before <= 0:
            balance_after = 0
            real_charge = 0
            should_disable = True

        elif charge_amount >= balance_before:
            real_charge = balance_before
            balance_after = 0
            should_disable = True

        else:
            real_charge = charge_amount
            balance_after = round(balance_before - real_charge, 6)
            should_disable = False

        conn.execute(
            "UPDATE users SET balance=? WHERE user_id=?",
            (balance_after, user_id),
        )

        conn.commit()
        return real_charge, balance_before, balance_after, should_disable

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
