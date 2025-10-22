"""
Wrapper to run Telegram bot with Flask web server for Render deployment
This satisfies Render's port binding requirement while keeping the bot running
Optimized for Render's 100GB/month bandwidth limit
"""
import os
import sys
from flask import Flask, jsonify, render_template, request, Response
from flask_compress import Compress
from ad_monetization import ad_monetization

app = Flask(__name__)

# Enable gzip compression to reduce bandwidth (saves ~70% on text responses)
compress = Compress()
compress.init_app(app)

@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'message': 'Telegram Bot is running!',
        'bot': 'Restricted Content Downloader'
    })

@app.route('/health')
def health():
    # Return minimal response to save bandwidth (8,640 pings/month from UptimeRobot)
    # HTTP 204 No Content = 0 bytes body vs JSON = ~20 bytes
    return '', 204

@app.route('/watch-ad')
def watch_ad():
    session_id = request.args.get('session', '')
    
    # Get ad codes from config (these are safe as they're from env vars, not user input)
    from config import PyroConf
    ad_code_1 = getattr(PyroConf, 'AD_CODE_1', '')
    ad_code_2 = getattr(PyroConf, 'AD_CODE_2', '')
    ad_code_3 = getattr(PyroConf, 'AD_CODE_3', '')
    
    response = app.make_response(render_template('ad_verify.html', 
                         session=session_id,
                         ad_code_1=ad_code_1,
                         ad_code_2=ad_code_2,
                         ad_code_3=ad_code_3))
    
    # Add security headers
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' https:; frame-src https:; script-src 'self' 'unsafe-inline' https:;"
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    
    # Cache ad page for 1 hour to reduce bandwidth
    response.headers['Cache-Control'] = 'public, max-age=3600'
    
    return response

@app.route('/verify-ad')
def verify_ad():
    """GET endpoint to verify ad completion and get verification code"""
    session_id = request.args.get('session', '')
    
    success, code, message = ad_monetization.verify_ad_completion(session_id)
    
    return jsonify({
        'success': success,
        'code': code,
        'message': message
    })

@app.route('/api/verify-session', methods=['POST'])
def verify_session():
    """API endpoint to verify ad completion and get verification code"""
    data = request.get_json()
    session_id = data.get('session', '')
    
    success, code, message = ad_monetization.verify_ad_completion(session_id)
    
    return jsonify({
        'success': success,
        'code': code,
        'message': message
    })

def run_bot():
    """Run the Telegram bot in a background thread with long polling"""
    import asyncio
    
    # Set uvloop policy for better performance (before creating loop)
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass
    
    # Create and set event loop BEFORE importing main
    # This ensures Pyrogram Client has an event loop during initialization
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Now import main - Pyrogram will see the event loop
    import main
    
    async def start_bot():
        """Start bot without signal handlers (thread-safe)"""
        try:
            main.LOGGER(__name__).info("Starting Telegram bot from server.py (long polling)")
            await main.bot.start()
            main.LOGGER(__name__).info("Bot started successfully, waiting for updates...")
            # Keep the bot running without signal handlers (thread-safe alternative to idle())
            await asyncio.Event().wait()
        finally:
            await main.bot.stop()
            main.LOGGER(__name__).info("Bot stopped")
    
    # Run the async coroutine on this thread's event loop
    loop.run_until_complete(start_bot())

# Start bot process when app initializes (for Gunicorn workers)
import threading
bot_started = False
bot_lock = threading.Lock()

def start_bot_once():
    """Start bot only once across all workers"""
    global bot_started
    with bot_lock:
        if not bot_started:
            print(f"Starting Telegram bot in background thread...")
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            bot_started = True

# Start bot when module loads (for Gunicorn)
start_bot_once()

if __name__ == '__main__':
    # This runs only for development (Replit, local testing)
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask development server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
