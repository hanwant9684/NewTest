# Copyright (C) @Wolfy004
# Channel: https://t.me/Wolfy004

import os
import shutil
import psutil
import asyncio
from time import time

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from pyleaves import Leaves
from pyrogram.enums import ParseMode
from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid, BadRequest
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from helpers.utils import (
    processMediaGroup,
    progressArgs,
    send_media
)

from helpers.files import (
    get_download_path,
    fileSizeLimit,
    get_readable_file_size,
    get_readable_time,
    cleanup_download
)

from helpers.msg import (
    getChatMsgID,
    get_file_name,
    get_parsed_msg
)

from config import PyroConf
from logger import LOGGER
from database import db
from phone_auth import PhoneAuthHandler
from access_control import admin_only, paid_or_admin_only, check_download_limit, register_user, check_user_session, get_user_client, force_subscribe
from admin_commands import (
    add_admin_command,
    remove_admin_command,
    set_premium_command,
    remove_premium_command,
    ban_user_command,
    unban_user_command,
    broadcast_command,
    admin_stats_command,
    user_info_command,
    broadcast_callback_handler
)

# Initialize the bot client with optimized settings for faster downloads/uploads
bot = Client(
    "media_bot",
    api_id=PyroConf.API_ID,
    api_hash=PyroConf.API_HASH,
    bot_token=PyroConf.BOT_TOKEN,
    workers=8,
    max_concurrent_transmissions=8,
    parse_mode=ParseMode.MARKDOWN,
)

# Client for user session (optional fallback) with optimized settings
user = Client(
    "user_session", 
    workers=8,
    max_concurrent_transmissions=8,
    session_string=PyroConf.SESSION_STRING
) if PyroConf.SESSION_STRING else None

# Phone authentication handler
phone_auth_handler = PhoneAuthHandler(PyroConf.API_ID, PyroConf.API_HASH)

RUNNING_TASKS = set()
USER_TASKS = {}

def track_task(coro, user_id=None):
    task = asyncio.create_task(coro)
    RUNNING_TASKS.add(task)
    
    if user_id:
        if user_id not in USER_TASKS:
            USER_TASKS[user_id] = set()
        USER_TASKS[user_id].add(task)
    
    def _remove(_):
        RUNNING_TASKS.discard(task)
        if user_id and user_id in USER_TASKS:
            USER_TASKS[user_id].discard(task)
            if not USER_TASKS[user_id]:
                del USER_TASKS[user_id]
    
    task.add_done_callback(_remove)
    return task

def get_user_tasks(user_id):
    return USER_TASKS.get(user_id, set())

def cancel_user_tasks(user_id):
    tasks = get_user_tasks(user_id)
    cancelled = 0
    for task in list(tasks):
        if not task.done():
            task.cancel()
            cancelled += 1
    return cancelled

# Auto-add OWNER_ID as admin on startup
@bot.on_message(filters.command("start") & filters.create(lambda _, __, m: m.from_user.id == PyroConf.OWNER_ID), group=-1)
async def auto_add_owner_as_admin(_, message: Message):
    if PyroConf.OWNER_ID and not db.is_admin(PyroConf.OWNER_ID):
        db.add_admin(PyroConf.OWNER_ID, PyroConf.OWNER_ID)
        LOGGER(__name__).info(f"Auto-added owner {PyroConf.OWNER_ID} as admin")

@bot.on_message(filters.command("start") & filters.private)
@register_user
async def start(_, message: Message):
    welcome_text = (
        "**Welcome to Save Restricted Content Bot!**\n\n"
        "📱 **Get Started:**\n"
        "1. Login with your phone number: `/login +1234567890`\n"
        "2. Enter the OTP code you receive\n"
        "3. Start downloading from your joined channels!\n\n"
        "ℹ️ Use `/help` to view all commands and examples.\n\n"
        "Ready? Login first with `/login <your_phone_number>`"
    )

    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Update Channel", url="https://t.me/Wolfy004")]]
    )
    await message.reply(welcome_text, reply_markup=markup, disable_web_page_preview=True)

@bot.on_message(filters.command("help") & filters.private)
@register_user
async def help_command(_, message: Message):
    help_text = (
        "💡 **Media Downloader Bot Help**\n\n"
        "➤ **Download Media**\n"
        "   – Send `/dl <post_URL>` **or** just paste a Telegram post link to fetch photos, videos, audio, or documents.\n\n"
        "➤ **Batch Download** (Premium Only)\n"
        "   – Send `/bdl start_link end_link` to grab a series of posts in one go.\n"
        "     💡 Example: `/bdl https://t.me/mychannel/100 https://t.me/mychannel/120`\n"
        "**It will download all posts from ID 100 to 120.**\n\n"
        "➤ **Cancel Downloads**\n"
        "   – `/canceldownload` - Cancel all your running downloads\n"
        "   – Note: You can only run one batch at a time\n\n"
        "➤ **Login with Phone Number**\n"
        "   – `/login +1234567890` - Start login process\n"
        "   – `/verify 1 2 3 4 5` - Enter OTP with spaces between digits\n"
        "   – `/password your_2fa_password` - Enter 2FA password (if enabled)\n"
        "   – `/logout` - Logout from your account\n"
        "   – `/cancel` - Cancel pending authentication\n\n"
        "➤ **User Commands**\n"
        "   – `/myinfo` - View your account information\n"
        "   – `/upgrade` - Get premium subscription info\n\n"
        "➤ **Limits**\n"
        "   – Free users: 5 downloads per day\n"
        "   – Premium users: Unlimited downloads\n"
        "   – Batch download: Max 20 posts at a time\n\n"
        "➤ **If the bot hangs**\n"
        "   – Send `/killall` to cancel any pending downloads (Admin only).\n\n"
        "➤ **Logs**\n"
        "   – Send `/logs` to download the bot's logs file.\n\n"
        "➤ **Stats**\n"
        "   – Send `/stats` to view current status:\n\n"
        "**Example**:\n"
        "  • `/dl https://t.me/Wolfy004`\n"
        "  • `https://t.me/Wolfy004`"
    )

    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Update Channel", url="https://t.me/itsSmartDev")]]
    )
    await message.reply(help_text, reply_markup=markup, disable_web_page_preview=True)

