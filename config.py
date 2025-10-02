# Copyright (C) @Wolfy004
# Channel: https://t.me/Wolfy004

import os
from time import time
from dotenv import load_dotenv

load_dotenv("config.env")

class PyroConf:
    try:
        API_ID = int(os.getenv("API_ID", "0"))
    except ValueError:
        API_ID = 0

    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    SESSION_STRING = os.getenv("SESSION_STRING", "")

    try:
        OWNER_ID = int(os.getenv("OWNER_ID", "0"))
    except ValueError:
        OWNER_ID = 0

    FORCE_SUBSCRIBE_CHANNEL = os.getenv("FORCE_SUBSCRIBE_CHANNEL", "")

    # Payment and Contact Configuration
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
    PAYPAL_URL = os.getenv("PAYPAL_URL", "")
    UPI_ID = os.getenv("UPI_ID", "")

    BOT_START_TIME = time()
