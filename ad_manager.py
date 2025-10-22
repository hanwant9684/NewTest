# Ad Manager - Handles Monetag and OnClicka integrations
# Copyright (C) @Wolfy004

import asyncio
from typing import Optional
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import PyroConf
from logger import LOGGER

class AdManager:
    """Manages different ad networks (Monetag, OnClicka) for bot monetization"""
    
    def __init__(self):
        self.monetag_interstitial_enabled = PyroConf.MONETAG_INTERSTITIAL_ENABLED
        self.onclicka_enabled = PyroConf.ONCLICKA_ENABLED
        self.onclicka_interstitial_enabled = PyroConf.ONCLICKA_INTERSTITIAL_ENABLED
        self.auto_delete_seconds = PyroConf.AD_AUTO_DELETE_SECONDS
        
    async def show_native_banner_ad(self, bot: Client, message: Message, position: str = "start") -> Optional[Message]:
        """
        Show native banner ad in /start or /help messages
        Uses OnClicka native ads - shown as visual preview box
        
        Args:
            bot: Pyrogram client
            message: User message
            position: "start" or "help" to customize ad content
        
        Returns:
            Message object if ad was sent, None otherwise
        """
        if not self.onclicka_enabled or not PyroConf.ONCLICKA_BANNER_ID:
            return None
        
        try:
            # Build OnClicka TMA Inpage URL (for banner position)
            ad_url = f"https://onclicka.com/inpage/{PyroConf.ONCLICKA_BANNER_ID}"
            
            # Show ad with web preview enabled (displays as visual box/card)
            if position == "start":
                ad_text = (
                    f"🎁 **Special Offer!**\n\n"
                    f"{ad_url}"
                )
            else:  # help
                ad_text = (
                    f"💡 **Featured Offer!**\n\n"
                    f"{ad_url}"
                )
            
            # Send with web preview ENABLED to show visual ad box
            sent_ad = await message.reply(
                ad_text,
                disable_web_page_preview=False
            )
            
            # Auto-delete after configured seconds
            asyncio.create_task(self._auto_delete_ad(sent_ad, self.auto_delete_seconds))
            
            LOGGER(__name__).info(f"OnClicka visual banner ad shown to user {message.from_user.id}")
            return sent_ad
            
        except Exception as e:
            LOGGER(__name__).error(f"Error showing OnClicka banner ad: {e}")
            return None
    
    async def show_interstitial_ad(self, bot: Client, message: Message) -> Optional[Message]:
        """
        Show interstitial ad after successful download
        Priority: Monetag (Primary) > OnClicka (Secondary)
        Shown as visual preview box
        
        Args:
            bot: Pyrogram client
            message: User message
        
        Returns:
            Message object if ad was sent, None otherwise
        """
        # Try Monetag first (Primary)
        if self.monetag_interstitial_enabled and PyroConf.MONETAG_INTERSTITIAL_ID:
            try:
                # Build Monetag direct URL
                ad_url = f"https://monetag.com/?zoneId={PyroConf.MONETAG_INTERSTITIAL_ID}"
                
                # Show ad as visual box with web preview
                ad_text = (
                    f"🎉 **Download Complete!**\n\n"
                    f"📺 **Advertisement:**\n\n"
                    f"{ad_url}"
                )
                
                # Send with web preview ENABLED to show visual ad box
                sent_ad = await message.reply(
                    ad_text,
                    disable_web_page_preview=False
                )
                
                # Auto-delete after configured seconds
                asyncio.create_task(self._auto_delete_ad(sent_ad, self.auto_delete_seconds))
                
                LOGGER(__name__).info(f"Monetag visual interstitial ad shown to user {message.from_user.id}")
                return sent_ad
                
            except Exception as e:
                LOGGER(__name__).error(f"Error showing Monetag interstitial ad: {e}")
        
        # Fallback to OnClicka if Monetag not available (Secondary)
        if self.onclicka_interstitial_enabled and PyroConf.ONCLICKA_INTERSTITIAL_ID:
            try:
                # Build OnClicka TMA Inpage URL
                ad_url = f"https://onclicka.com/inpage/{PyroConf.ONCLICKA_INTERSTITIAL_ID}"
                
                # Show ad as visual box with web preview
                ad_text = (
                    f"🎉 **Download Complete!**\n\n"
                    f"📺 **Advertisement:**\n\n"
                    f"{ad_url}"
                )
                
                # Send with web preview ENABLED to show visual ad box
                sent_ad = await message.reply(
                    ad_text,
                    disable_web_page_preview=False
                )
                
                # Auto-delete after configured seconds
                asyncio.create_task(self._auto_delete_ad(sent_ad, self.auto_delete_seconds))
                
                LOGGER(__name__).info(f"OnClicka visual interstitial ad shown to user {message.from_user.id}")
                return sent_ad
                
            except Exception as e:
                LOGGER(__name__).error(f"Error showing OnClicka interstitial ad: {e}")
        
        return None
    
    async def _auto_delete_ad(self, ad_message: Message, delay_seconds: int):
        """
        Auto-delete ad message after specified seconds
        
        Args:
            ad_message: The ad message to delete
            delay_seconds: Seconds to wait before deletion
        """
        try:
            await asyncio.sleep(delay_seconds)
            await ad_message.delete()
            LOGGER(__name__).debug(f"Auto-deleted ad message after {delay_seconds}s")
        except Exception as e:
            LOGGER(__name__).debug(f"Could not auto-delete ad message: {e}")

# Initialize global ad manager
ad_manager = AdManager()
