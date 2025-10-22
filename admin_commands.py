# Copyright (C) @Wolfy004
# Channel: https://t.me/Wolfy004

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from access_control import admin_only, register_user
from database import db
from logger import LOGGER

@admin_only
async def add_admin_command(client: Client, message: Message):
    """Add a new admin"""
    try:
        if len(message.command) < 2:
            await message.reply("**Usage:** `/addadmin <user_id>`")
            return

        target_user_id = int(message.command[1])
        admin_user_id = message.from_user.id

        if db.add_admin(target_user_id, admin_user_id):
            # Try to get user info
            try:
                user_info = await client.get_users(target_user_id)
                user_name = user_info.first_name or "Unknown"
            except:
                user_name = str(target_user_id)

            await message.reply(f"✅ **Successfully added {user_name} as admin.**")
            LOGGER(__name__).info(f"Admin {admin_user_id} added {target_user_id} as admin")
        else:
            await message.reply("❌ **Failed to add admin. User might already be an admin.**")

    except ValueError:
        await message.reply("❌ **Invalid user ID. Please provide a numeric user ID.**")
    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")
        LOGGER(__name__).error(f"Error in add_admin_command: {e}")

@admin_only
async def remove_admin_command(client: Client, message: Message):
    """Remove admin privileges"""
    try:
        if len(message.command) < 2:
            await message.reply("**Usage:** `/removeadmin <user_id>`")
            return

        target_user_id = int(message.command[1])

        if db.remove_admin(target_user_id):
            await message.reply(f"✅ **Successfully removed admin privileges from user {target_user_id}.**")
            LOGGER(__name__).info(f"Admin {message.from_user.id} removed admin privileges from {target_user_id}")
        else:
            await message.reply("❌ **User is not an admin or error occurred.**")

    except ValueError:
        await message.reply("❌ **Invalid user ID. Please provide a numeric user ID.**")
    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")

@admin_only
async def set_premium_command(client: Client, message: Message):
    """Set user as premium"""
    try:
        args = message.command[1:] if len(message.command) > 1 else []

        if len(args) < 1:
            await message.reply("**Usage:** `/setpremium <user_id> [days]`\n\n**Default:** 30 days")
            return

        target_user_id = int(args[0])
        days = int(args[1]) if len(args) > 1 else 30

        if db.set_user_type(target_user_id, 'paid', days):
            await message.reply(f"✅ **Successfully upgraded user {target_user_id} to premium for {days} days.**")
            LOGGER(__name__).info(f"Admin {message.from_user.id} set {target_user_id} as premium for {days} days")
        else:
            await message.reply("❌ **Failed to upgrade user.**")

    except ValueError:
        await message.reply("❌ **Invalid input. Use numeric values only.**")
    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")

@admin_only
async def remove_premium_command(client: Client, message: Message):
    """Remove premium subscription"""
    try:
        if len(message.command) < 2:
            await message.reply("**Usage:** `/removepremium <user_id>`")
            return

        target_user_id = int(message.command[1])

        if db.set_user_type(target_user_id, 'free'):
            await message.reply(f"✅ **Successfully downgraded user {target_user_id} to free plan.**")
            LOGGER(__name__).info(f"Admin {message.from_user.id} removed premium from {target_user_id}")
        else:
            await message.reply("❌ **Failed to downgrade user.**")

    except ValueError:
        await message.reply("❌ **Invalid user ID. Please provide a numeric user ID.**")
    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")

@admin_only
async def ban_user_command(client: Client, message: Message):
    """Ban a user"""
    try:
        if len(message.command) < 2:
            await message.reply("**Usage:** `/ban <user_id>`")
            return

        target_user_id = int(message.command[1])

        if target_user_id == message.from_user.id:
            await message.reply("❌ **You cannot ban yourself.**")
            return

        if db.is_admin(target_user_id):
            await message.reply("❌ **Cannot ban another admin.**")
            return

        if db.ban_user(target_user_id):
            await message.reply(f"✅ **Successfully banned user {target_user_id}.**")
            LOGGER(__name__).info(f"Admin {message.from_user.id} banned {target_user_id}")
        else:
            await message.reply("❌ **Failed to ban user.**")

    except ValueError:
        await message.reply("❌ **Invalid user ID. Please provide a numeric user ID.**")
    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")

@admin_only
async def unban_user_command(client: Client, message: Message):
    """Unban a user"""
    try:
        if len(message.command) < 2:
            await message.reply("**Usage:** `/unban <user_id>`")
            return

        target_user_id = int(message.command[1])

        if db.unban_user(target_user_id):
            await message.reply(f"✅ **Successfully unbanned user {target_user_id}.**")
            LOGGER(__name__).info(f"Admin {message.from_user.id} unbanned {target_user_id}")
        else:
            await message.reply("❌ **Failed to unban user or user was not banned.**")

    except ValueError:
        await message.reply("❌ **Invalid user ID. Please provide a numeric user ID.**")
    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")

@admin_only
async def broadcast_command(client: Client, message: Message):
    """Broadcast message to all users"""
    try:
        if len(message.command) < 2:
            await message.reply(
                "**Usage:** `/broadcast <message>`\n\n"
                "**Example:** `/broadcast Hello everyone! New features are now available.`"
            )
            return

        # Get the broadcast message (everything after /broadcast)
        broadcast_message = message.text.split(' ', 1)[1]

        # Confirm broadcast
        confirm_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Send Broadcast", callback_data=f"broadcast_confirm:{message.from_user.id}"),
                InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")
            ]
        ])

        preview = broadcast_message[:100] + "..." if len(broadcast_message) > 100 else broadcast_message

        await message.reply(
            f"**📢 Broadcast Preview:**\n\n{preview}\n\n"
            f"**Are you sure you want to send this message to all users?**",
            reply_markup=confirm_markup
        )

        # Store broadcast message temporarily (you might want to use a proper cache)
        setattr(client, f'pending_broadcast_{message.from_user.id}', broadcast_message)

    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")
        LOGGER(__name__).error(f"Error in broadcast_command: {e}")

