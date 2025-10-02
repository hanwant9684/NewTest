# Copyright (C) @Wolfy004
# Channel: https://t.me/Wolfy004

from functools import wraps
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, ChannelPrivate
from database import db
from logger import LOGGER
from config import PyroConf

def admin_only(func):
    """Decorator to restrict command to admins only"""
    @wraps(func)
    async def wrapper(client, message: Message):
        user_id = message.from_user.id

        # Add user to database if not exists
        db.add_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # Check if banned
        if db.is_banned(user_id):
            await message.reply("❌ **You are banned from using this bot.**")
            return

        # Check admin status
        if not db.is_admin(user_id):
            await message.reply("❌ **This command is restricted to administrators only.**")
            return

        return await func(client, message)
    return wrapper

def paid_or_admin_only(func):
    """Decorator to restrict command to paid users and admins"""
    @wraps(func)
    async def wrapper(client, message: Message):
        user_id = message.from_user.id

        # Add user to database if not exists
        db.add_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # Check if banned
        if db.is_banned(user_id):
            await message.reply("❌ **You are banned from using this bot.**")
            return

        user_type = db.get_user_type(user_id)
        if user_type not in ['paid', 'admin']:
            await message.reply(
                "❌ **This feature is available for premium users only.**\n\n"
                "💎 **Upgrade to Premium:**\n"
                "• Unlimited downloads\n"
                "• Batch download feature\n"
                "• Priority support\n\n"
                "Contact admin to upgrade your account."
            )
            return

        return await func(client, message)
    return wrapper

def check_download_limit(func):
    """Decorator to check download limits for free users"""
    @wraps(func)
    async def wrapper(client, message: Message):
        user_id = message.from_user.id

        # Add user to database if not exists
        db.add_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # Check if banned
        if db.is_banned(user_id):
            await message.reply("❌ **You are banned from using this bot.**")
            return

        # Check download limits
        can_download, message_text = db.can_download(user_id)
        if not can_download:
            await message.reply(f"❌ **{message_text}**")
            return

        # Show remaining downloads for free users
        user_type = db.get_user_type(user_id)
        if user_type == 'free' and message_text:
            await message.reply(f"ℹ️ {message_text}")

        return await func(client, message)
    return wrapper

def register_user(func):
    """Decorator to register user in database"""
    @wraps(func)
    async def wrapper(client, message: Message):
        user_id = message.from_user.id

        # Add user to database if not exists
        db.add_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # Check if banned
        if db.is_banned(user_id):
            await message.reply("❌ **You are banned from using this bot.**")
            return

        return await func(client, message)
    return wrapper

async def check_user_session(user_id: int):
    """Check if user has their own session string"""
    session = db.get_user_session(user_id)
    return session is not None

async def get_user_client(user_id: int):
    """Get user's personal client if they have session"""
    session = db.get_user_session(user_id)
    if session:
        from pyrogram import Client
        from config import PyroConf

        try:
            user_client = Client(
                f"user_{user_id}",
                api_id=PyroConf.API_ID,
                api_hash=PyroConf.API_HASH,
                session_string=session,
                workers=8,
                max_concurrent_transmissions=8,
                in_memory=True  # Use in-memory sessions to avoid file leaks
            )
            await user_client.start()
            return user_client
        except Exception as e:
            LOGGER(__name__).error(f"Failed to start user client for {user_id}: {e}")
            # Clear invalid session from database
            db.set_user_session(user_id, None)
            return None
    return None

def force_subscribe(func):
    """Decorator to enforce channel subscription before using bot features"""
    @wraps(func)
    async def wrapper(client, message: Message):
        # Skip if no force subscribe channel is configured
        if not PyroConf.FORCE_SUBSCRIBE_CHANNEL:
            return await func(client, message)
        
        user_id = message.from_user.id
        
        # Admins and owner bypass force subscribe
        if db.is_admin(user_id) or user_id == PyroConf.OWNER_ID:
            return await func(client, message)
        
        # Check if user is member of the channel
        try:
            channel = PyroConf.FORCE_SUBSCRIBE_CHANNEL
            # Remove @ if present
            if channel.startswith('@'):
                channel = channel[1:]
            
            member = await client.get_chat_member(f"@{channel}", user_id)
            
            # If user is member (any status except kicked/left), allow access
            if member.status not in ["kicked", "left"]:
                return await func(client, message)
                
        except UserNotParticipant:
            pass  # User not in channel, show join message
        except (ChatAdminRequired, ChannelPrivate) as e:
            LOGGER(__name__).error(f"Bot lacks permission to check channel membership: {e}")
            # If bot can't check, allow access (don't block users due to config error)
            return await func(client, message)
        except Exception as e:
            LOGGER(__name__).error(f"Error checking channel membership: {e}")
            return await func(client, message)
        
        # User is not subscribed, show join message
        channel_username = PyroConf.FORCE_SUBSCRIBE_CHANNEL
        if not channel_username.startswith('@'):
            channel_username = f"@{channel_username}"
        
        join_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel_username.replace('@', '')}")]
        ])
        
        await message.reply(
            f"❌ **Access Denied!**\n\n"
            f"🔒 You must join our channel to use this bot.\n\n"
            f"👉 **Channel:** {channel_username}\n\n"
            f"After joining, try your command again!",
            reply_markup=join_button
        )
    
    return wrapper