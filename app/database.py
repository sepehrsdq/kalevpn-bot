import os
import sqlite3

from app.config import (
    DB_PATH,
    ADMIN_ID,
    PANEL_URL,
    PANEL_USERNAME,
    PANEL_PASSWORD,
    PANEL_INBOUND_ID,
)


def get_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row

    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0,
        referrer_id INTEGER,
        is_banned INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins(
        user_id INTEGER PRIMARY KEY
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices(
        invoice_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL DEFAULT 0,
        plan TEXT,
        delivered INTEGER DEFAULT 0,
        status TEXT DEFAULT 'PENDING_DELIVERY',
        service_type TEXT DEFAULT 'fixed',
        sub_link TEXT,
        vless_link TEXT,
        client_uuid TEXT,
        client_email TEXT,
        sub_id TEXT,
        warned INTEGER DEFAULT 0,
        usage_last_bytes INTEGER DEFAULT 0,
        usage_total_bytes INTEGER DEFAULT 0,
        usage_charged_amount REAL DEFAULT 0,
        usage_low_balance_warned INTEGER DEFAULT 0,
        usage_disabled INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deposits(
        deposit_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        tx_hash TEXT,
        network TEXT,
        status TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS free_test(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vless TEXT,
        max_users INTEGER DEFAULT 0,
        used_users INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS free_test_claims(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        test_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, test_id)
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trial_services(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        invoice_id TEXT,
        client_email TEXT,
        client_uuid TEXT,
        sub_id TEXT,
        sub_link TEXT,
        vless_link TEXT,
        status TEXT DEFAULT 'TRIAL_ACTIVE',
        trial_gb REAL DEFAULT 0.5,
        trial_minutes INTEGER DEFAULT 30,
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT,
        bonus_expires_at TEXT,
        bonus_claimed INTEGER DEFAULT 0,
        converted_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referral_rewards(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL,
        referred_user_id INTEGER NOT NULL,
        invoice_id TEXT,
        amount REAL NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(referrer_id, referred_user_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usage_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id TEXT,
        user_id INTEGER,
        client_email TEXT,
        old_bytes INTEGER,
        new_bytes INTEGER,
        delta_bytes INTEGER,
        charged_amount REAL,
        balance_before REAL,
        balance_after REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    default_settings = {
        "fixed_price_per_gb": "0.90",
        "fixed_price_1_day_multiplier": "0.20",
        "fixed_price_7_day_multiplier": "0.45",
        "fixed_price_30_day_multiplier": "1.00",

        "usage_price_per_gb": "0.20",
        "usage_min_balance": "1.00",
        "usage_check_interval_seconds": "300",
        "usage_low_balance_threshold": "0.25",

        "referral_reward": "0.25",

        "trial_enabled": "1",
        "trial_minutes": "30",
        "trial_gb": "0.5",
        "trial_wallet_bonus": "0.10",
        "trial_bonus_window_minutes": "30",
        "trial_max_per_user": "1",

        "panel_url": PANEL_URL or "",
        "panel_username": PANEL_USERNAME or "",
        "panel_password": PANEL_PASSWORD or "",
        "panel_inbound_id": PANEL_INBOUND_ID or "1",
        "panel_sub_base_url": "",
        "panel_remark_prefix": "KaleVPN",
    }

    for key, value in default_settings.items():
        cursor.execute(
            """
            INSERT OR IGNORE INTO settings(key, value)
            VALUES(?, ?)
            """,
            (key, value),
        )

    cursor.execute(
        """
        INSERT OR IGNORE INTO admins(user_id)
        VALUES(?)
        """,
        (ADMIN_ID,),
    )

    conn.commit()
    conn.close()