async def handle_download(bot: Client, message: Message, post_url: str, user_client=None, increment_usage=True, cleanup_client=True):
    # Cut off URL at '?' if present
    if "?" in post_url:
        post_url = post_url.split("?", 1)[0]

    try:
        chat_id, message_id = getChatMsgID(post_url)

        # Use user's personal session if available
        # Only fall back to shared session for admins/owner
        client_to_use = user_client
        
        if not client_to_use:
            # Check if user is admin or owner
            user_id = message.from_user.id
            if db.is_admin(user_id) or user_id == PyroConf.OWNER_ID:
                # Allow admins to use fallback session if configured
                if user and not user.is_connected:
                    await user.start()
                client_to_use = user
            
            if not client_to_use:
                await message.reply(
                    "❌ **No active session found.**\n\n"
                    "Please login with your phone number:\n"
                    "`/login +1234567890`"
                )
                return

        chat_message = await client_to_use.get_messages(chat_id=chat_id, message_ids=message_id)

        LOGGER(__name__).info(f"Downloading media from URL: {post_url}")

        if chat_message.document or chat_message.video or chat_message.audio:
            file_size = (
                chat_message.document.file_size
                if chat_message.document
                else chat_message.video.file_size
                if chat_message.video
                else chat_message.audio.file_size
            )

            # Check file size limit based on actual client being used
            try:
                is_premium = False
                if client_to_use != user:
                    # User's personal client
                    me = await client_to_use.get_me()
                    is_premium = getattr(me, 'is_premium', False)
                else:
                    # Bot's session
                    if hasattr(user, 'me') and user.me:
                        is_premium = getattr(user.me, 'is_premium', False)
                    else:
                        me = await user.get_me()
                        is_premium = getattr(me, 'is_premium', False)
            except:
                is_premium = False

            if not await fileSizeLimit(file_size, message, "download", is_premium):
                return

        parsed_caption = await get_parsed_msg(
            chat_message.caption or "", chat_message.caption_entities
        )
        parsed_text = await get_parsed_msg(
            chat_message.text or "", chat_message.entities
        )

        if chat_message.media_group_id:
            if not await processMediaGroup(chat_message, bot, message):
                await message.reply(
                    "**Could not extract any valid media from the media group.**"
                )
            return

        elif chat_message.media:
            start_time = time()
            progress_message = await message.reply("**📥 Downloading Progress...**")

            filename = get_file_name(message_id, chat_message)
            download_path = get_download_path(message.id, filename)

            media_path = await chat_message.download(
                file_name=download_path,
                progress=Leaves.progress_for_pyrogram,
                progress_args=progressArgs(
                    "📥 Downloading Progress", progress_message, start_time
                ),
            )

            LOGGER(__name__).info(f"Downloaded media: {media_path}")

            media_type = (
                "photo"
                if chat_message.photo
                else "video"
                if chat_message.video
                else "audio"
                if chat_message.audio
                else "document"
            )
            await send_media(
                bot,
                message,
                media_path,
                media_type,
                parsed_caption,
                progress_message,
                start_time,
                message.from_user.id,
            )

            cleanup_download(media_path)
            await progress_message.delete()

            # Only increment usage after successful download
            if increment_usage:
                db.increment_usage(message.from_user.id)

        elif chat_message.text or chat_message.caption:
            await message.reply(parsed_text or parsed_caption)
        else:
            await message.reply("**No media or text found in the post URL.**")

    except (PeerIdInvalid, BadRequest, KeyError):
        await message.reply("**Make sure the user client is part of the chat.**")
    except Exception as e:
        error_message = f"**❌ {str(e)}**"
        await message.reply(error_message)
        LOGGER(__name__).error(e)
    finally:
        # Clean up user client only if cleanup is enabled (not in batch mode)
        if cleanup_client and user_client and user_client != user:
            try:
                await user_client.stop()
            except:
                pass

@bot.on_message(filters.command("dl") & filters.private)
@force_subscribe
@check_download_limit
async def download_media(bot: Client, message: Message):
    if len(message.command) < 2:
        await message.reply("**Provide a post URL after the /dl command.**")
        return

    post_url = message.command[1]

    # Check if user has personal session
    user_client = await get_user_client(message.from_user.id)

    await track_task(handle_download(bot, message, post_url, user_client, True), message.from_user.id)

@bot.on_message(filters.command("bdl") & filters.private)
@force_subscribe
@paid_or_admin_only
async def download_range(bot: Client, message: Message):
    args = message.text.split()

    if len(args) != 3 or not all(arg.startswith("https://t.me/") for arg in args[1:]):
        await message.reply(
            "🚀 **Batch Download Process**\n"
            "`/bdl start_link end_link`\n\n"
            "💡 **Example:**\n"
            "`/bdl https://t.me/mychannel/100 https://t.me/mychannel/120`"
        )
        return

    # Check if user already has a batch running
    user_tasks = get_user_tasks(message.from_user.id)
    if user_tasks:
        running_count = sum(1 for task in user_tasks if not task.done())
        if running_count > 0:
            await message.reply(
                f"❌ **You already have {running_count} download(s) running!**\n\n"
                "Please wait for them to finish or use `/canceldownload` to cancel them."
            )
            return

    try:
        start_chat, start_id = getChatMsgID(args[1])
        end_chat,   end_id   = getChatMsgID(args[2])
    except Exception as e:
        return await message.reply(f"**❌ Error parsing links:\n{e}**")

    if start_chat != end_chat:
        return await message.reply("**❌ Both links must be from the same channel.**")
    if start_id > end_id:
        return await message.reply("**❌ Invalid range: start ID cannot exceed end ID.**")
    
    # Limit batch to 20 posts at a time
    batch_count = end_id - start_id + 1
    if batch_count > 20:
        return await message.reply(
            f"**❌ Batch limit exceeded!**\n\n"
            f"You requested `{batch_count}` posts, but the maximum is **20 posts** at a time.\n\n"
            f"Please reduce your range and try again."
        )

    # Check if user has personal session
    user_client = await get_user_client(message.from_user.id)
    client_to_use = user_client
    
    if not client_to_use:
        # Check if user is admin or owner
        if db.is_admin(message.from_user.id) or message.from_user.id == PyroConf.OWNER_ID:
            if user and not user.is_connected:
                await user.start()
            client_to_use = user
        
        if not client_to_use:
            await message.reply(
                "❌ **No active session found.**\n\n"
                "Please login with your phone number:\n"
                "`/login +1234567890`"
            )
            return

    try:
        await client_to_use.get_chat(start_chat)
    except Exception:
        pass

    prefix = args[1].rsplit("/", 1)[0]
    loading = await message.reply(f"📥 **Downloading posts {start_id}–{end_id}…**")

    downloaded = skipped = failed = 0

    for msg_id in range(start_id, end_id + 1):
        url = f"{prefix}/{msg_id}"
        try:
            chat_msg = await client_to_use.get_messages(chat_id=start_chat, message_ids=msg_id)
            if not chat_msg:
                skipped += 1
                continue

            has_media = bool(chat_msg.media_group_id or chat_msg.media)
            has_text  = bool(chat_msg.text or chat_msg.caption)
            if not (has_media or has_text):
                skipped += 1
                continue

            task = track_task(handle_download(bot, message, url, client_to_use, False, cleanup_client=False), message.from_user.id)
            try:
                await task
                downloaded += 1
                # Increment usage count for batch downloads after success
                db.increment_usage(message.from_user.id)
            except asyncio.CancelledError:
                await loading.delete()
                # Clean up client before returning
                if user_client and user_client != user:
                    try:
                        await user_client.stop()
                    except:
                        pass
                return await message.reply(
                    f"**❌ Batch canceled** after downloading `{downloaded}` posts."
                )

        except Exception as e:
            failed += 1
            LOGGER(__name__).error(f"Error at {url}: {e}")

        await asyncio.sleep(3)

    await loading.delete()
    
    # Clean up user client after batch completes
    if user_client and user_client != user:
        try:
            await user_client.stop()
        except:
            pass
    
    await message.reply(
        "**✅ Batch Process Complete!**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📥 **Downloaded** : `{downloaded}` post(s)\n"
        f"⏭️ **Skipped**    : `{skipped}` (no content)\n"
        f"❌ **Failed**     : `{failed}` error(s)"
    )

# Phone authentication commands
@bot.on_message(filters.command("login") & filters.private)
@register_user
async def login_command(client: Client, message: Message):
    """Start login process with phone number"""
    try:
        if len(message.command) < 2:
            await message.reply(
                "**Usage:** `/login +1234567890`\n\n"
                "**Example:** `/login +919876543210`\n\n"
                "Make sure to include country code with +"
            )
            return

        phone_number = message.command[1].strip()

        if not phone_number.startswith('+'):
            await message.reply("❌ **Please include country code with + sign.**\n\n**Example:** `/login +1234567890`")
            return

        # Send OTP
        success, msg, _ = await phone_auth_handler.send_otp(message.from_user.id, phone_number)
        await message.reply(msg)

    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")
        LOGGER(__name__).error(f"Error in login_command: {e}")

@bot.on_message(filters.command("verify") & filters.private)
@register_user
async def verify_command(client: Client, message: Message):
    """Verify OTP code"""
    try:
        if len(message.command) < 2:
            await message.reply(
                "**Usage:** `/verify 1 2 3 4 5` (with spaces between digits)\n\n"
                "**Example:** If code is 12345, send:\n"
                "`/verify 1 2 3 4 5`"
            )
            return

        # Get OTP code (all arguments after /verify)
        otp_code = ' '.join(message.command[1:])

        # Verify OTP
        result = await phone_auth_handler.verify_otp(message.from_user.id, otp_code)

        if len(result) == 4:
            success, msg, needs_2fa, session_string = result
        else:
            success, msg, needs_2fa = result
            session_string = None

        await message.reply(msg)

        # Save session string if authentication successful
        if success and session_string:
            db.set_user_session(message.from_user.id, session_string)
            LOGGER(__name__).info(f"Saved session for user {message.from_user.id}")

    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")
        LOGGER(__name__).error(f"Error in verify_command: {e}")

