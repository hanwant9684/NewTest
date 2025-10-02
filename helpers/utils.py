# Copyright (C) @TheSmartBisnu
# Channel: https://t.me/itsSmartDev

import os
from time import time
from PIL import Image
from logger import LOGGER
from typing import Optional
from asyncio.subprocess import PIPE
from asyncio import create_subprocess_exec, create_subprocess_shell, wait_for

from pyleaves import Leaves
from pyrogram.parser import Parser
from pyrogram.utils import get_channel_id
from pyrogram.types import (
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
    InputMediaAudio,
    Voice,
)

from helpers.files import (
    fileSizeLimit,
    cleanup_download
)

from helpers.msg import (
    get_parsed_msg
)

async def process_thumbnail(thumb_path, max_size_kb=200):
    """
    Process thumbnail to meet Telegram requirements:
    - JPEG format
    - <= 200 KB
    - Max 320px width/height
    """
    try:
        with Image.open(thumb_path) as img:
            # Convert to RGB (remove alpha channel if present)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize to fit within 320x320 while maintaining aspect ratio
            img.thumbnail((320, 320), Image.Resampling.LANCZOS)
            
            # Save with compression, iteratively reduce quality if needed
            quality = 95
            while quality > 10:
                img.save(thumb_path, 'JPEG', quality=quality, optimize=True)
                
                # Check file size
                file_size_kb = os.path.getsize(thumb_path) / 1024
                if file_size_kb <= max_size_kb:
                    return True
                
                quality -= 10
            
            # If still too large after minimum quality, return False
            file_size_kb = os.path.getsize(thumb_path) / 1024
            if file_size_kb > max_size_kb:
                LOGGER(__name__).warning(f"Thumbnail still {file_size_kb:.2f} KB after compression")
                return False
            
            return True
    except Exception as e:
        LOGGER(__name__).error(f"Error processing thumbnail: {e}")
        return False

# Progress bar template
PROGRESS_BAR = """
Percentage: {percentage:.2f}% | {current}/{total}
Speed: {speed}/s
Estimated Time Left: {est_time} seconds
"""

async def cmd_exec(cmd, shell=False):
    if shell:
        proc = await create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE)
    else:
        proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    try:
        stdout = stdout.decode().strip()
    except:
        stdout = "Unable to decode the response!"
    try:
        stderr = stderr.decode().strip()
    except:
        stderr = "Unable to decode the error!"
    return stdout, stderr, proc.returncode


async def get_media_info(path):
    try:
        result = await cmd_exec([
            "ffprobe", "-hide_banner", "-loglevel", "error",
            "-print_format", "json", "-show_format", "-show_streams", path,
        ])
    except Exception as e:
        print(f"Get Media Info: {e}. Mostly File not found! - File: {path}")
        return 0, None, None
    
    if result[0] and result[2] == 0:
        try:
            import json
            data = json.loads(result[0])
        except json.JSONDecodeError as e:
            LOGGER(__name__).error(f"Failed to parse ffprobe JSON: {e}")
            return 0, None, None
        
        duration = 0
        artist = None
        title = None
        
        # Try to get duration from format first
        format_info = data.get("format", {})
        if format_info:
            try:
                duration_str = format_info.get("duration", "0")
                if duration_str and duration_str != "N/A":
                    duration = round(float(duration_str))
            except (ValueError, TypeError):
                pass
            
            # Get tags from format
            tags = format_info.get("tags", {})
            artist = tags.get("artist") or tags.get("ARTIST") or tags.get("Artist")
            title = tags.get("title") or tags.get("TITLE") or tags.get("Title")
        
        # If format duration is 0 or missing, try to get from video stream
        if duration == 0:
            streams = data.get("streams", [])
            for stream in streams:
                if stream.get("codec_type") == "video":
                    try:
                        stream_duration = stream.get("duration")
                        if stream_duration and stream_duration != "N/A":
                            duration = round(float(stream_duration))
                            LOGGER(__name__).info(f"Got duration from video stream: {duration}s")
                            break
                    except (ValueError, TypeError):
                        continue
        
        return duration, artist, title
    return 0, None, None


async def get_video_thumbnail(video_file, duration):
    output = os.path.join("Assets", "video_thumb.jpg")
    if duration is None:
        duration = (await get_media_info(video_file))[0]
    if not duration:
        duration = 3
    duration //= 2
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", str(duration), "-i", video_file,
        "-vf", "thumbnail", "-q:v", "1", "-frames:v", "1",
        "-threads", str((os.cpu_count() or 4) // 2), output,
    ]
    try:
        _, err, code = await wait_for(cmd_exec(cmd), timeout=60)
        if code != 0 or not os.path.exists(output):
            return None
    except:
        return None
    return output


