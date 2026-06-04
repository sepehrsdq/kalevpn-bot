# KaleVPN Telegram Bot

KaleVPN Bot is a Telegram bot for selling and managing VPN services through a Sanaei / 3x-ui panel.

## Features

- User registration through Telegram
- Force join channel check
- Wallet system
- Manual crypto deposit approval by admin
- Fixed-volume service purchase
- Usage-based service purchase
- Automatic client creation in Sanaei / 3x-ui
- Subscription link delivery
- Direct VLESS config delivery
- Usage monitoring
- Automatic wallet deduction for usage-based service
- Low balance warning
- Auto-disable client when wallet balance reaches zero
- Referral reward system
- Admin panel
- Dynamic pricing
- Dynamic panel settings
- Free test management
- User ban / unban
- Broadcast message
- SQLite database

---

## Project Structure

```text
kale_vpn_bot/
│
├── main.py
├── requirements.txt
├── .env
├── .env.example
├── README.md
│
├── app/
│   ├── config.py
│   ├── database.py
│   ├── keyboards.py
│   ├── utils.py
│   │
│   ├── handlers/
│   │   ├── start.py
│   │   ├── menu.py
│   │   └── messages.py
│   │
│   ├── services/
│   │   ├── xui.py
│   │   ├── billing.py
│   │   ├── referrals.py
│   │   └── sync.py
│   │
│   └── jobs/
│       └── usage_monitor.py
│
├── data/
│   └── bot_database.db
│
├── backups/
│
└── logs/
````

---

## Important Security Notes

Never push these files to Git:

```text
.env
data/bot_database.db
backups/
logs/
venv/
```

The `.env` file contains private tokens and passwords.

The database contains users, balances, invoices, deposits, and service records.

Use `.env.example` for sample configuration only.

---

## Required Server Packages

For Ubuntu / Debian:

```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git nano sqlite3 unzip
```

---

## Fresh Installation on a New VPS

### 1. Clone the project

```bash
cd /root
git clone https://github.com/YOUR_USERNAME/kale_vpn_bot.git
cd /root/kale_vpn_bot
```

If the project already exists:

```bash
cd /root/kale_vpn_bot
git pull origin main
```

---

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install requirements

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 4. Create `.env`

```bash
cp .env.example .env
nano .env
```

Example:

```env
TOKEN=YOUR_TELEGRAM_BOT_TOKEN
ADMIN_ID=123456789
FORCE_CHANNEL=@your_channel

TON_WALLET=
TRON_WALLET=
BSC_WALLET=
LTC_WALLET=
SUPPORT_BOT=https://t.me/your_support_bot

PANEL_URL=https://panel.example.com:35816/path
PANEL_USERNAME=admin
PANEL_PASSWORD=password
PANEL_INBOUND_ID=1

DB_PATH=/root/kale_vpn_bot/data/bot_database.db
```

Important:

`PANEL_URL` must be the panel login/API address.

Subscription base URL should be set later from the bot admin panel:

```text
Admin Panel → Sanaei Panel Settings → Change Subscription URL
```

Example subscription URL:

```text
https://panel.example.com:2096/sub-path
```

---

### 5. Create database

```bash
source venv/bin/activate
python -c "from app.database import init_db; init_db(); print('DB OK')"
```

Check tables:

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db ".tables"
```

Check admin:

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db "SELECT * FROM admins;"
```

---

### 6. Run manually for test

```bash
source venv/bin/activate
python main.py
```

If the bot starts correctly, stop it with:

```text
Ctrl + C
```

---

## Run Bot Permanently with systemd

### 1. Create service file

```bash
nano /etc/systemd/system/kalevpn.service
```

Put this content:

```ini
[Unit]
Description=KaleVPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/kale_vpn_bot
Environment="PATH=/root/kale_vpn_bot/venv/bin"
ExecStart=/root/kale_vpn_bot/venv/bin/python /root/kale_vpn_bot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Save:

```text
Ctrl + O
Enter
Ctrl + X
```

---

### 2. Enable and start service

```bash
systemctl daemon-reload
systemctl enable kalevpn.service
systemctl start kalevpn.service
```

---

### 3. Check status

```bash
systemctl status kalevpn.service
```

---

### 4. Watch live logs

```bash
journalctl -u kalevpn.service -f
```

---

### 5. Restart bot

```bash
systemctl restart kalevpn.service
```

---

### 6. Stop bot

```bash
systemctl stop kalevpn.service
```

---

## Updating the Bot from Git

