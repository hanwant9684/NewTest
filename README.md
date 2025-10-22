# Telegram Media Bot

A Telegram bot for downloading and forwarding media from private/public channels with ad monetization support.

## Features

- Download and forward media from Telegram channels
- Support for multiple media types (photos, videos, documents)
- Queue management for downloads
- Ad monetization with Monetag/Adsterra
- MongoDB database for user and session management
- Premium user system
- Admin controls and broadcasting
- Phone authentication for accessing restricted content

## Setup Instructions

### Required Environment Variables

The bot requires the following environment variables to run. You can set them in Replit Secrets:

1. **MONGODB_URI** - MongoDB Atlas connection string
   - Get from: https://cloud.mongodb.com
   - Format: `mongodb+srv://username:password@cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority`

2. **API_ID** - Telegram API ID
   - Get from: https://my.telegram.org/apps

3. **API_HASH** - Telegram API Hash
   - Get from: https://my.telegram.org/apps

4. **BOT_TOKEN** - Telegram Bot Token
   - Get from: @BotFather on Telegram

5. **OWNER_ID** - Your Telegram user ID (will be auto-added as admin)
   - Get from: @userinfobot on Telegram

### Optional Environment Variables

- **FORCE_SUBSCRIBE_CHANNEL** - Channel username or ID for forced subscription
- **ADMIN_USERNAME** - Bot admin username for contact
- **PAYPAL_URL** - PayPal payment URL for premium subscriptions
- **UPI_ID** - UPI ID for payments
- **AD_ID_1**, **AD_ID_2**, **AD_ID_3** - Monetag zone IDs for ad monetization
- **SESSION_STRING** - Session string for admin downloads (optional)

## How to Run

1. Set all required environment variables in Replit Secrets
2. The bot will start automatically once all required variables are configured
3. The Flask server will run on port 5000 for ad verification

## Project Structure

- `main.py` - Main bot logic and message handlers
- `server.py` - Flask server for ad verification
- `database.py` - MongoDB database manager
- `config.py` - Configuration and environment variable loader
- `ad_monetization.py` - Ad monetization logic
- `access_control.py` - User authentication and access control
- `admin_commands.py` - Admin-only commands
- `queue_manager.py` - Download queue management
- `helpers/` - Utility functions for media, files, and messages

## Credits

Created by @Wolfy004
Channel: https://t.me/Wolfy004
