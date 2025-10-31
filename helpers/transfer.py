import os
import asyncio
import math
from typing import Optional, Callable, BinaryIO
from telethon import TelegramClient, utils
from telethon.tl.types import Message, Document, TypeMessageMedia, InputPhotoFileLocation, InputDocumentFileLocation
from logger import LOGGER
from FastTelethon import download_file as fast_download, upload_file as fast_upload, ParallelTransferrer

IS_CONSTRAINED = bool(
    os.getenv('RENDER') or 
    os.getenv('RENDER_EXTERNAL_URL') or 
    os.getenv('REPLIT_DEPLOYMENT') or 
    os.getenv('REPL_ID')
)

# Optimized for Render free plan (512MB RAM)
# Higher connection counts = faster downloads/uploads
# Each connection uses ~5-10MB RAM, so 8 connections = ~80MB max
MAX_DOWNLOAD_CONNECTIONS = 8 if IS_CONSTRAINED else 10
MAX_UPLOAD_CONNECTIONS = 4 if IS_CONSTRAINED else 6

async def download_media_fast(
    client: TelegramClient,
    message: Message,
    file: str,
    progress_callback: Optional[Callable] = None
) -> str:
    if not message.media:
        raise ValueError("Message has no media")
    
    try:
        media = None
        file_size = 0
        
        if message.document:
            media = message.document
            file_size = message.document.size
        elif message.video:
            media = message.video
            file_size = getattr(message.video, 'size', 0)
        elif message.audio:
            media = message.audio
            file_size = getattr(message.audio, 'size', 0)
        elif message.photo:
            photo_sizes = [size for size in message.photo.sizes if hasattr(size, 'size')]
            if not photo_sizes:
                LOGGER(__name__).warning("No valid photo sizes found, using standard download")
                return await client.download_media(message, file=file, progress_callback=progress_callback)
            
            largest_size = max(photo_sizes, key=lambda s: s.size)
            file_size = largest_size.size
            
            media = InputPhotoFileLocation(
                id=message.photo.id,
                access_hash=message.photo.access_hash,
                file_reference=message.photo.file_reference,
                thumb_size=largest_size.type
            )
        else:
            raise ValueError("Unsupported media type")
        
        # Use FastTelethon for files >= 512KB (lowered from 1MB for better speed)
        if file_size < 512 * 1024:
            LOGGER(__name__).debug(f"Small file ({file_size} bytes), using standard download")
            return await client.download_media(message, file=file, progress_callback=progress_callback)
        
        LOGGER(__name__).info(f"FastTelethon download starting: {file} ({file_size} bytes, {MAX_DOWNLOAD_CONNECTIONS} connections)")
        
        with open(file, 'wb') as f:
            await fast_download(
                client=client,
                location=media,
                out=f,
                progress_callback=progress_callback,
                file_size=file_size
            )
        
        LOGGER(__name__).info(f"FastTelethon download complete: {file}")
        return file
        
    except Exception as e:
        LOGGER(__name__).error(f"FastTelethon download failed, falling back to standard: {e}")
        return await client.download_media(message, file=file, progress_callback=progress_callback)

async def upload_media_fast(
    client: TelegramClient,
    file_path: str,
    progress_callback: Optional[Callable] = None
):
    file_size = os.path.getsize(file_path)
    
    # Use FastTelethon for files >= 512KB (lowered from 1MB for better speed)
    if file_size < 512 * 1024:
        LOGGER(__name__).debug(f"Small file ({file_size} bytes), using standard upload")
        return None
    
    try:
        LOGGER(__name__).info(f"FastTelethon upload starting: {file_path} ({file_size} bytes, {MAX_UPLOAD_CONNECTIONS} connections)")
        
        with open(file_path, 'rb') as f:
            result = await fast_upload(
                client=client,
                file=f,
                progress_callback=progress_callback
            )
        
        LOGGER(__name__).info(f"FastTelethon upload complete: {file_path}")
        return result
        
    except Exception as e:
        LOGGER(__name__).error(f"FastTelethon upload failed: {e}")
        return None

def _optimized_connection_count(file_size, max_count=MAX_DOWNLOAD_CONNECTIONS, full_size=100*1024*1024):
    """
    Dynamically scale connection count based on file size for optimal speed
    - Small files (< 50MB): Use fewer connections to avoid overhead
    - Large files (>= 100MB): Use maximum connections for best speed
    """
    if file_size >= full_size:
        return max_count
    # Use at least 3 connections for files >= 5MB (increased from 2)
    return max(3, math.ceil((file_size / full_size) * max_count))

ParallelTransferrer._get_connection_count = staticmethod(_optimized_connection_count)
