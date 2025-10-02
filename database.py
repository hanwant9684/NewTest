# Copyright (C) @Wolfy004
# Channel: https://t.me/Wolfy004

import sqlite3
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from logger import LOGGER

class DatabaseManager:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    user_type TEXT DEFAULT 'free',
                    subscription_end DATE,
                    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_banned BOOLEAN DEFAULT FALSE,
                    session_string TEXT,
                    custom_thumbnail TEXT
                )
            ''')
            
            # Add custom_thumbnail column if it doesn't exist (for existing databases)
            try:
                cursor.execute('ALTER TABLE users ADD COLUMN custom_thumbnail TEXT')
            except:
                pass  # Column already exists

            # Daily usage tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    date DATE,
                    files_downloaded INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, date)
                )
            ''')

            # Admins table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    added_by INTEGER,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')

            # Broadcast history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT,
                    sent_by INTEGER,
                    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_users INTEGER,
                    successful_sends INTEGER,
                    FOREIGN KEY (sent_by) REFERENCES users(user_id)
                )
            ''')

            conn.commit()
            LOGGER(__name__).info("Database initialized successfully")

    def add_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None,
                 last_name: Optional[str] = None, user_type: str = 'free') -> bool:
        """Add new user or update basic profile information (preserves roles and settings)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # First try to insert new user
                cursor.execute('''
                    INSERT OR IGNORE INTO users
                    (user_id, username, first_name, last_name, user_type, last_activity)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, username, first_name, last_name, user_type, datetime.now()))

                # Then update only basic profile fields, preserving important data
                cursor.execute('''
                    UPDATE users SET
                        username = COALESCE(?, username),
                        first_name = COALESCE(?, first_name),
                        last_name = COALESCE(?, last_name),
                        last_activity = ?
                    WHERE user_id = ?
                ''', (username, first_name, last_name, datetime.now(), user_id))
                conn.commit()
                return True
        except Exception as e:
            LOGGER(__name__).error(f"Error adding user {user_id}: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            LOGGER(__name__).error(f"Error getting user {user_id}: {e}")
            return None

    def get_user_type(self, user_id: int) -> str:
        """Get user type (free, paid, admin)"""
        user = self.get_user(user_id)
        if not user:
            return 'free'

        # Check if admin
        if self.is_admin(user_id):
            return 'admin'

        # Check if paid subscription is active
        if user['user_type'] == 'paid' and user['subscription_end']:
            sub_end = datetime.strptime(user['subscription_end'], '%Y-%m-%d')
            if sub_end > datetime.now():
                return 'paid'

        return 'free'

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            LOGGER(__name__).error(f"Error checking admin status for {user_id}: {e}")
            return False

    def add_admin(self, user_id: int, added_by: int) -> bool:
        """Add user as admin"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO admins (user_id, added_by)
                    VALUES (?, ?)
                ''', (user_id, added_by))
                conn.commit()
                return True
        except Exception as e:
            LOGGER(__name__).error(f"Error adding admin {user_id}: {e}")
            return False

    def remove_admin(self, user_id: int) -> bool:
        """Remove admin privileges"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            LOGGER(__name__).error(f"Error removing admin {user_id}: {e}")
            return False

    def set_user_type(self, user_id: int, user_type: str, days: int = 30) -> bool:
        """Set user type and subscription"""
        try:
            subscription_end: Optional[str] = None
            if user_type == 'paid':
                subscription_end = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET user_type = ?, subscription_end = ?
                    WHERE user_id = ?
                ''', (user_type, subscription_end, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            LOGGER(__name__).error(f"Error setting user type for {user_id}: {e}")
            return False

    def get_daily_usage(self, user_id: int, date: Optional[str] = None) -> int:
        """Get daily file download count"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT files_downloaded FROM daily_usage
                    WHERE user_id = ? AND date = ?
                ''', (user_id, date))
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            LOGGER(__name__).error(f"Error getting daily usage for {user_id}: {e}")
            return 0

    def increment_usage(self, user_id: int, count: int = 1) -> bool:
        """Increment daily usage count"""
        date = datetime.now().strftime('%Y-%m-%d')
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_usage (user_id, date, files_downloaded)
                    VALUES (?, ?, COALESCE((SELECT files_downloaded FROM daily_usage
                                          WHERE user_id = ? AND date = ?), 0) + ?)
                ''', (user_id, date, user_id, date, count))
                conn.commit()
                return True
        except Exception as e:
            LOGGER(__name__).error(f"Error incrementing usage for {user_id}: {e}")
            return False

    def can_download(self, user_id: int) -> tuple[bool, str]:
        """Check if user can download (considering daily limits)"""
        user_type = self.get_user_type(user_id)

        # Admins and paid users have unlimited access
        if user_type in ['admin', 'paid']:
            return True, ""

        # Free users have daily limit
        daily_usage = self.get_daily_usage(user_id)
        if daily_usage >= 5:
            return False, "Daily limit reached (5 files). Upgrade to premium for unlimited downloads."

        return True, f"Downloads remaining today: {5 - daily_usage}"

    def get_all_users(self) -> List[int]:
        """Get all user IDs"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM users WHERE is_banned = FALSE')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            LOGGER(__name__).error(f"Error getting all users: {e}")
            return []

    def save_broadcast(self, message: str, sent_by: int, total_users: int, successful_sends: int) -> bool:
        """Save broadcast history"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO broadcasts (message, sent_by, total_users, successful_sends)
                    VALUES (?, ?, ?, ?)
                ''', (message, sent_by, total_users, successful_sends))
                conn.commit()
                return True
        except Exception as e:
            LOGGER(__name__).error(f"Error saving broadcast: {e}")
            return False

    def ban_user(self, user_id: int) -> bool:
        """Ban a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET is_banned = TRUE WHERE user_id = ?', (user_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            LOGGER(__name__).error(f"Error banning user {user_id}: {e}")
            return False

    def unban_user(self, user_id: int) -> bool:
        """Unban a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET is_banned = FALSE WHERE user_id = ?', (user_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            LOGGER(__name__).error(f"Error unbanning user {user_id}: {e}")
            return False

    def is_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        user = self.get_user(user_id)
        return bool(user and user.get('is_banned', False))

    def set_user_session(self, user_id: int, session_string: Optional[str] = None) -> bool:
        """Set user's session string for accessing restricted content (None to logout)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET session_string = ? WHERE user_id = ?
                ''', (session_string, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            LOGGER(__name__).error(f"Error setting session for {user_id}: {e}")
            return False

    def get_user_session(self, user_id: int) -> Optional[str]:
        """Get user's session string"""
        user = self.get_user(user_id)
        return user.get('session_string') if user else None

    def get_stats(self) -> Dict:
        """Get bot statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Total users
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]

                # Active users (last 7 days)
                week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('SELECT COUNT(*) FROM users WHERE last_activity > ?', (week_ago,))
                active_users = cursor.fetchone()[0]

                # Paid users
                cursor.execute('''
                    SELECT COUNT(*) FROM users
                    WHERE user_type = 'paid' AND subscription_end > date('now')
                ''')
                paid_users = cursor.fetchone()[0]

                # Admins
                cursor.execute('SELECT COUNT(*) FROM admins')
                admin_count = cursor.fetchone()[0]

                # Today's downloads
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute('SELECT SUM(files_downloaded) FROM daily_usage WHERE date = ?', (today,))
                today_downloads = cursor.fetchone()[0] or 0

                return {
                    'total_users': total_users,
                    'active_users': active_users,
                    'paid_users': paid_users,
                    'admin_count': admin_count,
                    'today_downloads': today_downloads
                }
        except Exception as e:
            LOGGER(__name__).error(f"Error getting stats: {e}")
            return {}
    
    def set_custom_thumbnail(self, user_id: int, file_id: str) -> bool:
        """Set custom thumbnail for user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET custom_thumbnail = ? WHERE user_id = ?
                ''', (file_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            LOGGER(__name__).error(f"Error setting custom thumbnail for {user_id}: {e}")
            return False
    
    def get_custom_thumbnail(self, user_id: int) -> Optional[str]:
        """Get user's custom thumbnail file_id"""
        user = self.get_user(user_id)
        return user.get('custom_thumbnail') if user else None
    
    def delete_custom_thumbnail(self, user_id: int) -> bool:
        """Delete custom thumbnail for user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET custom_thumbnail = NULL WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            LOGGER(__name__).error(f"Error deleting custom thumbnail for {user_id}: {e}")
            return False
    
    def get_premium_users(self) -> List[Dict]:
        """Get list of all premium (paid) users with active subscriptions"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, username, subscription_end as premium_expiry
                    FROM users
                    WHERE user_type = 'paid' AND subscription_end > date('now')
                    ORDER BY subscription_end DESC
                ''')
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            LOGGER(__name__).error(f"Error getting premium users: {e}")
            return []

# Initialize database
db = DatabaseManager()