```bash
cd /root/kale_vpn_bot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python -m py_compile main.py app/handlers/*.py app/services/*.py app/jobs/*.py
systemctl restart kalevpn.service
journalctl -u kalevpn.service -f
```

---

## Database Backup

The database path is:

```text
/root/kale_vpn_bot/data/bot_database.db
```

### Manual backup

```bash
cd /root/kale_vpn_bot
mkdir -p backups
cp data/bot_database.db backups/bot_database_$(date +%Y-%m-%d_%H-%M-%S).db
```

Check backups:

```bash
ls -lh backups
```

---

## Safer SQLite Backup

This method is better if the bot is running:

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db ".backup '/root/kale_vpn_bot/backups/bot_database_$(date +%Y-%m-%d_%H-%M-%S).db'"
```

---

## Automatic Daily Backup

Create script:

```bash
nano /root/kale_vpn_bot/backup_db.sh
```

Put this content:

```bash
#!/bin/bash

PROJECT_DIR="/root/kale_vpn_bot"
DB_PATH="$PROJECT_DIR/data/bot_database.db"
BACKUP_DIR="$PROJECT_DIR/backups"

mkdir -p "$BACKUP_DIR"

sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/bot_database_$(date +%Y-%m-%d_%H-%M-%S).db'"

find "$BACKUP_DIR" -type f -name "*.db" -mtime +14 -delete
```

Make executable:

```bash
chmod +x /root/kale_vpn_bot/backup_db.sh
```

Open cron:

```bash
crontab -e
```

Add this line for daily backup at 04:00:

```cron
0 4 * * * /root/kale_vpn_bot/backup_db.sh >> /root/kale_vpn_bot/logs/backup.log 2>&1
```

Check cron list:

```bash
crontab -l
```

---

## Restore Database from Backup

### 1. Stop bot

```bash
systemctl stop kalevpn.service
```

### 2. Backup current database before restore

```bash
cd /root/kale_vpn_bot
cp data/bot_database.db data/bot_database_before_restore_$(date +%Y-%m-%d_%H-%M-%S).db
```

### 3. Restore selected backup

Example:

```bash
cp backups/bot_database_2026-06-04_04-00-00.db data/bot_database.db
```

### 4. Start bot

```bash
systemctl start kalevpn.service
```

### 5. Check logs

```bash
journalctl -u kalevpn.service -f
```

---

## Moving to Another Server

### On old server

Create backup:

```bash
cd /root/kale_vpn_bot
sqlite3 data/bot_database.db ".backup 'backups/bot_database_transfer.db'"
```

Create archive without private `.env` if you only want code:

```bash
cd /root
tar --exclude='kale_vpn_bot/venv' \
    --exclude='kale_vpn_bot/.env' \
    --exclude='kale_vpn_bot/logs' \
    -czvf kale_vpn_bot_code.tar.gz kale_vpn_bot
```

Create archive with database backup:

```bash
cd /root
tar --exclude='kale_vpn_bot/venv' \
    --exclude='kale_vpn_bot/logs' \
    -czvf kale_vpn_bot_full_with_db.tar.gz kale_vpn_bot
```

Download from old server:

```bash
scp root@OLD_SERVER_IP:/root/kale_vpn_bot_full_with_db.tar.gz .
```

Upload to new server:

```bash
scp kale_vpn_bot_full_with_db.tar.gz root@NEW_SERVER_IP:/root/
```

### On new server

```bash
cd /root
tar -xzvf kale_vpn_bot_full_with_db.tar.gz
cd /root/kale_vpn_bot
```

Install requirements:

```bash
apt update
apt install -y python3 python3-venv python3-pip sqlite3 nano git
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Check `.env`:

```bash
nano .env
```

Check database:

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db ".tables"
```

Create systemd service again:

```bash
nano /etc/systemd/system/kalevpn.service
```

Use:

```ini
[Unit]
Description=KaleVPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/kale_vpn_bot
Environment="PATH=/root/kale_vpn_bot/venv/bin"
ExecStart=/root/kale_vpn_bot/venv/bin/python /root/kale_vpn_bot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Start:

```bash
systemctl daemon-reload
systemctl enable kalevpn.service
systemctl start kalevpn.service
systemctl status kalevpn.service
```

---

## Git Setup

### First time push to Git

Create `.gitignore`:

```bash
nano .gitignore
```

Content:

```gitignore
venv/
__pycache__/
*.pyc

.env

data/bot_database.db
data/*.db
backups/
logs/

*.zip
*.tar.gz
```

