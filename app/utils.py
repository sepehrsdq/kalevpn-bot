import random
import string

from app.database import get_db


def get_setting(key, default=None):
    conn = get_db()

    row = conn.execute(
        """
        SELECT value
        FROM settings
        WHERE key=?
        """,
        (key,),
    ).fetchone()

    conn.close()

    if row:
        return row["value"]

    return default


def set_setting(key, value):
    conn = get_db()

    conn.execute(
        """
        INSERT INTO settings(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (key, str(value)),
    )

    conn.commit()
    conn.close()


def get_float_setting(key, default=0):
    try:
        return float(get_setting(key, default))
    except Exception:
        return float(default)


def get_int_setting(key, default=0):
    try:
        return int(float(get_setting(key, default)))
    except Exception:
        return int(default)


def get_panel_setting(key, env_value=None):
    value = get_setting(key, None)

    if value is not None and str(value).strip() != "":
        return str(value).strip()

    if env_value is not None:
        return str(env_value).strip()

    return ""


def get_panel_url():
    from app.config import PANEL_URL

    return get_panel_setting("panel_url", PANEL_URL).rstrip("/")


def get_panel_username():
    from app.config import PANEL_USERNAME

    return get_panel_setting("panel_username", PANEL_USERNAME)


def get_panel_password():
    from app.config import PANEL_PASSWORD

    return get_panel_setting("panel_password", PANEL_PASSWORD)


def get_panel_inbound_id():
    from app.config import PANEL_INBOUND_ID

    return get_panel_setting("panel_inbound_id", PANEL_INBOUND_ID or "1")


def get_panel_sub_base_url():
    value = get_setting("panel_sub_base_url", "")

    if value and str(value).strip():
        return str(value).strip().rstrip("/")

    return get_panel_url().rstrip("/")


def get_panel_remark_prefix():
    value = get_setting("panel_remark_prefix", "KaleVPN")

    return str(value or "KaleVPN").strip()


def mask_secret(value):
    if not value:
        return "تنظیم نشده"

    value = str(value)

    if len(value) <= 4:
        return "****"

    return value[:2] + "****" + value[-2:]


def is_admin(user_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT user_id
        FROM admins
        WHERE user_id=?
        """,
        (user_id,),
    ).fetchone()

    conn.close()

    return row is not None


def get_all_admins():
    conn = get_db()

    rows = conn.execute(
        """
        SELECT user_id
        FROM admins
        """
    ).fetchall()

    conn.close()

    return [row["user_id"] for row in rows]


def generate_invoice_id(length=8):
    chars = string.ascii_uppercase + string.digits
    conn = get_db()

    while True:
        invoice = "".join(
            random.choice(chars)
            for _ in range(length)
        )

        exists = conn.execute(
            """
            SELECT invoice_id
            FROM invoices
            WHERE invoice_id=?
            """,
            (invoice,),
        ).fetchone()

        if not exists:
            conn.close()
            return invoice


def generate_deposit_id(network, length=6):
    chars = string.ascii_uppercase + string.digits
    conn = get_db()

    while True:
        random_part = "".join(
            random.choice(chars)
            for _ in range(length)
        )

        deposit_id = f"{network}_{random_part}"

        exists = conn.execute(
            """
            SELECT deposit_id
            FROM deposits
            WHERE deposit_id=?
            """,
            (deposit_id,),
        ).fetchone()

        if not exists:
            conn.close()
            return deposit_id


def calculate_fixed_price(gb, days):
    price_per_gb = get_float_setting(
        "fixed_price_per_gb",
        0.90,
    )

    if days == 30:
        multiplier = get_float_setting(
            "fixed_price_30_day_multiplier",
            1.00,
        )

    elif days == 7:
        multiplier = get_float_setting(
            "fixed_price_7_day_multiplier",
            0.45,
        )

    else:
        multiplier = get_float_setting(
            "fixed_price_1_day_multiplier",
            0.20,
        )

    return round(float(gb) * price_per_gb * multiplier, 2)


def bytes_to_gb(value):
    try:
        return float(value) / 1024 / 1024 / 1024
    except Exception:
        return 0


def format_usage(value):
    gb = bytes_to_gb(value)

    if gb >= 1:
        return f"{gb:.2f}GB"

    mb = float(value) / 1024 / 1024

    return f"{mb:.2f}MB"


def generate_client_email(user_id, invoice_id, service_type):
    prefix = get_panel_remark_prefix()

    return f"{prefix}-{service_type}-{user_id}-{invoice_id}"
