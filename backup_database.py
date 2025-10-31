#!/usr/bin/env python3
"""
Automatic SQLite Database Backup Script
Backs up telegram_bot.db to prevent data loss during deployments
"""

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
import asyncio
from logger import LOGGER

BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
DB_PATH = os.getenv("DATABASE_PATH", "telegram_bot.db")
MAX_LOCAL_BACKUPS = int(os.getenv("MAX_BACKUPS", "2"))

def create_backup_dir():
    """Create backup directory if it doesn't exist"""
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    LOGGER(__name__).info(f"Backup directory: {BACKUP_DIR}")

def backup_database():
    """Create a backup of the SQLite database"""
    if not os.path.exists(DB_PATH):
        LOGGER(__name__).warning(f"Database file not found: {DB_PATH}")
        return None
    
    create_backup_dir()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"telegram_bot_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        backup_conn = sqlite3.connect(backup_path)
        
        with backup_conn:
            conn.backup(backup_conn)
        
        conn.close()
        backup_conn.close()
        
        file_size = os.path.getsize(backup_path) / 1024
        LOGGER(__name__).info(f"✅ Database backed up successfully: {backup_filename} ({file_size:.2f} KB)")
        
        cleanup_old_backups()
        
        return backup_path
    except Exception as e:
        LOGGER(__name__).error(f"❌ Backup failed: {e}")
        return None

def cleanup_old_backups():
    """Remove old backups to save space, keeping only the most recent ones"""
    try:
        backups = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.startswith("telegram_bot_backup_") and f.endswith(".db")],
            reverse=True
        )
        
        if len(backups) > MAX_LOCAL_BACKUPS:
            for old_backup in backups[MAX_LOCAL_BACKUPS:]:
                old_path = os.path.join(BACKUP_DIR, old_backup)
                os.remove(old_path)
                LOGGER(__name__).info(f"🗑️ Removed old backup: {old_backup}")
    except Exception as e:
        LOGGER(__name__).error(f"Error cleaning up old backups: {e}")

def restore_database(backup_path):
    """Restore database from a backup file"""
    if not os.path.exists(backup_path):
        LOGGER(__name__).error(f"Backup file not found: {backup_path}")
        return False
    
    try:
        if os.path.exists(DB_PATH):
            backup_current = f"{DB_PATH}.before_restore"
            shutil.copy2(DB_PATH, backup_current)
            LOGGER(__name__).info(f"Current database backed up to: {backup_current}")
        
        shutil.copy2(backup_path, DB_PATH)
        LOGGER(__name__).info(f"✅ Database restored from: {backup_path}")
        return True
    except Exception as e:
        LOGGER(__name__).error(f"❌ Restore failed: {e}")
        return False

def get_latest_backup():
    """Get the path to the most recent backup"""
    if not os.path.exists(BACKUP_DIR):
        return None
    
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("telegram_bot_backup_") and f.endswith(".db")],
        reverse=True
    )
    
    return os.path.join(BACKUP_DIR, backups[0]) if backups else None

async def periodic_backup(interval_hours=1):
    """Run periodic backups in the background"""
    while True:
        try:
            LOGGER(__name__).info(f"⏰ Starting scheduled local backup (interval: {interval_hours}h)")
            backup_database()
            await asyncio.sleep(interval_hours * 3600)
        except Exception as e:
            LOGGER(__name__).error(f"Error in periodic backup: {e}")
            await asyncio.sleep(3600)

def export_to_json(output_file="database_export.json"):
    """Export database to JSON for easy transfer (optional)"""
    try:
        import json
        
        if not os.path.exists(DB_PATH):
            LOGGER(__name__).error("Database not found")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        export_data = {}
        
        tables = ['users', 'admins', 'daily_usage', 'broadcasts', 'ad_sessions', 'ad_verifications']
        
        for table in tables:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            export_data[table] = [dict(row) for row in rows]
        
        conn.close()
        
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        file_size = os.path.getsize(output_file) / 1024
        LOGGER(__name__).info(f"✅ Database exported to JSON: {output_file} ({file_size:.2f} KB)")
        return True
    except Exception as e:
        LOGGER(__name__).error(f"❌ JSON export failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Database Backup Utility")
    print("=" * 60)
    print("\n1. Create backup")
    print("2. Restore from backup")
    print("3. Export to JSON")
    print("4. List backups")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        backup_database()
    elif choice == "2":
        latest = get_latest_backup()
        if latest:
            print(f"\nLatest backup: {latest}")
            confirm = input("Restore from this backup? (yes/no): ").lower()
            if confirm == "yes":
                restore_database(latest)
        else:
            print("No backups found!")
    elif choice == "3":
        export_to_json()
    elif choice == "4":
        create_backup_dir()
        backups = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.startswith("telegram_bot_backup_")],
            reverse=True
        )
        if backups:
            print("\nAvailable backups:")
            for i, backup in enumerate(backups, 1):
                path = os.path.join(BACKUP_DIR, backup)
                size = os.path.getsize(path) / 1024
                print(f"{i}. {backup} ({size:.2f} KB)")
        else:
            print("\nNo backups found!")
