#!/bin/bash

PROJECT_DIR="/root/kale_vpn_bot"
DB_PATH="$PROJECT_DIR/data/bot_database.db"
BACKUP_DIR="$PROJECT_DIR/backups"

mkdir -p "$BACKUP_DIR"

sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/bot_database_$(date +%Y-%m-%d_%H-%M-%S).db'"

find "$BACKUP_DIR" -type f -name "*.db" -mtime +14 -delete
