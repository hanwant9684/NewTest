import os
import secrets
from datetime import datetime, timedelta

from logger import LOGGER
try:
    from database_sqlite import db
except ImportError:
    from database import db

PREMIUM_DOWNLOADS = 5
SESSION_VALIDITY_MINUTES = 30

class AdMonetization:
    def __init__(self):
        # Check all URL shortener API keys
        self.services = {
            'droplink': os.getenv('DROPLINK_API_KEY'),
            'gplinks': os.getenv('GPLINKS_API_KEY'),
            'arlinks': os.getenv('ARLINKS_API_KEY'),
            'upshrink': os.getenv('UPSHRINK_API_KEY')
        }
        
        configured_services = [name for name, key in self.services.items() if key]
        if configured_services:
            LOGGER(__name__).info(f"URL shortener services configured: {', '.join(configured_services)}")
        else:
            LOGGER(__name__).warning("No URL shortener API keys configured - ad monetization disabled")
    
    def create_ad_session(self, user_id: int) -> str:
        """Create a temporary session for ad watching"""
        session_id = secrets.token_hex(16)
        db.create_ad_session(session_id, user_id)
        
        LOGGER(__name__).info(f"Created ad session {session_id} for user {user_id}")
        return session_id
    
    def verify_ad_completion(self, session_id: str) -> tuple[bool, str, str]:
        """Verify that user clicked through droplink and generate verification code"""
        session_data = db.get_ad_session(session_id)
        
        if not session_data:
            return False, "", "❌ Invalid or expired session. Please start over with /getpremium"
        
        # Check if session expired (30 minutes max)
        elapsed_time = datetime.now() - session_data['created_at']
        if elapsed_time > timedelta(minutes=SESSION_VALIDITY_MINUTES):
            db.delete_ad_session(session_id)
            return False, "", "⏰ Session expired. Please start over with /getpremium"
        
        # Atomically mark session as used (prevents race condition)
        success = db.mark_ad_session_used(session_id)
        if not success:
            return False, "", "❌ This session has already been used. Please use /getpremium to get a new link."
        
        # Generate verification code
        verification_code = self._generate_verification_code(session_data['user_id'])
        
        # Delete session after successful verification
        db.delete_ad_session(session_id)
        
        LOGGER(__name__).info(f"User {session_data['user_id']} completed ad session {session_id}, generated code {verification_code}")
        return True, verification_code, "✅ Ad completed! Here's your verification code"
    
    def _generate_verification_code(self, user_id: int) -> str:
        """Generate verification code after ad is watched"""
        code = secrets.token_hex(4).upper()
        db.create_verification_code(code, user_id)
        
        LOGGER(__name__).info(f"Generated verification code {code} for user {user_id}")
        return code
    
    def verify_code(self, code: str, user_id: int) -> tuple[bool, str]:
        """Verify user's code and grant free downloads"""
        code = code.upper().strip()
        
        verification_data = db.get_verification_code(code)
        
        if not verification_data:
            return False, "❌ **Invalid verification code.**\n\nPlease make sure you entered the code correctly or get a new one with `/getpremium`"
        
        if verification_data['user_id'] != user_id:
            return False, "❌ **This verification code belongs to another user.**"
        
        created_at = verification_data['created_at']
        if datetime.now() - created_at > timedelta(minutes=30):
            db.delete_verification_code(code)
            return False, "⏰ **Verification code has expired.**\n\nCodes expire after 30 minutes. Please get a new one with `/getpremium`"
        
        db.delete_verification_code(code)
        
        # Grant ad downloads
        db.add_ad_downloads(user_id, PREMIUM_DOWNLOADS)
        
        # Rotate user to next shortener for their next /getpremium request
        # This ensures each user gets a different shortener service each time
        db.rotate_user_shortener(user_id)
        
        LOGGER(__name__).info(f"User {user_id} successfully verified code {code}, granted {PREMIUM_DOWNLOADS} ad downloads")
        return True, f"✅ **Verification successful!**\n\nYou now have **{PREMIUM_DOWNLOADS} free download(s)**!"
    
    def _shorten_with_droplink_only(self, long_url: str) -> str:
        """Shorten URL using droplink.co API without fallback"""
        try:
            import orjson
        except ImportError:
            import json as orjson
        from urllib.request import urlopen, Request
        from urllib.parse import urlencode
        from urllib.error import URLError, HTTPError
        
        api_key = self.services.get('droplink')
        if not api_key:
            LOGGER(__name__).error("DROPLINK_API_KEY not configured!")
            return long_url
        
        try:
            params = urlencode({"api": api_key, "url": long_url})
            url = f"https://droplink.co/api?{params}"
            
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=10) as response:
                data = orjson.loads(response.read())
                
                if data.get("status") == "success":
                    short_url = data.get("shortenedUrl")
                    
                    if short_url:
                        LOGGER(__name__).info(f"Successfully shortened URL via droplink.co: {short_url}")
                        return short_url
                    else:
                        LOGGER(__name__).error(f"Droplink API response missing shortenedUrl: {data}")
                else:
                    LOGGER(__name__).error(f"Droplink API returned non-success status: {data}")
        
        except (URLError, HTTPError) as e:
            LOGGER(__name__).error(f"Failed to shorten URL with droplink.co: {e}")
        except Exception as e:
            LOGGER(__name__).error(f"Failed to shorten URL with droplink.co: {e}")
        
        return long_url
    
    def _shorten_with_droplink(self, long_url: str) -> str:
        """Shorten URL using droplink.co API (using urllib instead of requests)"""
        return self._shorten_with_droplink_only(long_url)
    
    def _shorten_with_gplinks_only(self, long_url: str) -> str:
        """Shorten URL using gplinks.co API without fallback"""
        try:
            import orjson
        except ImportError:
            import json as orjson
        from urllib.request import urlopen, Request
        from urllib.parse import urlencode
        from urllib.error import URLError, HTTPError
        
        api_key = self.services.get('gplinks')
        if not api_key:
            LOGGER(__name__).warning("GPLINKS_API_KEY not configured")
            return long_url
        
        try:
            params = urlencode({"api": api_key, "url": long_url})
            url = f"https://api.gplinks.com/api?{params}"
            
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=10) as response:
                data = orjson.loads(response.read())
                
                if data.get("status") == "success":
                    short_url = data.get("shortenedUrl")
                    
                    if short_url:
                        LOGGER(__name__).info(f"Successfully shortened URL via gplinks.com: {short_url}")
                        return short_url
                    else:
                        LOGGER(__name__).error(f"GPLinks API response missing shortenedUrl: {data}")
                else:
                    LOGGER(__name__).error(f"GPLinks API returned non-success status: {data}")
        
        except (URLError, HTTPError) as e:
            LOGGER(__name__).error(f"Failed to shorten URL with gplinks.com: {e}")
        except Exception as e:
            LOGGER(__name__).error(f"Failed to shorten URL with gplinks.com: {e}")
        
        return long_url
    
    def _shorten_with_gplinks(self, long_url: str) -> str:
        """Shorten URL using gplinks.co API (using urllib instead of requests)"""
        result = self._shorten_with_gplinks_only(long_url)
        if result == long_url:
            LOGGER(__name__).info("Falling back to droplink.co")
            return self._shorten_with_droplink(long_url)
        return result
    
    def _shorten_with_arlinks_only(self, long_url: str) -> str:
        """Shorten URL using arlinks.in API without fallback"""
        try:
            import orjson
        except ImportError:
            import json as orjson
        from urllib.request import urlopen, Request
        from urllib.parse import urlencode
        from urllib.error import URLError, HTTPError
        
        api_key = self.services.get('arlinks')
        if not api_key:
            LOGGER(__name__).warning("ARLINKS_API_KEY not configured")
            return long_url
        
        try:
            params = urlencode({"api": api_key, "url": long_url})
            url = f"https://arlinks.in/api?{params}"
            
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=10) as response:
                data = orjson.loads(response.read())
                
                if data.get("status") == "success":
                    short_url = data.get("shortenedUrl")
                    
                    if short_url:
                        LOGGER(__name__).info(f"Successfully shortened URL via arlinks.in: {short_url}")
                        return short_url
                    else:
                        LOGGER(__name__).error(f"ARLinks API response missing shortenedUrl: {data}")
                else:
                    LOGGER(__name__).error(f"ARLinks API returned non-success status: {data}")
        
        except (URLError, HTTPError) as e:
            LOGGER(__name__).error(f"Failed to shorten URL with arlinks.in: {e}")
        except Exception as e:
            LOGGER(__name__).error(f"Failed to shorten URL with arlinks.in: {e}")
        
        return long_url
    
    def _shorten_with_arlinks(self, long_url: str) -> str:
        """Shorten URL using arlinks.in API (using urllib instead of requests)"""
        result = self._shorten_with_arlinks_only(long_url)
        if result == long_url:
            LOGGER(__name__).info("Falling back to droplink.co")
            return self._shorten_with_droplink(long_url)
        return result
    
    def _shorten_with_upshrink_only(self, long_url: str) -> str:
        """Shorten URL using upshrink.com API without fallback"""
        try:
            import orjson
        except ImportError:
            import json as orjson
        from urllib.request import urlopen, Request
        from urllib.parse import urlencode
        from urllib.error import URLError, HTTPError
        
        api_key = self.services.get('upshrink')
        if not api_key:
            LOGGER(__name__).warning("UPSHRINK_API_KEY not configured")
            return long_url
        
        try:
            params = urlencode({"api": api_key, "url": long_url})
            url = f"https://upshrink.com/api?{params}"
            
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=10) as response:
                data = orjson.loads(response.read())
                
                if data.get("status") == "success":
                    short_url = data.get("shortenedUrl")
                    
                    if short_url:
                        LOGGER(__name__).info(f"Successfully shortened URL via upshrink.com: {short_url}")
                        return short_url
                    else:
                        LOGGER(__name__).error(f"UpShrink API response missing shortenedUrl: {data}")
                else:
                    LOGGER(__name__).error(f"UpShrink API returned non-success status: {data}")
        
        except (URLError, HTTPError) as e:
            LOGGER(__name__).error(f"Failed to shorten URL with upshrink.com: {e}")
        except Exception as e:
            LOGGER(__name__).error(f"Failed to shorten URL with upshrink.com: {e}")
        
        return long_url
    
    def _shorten_with_upshrink(self, long_url: str) -> str:
        """Shorten URL using upshrink.com API (using urllib instead of requests)"""
        result = self._shorten_with_upshrink_only(long_url)
        if result == long_url:
            LOGGER(__name__).info("Falling back to droplink.co")
            return self._shorten_with_droplink(long_url)
        return result
    
    def _try_next_shortener(self, long_url: str, start_index: int, user_id: int) -> tuple[str, str]:
        """Try shorteners in rotation starting from start_index until one succeeds"""
        service_map = {
            0: ('droplink', self._shorten_with_droplink_only),
            1: ('gplinks', self._shorten_with_gplinks_only),
            2: ('arlinks', self._shorten_with_arlinks_only),
            3: ('upshrink', self._shorten_with_upshrink_only)
        }
        
        # Try all 4 services in rotation
        for i in range(4):
            index = (start_index + i) % 4
            service_name, shorten_func = service_map[index]
            
            # Check if this service has API key configured
            if not self.services.get(service_name):
                LOGGER(__name__).info(f"User {user_id}: {service_name} API key not configured, trying next...")
                continue
            
            LOGGER(__name__).info(f"User {user_id}: Attempting to shorten with {service_name} (index {index})")
            short_url = shorten_func(long_url)
            
            # If shortening succeeded (URL changed), return it
            if short_url != long_url:
                LOGGER(__name__).info(f"User {user_id}: Successfully shortened URL with {service_name}")
                return short_url, service_name
            else:
                LOGGER(__name__).warning(f"User {user_id}: {service_name} failed or returned original URL, trying next...")
        
        # All services failed or not configured
        LOGGER(__name__).error(f"User {user_id}: All shortener services failed or not configured. User will access bot directly (no ads, no revenue).")
        return long_url, "none"
    
    def generate_droplink_ad_link(self, user_id: int, bot_domain: str | None = None) -> tuple[str, str]:
        """Generate monetized ad link using per-user rotation system
        
        Each user gets different shortener on each /getpremium request:
        1st request: Droplink -> 2nd: GPLinks -> 3rd: ARLinks -> 4th: UpShrink -> 5th: Droplink (cycle repeats)
        
        If a shortener is not configured or fails, automatically tries the next one in rotation.
        """
        session_id = self.create_ad_session(user_id)
        
        # Get user's current shortener index (per-user rotation, not global)
        current_index = db.get_user_shortener_index(user_id)
        
        LOGGER(__name__).info(f"User {user_id}: Generating ad link starting with index {current_index}")
        
        if bot_domain:
            verify_url = f"{bot_domain}/verify-ad?session={session_id}"
            LOGGER(__name__).info(f"User {user_id}: Original verify URL: {verify_url}")
            
            # Try shorteners in rotation until one succeeds
            short_url, used_service = self._try_next_shortener(verify_url, current_index, user_id)
            
            # Log whether shortening succeeded
            if short_url == verify_url:
                LOGGER(__name__).warning(f"User {user_id}: All URL shorteners failed. User will access bot directly (no ads, no revenue).")
            else:
                LOGGER(__name__).info(f"User {user_id}: Successfully shortened URL to: {short_url} using {used_service}")
            
            return session_id, short_url
        
        LOGGER(__name__).error(f"User {user_id}: No bot_domain configured! Cannot generate verification URL.")
        return session_id, "https://example.com/verify"
    
    def get_premium_downloads(self) -> int:
        """Get number of downloads given for watching ads"""
        return PREMIUM_DOWNLOADS

ad_monetization = AdMonetization()
