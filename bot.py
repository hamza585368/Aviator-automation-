import time
import io
import threading
import requests
from PIL import Image
from flask import Flask, send_file, request, redirect
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

# =========================================================================
# USER CONFIGURATION (Aapki saari details pehle se bhari hui hain)
# =========================================================================
SITE_URL = "https://10wicket777.com"
GAME_LOBBY_URL = "https://10wicket777.comaviator"

USERNAME = "WtAvinash"
PASSWORD = "Asdf@1234"

TELEGRAM_BOT_TOKEN = "9029740245:AAGc1on9TUQvGut_V06vRHSkY1N66YSny8A"
TELEGRAM_CHAT_ID = "7431620371"

TARGET_BLUE_COUNT = 10      # Kitne lagatar Asmani Blue (<2x) numbers par alert bhejna hai
CHECK_INTERVAL = 8          # Har kitne second mein screen check karni hai

# Exact click coordinates (720x1520 mobile view)
LOGIN_OPEN_BTN = (655, 112) # Top-right LOGIN button
AVIATOR_CARD_XY = (590, 305)# Lobby mein 'Aviator' game card
HISTORY_BTN_XY = (675, 198) # Round History kholne wala dropdown button

# Opened Round History ke pehle 10 numbers ke center coordinates
BUBBLE_CENTERS = [
    (82, 266), (160, 266), (238, 266), (316, 266),
    (394, 266), (472, 266), (550, 266), (628, 266),
    (82, 310), (160, 310)
]
# =========================================================================

app = Flask(__name__)
alert_sent = False
current_blue_streak = 0
bot_status = "Initializing..."
latest_screenshot = None
pending_clicks = []         # Phone se aane wale live clicks ki queue
pending_url = None          # Phone se URL change karne ka command

def send_telegram(msg):
    url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)

def check_pill_color(img, cx, cy):
    blue_pixels = 0
    purple_pixels = 0
    for x in range(cx - 25, cx + 25, 2):
        for y in range(cy - 10, cy + 10, 2):
            r, g, b = img.getpixel((x, y))
            if b > 140 and b > r + 40:
                blue_pixels += 1
            elif r > 120 and b > 120 and r > g + 30:
                purple_pixels += 1
    if blue_pixels > 4 and blue_pixels > purple_pixels:
        return "BLUE"
    elif purple_pixels > 4:
        return "PURPLE"
    return "UNKNOWN"

def process_user_commands(page):
    global pending_url
    if pending_url:
        url = pending_url
        pending_url = None
        page.goto(url, timeout=60000)
        time.sleep(3)
    while pending_clicks:
        cx, cy = pending_clicks.pop(0)
        page.mouse.click(cx, cy)
        time.sleep(1.5)