Initialize git:

```bash
cd /root/kale_vpn_bot
git init
git add .
git commit -m "Initial production version"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/kale_vpn_bot.git
git push -u origin main
```

---

## Important After First Run

From Telegram admin panel, set:

```text
Admin Panel
→ Sanaei Panel Settings
→ Test Panel Connection
→ Change Subscription URL
```

Then test:

```text
Buy fixed service
Buy usage-based service
My Services
Wallet deposit
Usage monitor
Referral
Free test
```

---

## Common Commands

Restart bot:

```bash
systemctl restart kalevpn.service
```

Show logs:

```bash
journalctl -u kalevpn.service -f
```

Check database:

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db ".tables"
```

Check users:

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db "SELECT user_id, username, balance FROM users;"
```

Check invoices:

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db "SELECT invoice_id, user_id, service_type, status, amount FROM invoices;"
```

Check deposits:

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db "SELECT deposit_id, user_id, amount, network, status FROM deposits;"
```

---

## Troubleshooting

If the bot does not start:

```bash
journalctl -u kalevpn.service -n 100 --no-pager
```

If database is missing:

```bash
python -c "from app.database import init_db; init_db(); print('DB OK')"
```

If imports fail:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

If Telegram bot does not respond:

```bash
systemctl restart kalevpn.service
journalctl -u kalevpn.service -f
```

If panel connection fails:

* Check `PANEL_URL`
* Check `PANEL_USERNAME`
* Check `PANEL_PASSWORD`
* Check `PANEL_INBOUND_ID`
* Check firewall
* Check that panel API path is correct

If subscription link is wrong:

Set it from bot admin panel:

```text
Admin Panel → Sanaei Panel Settings → Change Subscription URL
```

````
برای دیدن اطلاعات دیتابیس روی VPS، اول برو داخل پروژه:

```bash
cd /root/kale_vpn_bot
```

## 1. باز کردن دیتابیس

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db
```

بعد وارد محیط SQLite می‌شی. این دستورها را می‌تونی بزنی:

```sql
.tables
```

نمایش ساختار جدول‌ها:

```sql
.schema users
.schema invoices
.schema deposits
```

خروج:

```sql
.exit
```

---

## 2. دیدن جدول کاربران

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db "SELECT user_id, username, balance, referrer_id, is_banned FROM users;"
```

---

## 3. دیدن خریدها / سرویس‌ها

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db "SELECT invoice_id, user_id, service_type, plan, amount, status, delivered, client_email, sub_id, created_at FROM invoices ORDER BY created_at DESC;"
```

---

## 4. دیدن شارژها

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db "SELECT deposit_id, user_id, amount, network, status, tx_hash, created_at FROM deposits ORDER BY created_at DESC;"
```

---

## 5. دیدن تنظیمات بات

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db "SELECT key, value FROM settings;"
```

برای اینکه پسورد پنل را در خروجی نبینی، این بهتره:

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db "SELECT key, CASE WHEN key='panel_password' THEN '***HIDDEN***' ELSE value END AS value FROM settings;"
```

---

## 6. دیدن لاگ مصرف سرویس مصرفی

```bash
sqlite3 /root/kale_vpn_bot/data/bot_database.db "SELECT invoice_id, user_id, client_email, delta_bytes, charged_amount, balance_before, balance_after, created_at FROM usage_logs ORDER BY created_at DESC;"
```

---

## 7. خروجی مرتب‌تر با ستون‌بندی

برای حالت خواناتر:

```bash
sqlite3 -header -column /root/kale_vpn_bot/data/bot_database.db "SELECT user_id, username, balance, is_banned FROM users;"
```

مثلاً خریدها:

```bash
sqlite3 -header -column /root/kale_vpn_bot/data/bot_database.db "SELECT invoice_id, user_id, service_type, amount, status, created_at FROM invoices ORDER BY created_at DESC;"
```

---

## 8. بکاپ سریع قبل از دستکاری

قبل از هر تغییر دستی در دیتابیس، این را بزن:

```bash
cd /root/kale_vpn_bot
sqlite3 data/bot_database.db ".backup 'backups/bot_database_manual_$(date +%Y-%m-%d_%H-%M-%S).db'"
```

بعد اگر خواستی یک کاربر خاص را ببینی:

```bash
sqlite3 -header -column /root/kale_vpn_bot/data/bot_database.db "SELECT * FROM users WHERE user_id=USER_ID;"
```

به جای `USER_ID` آیدی عددی کاربر را بگذار.


