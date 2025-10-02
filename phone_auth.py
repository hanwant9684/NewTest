# Phone Number Authentication Handler
# Copyright (C) @Wolfy004

import os
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid, FloodWait
from logger import LOGGER

class PhoneAuthHandler:
    """Handle phone number based authentication for users"""

    def __init__(self, api_id, api_hash):
        self.api_id = api_id
        self.api_hash = api_hash
        self.pending_auth = {}

    async def send_otp(self, user_id: int, phone_number: str):
        """
        Send OTP to user's phone number
        Returns: (success: bool, message: str, phone_code_hash: str or None)
        """
        try:
            session_name = f"user_{user_id}"

            client = Client(
                session_name,
                api_id=self.api_id,
                api_hash=self.api_hash,
                workers=8,
                max_concurrent_transmissions=8
            )

            await client.connect()

            sent_code_info = await client.send_code(phone_number)
            phone_code_hash = sent_code_info.phone_code_hash

            self.pending_auth[user_id] = {
                'phone_number': phone_number,
                'phone_code_hash': phone_code_hash,
                'client': client,
                'session_name': session_name
            }

            LOGGER(__name__).info(f"OTP sent to {phone_number} for user {user_id}")

            return True, f"✅ **OTP sent to {phone_number}**\n\nPlease send the code using:\n`/verify 1 2 3 4 5` (with spaces between each digit)\n\n**Example:** If code is 12345, send:\n`/verify 1 2 3 4 5`", phone_code_hash

        except FloodWait as e:
            LOGGER(__name__).error(f"FloodWait error: {e}")
            return False, f"❌ **Rate limit exceeded. Please wait {e.value} seconds before trying again.**", None

        except Exception as e:
            LOGGER(__name__).error(f"Error sending OTP to {phone_number}: {e}")
            return False, f"❌ **Failed to send OTP: {str(e)}**\n\nMake sure the phone number is in international format (e.g., +1234567890)", None

    async def verify_otp(self, user_id: int, otp_code: str):
        """
        Verify OTP code
        Returns: (success: bool, message: str, needs_2fa: bool)
        """
        if user_id not in self.pending_auth:
            return False, "❌ **No pending authentication found.**\n\nPlease start with `/login <phone_number>` first.", False

        auth_data = self.pending_auth[user_id]
        client = auth_data['client']
        phone_number = auth_data['phone_number']
        phone_code_hash = auth_data['phone_code_hash']

        # Strip spaces and any non-digit characters from OTP code
        # This allows users to enter codes like "1 2 3 4 5" or "12345"
        cleaned_code = ''.join(filter(str.isdigit, otp_code))

        try:
            await client.sign_in(
                phone_number=phone_number,
                phone_code_hash=phone_code_hash,
                phone_code=cleaned_code
            )

            session_string = await client.export_session_string()

            await client.disconnect()

            del self.pending_auth[user_id]

            LOGGER(__name__).info(f"User {user_id} successfully authenticated with phone {phone_number}")

            return True, "✅ **Authentication successful!**\n\nYou can now download content from channels you've joined.", False, session_string

        except SessionPasswordNeeded:
            LOGGER(__name__).info(f"2FA required for user {user_id}")
            return False, "🔐 **Two-Factor Authentication (2FA) detected!**\n\nPlease send your 2FA password using:\n`/password <YOUR_2FA_PASSWORD>`", True, None

        except PhoneCodeInvalid:
            LOGGER(__name__).error(f"Invalid OTP for user {user_id}")
            return False, "❌ **Invalid OTP code.**\n\nPlease try again with `/verify 1 2 3 4 5` (spaces between digits)\n\nOr restart the process with `/login <phone_number>`", False, None

        except Exception as e:
            LOGGER(__name__).error(f"Error verifying OTP for user {user_id}: {e}")

            if user_id in self.pending_auth:
                try:
                    await self.pending_auth[user_id]['client'].disconnect()
                except:
                    pass
                del self.pending_auth[user_id]

            return False, f"❌ **Verification failed: {str(e)}**\n\nPlease restart with `/login <phone_number>`", False, None

    async def verify_2fa_password(self, user_id: int, password: str):
        """
        Verify 2FA password
        Returns: (success: bool, message: str, session_string: str or None)
        """
        if user_id not in self.pending_auth:
            return False, "❌ **No pending authentication found.**\n\nPlease start with `/login <phone_number>` first.", None

        auth_data = self.pending_auth[user_id]
        client = auth_data['client']

        try:
            await client.check_password(password)

            session_string = await client.export_session_string()

            await client.disconnect()

            del self.pending_auth[user_id]

            LOGGER(__name__).info(f"User {user_id} successfully authenticated with 2FA")

            return True, "✅ **Authentication successful!**\n\nYou can now download content from channels you've joined.", session_string

        except PasswordHashInvalid:
            LOGGER(__name__).error(f"Invalid 2FA password for user {user_id}")
            return False, "❌ **Invalid 2FA password.**\n\nPlease try again with `/password <YOUR_2FA_PASSWORD>`\n\nOr restart the process with `/login <phone_number>`", None

        except Exception as e:
            LOGGER(__name__).error(f"Error verifying 2FA for user {user_id}: {e}")

            if user_id in self.pending_auth:
                try:
                    await self.pending_auth[user_id]['client'].disconnect()
                except:
                    pass
                del self.pending_auth[user_id]

            return False, f"❌ **2FA verification failed: {str(e)}**\n\nPlease restart with `/login <phone_number>`", None

    async def cancel_auth(self, user_id: int):
        """Cancel pending authentication"""
        if user_id in self.pending_auth:
            try:
                await self.pending_auth[user_id]['client'].disconnect()
            except:
                pass
            del self.pending_auth[user_id]
            return True, "✅ **Authentication cancelled.**"
        return False, "❌ **No pending authentication to cancel.**"

    def has_pending_auth(self, user_id: int) -> bool:
        """Check if user has pending authentication"""
        return user_id in self.pending_auth