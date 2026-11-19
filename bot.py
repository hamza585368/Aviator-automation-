import time
import io
import threading
import requests
from PIL import Image
from flask import Flask, send_file
from playwright.sync_api import sync_playwright

# =========================================================================
# USER CONFIGURATION (Aapki saari details pehle se bhari hui hain)
# =========================================================================
SITE_URL = "https://10wicket777.com"             # Website ka main link
GAME_LOBBY_URL = "https://10wicket777.com/aviator"# Aviator lobby link

USERNAME = "WtAvinash"                               # Aapka Username
PASSWORD = "Asdf@1234"                               # Aapka Password

TELEGRAM_BOT_TOKEN = "9029740245:AAGc1on9TUQvGut_V06vRHSkY1N66YSny8A"
TELEGRAM_CHAT_ID = "7431620371"

TARGET_BLUE_COUNT = 10      # Kitne lagatar Asmani Blue (<2x) numbers par alert bhejna hai
CHECK_INTERVAL = 8          # Har kitne second mein screen check karni hai

# Video ke hisab se exact click coordinates (720x1520 mobile view)
LOGIN_OPEN_BTN = (655, 112) # Home page par top-right LOGIN button
AVIATOR_CARD_XY = (590, 305)# Lobby mein top-right 'Aviator' (Red plane) game card
HISTORY_BTN_XY = (675, 198) # Game ke andar Round History kholne wala dropdown button

# Opened Round History ke pehle 10 numbers ke center coordinates (Row 1 ke 8 + Row 2 ke 2)
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

def send_telegram(msg):
    url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)

def check_pill_color(img, cx, cy):
    """Pill ke center (cx, cy) ke aas-paas 50x20 box scan karke Asmani Blue vs Purple/Pink batata hai"""
    blue_pixels = 0
    purple_pixels = 0
    
    for x in range(cx - 25, cx + 25, 2):
        for y in range(cy - 10, cy + 10, 2):
            r, g, b = img.getpixel((x, y))
            # Asmani Blue text (< 2.00x): Blue zyada aur Red kam hota hai
            if b > 140 and b > r + 40:
                blue_pixels += 1
            # Purple / Pink text (>= 2.00x): Red aur Blue dono high hote hain
            elif r > 120 and b > 120 and r > g + 30:
                purple_pixels += 1

    if blue_pixels > 4 and blue_pixels > purple_pixels:
        return "BLUE"
    elif purple_pixels > 4:
        return "PURPLE"
    return "UNKNOWN"

def run_bot():
    global alert_sent, current_blue_streak, bot_status, latest_screenshot
    
    while True:
        try:
            with sync_playwright() as p:
                bot_status = "Starting Low-RAM Browser..."
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--single-process",
                        "--no-zygote",
                        "--js-flags=--max-old-space-size=160"
                    ]
                )
                context = browser.new_context(
                    viewport={"width": 720, "height": 1520},
                    user_agent="Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"
                )
                page = context.new_page()
                
                # 1. Website kholna aur LOGIN popup open karna
                bot_status = "Opening Website..."
                page.goto(SITE_URL, timeout=60000)
                time.sleep(4)
                page.mouse.click(LOGIN_OPEN_BTN, LOGIN_OPEN_BTN)
                time.sleep(2)
                
                # 2. Username aur Password bhar kar Login karna
                bot_status = "Logging in..."
                page.fill('input[placeholder*="Username"], input[type="text"]', USERNAME)
                page.fill('input[placeholder*="Password"], input[type="password"]', PASSWORD)
                page.click('button:has-text("Login")')
                time.sleep(5)
                
                # 3. Aviator Lobby par jana aur Aviator Studio card par click karna
                bot_status = "Opening Aviator Lobby..."
                page.goto(GAME_LOBBY_URL, timeout=60000)
                time.sleep(4)
                page.mouse.click(AVIATOR_CARD_XY, AVIATOR_CARD_XY)
                
                # 4. Aviator Studio load hone ka wait karna (14 seconds)
                bot_status = "Loading Aviator Game..."
                time.sleep(14)
                
                # 5. Round History dropdown kholna
                page.mouse.click(HISTORY_BTN_XY, HISTORY_BTN_XY)
                time.sleep(2)
                
                send_telegram("✅ Render Cloud Bot Live! Aviator Round History monitor ho rahi hai.")
                bot_status = "Monitoring Live Colors..."
                
                while True:
                    png_bytes = page.screenshot()
                    latest_screenshot = png_bytes
                    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                    
                    # Agar Round History dropdown band ho gaya ho toh dubara kholna
                    first_status = check_pill_color(img, BUBBLE_CENTERS, BUBBLE_CENTERS)
                    if first_status == "UNKNOWN":
                        page.mouse.click(HISTORY_BTN_XY, HISTORY_BTN_XY)
                        time.sleep(1.5)
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
        f"<h3>Aviator Render Cloud Bot</h3>"
        f"<p><b>Status:</b> {bot_status}</p>"
        f"<p>Live screenshot dekhne ke liye <a href='/screen'>/screen</a> kholein.</p>"
    )

@app.route('/screen')
def screen():
    if latest_screenshot:
        return send_file(io.BytesIO(latest_screenshot), mimetype='image/png')
    return "Screenshot abhi taiyar ho raha hai, 15 second baad refresh karein."

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
              