@bot.on_message(filters.command("password") & filters.private)
@register_user
async def password_command(client: Client, message: Message):
    """Enter 2FA password"""
    try:
        if len(message.command) < 2:
            await message.reply(
                "**Usage:** `/password <YOUR_2FA_PASSWORD>`\n\n"
                "**Example:** `/password MySecretPassword123`"
            )
            return

        # Get password (everything after /password)
        password = message.text.split(' ', 1)[1]

        # Verify 2FA
        success, msg, session_string = await phone_auth_handler.verify_2fa_password(message.from_user.id, password)
        await message.reply(msg)

        # Save session string if successful
        if success and session_string:
            db.set_user_session(message.from_user.id, session_string)
            LOGGER(__name__).info(f"Saved session for user {message.from_user.id} after 2FA")

    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")
        LOGGER(__name__).error(f"Error in password_command: {e}")

@bot.on_message(filters.command("logout") & filters.private)
@register_user
async def logout_command(client: Client, message: Message):
    """Logout from account"""
    try:
        if db.set_user_session(message.from_user.id, None):
            await message.reply(
                "✅ **Successfully logged out!**\n\n"
                "Use `/login <phone_number>` to login again."
            )
            LOGGER(__name__).info(f"User {message.from_user.id} logged out")
        else:
            await message.reply("❌ **You are not logged in.**")

    except Exception as e:
        await message.reply(f"❌ **Error: {str(e)}**")

@bot.on_message(filters.command("cancel") & filters.private)
@register_user
async def cancel_command(client: Client, message: Message):
    """Cancel pending authentication"""
    success, msg = await phone_auth_handler.cancel_auth(message.from_user.id)
    await message.reply(msg)

@bot.on_message(filters.command("canceldownload") & filters.private)
@register_user
async def cancel_download_command(client: Client, message: Message):
    """Cancel user's running downloads"""
    cancelled = cancel_user_tasks(message.from_user.id)
    if cancelled > 0:
        await message.reply(
            f"✅ **Cancelled {cancelled} download(s)!**\n\n"
            "You can start new downloads now."
        )
        LOGGER(__name__).info(f"User {message.from_user.id} cancelled {cancelled} download(s)")
    else:
        await message.reply("ℹ️ **You have no active downloads to cancel.**")

@bot.on_message(filters.private & ~filters.command(["start", "help", "dl", "stats", "logs", "killall", "bdl", "myinfo", "upgrade", "premiumlist", "login", "verify", "password", "logout", "cancel", "canceldownload", "setthumb", "delthumb", "viewthumb", "addadmin", "removeadmin", "setpremium", "removepremium", "ban", "unban", "broadcast", "adminstats", "userinfo"]))
@force_subscribe
@check_download_limit
async def handle_any_message(bot: Client, message: Message):
    if message.text and not message.text.startswith("/"):
        # Check if user has personal session
        user_client = await get_user_client(message.from_user.id)

        await track_task(handle_download(bot, message, message.text, user_client, True), message.from_user.id)

@bot.on_message(filters.command("stats") & filters.private)
@register_user
async def stats(_, message: Message):
    currentTime = get_readable_time(int(time() - PyroConf.BOT_START_TIME))
    total, used, free = shutil.disk_usage(".")
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
    recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
    cpuUsage = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    process = psutil.Process(os.getpid())

    stats_text = (
        "**≧◉◡◉≦ Bot is Up and Running successfully.**\n\n"
        f"**➜ Bot Uptime:** `{currentTime}`\n"
        f"**➜ Total Disk Space:** `{total}`\n"
        f"**➜ Used:** `{used}`\n"
        f"**➜ Free:** `{free}`\n"
        f"**➜ Memory Usage:** `{round(process.memory_info()[0] / 1024**2)} MiB`\n\n"
        f"**➜ Upload:** `{sent}`\n"
        f"**➜ Download:** `{recv}`\n\n"
        f"**➜ CPU:** `{cpuUsage}%` | "
        f"**➜ RAM:** `{memory}%` | "
        f"**➜ DISK:** `{disk}%`"
    )
    await message.reply(stats_text)