def run_bot():
    global alert_sent, current_blue_streak, bot_status, latest_screenshot
    
    while True:
        try:
            with sync_playwright() as p:
                bot_status = "Starting Stealth Browser..."
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-blink-features=AutomationControlled",
                        "--single-process",
                        "--no-zygote",
                        "--js-flags=--max-old-space-size=160"
                    ]
                )
                context = browser.new_context(
                    viewport={"width": 720, "height": 1520},
                    user_agent="Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                    locale="en-IN",
                    timezone_id="Asia/Kolkata"
                )
                page = context.new_page()
                
                # Stealth mode ON (Cloudflare bypass karne ke liye)
                stealth_sync(page)
                
                # 1. Website kholna aur Cloudflare check pass hone ka wait karna
                bot_status = "Opening Website (Waiting for Cloudflare)..."
                page.goto(SITE_URL, timeout=60000)
                time.sleep(8)
                latest_screenshot = page.screenshot()
                
                # LOGIN button par click karna
                page.mouse.click(LOGIN_OPEN_BTN, LOGIN_OPEN_BTN)
                time.sleep(2)
                latest_screenshot = page.screenshot()
                
                # 2. Username aur Password bharna
                bot_status = "Logging in..."
                page.fill('input[placeholder*="Username"], input[type="text"]', USERNAME)
                page.fill('input[placeholder*="Password"], input[type="password"]', PASSWORD)
                page.click('button:has-text("Login")')
                time.sleep(5)
                latest_screenshot = page.screenshot()
                
                # 3. Aviator Lobby par jana aur Game kholna
                bot_status = "Opening Aviator Lobby..."
                page.goto(GAME_LOBBY_URL, timeout=60000)
                time.sleep(4)
                latest_screenshot = page.screenshot()
                
                page.mouse.click(AVIATOR_CARD_XY, AVIATOR_CARD_XY)
                bot_status = "Loading Aviator Game (14s)..."
                time.sleep(14)
                latest_screenshot = page.screenshot()
                
                # 4. Round History kholna
                page.mouse.click(HISTORY_BTN_XY, HISTORY_BTN_XY)
                time.sleep(2)
                latest_screenshot = page.screenshot()
                
                send_telegram("✅ Render Stealth Cloud Bot Live! Aviator Round History monitor ho rahi hai.")
                bot_status = "Monitoring Live Colors..."
                
                while True:
                    process_user_commands(page)
                    
                    png_bytes = page.screenshot()
                    latest_screenshot = png_bytes
                    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                    
                    streak = 0
                    for (cx, cy) in BUBBLE_CENTERS:
                        color = check_pill_color(img, cx, cy)
                        if color == "BLUE":
                            streak += 1
                        else:
                            break
                    
                    current_blue_streak = streak
                    bot_status = f"Live | Lagatar Asmani Blue (<2x): {current_blue_streak}/{TARGET_BLUE_COUNT}"
                    
                    if current_blue_streak >= TARGET_BLUE_COUNT and not alert_sent:
                        send_telegram(
                            f"🚨 AVIATOR 10x MISS ALERT! 🚨\n\n"
                            f"Round History mein shuru ke {current_blue_streak} numbers ASMANI BLUE (< 2.00x) hain!\n"
                            f"Turant game check karein!"
                        )
                        alert_sent = True
                    elif current_blue_streak == 0:
                        alert_sent = False
                        
                    time.sleep(CHECK_INTERVAL)
                    
        except Exception as e:
            bot_status = f"Restarting after error: {str(e)}"
            time.sleep(10)

@app.route('/')
def home():
    return (
        f"<h2>Aviator Stealth Cloud Bot</h2>"
        f"<p><b>Status:</b> {bot_status}</p>"
        f"<p><a href='/control' style='font-size:20px; color:green;'><b>👉 Live Remote Control & Screen Kholein (/control)</b></a></p>"
    )

@app.route('/screen')
def screen():
    if latest_screenshot:
        return send_file(io.BytesIO(latest_screenshot), mimetype='image/png')
    return "Screenshot abhi taiyar ho raha hai, 5 second baad refresh karein."

@app.route('/control')
def control():
    return """
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="background:#111; color:#fff; text-align:center; font-family:sans-serif; margin:0; padding:10px;">
        <h3>Cloud Browser Live Remote Control</h3>
        <p style="font-size:13px; color:#aaa;">Photo par kahin bhi touch karein—cloud browser mein wahi click hoga!</p>
        <div style="margin-bottom:10px;">
            <a href="/goto?url=https://10wicket777.comaviator" style="background:#28a745; color:#fff; padding:8px 12px; text-decoration:none; border-radius:5px;">Aviator Lobby</a>
            <a href="/tap?x=675&y=198" style="background:#007bff; color:#fff; padding:8px 12px; text-decoration:none; border-radius:5px;">Open History</a>
            <a href="/control" style="background:#555; color:#fff; padding:8px 12px; text-decoration:none; border-radius:5px;">Refresh</a>
        </div>
        <img id="liveImg" src="/screen" style="width:100%; max-width:400px; border:2px solid #444; cursor:crosshair;" onclick="tapScreen(event)"/>
        <script>
            setInterval(() => {
                document.getElementById('liveImg').src = '/screen?t=' + new Date().getTime();
            }, 3000);
            function tapScreen(e) {
                const img = e.target;
                const rect = img.getBoundingClientRect();
                const scaleX = 720 / rect.width;
                const scaleY = 1520 / rect.height;
                const x = Math.round((e.clientX - rect.left) * scaleX);
                const y = Math.round((e.clientY - rect.top) * scaleY);
                fetch('/tap?x=' + x + '&y=' + y).then(() => {
                    setTimeout(() => { document.getElementById('liveImg').src = '/screen?t=' + new Date().getTime(); }, 1500);
                });
            }
        </script>
    </body>
    </html>
    """

@app.route('/tap')
def tap():
    x = int(request.args.get('x', 0))
    y = int(request.args.get('y', 0))
    pending_clicks.append((x, y))
    return "OK"

@app.route('/goto')
              