async def execute_broadcast(client: Client, admin_id: int, broadcast_message: str):
    """Execute the actual broadcast"""
    all_users = db.get_all_users()
    total_users = len(all_users)
    successful_sends = 0

    if total_users == 0:
        return 0, 0

    # Send broadcast to all users
    for user_id in all_users:
        try:
            await client.send_message(user_id, broadcast_message)
            successful_sends += 1
            await asyncio.sleep(0.1)  # Small delay to avoid rate limits
        except Exception as e:
            LOGGER(__name__).debug(f"Failed to send broadcast to {user_id}: {e}")
            continue

    # Save broadcast history
    db.save_broadcast(broadcast_message, admin_id, total_users, successful_sends)

    return total_users, successful_sends

@admin_only
async def admin_stats_command(client: Client, message: Message, queue_manager=None):
    """Show detailed admin statistics"""
    try:
        stats = db.get_stats()
        
        # Get queue stats if queue manager is provided
        active_downloads = 0
        queue_size = 0
        if queue_manager:
            active_downloads = len(queue_manager.active_downloads)
            queue_size = len(queue_manager.waiting_queue)

        stats_text = (
            "👑 **ADMIN DASHBOARD**\n"
            "——————————————————————————\n\n"
            "👥 **User Analytics:**\n"
            f"📊 Total Users: `{stats.get('total_users', 0)}`\n"
            f"💎 Premium Users: `{stats.get('paid_users', 0)}`\n"
            f"🟢 Active (7d): `{stats.get('active_users', 0)}`\n"
            f"🆕 New Today: `{stats.get('today_new_users', 0)}`\n"
            f"🔐 Admins: `{stats.get('admin_count', 0)}`\n\n"
            "📈 **Download Activity:**\n"
            f"📥 Today: `{stats.get('today_downloads', 0)}`\n"
            f"⚡ Active: `{active_downloads}`\n"
            f"📋 Queue: `{queue_size}`\n\n"
            "——————————————————————————\n\n"
            "⚙️ **Quick Admin Actions:**\n"
            "• `/killall` - Cancel all downloads\n"
            "• `/broadcast` - Send message to all\n"
            "• `/logs` - View bot logs"
        )

        await message.reply(stats_text)

    except Exception as e:
        await message.reply(f"❌ **Error getting stats: {str(e)}**")
        LOGGER(__name__).error(f"Error in admin_stats_command: {e}")

@register_user
async def user_info_command(client: Client, message: Message):
    """Show user information"""
    try:
        user_id = message.from_user.id
        user_type = db.get_user_type(user_id)
        daily_usage = db.get_daily_usage(user_id)

        user_info_text = (
            f"**👤 Your Account Information**\n\n"
            f"**User ID:** `{user_id}`\n"
            f"**Account Type:** `{user_type.title()}`\n"
        )

        if user_type == 'free':
            remaining = 5 - daily_usage
            user_info_text += (
                f"**Today's Downloads:** `{daily_usage}/5`\n"
                f"**Remaining:** `{remaining}`\n\n"
                "💎 **Upgrade to Premium for unlimited downloads!**"
            )
        elif user_type == 'paid':
            user = db.get_user(user_id)
            if user and user['subscription_end']:
                user_info_text += f"**Subscription Valid Until:** `{user['subscription_end']}`\n"
            user_info_text += f"**Today's Downloads:** `{daily_usage}` (unlimited)\n"
        else:  # admin
            user_info_text += f"**Today's Downloads:** `{daily_usage}` (unlimited)\n**Privileges:** `Administrator`\n"

        await message.reply(user_info_text)

    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")
        LOGGER(__name__).error(f"Error in user_info_command: {e}")

# Callback handler for broadcast confirmation
async def broadcast_callback_handler(client: Client, callback_query):
    """Handle broadcast confirmation callbacks"""
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data == "broadcast_cancel":
        await callback_query.edit_message_text("❌ **Broadcast cancelled.**")
        return

    if data.startswith("broadcast_confirm:"):
        admin_id = int(data.split(":")[1])

        if user_id != admin_id:
            await callback_query.answer("❌ You are not authorized to confirm this broadcast.", show_alert=True)
            return

        # Get the stored broadcast message
        broadcast_message = getattr(client, f'pending_broadcast_{admin_id}', None)

        if not broadcast_message:
            await callback_query.edit_message_text("❌ **Broadcast message not found. Please try again.**")
            return

        # Update message to show processing
        await callback_query.edit_message_text("📡 **Sending broadcast... Please wait.**")

        # Execute broadcast
        total_users, successful_sends = await execute_broadcast(client, admin_id, broadcast_message)

        # Clean up stored message
        if hasattr(client, f'pending_broadcast_{admin_id}'):
            delattr(client, f'pending_broadcast_{admin_id}')

        # Send results
        result_text = (
            f"✅ **Broadcast Completed!**\n\n"
            f"**Total Users:** `{total_users}`\n"
            f"**Successful Sends:** `{successful_sends}`\n"
            f"**Failed Sends:** `{total_users - successful_sends}`\n"
            f"**Success Rate:** `{(successful_sends/total_users*100):.1f}%`" if total_users > 0 else "**Success Rate:** `0%`"
        )

        await callback_query.edit_message_text(result_text)