@bot.on_message(filters.command("logs") & filters.private)
@admin_only
async def logs(_, message: Message):
    if os.path.exists("logs.txt"):
        await message.reply_document(document="logs.txt", caption="**Logs**")
    else:
        await message.reply("**Not exists**")

@bot.on_message(filters.command("killall") & filters.private)
@admin_only
async def cancel_all_tasks(_, message: Message):
    cancelled = 0
    for task in list(RUNNING_TASKS):
        if not task.done():
            task.cancel()
            cancelled += 1
    await message.reply(f"**Cancelled {cancelled} running task(s).**")

# Thumbnail commands
@bot.on_message(filters.command("setthumb") & filters.private)
@register_user
async def set_thumbnail(_, message: Message):
    """Set custom thumbnail for video uploads"""
    if message.reply_to_message and message.reply_to_message.photo:
        # User replied to a photo
        photo = message.reply_to_message.photo
        file_id = photo.file_id
        
        if db.set_custom_thumbnail(message.from_user.id, file_id):
            await message.reply(
                "✅ **Custom thumbnail saved successfully!**\n\n"
                "This thumbnail will be used for all your video downloads.\n\n"
                "Use `/delthumb` to remove it."
            )
            LOGGER(__name__).info(f"User {message.from_user.id} set custom thumbnail")
        else:
            await message.reply("❌ **Failed to save thumbnail. Please try again.**")
    else:
        await message.reply(
            "📸 **How to set a custom thumbnail:**\n\n"
            "1. Send or forward a photo to the bot\n"
            "2. Reply to that photo with `/setthumb`\n\n"
            "The photo will be used as thumbnail for all your video downloads."
        )

@bot.on_message(filters.command("delthumb") & filters.private)
@register_user
async def delete_thumbnail(_, message: Message):
    """Delete custom thumbnail"""
    if db.delete_custom_thumbnail(message.from_user.id):
        await message.reply(
            "✅ **Custom thumbnail removed!**\n\n"
            "Videos will now use auto-generated thumbnails from the video itself."
        )
        LOGGER(__name__).info(f"User {message.from_user.id} deleted custom thumbnail")
    else:
        await message.reply("ℹ️ **You don't have a custom thumbnail set.**")

@bot.on_message(filters.command("viewthumb") & filters.private)
@register_user
async def view_thumbnail(_, message: Message):
    """View current custom thumbnail"""
    thumb_id = db.get_custom_thumbnail(message.from_user.id)
    if thumb_id:
        try:
            await message.reply_photo(
                thumb_id,
                caption="**Your current custom thumbnail**\n\nUse `/delthumb` to remove it."
            )
        except:
            await message.reply(
                "⚠️ **Thumbnail exists but couldn't be displayed.**\n\n"
                "It might have expired. Please set a new one with `/setthumb`"
            )
    else:
        await message.reply(
            "ℹ️ **You don't have a custom thumbnail set.**\n\n"
            "Use `/setthumb` to set one."
        )

# Admin commands
@bot.on_message(filters.command("addadmin") & filters.private)
async def add_admin_handler(client: Client, message: Message):
    await add_admin_command(client, message)

@bot.on_message(filters.command("removeadmin") & filters.private)
async def remove_admin_handler(client: Client, message: Message):
    await remove_admin_command(client, message)

@bot.on_message(filters.command("setpremium") & filters.private)
async def set_premium_handler(client: Client, message: Message):
    await set_premium_command(client, message)

@bot.on_message(filters.command("removepremium") & filters.private)
async def remove_premium_handler(client: Client, message: Message):
    await remove_premium_command(client, message)