# Generate progress bar for downloading/uploading
def progressArgs(action: str, progress_message, start_time):
    return (action, progress_message, start_time, PROGRESS_BAR, "▓", "░")


async def send_media(
    bot, message, media_path, media_type, caption, progress_message, start_time, user_id=None
):
    file_size = os.path.getsize(media_path)

    if not await fileSizeLimit(file_size, message, "upload"):
        return

    progress_args = progressArgs("📥 Uploading Progress", progress_message, start_time)
    LOGGER(__name__).info(f"Uploading media: {media_path} ({media_type})")

    if media_type == "photo":
        await message.reply_photo(
            media_path,
            caption=caption or "",
            progress=Leaves.progress_for_pyrogram,
            progress_args=progress_args,
        )
    elif media_type == "video":
        # Check for custom thumbnail first
        thumb = None
        custom_thumb_path = None
        fallback_thumb = None
        
        if user_id:
            from database import db
            custom_thumb_file_id = db.get_custom_thumbnail(user_id)
            if custom_thumb_file_id:
                try:
                    # Use unique temp path to avoid race conditions
                    import time as time_module
                    timestamp = int(time_module.time() * 1000)
                    os.makedirs("Assets/thumbs", exist_ok=True)
                    custom_thumb_path = f"Assets/thumbs/user_{user_id}_{timestamp}.jpg"
                    
                    # Download the thumbnail from Telegram
                    await bot.download_media(custom_thumb_file_id, file_name=custom_thumb_path)
                    
                    # Process thumbnail to meet Telegram requirements
                    if await process_thumbnail(custom_thumb_path):
                        thumb = custom_thumb_path
                        LOGGER(__name__).info(f"Using custom thumbnail for user {user_id}")
                    else:
                        LOGGER(__name__).warning(f"Failed to process custom thumbnail for user {user_id}, will try fallback")
                        thumb = None
                except Exception as e:
                    LOGGER(__name__).error(f"Failed to download custom thumbnail for user {user_id}: {e}")
                    thumb = None
        
        # Get video duration
        duration = (await get_media_info(media_path))[0]
        
        # If no custom thumbnail, prepare unique fallback thumbnail
        if not thumb:
            import time as time_module
            timestamp = int(time_module.time() * 1000)
            os.makedirs("Assets/thumbs", exist_ok=True)
            fallback_thumb = f"Assets/thumbs/fb_{user_id or 0}_{timestamp}.jpg"
            
            # Extract thumbnail from video to unique path
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-ss", str(duration // 2 if duration else 3), "-i", media_path,
                "-vf", "thumbnail", "-q:v", "1", "-frames:v", "1",
                "-threads", str((os.cpu_count() or 4) // 2), fallback_thumb,
            ]
            try:
                _, err, code = await wait_for(cmd_exec(cmd), timeout=60)
                if code == 0 and os.path.exists(fallback_thumb):
                    thumb = fallback_thumb
                else:
                    thumb = None
            except:
                thumb = None
        
        # Get video dimensions
        if thumb and thumb != "none" and os.path.exists(str(thumb)):
            try:
                with Image.open(thumb) as img:
                    width, height = img.size
            except:
                width = 480
                height = 320
        else:
            width = 480
            height = 320

        if thumb == "none":
            thumb = None

        # Try uploading with thumbnail, fallback on error
        # Only include duration if > 0, otherwise let Telegram compute it
        video_kwargs = {
            "width": width,
            "height": height,
            "thumb": thumb,
            "caption": caption or "",
            "progress": Leaves.progress_for_pyrogram,
            "progress_args": progress_args,
        }
        if duration > 0:
            video_kwargs["duration"] = duration
        
        try:
            await message.reply_video(media_path, **video_kwargs)
        except Exception as e:
            # If thumbnail causes error, try with fallback or no thumb
            LOGGER(__name__).error(f"Upload failed with thumbnail: {e}")
            
            # If custom thumbnail was used, generate fallback now
            if custom_thumb_path and not fallback_thumb:
                LOGGER(__name__).info("Custom thumbnail failed, generating fallback thumbnail")
                try:
                    import time as time_module
                    timestamp = int(time_module.time() * 1000)
                    fallback_thumb = f"Assets/thumbs/fb_{user_id or 0}_{timestamp}.jpg"
                    
                    cmd = [
                        "ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-ss", str(duration // 2 if duration else 3), "-i", media_path,
                        "-vf", "thumbnail", "-q:v", "1", "-frames:v", "1",
                        "-threads", str((os.cpu_count() or 4) // 2), fallback_thumb,
                    ]
                    _, err, code = await wait_for(cmd_exec(cmd), timeout=60)
                    if code != 0 or not os.path.exists(fallback_thumb):
                        fallback_thumb = None
                except:
                    fallback_thumb = None
            
            # Try with fallback thumbnail
            if fallback_thumb:
                LOGGER(__name__).info("Retrying with auto-extracted thumbnail")
                try:
                    video_kwargs["thumb"] = fallback_thumb
                    await message.reply_video(media_path, **video_kwargs)
                except Exception as e2:
                    LOGGER(__name__).error(f"Upload failed with fallback: {e2}, trying without thumbnail")
                    video_kwargs["thumb"] = None
                    await message.reply_video(media_path, **video_kwargs)
            else:
                LOGGER(__name__).info("Retrying without thumbnail")
                video_kwargs["thumb"] = None
                await message.reply_video(media_path, **video_kwargs)
        
        # Clean up thumbnails after upload
        if custom_thumb_path and os.path.exists(custom_thumb_path):
            try:
                os.remove(custom_thumb_path)
            except:
                pass
        if fallback_thumb and os.path.exists(fallback_thumb):
            try:
                os.remove(fallback_thumb)
            except:
                pass
    elif media_type == "audio":
        duration, artist, title = await get_media_info(media_path)
        await message.reply_audio(
            media_path,
            duration=duration,
            performer=artist,
            title=title,
            caption=caption or "",
            progress=Leaves.progress_for_pyrogram,
            progress_args=progress_args,
        )
    elif media_type == "document":
        await message.reply_document(
            media_path,
            caption=caption or "",
            progress=Leaves.progress_for_pyrogram,
            progress_args=progress_args,
        )


async def processMediaGroup(chat_message, bot, message):
    media_group_messages = await chat_message.get_media_group()
    valid_media = []
    temp_paths = []
    invalid_paths = []

    start_time = time()
    progress_message = await message.reply("📥 Downloading media group...")
    LOGGER(__name__).info(
        f"Downloading media group with {len(media_group_messages)} items..."
    )

    for msg in media_group_messages:
        if msg.photo or msg.video or msg.document or msg.audio:
            try:
                media_path = await msg.download(
                    progress=Leaves.progress_for_pyrogram,
                    progress_args=progressArgs(
                        "📥 Downloading Progress", progress_message, start_time
                    ),
                )
                temp_paths.append(media_path)

                if msg.photo:
                    valid_media.append(
                        InputMediaPhoto(
                            media=media_path,
                            caption=await get_parsed_msg(
                                msg.caption or "", msg.caption_entities
                            ),
                        )
                    )
                elif msg.video:
                    duration = (await get_media_info(media_path))[0]
                    valid_media.append(
                        InputMediaVideo(
                            media=media_path,
                            duration=duration,
                            caption=await get_parsed_msg(
                                msg.caption or "", msg.caption_entities
                            ),
                        )
                    )
                elif msg.document:
                    valid_media.append(
                        InputMediaDocument(
                            media=media_path,
                            caption=await get_parsed_msg(
                                msg.caption or "", msg.caption_entities
                            ),
                        )
                    )
                elif msg.audio:
                    valid_media.append(
                        InputMediaAudio(
                            media=media_path,
                            caption=await get_parsed_msg(
                                msg.caption or "", msg.caption_entities
                            ),
                        )
                    )

            except Exception as e:
                LOGGER(__name__).info(f"Error downloading media: {e}")
                media_path = None
                continue

    LOGGER(__name__).info(f"Valid media count: {len(valid_media)}")

    if valid_media:
        try:
            await bot.send_media_group(chat_id=message.chat.id, media=valid_media)
            await progress_message.delete()
        except Exception:
            await message.reply(
                "**❌ Failed to send media group, trying individual uploads**"
            )
            for media in valid_media:
                try:
                    if isinstance(media, InputMediaPhoto):
                        await bot.send_photo(
                            chat_id=message.chat.id,
                            photo=media.media,
                            caption=media.caption,
                        )
                    elif isinstance(media, InputMediaVideo):
                        await bot.send_video(
                            chat_id=message.chat.id,
                            video=media.media,
                            duration=media.duration,
                            caption=media.caption,
                        )
                    elif isinstance(media, InputMediaDocument):
                        await bot.send_document(
                            chat_id=message.chat.id,
                            document=media.media,
                            caption=media.caption,
                        )
                    elif isinstance(media, InputMediaAudio):
                        await bot.send_audio(
                            chat_id=message.chat.id,
                            audio=media.media,
                            caption=media.caption,
                        )
                    elif isinstance(media, Voice):
                        await bot.send_voice(
                            chat_id=message.chat.id,
                            voice=media.media,
                            caption=media.caption,
                        )
                except Exception as individual_e:
                    await message.reply(
                        f"Failed to upload individual media: {individual_e}"
                    )

            await progress_message.delete()

        for path in temp_paths + invalid_paths:
            cleanup_download(path)
        return True

    await progress_message.delete()
    await message.reply("❌ No valid media found in the media group.")
    for path in invalid_paths:
        cleanup_download(path)
    return False
