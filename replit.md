# Telegram Media Bot - Replit Setup

## Overview

This is a Telegram bot for downloading and forwarding media from private/public channels with ad monetization support. The bot uses Telethon for Telegram integration and includes a WSGI server for ad verification.

**Purpose:** Download and forward media from Telegram channels with queue management, premium user system, and ad monetization.

**Current State:** Fully functional and running on Replit with all dependencies installed.

## Recent Changes

- **2025-11-01:** Optimized media group downloads to prevent high RAM usage
  - **Problem:** Media groups were downloading all files into memory before uploading, causing high RAM usage and potential out-of-memory crashes
  - **Solution:** Implemented sequential file processing (download → upload → delete → next)
  - Modified `processMediaGroup()` in `helpers/utils.py` to process files one at a time
  - Modified `send_media()` to return boolean success/failure for accurate tracking
  - Each file is now deleted immediately after upload to free RAM
  - Preserves all safeguards: file size checks, fast uploads, thumbnails, dump channel forwarding
  - **Trade-off:** Files are now sent as individual messages instead of grouped albums (necessary for RAM efficiency)
  - **Impact:** Bot can now handle large media groups without running out of memory

- **2025-11-01:** Fixed critical ad verification bug - Premature code generation
  - **Problem:** URL shortener services validate links before shortening, which triggered verification code generation before users even received the link
  - **Solution:** Implemented two-step verification with landing page
  - When users click the shortened link, they now see a landing page with a "Get Verification Code" button
  - Verification codes are only generated when the button is clicked (confirm=1 parameter)
  - This prevents shortener validation requests from consuming sessions
  - Tightened security by requiring exact match `confirm == '1'`
  - **Impact:** Users can now reliably receive and use their verification codes

- **2025-11-01:** Replaced ARLinks with Shrtfly URL shortener
  - Updated `ad_monetization.py` to use Shrtfly (https://shrtfly.com/) instead of ARLinks
  - Added SHRTFLY_API_KEY to environment secrets
  - Updated documentation (README.md and replit.md) to reflect the change
  - URL shortener rotation now: Droplink → GPLinks → Shrtfly → UpShrink (repeats)

- **2025-11-01:** Project imported from GitHub and configured for Replit environment
  - Installed all Python dependencies (Telethon, cryptg, psutil, uvloop, waitress, orjson)
  - Configured workflow to run WSGI server on port 5000
  - Bot successfully connected and running with cloud backup integration
  - **Fixed critical bugs from Render deployment:**
    - Fixed cleanup_download crash when called with None paths
    - Implemented proper background task tracking and graceful shutdown
    - Prevents "Task was destroyed but it is pending!" errors on forced shutdowns
    - Orphaned files now cleaned by periodic cleanup task

## Project Architecture

### Technology Stack
- **Language:** Python 3.12
- **Framework:** Telethon (Telegram client library)
- **Web Server:** Waitress WSGI server (minimal RAM usage)
- **Database:** SQLite (portable & lightweight)
- **Event Loop:** uvloop (performance optimization)

### Key Components

#### Core Files
- `main.py` - Main bot logic and message handlers (Telethon event handlers)
- `server_wsgi.py` - WSGI server entry point and bot orchestration
- `config.py` - Configuration and environment variable management
- `database_sqlite.py` - SQLite database manager for users and sessions

#### Feature Modules
- `ad_monetization.py` - Ad verification system with URL shorteners
- `access_control.py` - User authentication and permission system
- `admin_commands.py` - Admin-only bot commands
- `queue_manager.py` - Download queue with concurrency control
- `phone_auth.py` - Phone-based authentication for restricted content
- `memory_monitor.py` - Memory usage tracking and optimization
- `cloud_backup.py` - GitHub-based database backup system
- `backup_database.py` - Local database backup utilities

#### Helper Modules (helpers/)
- `utils.py` - Media processing and progress tracking
- `transfer.py` - Fast media download with FastTelethon
- `files.py` - File management and cleanup
- `msg.py` - Message parsing utilities
- `session_manager.py` - Session lifecycle management
- `cleanup.py` - Periodic cleanup tasks

### Architecture Decisions

1. **SQLite over MongoDB:** Uses SQLite for better portability and lower resource usage in cloud environments
2. **WSGI over Flask:** Uses minimal WSGI server (Waitress) instead of Flask to save 15-20MB RAM
3. **Session Management:** Implements session pooling with max 3 concurrent sessions and 30-minute idle timeout
4. **Memory Optimization:** Periodic garbage collection, orphaned file cleanup, and memory monitoring
5. **Cloud Backup:** Automatic GitHub backup every 10 minutes for database persistence

## Environment Variables

### Required Secrets (Already Configured)
- `API_ID` - Telegram API ID from https://my.telegram.org/apps
- `API_HASH` - Telegram API Hash from https://my.telegram.org/apps
- `BOT_TOKEN` - Bot token from @BotFather
- `OWNER_ID` - Telegram user ID (auto-added as admin)

### Optional Configuration
- `FORCE_SUBSCRIBE_CHANNEL` - Channel for forced subscription
- `ADMIN_USERNAME` - Bot admin username for contact
- `PAYPAL_URL`, `UPI_ID`, `TELEGRAM_TON`, `CRYPTO_ADDRESS` - Payment methods
- `DROPLINK_API_KEY`, `GPLINKS_API_KEY`, `SHRTFLY_API_KEY`, `UPSHRINK_API_KEY` - URL shortener API keys
- `SESSION_STRING` - Admin session for downloads
- `DUMP_CHANNEL_ID` - Channel ID for media forwarding
- `CLOUD_BACKUP_SERVICE` - Set to "github" for cloud backup
- `GITHUB_TOKEN`, `GITHUB_BACKUP_REPO` - GitHub backup credentials
- `CLOUD_BACKUP_INTERVAL_HOURS` - Backup interval (default: 6 hours)

## Workflow Configuration

The bot runs via a single workflow:
- **Name:** telegram-bot
- **Command:** `python server_wsgi.py`
- **Port:** 5000 (WSGI server for ad verification)
- **Output:** WebView (shows verification pages)

## Database Schema

SQLite database (`telegram_bot.db`) with tables:
- `users` - User information and permissions
- `admins` - Admin users list
- `premium_users` - Premium subscription data
- `banned_users` - Banned user records
- `ad_sessions` - Ad verification sessions
- `verification_codes` - Premium verification codes
- `user_sessions` - Telethon user sessions

## User Preferences

None specified yet. Add preferences as they are expressed.

## Deployment Notes

- Server binds to `0.0.0.0:5000` as required by Replit
- The bot uses long polling (no webhooks) for Telegram updates
- All sessions and downloads are managed in-memory with periodic cleanup
- Cloud backup keeps database synced to GitHub repository
- Memory monitoring logs to `memory_debug.log` for diagnostics

## Credits

Created by @Wolfy004  
Channel: https://t.me/Wolfy004