@bot.on_message(filters.command("ban") & filters.private)
async def ban_user_handler(client: Client, message: Message):
    await ban_user_command(client, message)

@bot.on_message(filters.command("unban") & filters.private)
async def unban_user_handler(client: Client, message: Message):
    await unban_user_command(client, message)

@bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_handler(client: Client, message: Message):
    await broadcast_command(client, message)

@bot.on_message(filters.command("adminstats") & filters.private)
async def admin_stats_handler(client: Client, message: Message):
    await admin_stats_command(client, message)

@bot.on_message(filters.command("upgrade") & filters.private)
@register_user
async def upgrade_command(client: Client, message: Message):
    """Show premium upgrade information with pricing and payment details"""
    upgrade_text = (
        "💎 **Upgrade to Premium**\n\n"
        "**Premium Features:**\n"
        "✅ Unlimited downloads per day\n"
        "✅ Batch download support (/bdl command)\n"
        "✅ Download up to 20 posts at once\n"
        "✅ Priority support\n"
        "✅ No daily limits\n\n"
        "**Pricing:**\n"
        "💰 **30 Days Premium = $1 USD**\n\n"
        "**How to Upgrade:**\n"
    )
    
    # Add payment information if configured
    if PyroConf.PAYPAL_URL or PyroConf.UPI_ID:
        upgrade_text += "1️⃣ **Make Payment:**\n"
        
        if PyroConf.PAYPAL_URL:
            upgrade_text += f"   💳 PayPal: {PyroConf.PAYPAL_URL}\n"
        
        if PyroConf.UPI_ID:
            upgrade_text += f"   📱 UPI: `{PyroConf.UPI_ID}`\n"
        
        upgrade_text += "\n"
    
    # Add contact information
    if PyroConf.ADMIN_USERNAME:
        upgrade_text += f"2️⃣ **Contact Admin:**\n   👤 @{PyroConf.ADMIN_USERNAME}\n\n"
    else:
        upgrade_text += f"2️⃣ **Contact Admin:**\n   👤 Contact the bot owner\n\n"
    
    upgrade_text += (
        "3️⃣ **Send Payment Proof:**\n"
        "   Send screenshot/transaction ID to admin\n\n"
        "4️⃣ **Get Activated:**\n"
        "   Admin will activate your premium within 24 hours!\n\n"
        "**Note:** Premium subscription is valid for 30 days from activation."
    )
    
    await message.reply(upgrade_text, disable_web_page_preview=True)

@bot.on_message(filters.command("premiumlist") & filters.private)
async def premium_list_command(client: Client, message: Message):
    """Show list of all premium users (Owner only)"""
    if message.from_user.id != PyroConf.OWNER_ID:
        await message.reply("❌ **This command is only available to the bot owner.**")
        return
    
    premium_users = db.get_premium_users()
    
    if not premium_users:
        await message.reply("ℹ️ **No premium users found.**")
        return
    
    premium_text = "💎 **Premium Users List**\n\n"
    
    for idx, user in enumerate(premium_users, 1):
        user_id = user.get('user_id', 'Unknown')
        username = user.get('username', 'N/A')
        expiry_date = user.get('premium_expiry', 'N/A')
        
        premium_text += f"{idx}. **User ID:** `{user_id}`\n"
        if username and username != 'N/A':
            premium_text += f"   **Username:** @{username}\n"
        premium_text += f"   **Expires:** {expiry_date}\n\n"
    
    premium_text += f"**Total Premium Users:** {len(premium_users)}"
    
    await message.reply(premium_text)

@bot.on_message(filters.command("myinfo") & filters.private)
async def myinfo_handler(client: Client, message: Message):
    await user_info_command(client, message)

# Callback query handler
@bot.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    await broadcast_callback_handler(client, callback_query)

if __name__ == "__main__":
    try:
        LOGGER(__name__).info("Bot Started!")
        bot.run()
    except KeyboardInterrupt:
        pass
    except Exception as err:
        LOGGER(__name__).error(err)
    finally:
        LOGGER(__name__).info("Bot Stopped")