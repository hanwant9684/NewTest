#!/usr/bin/env python3
"""
GitHub Backup Integration for SQLite Database
Automatically backs up database to GitHub repository
"""

import os
from datetime import datetime
from backup_database import backup_database, restore_database
from logger import LOGGER
import threading

DB_PATH = os.getenv("DATABASE_PATH", "telegram_bot.db")

# Concurrency control for backup operations
_backup_lock = threading.Lock()
_backup_in_progress = False

def cleanup_old_github_backups(token, repo, keep_count=2):
    """Delete old backups from GitHub, keeping only the newest ones"""
    try:
        import urllib.request
        import json
        
        list_url = f"https://api.github.com/repos/{repo}/contents/backups"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        req = urllib.request.Request(list_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            backups = json.loads(response.read().decode())
        
        if not backups or len(backups) <= keep_count:
            return
        
        sorted_backups = sorted(backups, key=lambda x: x['name'], reverse=True)
        backups_to_delete = sorted_backups[keep_count:]
        
        for backup in backups_to_delete:
            try:
                delete_url = f"https://api.github.com/repos/{repo}/contents/{backup['path']}"
                
                req = urllib.request.Request(delete_url, headers=headers)
                with urllib.request.urlopen(req) as resp:
                    file_data = json.loads(resp.read().decode())
                
                data = {
                    "message": f"Cleanup: Remove old backup {backup['name']}",
                    "sha": file_data['sha']
                }
                
                req = urllib.request.Request(
                    delete_url,
                    data=json.dumps(data).encode(),
                    headers=headers,
                    method='DELETE'
                )
                
                with urllib.request.urlopen(req) as response:
                    if response.status == 200:
                        LOGGER(__name__).info(f"🗑️ Deleted old backup: {backup['name']}")
            except Exception as e:
                LOGGER(__name__).warning(f"Failed to delete {backup['name']}: {e}")
    
    except Exception as e:
        LOGGER(__name__).warning(f"Cleanup failed: {e}")

def backup_to_github():
    """Upload database backup to GitHub repository"""
    try:
        import base64
        import urllib.request
        import json
        
        token = os.getenv("GITHUB_TOKEN")
        repo = os.getenv("GITHUB_BACKUP_REPO")
        
        if not token or not repo:
            LOGGER(__name__).error("GITHUB_TOKEN or GITHUB_BACKUP_REPO not set")
            return False
        
        local_backup = backup_database()
        if not local_backup:
            return False
        
        with open(local_backup, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"backups/backup_{timestamp}.db"
        
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
        
        data = {
            "message": f"Automated backup - {timestamp}",
            "content": content
        }
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method='PUT')
        
        with urllib.request.urlopen(req) as response:
            if response.status == 201:
                LOGGER(__name__).info(f"✅ Uploaded to GitHub: {file_path}")
                
                cleanup_old_github_backups(token, repo, keep_count=2)
                
                return True
            else:
                LOGGER(__name__).error(f"GitHub upload failed: {response.status}")
                return False
                
    except Exception as e:
        LOGGER(__name__).error(f"❌ GitHub backup failed: {e}")
        return False

def trigger_backup_on_session(user_id):
    """Trigger backup when new user session is created (non-blocking, thread-safe)"""
    global _backup_in_progress
    
    backup_service = os.getenv("CLOUD_BACKUP_SERVICE", "").lower()
    if backup_service != "github":
        return False
    
    with _backup_lock:
        if _backup_in_progress:
            LOGGER(__name__).debug(f"Backup already in progress, skipping trigger for user {user_id}")
            return False
        
        _backup_in_progress = True
    
    def _backup_worker():
        global _backup_in_progress
        try:
            LOGGER(__name__).info(f"🔐 New session created for user {user_id}, triggering backup...")
            backup_to_github()
        except Exception as e:
            LOGGER(__name__).error(f"Session backup failed: {e}")
        finally:
            with _backup_lock:
                _backup_in_progress = False
    
    thread = threading.Thread(target=_backup_worker, daemon=True, name=f"SessionBackup-{user_id}")
    thread.start()
    return True

def trigger_backup_on_critical_change(operation_name, user_id=None):
    """
    Trigger backup when critical database changes occur (non-blocking, thread-safe)
    
    Critical operations that trigger backup:
    - add_ad_downloads: User earns ad download credits
    - set_premium: User gets premium subscription
    - set_user_type: User type changes
    - ban_user/unban_user: User ban status changes
    - increment_usage: User downloads files
    
    This prevents data loss on Render/VPS restarts!
    """
    global _backup_in_progress
    
    backup_service = os.getenv("CLOUD_BACKUP_SERVICE", "").lower()
    if backup_service != "github":
        return False
    
    with _backup_lock:
        if _backup_in_progress:
            LOGGER(__name__).debug(f"Backup already in progress, skipping trigger for {operation_name}")
            return False
        
        _backup_in_progress = True
    
    def _backup_worker():
        global _backup_in_progress
        try:
            user_info = f" (user {user_id})" if user_id else ""
            LOGGER(__name__).info(f"💾 Critical change detected: {operation_name}{user_info}, triggering backup...")
            backup_to_github()
        except Exception as e:
            LOGGER(__name__).error(f"Critical change backup failed: {e}")
        finally:
            with _backup_lock:
                _backup_in_progress = False
    
    thread = threading.Thread(target=_backup_worker, daemon=True, name=f"CriticalBackup-{operation_name}")
    thread.start()
    return True

def restore_from_github(backup_name=None):
    """
    Download and restore database from GitHub
    
    IMPORTANT: When deployed to Render or any service restart:
    - This function ALWAYS downloads the NEWEST backup file
    - Backups are sorted by filename (timestamp) in descending order
    - The latest backup is automatically selected
    - This ensures user data is preserved across service restarts
    """
    try:
        import base64
        import urllib.request
        import json
        
        token = os.getenv("GITHUB_TOKEN")
        repo = os.getenv("GITHUB_BACKUP_REPO")
        
        if not token or not repo:
            LOGGER(__name__).error("GITHUB_TOKEN or GITHUB_BACKUP_REPO not set")
            return False
        
        if not backup_name:
            list_url = f"https://api.github.com/repos/{repo}/contents/backups"
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            req = urllib.request.Request(list_url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                backups = json.loads(response.read().decode())
            
            if not backups:
                LOGGER(__name__).warning("No backups found in GitHub")
                return False
            
            # CRITICAL: Sort by name (contains timestamp) and get the NEWEST (first) backup
            latest = sorted(backups, key=lambda x: x['name'], reverse=True)[0]
            backup_name = latest['name']
            download_url = latest['download_url']
        else:
            download_url = f"https://raw.githubusercontent.com/{repo}/main/backups/{backup_name}"
        
        req = urllib.request.Request(download_url)
        
        with urllib.request.urlopen(req) as response:
            backup_content = response.read()
        
        temp_path = "temp_restore.db"
        with open(temp_path, "wb") as f:
            f.write(backup_content)
        
        success = restore_database(temp_path)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if success:
            LOGGER(__name__).info(f"✅ Restored from GitHub: {backup_name}")
        
        return success
    except Exception as e:
        LOGGER(__name__).error(f"❌ GitHub restore failed: {e}")
        return False

async def periodic_cloud_backup(interval_minutes=10):
    """Run periodic GitHub backups in the background"""
    import asyncio
    
    backup_service = os.getenv("CLOUD_BACKUP_SERVICE", "").lower()
    
    if backup_service != "github":
        LOGGER(__name__).debug("GitHub backup not enabled")
        return
    
    LOGGER(__name__).info(f"Starting periodic GitHub backups every {interval_minutes} minutes")
    
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            backup_to_github()
        except Exception as e:
            LOGGER(__name__).error(f"Error in periodic GitHub backup: {e}")
            await asyncio.sleep(600)

async def restore_latest_from_cloud():
    """Restore latest backup from GitHub"""
    # Import config to get cloud backup settings
    try:
        from config import PyroConf
        backup_service = PyroConf.CLOUD_BACKUP_SERVICE
    except:
        backup_service = os.getenv("CLOUD_BACKUP_SERVICE", "").lower()
    
    if not backup_service or backup_service != "github":
        LOGGER(__name__).debug(f"GitHub backup not configured (service: {backup_service})")
        return False
    
    LOGGER(__name__).info("Attempting to restore from GitHub...")
    return restore_from_github()

if __name__ == "__main__":
    print("=" * 60)
    print("GitHub Backup Utility")
    print("=" * 60)
    print("\n1. Backup to GitHub")
    print("2. Restore from GitHub")
    
    choice = input("\nEnter choice (1-2): ").strip()
    
    if choice == "1":
        backup_to_github()
    elif choice == "2":
        import asyncio
        asyncio.run(restore_latest_from_cloud())
