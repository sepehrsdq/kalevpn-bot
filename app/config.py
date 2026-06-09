import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")

TON_WALLET = os.getenv("TON_WALLET", "")
TRON_WALLET = os.getenv("TRON_WALLET", "")
BSC_WALLET = os.getenv("BSC_WALLET", "")
LTC_WALLET = os.getenv("LTC_WALLET", "")

SUPPORT_BOT = os.getenv("SUPPORT_BOT", "")

PANEL_URL = os.getenv("PANEL_URL", "")
PANEL_USERNAME = os.getenv("PANEL_USERNAME", "")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "")
PANEL_INBOUND_ID = os.getenv("PANEL_INBOUND_ID", "1")

DB_PATH = os.getenv(
    "DB_PATH",
    "/root/kale_vpn_bot/data/bot_database.db"
)

APK_FILE_ID = "BQACAgEAAxkBAAIDkGn_F8ZlS8a0NxNeVfC7qGKHKZ7CAALACAACrQP4R8Nw28-XYSDQOwQ"


def validate_config():
    missing = []

    if not TOKEN:
        missing.append("TOKEN")

    if not ADMIN_ID:
        missing.append("ADMIN_ID")

    if not FORCE_CHANNEL:
        missing.append("FORCE_CHANNEL")

    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )

