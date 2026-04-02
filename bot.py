# -*- coding: utf-8 -*-
import re
import json
import os
import traceback
from urllib.parse import urljoin
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]  # Set this in Railway environment variables

ADMIN_CHAT_IDS   = ["8339856952"]
INITIAL_CHAT_IDS = ["-1003053441379"]

LOGIN_URL        = "https://www.ivasms.com/login"
BASE_URL         = "https://www.ivasms.com/"
SMS_API_ENDPOINT = "https://www.ivasms.com/portal/sms/received/getsms"

USERNAME         = "tawandamahachi07@gmail.com"
PASSWORD         = "mahachi2007"

POLLING_INTERVAL = 15  # seconds
STATE_FILE       = "/data/processed_sms_ids.json"
CHAT_IDS_FILE    = "/data/chat_ids.json"

# Use local paths if /data is not available (local dev fallback)
if not os.path.exists("/data"):
    STATE_FILE    = "processed_sms_ids.json"
    CHAT_IDS_FILE = "chat_ids.json"

INLINE_BUTTONS = [
    InlineKeyboardButton("📱 NUMBER CHANNEL", url="https://t.me/mrafrixtech"),
    InlineKeyboardButton("BACKUP CHANNEL",    url="https://t.me/auroratechinc"),
    InlineKeyboardButton("OTP GROUP",         url="https://t.me/afrixotpgc"),
    InlineKeyboardButton("CONTACT DEV",       url="https://t.me/jaden_afrix"),
]

# ─────────────────────────────────────────────
#  COUNTRY FLAGS
# ─────────────────────────────────────────────
COUNTRY_FLAGS = {
    "Afghanistan": "🇦🇫", "Albania": "🇦🇱", "Algeria": "🇩🇿", "Andorra": "🇦🇩",
    "Angola": "🇦🇴", "Argentina": "🇦🇷", "Armenia": "🇦🇲", "Australia": "🇦🇺",
    "Austria": "🇦🇹", "Azerbaijan": "🇦🇿", "Bahrain": "🇧🇭", "Bangladesh": "🇧🇩",
    "Belarus": "🇧🇾", "Belgium": "🇧🇪", "Benin": "🇧🇯", "Bhutan": "🇧🇹",
    "Bolivia": "🇧🇴", "Brazil": "🇧🇷", "Bulgaria": "🇧🇬", "Burkina Faso": "🇧🇫",
    "Cambodia": "🇰🇭", "Cameroon": "🇨🇲", "Canada": "🇨🇦", "Chad": "🇹🇩",
    "Chile": "🇨🇱", "China": "🇨🇳", "Colombia": "🇨🇴", "Congo": "🇨🇬",
    "Croatia": "🇭🇷", "Cuba": "🇨🇺", "Cyprus": "🇨🇾", "Czech Republic": "🇨🇿",
    "Denmark": "🇩🇰", "Egypt": "🇪🇬", "Estonia": "🇪🇪", "Ethiopia": "🇪🇹",
    "Finland": "🇫🇮", "France": "🇫🇷", "Gabon": "🇬🇦", "Gambia": "🇬🇲",
    "Georgia": "🇬🇪", "Germany": "🇩🇪", "Ghana": "🇬🇭", "Greece": "🇬🇷",
    "Guatemala": "🇬🇹", "Guinea": "🇬🇳", "Haiti": "🇭🇹", "Honduras": "🇭🇳",
    "Hong Kong": "🇭🇰", "Hungary": "🇭🇺", "Iceland": "🇮🇸", "India": "🇮🇳",
    "Indonesia": "🇮🇩", "Iran": "🇮🇷", "Iraq": "🇮🇶", "Ireland": "🇮🇪",
    "Israel": "🇮🇱", "Italy": "🇮🇹", "Ivory Coast": "🇨🇮", "IVORY COAST": "🇨🇮",
    "Jamaica": "🇯🇲", "Japan": "🇯🇵", "Jordan": "🇯🇴", "Kazakhstan": "🇰🇿",
    "Kenya": "🇰🇪", "Kuwait": "🇰🇼", "Kyrgyzstan": "🇰🇬", "Laos": "🇱🇦",
    "Latvia": "🇱🇻", "Lebanon": "🇱🇧", "Liberia": "🇱🇷", "Libya": "🇱🇾",
    "Lithuania": "🇱🇹", "Luxembourg": "🇱🇺", "Madagascar": "🇲🇬", "Malaysia": "🇲🇾",
    "Mali": "🇲🇱", "Malta": "🇲🇹", "Mexico": "🇲🇽", "Moldova": "🇲🇩",
    "Monaco": "🇲🇨", "Mongolia": "🇲🇳", "Montenegro": "🇲🇪", "Morocco": "🇲🇦",
    "Mozambique": "🇲🇿", "Myanmar": "🇲🇲", "Namibia": "🇳🇦", "Nepal": "🇳🇵",
    "Netherlands": "🇳🇱", "New Zealand": "🇳🇿", "Nicaragua": "🇳🇮", "Niger": "🇳🇪",
    "Nigeria": "🇳🇬", "North Korea": "🇰🇵", "North Macedonia": "🇲🇰", "Norway": "🇳🇴",
    "Oman": "🇴🇲", "Pakistan": "🇵🇰", "Panama": "🇵🇦", "Paraguay": "🇵🇾",
    "Peru": "🇵🇪", "Philippines": "🇵🇭", "Poland": "🇵🇱", "Portugal": "🇵🇹",
    "Qatar": "🇶🇦", "Romania": "🇷🇴", "Russia": "🇷🇺", "Rwanda": "🇷🇼",
    "Saudi Arabia": "🇸🇦", "Senegal": "🇸🇳", "Serbia": "🇷🇸", "Sierra Leone": "🇸🇱",
    "Singapore": "🇸🇬", "Slovakia": "🇸🇰", "Slovenia": "🇸🇮", "Somalia": "🇸🇴",
    "South Africa": "🇿🇦", "South Korea": "🇰🇷", "Spain": "🇪🇸", "Sri Lanka": "🇱🇰",
    "Sudan": "🇸🇩", "Sweden": "🇸🇪", "Switzerland": "🇨🇭", "Syria": "🇸🇾",
    "Taiwan": "🇹🇼", "Tajikistan": "🇹🇯", "Tanzania": "🇹🇿", "Thailand": "🇹🇭",
    "TOGO": "🇹🇬", "Togo": "🇹🇬", "Tunisia": "🇹🇳", "Turkey": "🇹🇷",
    "Turkmenistan": "🇹🇲", "Uganda": "🇺🇬", "Ukraine": "🇺🇦",
    "United Arab Emirates": "🇦🇪", "United Kingdom": "🇬🇧", "United States": "🇺🇸",
    "Uruguay": "🇺🇾", "Uzbekistan": "🇺🇿", "Venezuela": "🇻🇪", "Vietnam": "🇻🇳",
    "Yemen": "🇾🇪", "Zambia": "🇿🇲", "Zimbabwe": "🇿🇼", "Unknown Country": "🏴‍☠️",
}

# ─────────────────────────────────────────────
#  SERVICE DETECTION
# ─────────────────────────────────────────────
SERVICE_KEYWORDS = {
    "Facebook": ["facebook"], "Google": ["google", "gmail"], "WhatsApp": ["whatsapp"],
    "Telegram": ["telegram"], "Instagram": ["instagram"], "Amazon": ["amazon"],
    "Netflix": ["netflix"], "LinkedIn": ["linkedin"],
    "Microsoft": ["microsoft", "outlook", "live.com"], "Apple": ["apple", "icloud"],
    "Twitter": ["twitter"], "Snapchat": ["snapchat"], "TikTok": ["tiktok"],
    "Discord": ["discord"], "Signal": ["signal"], "Viber": ["viber"], "IMO": ["imo"],
    "PayPal": ["paypal"], "Binance": ["binance"], "Uber": ["uber"], "Bolt": ["bolt"],
    "Airbnb": ["airbnb"], "Yahoo": ["yahoo"], "Steam": ["steam"], "Blizzard": ["blizzard"],
    "Foodpanda": ["foodpanda"], "Pathao": ["pathao"], "Messenger": ["messenger", "meta"],
    "YouTube": ["youtube"], "eBay": ["ebay"], "AliExpress": ["aliexpress"],
    "Alibaba": ["alibaba"], "Flipkart": ["flipkart"], "Skype": ["skype"],
    "Spotify": ["spotify"], "Stripe": ["stripe"], "Cash App": ["cash app", "square cash"],
    "Venmo": ["venmo"], "Zelle": ["zelle"], "Wise": ["wise", "transferwise"],
    "Coinbase": ["coinbase"], "KuCoin": ["kucoin"], "Bybit": ["bybit"],
    "OKX": ["okx"], "Huobi": ["huobi"], "Kraken": ["kraken"], "MetaMask": ["metamask"],
    "Epic Games": ["epic games", "epicgames"], "PlayStation": ["playstation", "psn"],
    "Xbox": ["xbox"], "Twitch": ["twitch"], "Reddit": ["reddit"],
    "ProtonMail": ["protonmail", "proton"], "Zoho": ["zoho"], "Quora": ["quora"],
    "StackOverflow": ["stackoverflow"], "Indeed": ["indeed"], "Upwork": ["upwork"],
    "Fiverr": ["fiverr"], "Glassdoor": ["glassdoor"], "Booking.com": ["booking.com"],
    "Careem": ["careem"], "Swiggy": ["swiggy"], "Zomato": ["zomato"],
    "McDonald's": ["mcdonalds", "mcdonald's"], "KFC": ["kfc"], "Nike": ["nike"],
    "Adidas": ["adidas"], "Shein": ["shein"], "OnlyFans": ["onlyfans"],
    "Tinder": ["tinder"], "Bumble": ["bumble"], "Grindr": ["grindr"],
    "Line": ["line"], "WeChat": ["wechat"], "VK": ["vk", "vkontakte"],
}

SERVICE_EMOJIS = {
    "Telegram": "📩", "WhatsApp": "🟢", "Facebook": "📘", "Instagram": "📸",
    "Messenger": "💬", "Google": "🔍", "Gmail": "✉️", "YouTube": "▶️",
    "Twitter": "🐦", "X": "❌", "TikTok": "🎵", "Snapchat": "👻",
    "Amazon": "🛒", "eBay": "📦", "AliExpress": "📦", "Alibaba": "🏭",
    "Flipkart": "📦", "Microsoft": "🪟", "Outlook": "📧", "Skype": "📞",
    "Netflix": "🎬", "Spotify": "🎶", "Apple": "🍏", "iCloud": "☁️",
    "PayPal": "💰", "Stripe": "💳", "Cash App": "💵", "Venmo": "💸",
    "Zelle": "🏦", "Wise": "🌐", "Binance": "🪙", "Coinbase": "🪙",
    "KuCoin": "🪙", "Bybit": "📈", "OKX": "🟠", "Huobi": "🔥",
    "Kraken": "🐙", "MetaMask": "🦊", "Discord": "🗨️", "Steam": "🎮",
    "Epic Games": "🕹️", "PlayStation": "🎮", "Xbox": "🎮", "Twitch": "📺",
    "Reddit": "👽", "Yahoo": "🟣", "ProtonMail": "🔐", "Zoho": "📬",
    "Quora": "❓", "StackOverflow": "🧑‍💻", "LinkedIn": "💼", "Indeed": "📋",
    "Upwork": "🧑‍💻", "Fiverr": "💻", "Glassdoor": "🔎", "Airbnb": "🏠",
    "Booking.com": "🛏️", "Uber": "🚗", "Bolt": "🚖", "Careem": "🚗",
    "Swiggy": "🍔", "Zomato": "🍽️", "Foodpanda": "🍱", "McDonald's": "🍟",
    "KFC": "🍗", "Nike": "👟", "Adidas": "👟", "Shein": "👗",
    "OnlyFans": "🔞", "Tinder": "🔥", "Bumble": "🐝", "Grindr": "😈",
    "Signal": "🔐", "Viber": "📞", "Line": "💬", "WeChat": "💬",
    "VK": "🌐", "Unknown": "❓",
}

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def escape_markdown(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+=|{}.!\-\\])', r'\\\1', str(text))

def load_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default

def save_json_file(path: str, data) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_chat_ids() -> list:
    data = load_json_file(CHAT_IDS_FILE, None)
    if data is None:
        save_json_file(CHAT_IDS_FILE, INITIAL_CHAT_IDS)
        return list(INITIAL_CHAT_IDS)
    return data

def save_chat_ids(chat_ids: list) -> None:
    save_json_file(CHAT_IDS_FILE, chat_ids)

def load_processed_ids() -> set:
    return set(load_json_file(STATE_FILE, []))

def save_processed_id(sms_id: str) -> None:
    ids = load_processed_ids()
    ids.add(sms_id)
    trimmed = list(ids)[-5000:]  # cap at 5000 to prevent unbounded growth
    save_json_file(STATE_FILE, trimmed)

def detect_service(sms_text: str) -> str:
    lower = sms_text.lower()
    for name, keywords in SERVICE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return name
    return "Unknown"

def extract_code(sms_text: str) -> str:
    m = re.search(r'\b(\d{3}-\d{3})\b', sms_text)
    if m:
        return m.group(1)
    m = re.search(r'\b(\d{4,8})\b', sms_text)
    return m.group(1) if m else "N/A"

def build_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[btn] for btn in INLINE_BUTTONS])

def is_admin(user_id) -> bool:
    return str(user_id) in ADMIN_CHAT_IDS

# ─────────────────────────────────────────────
#  COMMAND HANDLERS
# ─────────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if is_admin(uid):
        text = (
            "Welcome Admin\\!\n\n"
            "`/add_chat <id>` — Add a chat ID\n"
            "`/remove_chat <id>` — Remove a chat ID\n"
            "`/list_chats` — List all chat IDs"
        )
        await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=build_markup())
    else:
        await update.message.reply_text(
            "Sorry, you are not authorized to use this bot\\.",
            parse_mode="MarkdownV2",
            reply_markup=build_markup(),
        )

async def add_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("Sorry, only admins can use this command.")
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /add\\_chat \\<chat\\_id\\>", parse_mode="MarkdownV2")
        return
    new_id = context.args[0]
    chat_ids = load_chat_ids()
    if new_id in chat_ids:
        await update.message.reply_text(
            f"⚠️ Chat ID `{escape_markdown(new_id)}` is already registered\\.",
            parse_mode="MarkdownV2"
        )
    else:
        chat_ids.append(new_id)
        save_chat_ids(chat_ids)
        await update.message.reply_text(
            f"✅ Chat ID `{escape_markdown(new_id)}` added\\.",
            parse_mode="MarkdownV2"
        )

async def remove_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("Sorry, only admins can use this command.")
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /remove\\_chat \\<chat\\_id\\>", parse_mode="MarkdownV2")
        return
    target = context.args[0]
    chat_ids = load_chat_ids()
    if target in chat_ids:
        chat_ids.remove(target)
        save_chat_ids(chat_ids)
        await update.message.reply_text(
            f"✅ Chat ID `{escape_markdown(target)}` removed\\.",
            parse_mode="MarkdownV2"
        )
    else:
        await update.message.reply_text(
            f"🤔 Chat ID `{escape_markdown(target)}` not found\\.",
            parse_mode="MarkdownV2"
        )

async def list_chats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("Sorry, only admins can use this command.")
        return
    chat_ids = load_chat_ids()
    if not chat_ids:
        await update.message.reply_text("No chat IDs registered.")
        return
    lines = "\n".join(f"• `{escape_markdown(cid)}`" for cid in chat_ids)
    await update.message.reply_text(
        f"📜 *Registered Chat IDs:*\n\n{lines}",
        parse_mode="MarkdownV2",
    )

# ─────────────────────────────────────────────
#  SMS FETCHING
# ─────────────────────────────────────────────
async def fetch_sms_from_api(session: AsyncSession, csrf_token: str) -> list:
    all_messages = []
    try:
        today      = datetime.utcnow()
        start_date = today - timedelta(days=1)
        from_str   = start_date.strftime('%m/%d/%Y')
        to_str     = today.strftime('%m/%d/%Y')

        resp = await session.post(
            SMS_API_ENDPOINT,
            data={"from": from_str, "to": to_str, "_token": csrf_token},
        )
        resp.raise_for_status()
        soup       = BeautifulSoup(resp.text, "html.parser")
        group_divs = soup.find_all("div", {"class": "pointer"})
        if not group_divs:
            return []

        group_ids = []
        for div in group_divs:
            onclick = div.get("onclick", "")
            m = re.search(r"getDetials\('(.+?)'\)", onclick)
            if m:
                group_ids.append(m.group(1))

        numbers_url = urljoin(BASE_URL, "portal/sms/received/getsms/number")
        sms_url     = urljoin(BASE_URL, "portal/sms/received/getsms/number/sms")

        for group_id in group_ids:
            num_resp = await session.post(
                numbers_url,
                data={"start": from_str, "end": to_str, "range": group_id, "_token": csrf_token},
            )
            num_soup    = BeautifulSoup(num_resp.text, "html.parser")
            number_divs = num_soup.select("div[onclick*='getDetialsNumber']")
            if not number_divs:
                continue

            for div in number_divs:
                phone    = div.text.strip()
                sms_resp = await session.post(
                    sms_url,
                    data={
                        "start": from_str, "end": to_str,
                        "Number": phone, "Range": group_id,
                        "_token": csrf_token,
                    },
                )
                sms_soup  = BeautifulSoup(sms_resp.text, "html.parser")
                sms_cards = sms_soup.find_all("div", class_="card-body")

                for card in sms_cards:
                    p = card.find("p", class_="mb-0")
                    if not p:
                        continue
                    sms_text = p.get_text(separator="\n").strip()
                    m        = re.match(r'([a-zA-Z\s]+)', group_id)
                    country  = m.group(1).strip() if m else group_id.strip()
                    flag     = COUNTRY_FLAGS.get(country, COUNTRY_FLAGS.get(country.title(), "🏴‍☠️"))

                    all_messages.append({
                        "id":       f"{phone}-{sms_text}",
                        "time":     datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                        "number":   phone,
                        "country":  country,
                        "flag":     flag,
                        "service":  detect_service(sms_text),
                        "code":     extract_code(sms_text),
                        "full_sms": sms_text,
                    })

    except Exception as e:
        print(f"❌ fetch_sms_from_api error: {e}")
        traceback.print_exc()

    return all_messages

# ─────────────────────────────────────────────
#  TELEGRAM MESSAGE SENDER
# ─────────────────────────────────────────────
async def send_telegram_message(context: ContextTypes.DEFAULT_TYPE, chat_id: str, msg: dict):
    service       = msg.get("service", "Unknown")
    service_emoji = SERVICE_EMOJIS.get(service, "❓")
    flag          = msg.get("flag", "🏴‍☠️")

    text = (
        f"🔔 *New OTP Received*\n\n"
        f"📞 *Number:* `{escape_markdown(msg.get('number', 'N/A'))}`\n"
        f"🔑 *Code:* `{escape_markdown(msg.get('code', 'N/A'))}`\n"
        f"🏆 *Service:* {service_emoji} {escape_markdown(service)}\n"
        f"🌎 *Country:* {escape_markdown(msg.get('country', 'N/A'))} {flag}\n"
        f"⏳ *Time:* {escape_markdown(msg.get('time', 'N/A'))}\n\n"
        f"💬 *Message:*\n{escape_markdown(msg.get('full_sms', 'N/A'))}"
    )

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="MarkdownV2",
            reply_markup=build_markup(),
        )
    except Exception as e:
        print(f"⚠️ MarkdownV2 send failed for {chat_id}: {e} — trying plain text")
        try:
            plain = (
                f"New OTP Received\n\n"
                f"Number: {msg.get('number')}\n"
                f"Code: {msg.get('code')}\n"
                f"Service: {service}\n"
                f"Country: {msg.get('country')} {flag}\n"
                f"Time: {msg.get('time')}\n\n"
                f"Message:\n{msg.get('full_sms')}"
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=plain,
                reply_markup=build_markup(),
            )
        except Exception as e2:
            print(f"❌ Both sends failed for {chat_id}: {e2}")

# ─────────────────────────────────────────────
#  MAIN POLLING JOB
# ─────────────────────────────────────────────
async def check_sms_job(context: ContextTypes.DEFAULT_TYPE):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] Checking for new messages…")

    async with AsyncSession(impersonate="chrome110") as session:
        try:
            # 1. Load login page → grab CSRF
            login_page  = await session.get(LOGIN_URL)
            soup        = BeautifulSoup(login_page.text, "html.parser")
            token_input = soup.find("input", {"name": "_token"})
            csrf        = token_input["value"] if token_input else ""

            # 2. POST login
            login_resp = await session.post(
                LOGIN_URL,
                data={"email": USERNAME, "password": PASSWORD, "_token": csrf},
            )

            # 3. Detect login failure
            if 'name="password"' in login_resp.text:
                print("❌ Login failed — check USERNAME/PASSWORD.")
                return

            print("✅ Logged in.")

            # 4. Grab fresh CSRF from dashboard
            dash_soup  = BeautifulSoup(login_resp.text, "html.parser")
            csrf_meta  = dash_soup.find("meta", {"name": "csrf-token"})
            if not csrf_meta:
                print("❌ CSRF token not found on dashboard.")
                return
            csrf_token = csrf_meta.get("content", "")

            # 5. Fetch SMS
            messages = await fetch_sms_from_api(session, csrf_token)
            if not messages:
                print("✔ No messages found.")
                return

            processed = load_processed_ids()
            chat_ids  = load_chat_ids()
            new_count = 0

            for msg in reversed(messages):
                if msg["id"] in processed:
                    continue
                new_count += 1
                print(f"  → New OTP from {msg['number']} ({msg['service']})")
                for cid in chat_ids:
                    await send_telegram_message(context, cid, msg)
                save_processed_id(msg["id"])

            if new_count:
                print(f"✅ Sent {new_count} new message(s).")
            else:
                print("✔ All messages already processed.")

        except Exception as e:
            print(f"❌ Job error: {e}")
            traceback.print_exc()

# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
def main():
    print("🚀 iVasms → Telegram bot starting…")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",       start_command))
    app.add_handler(CommandHandler("add_chat",    add_chat_command))
    app.add_handler(CommandHandler("remove_chat", remove_chat_command))
    app.add_handler(CommandHandler("list_chats",  list_chats_command))

    jq = app.job_queue
    if jq is None:
        print("❌ JobQueue unavailable.")
        print("   Run: pip install 'python-telegram-bot[job-queue]'")
        return

    jq.run_repeating(check_sms_job, interval=POLLING_INTERVAL, first=3)
    print(f"✅ Polling every {POLLING_INTERVAL}s.")
    print("🤖 Bot online. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
