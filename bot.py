import re
import json
import os
import asyncio
import traceback
import logging
import sys
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, BrowserContext, Playwright
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import Conflict, TimedOut, NetworkError, RetryAfter

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Credentials ── env vars override, hardcoded values are the fallback
BOT_TOKEN     = os.environ.get("BOT_TOKEN",      "8724296336:AAEJHu1BSrF91rdrECfOva09eQBs1fpgwfo")
IVAS_EMAIL    = os.environ.get("IVAS_EMAIL",      "tawandamahachi07@gmail.com")
IVAS_PASSWORD = os.environ.get("IVAS_PASSWORD",   "mahachi2007")
ADMIN_IDS     = [os.environ.get("ADMIN_ID",       "8339856952")]
INITIAL_CHATS = [os.environ.get("INITIAL_CHAT",   "-1003854641278")]

BASE         = "https://www.ivasms.com"
LOGIN_URL    = f"{BASE}/login"
SMS_ENDPOINT = f"{BASE}/portal/sms/received/getsms"
NUMBERS_URL  = f"{BASE}/portal/sms/received/getsms/number"
SMS_DETAIL   = f"{BASE}/portal/sms/received/getsms/number/sms"
PORTAL_URL   = f"{BASE}/portal/sms/received"

DATA_DIR   = "/data" if os.path.isdir("/data") else "."
STATE_FILE = os.path.join(DATA_DIR, "seen.json")
CHATS_FILE = os.path.join(DATA_DIR, "chats.json")

POLL_SECS  = 30

BUTTONS = InlineKeyboardMarkup([
    [InlineKeyboardButton("📱 NUMBER CHANNEL", url="https://t.me/mrafrixtech")],
    [InlineKeyboardButton("📡 BACKUP CHANNEL",  url="https://t.me/auroratechinc")],
    [InlineKeyboardButton("🔑 OTP GROUP",        url="https://t.me/afrixotpgc")],
    [InlineKeyboardButton("👨‍💻 CONTACT DEV",     url="https://t.me/jaden_afrix")],
])

COUNTRY_FLAGS = {
    "Afghanistan":"🇦🇫","Albania":"🇦🇱","Algeria":"🇩🇿","Angola":"🇦🇴","Argentina":"🇦🇷",
    "Armenia":"🇦🇲","Australia":"🇦🇺","Austria":"🇦🇹","Azerbaijan":"🇦🇿","Bahrain":"🇧🇭",
    "Bangladesh":"🇧🇩","Belarus":"🇧🇾","Belgium":"🇧🇪","Benin":"🇧🇯","Bolivia":"🇧🇴",
    "Brazil":"🇧🇷","Bulgaria":"🇧🇬","Cambodia":"🇰🇭","Cameroon":"🇨🇲","Canada":"🇨🇦",
    "Chad":"🇹🇩","Chile":"🇨🇱","China":"🇨🇳","Colombia":"🇨🇴","Congo":"🇨🇬",
    "Croatia":"🇭🇷","Cuba":"🇨🇺","Cyprus":"🇨🇾","Czech Republic":"🇨🇿","Denmark":"🇩🇰",
    "Egypt":"🇪🇬","Estonia":"🇪🇪","Ethiopia":"🇪🇹","Finland":"🇫🇮","France":"🇫🇷",
    "Gabon":"🇬🇦","Gambia":"🇬🇲","Georgia":"🇬🇪","Germany":"🇩🇪","Ghana":"🇬🇭",
    "Greece":"🇬🇷","Guatemala":"🇬🇹","Guinea":"🇬🇳","Haiti":"🇭🇹","Honduras":"🇭🇳",
    "Hong Kong":"🇭🇰","Hungary":"🇭🇺","Iceland":"🇮🇸","India":"🇮🇳","Indonesia":"🇮🇩",
    "Iran":"🇮🇷","Iraq":"🇮🇶","Ireland":"🇮🇪","Israel":"🇮🇱","Italy":"🇮🇹",
    "Ivory Coast":"🇨🇮","IVORY COAST":"🇨🇮","Jamaica":"🇯🇲","Japan":"🇯🇵","Jordan":"🇯🇴",
    "Kazakhstan":"🇰🇿","Kenya":"🇰🇪","Kuwait":"🇰🇼","Kyrgyzstan":"🇰🇬","Laos":"🇱🇦",
    "Latvia":"🇱🇻","Lebanon":"🇱🇧","Liberia":"🇱🇷","Libya":"🇱🇾","Lithuania":"🇱🇹",
    "Luxembourg":"🇱🇺","Madagascar":"🇲🇬","Malaysia":"🇲🇾","Mali":"🇲🇱","Malta":"🇲🇹",
    "Mexico":"🇲🇽","Moldova":"🇲🇩","Monaco":"🇲🇨","Mongolia":"🇲🇳","Montenegro":"🇲🇪",
    "Morocco":"🇲🇦","Mozambique":"🇲🇿","Myanmar":"🇲🇲","Namibia":"🇳🇦","Nepal":"🇳🇵",
    "Netherlands":"🇳🇱","New Zealand":"🇳🇿","Nicaragua":"🇳🇮","Niger":"🇳🇪","Nigeria":"🇳🇬",
    "North Korea":"🇰🇵","North Macedonia":"🇲🇰","Norway":"🇳🇴","Oman":"🇴🇲","Pakistan":"🇵🇰",
    "Panama":"🇵🇦","Paraguay":"🇵🇾","Peru":"🇵🇪","Philippines":"🇵🇭","Poland":"🇵🇱",
    "Portugal":"🇵🇹","Qatar":"🇶🇦","Romania":"🇷🇴","Russia":"🇷🇺","Rwanda":"🇷🇼",
    "Saudi Arabia":"🇸🇦","Senegal":"🇸🇳","Serbia":"🇷🇸","Sierra Leone":"🇸🇱",
    "Singapore":"🇸🇬","Slovakia":"🇸🇰","Slovenia":"🇸🇮","Somalia":"🇸🇴",
    "South Africa":"🇿🇦","South Korea":"🇰🇷","Spain":"🇪🇸","Sri Lanka":"🇱🇰",
    "Sudan":"🇸🇩","Sweden":"🇸🇪","Switzerland":"🇨🇭","Syria":"🇸🇾","Taiwan":"🇹🇼",
    "Tajikistan":"🇹🇯","Tanzania":"🇹🇿","Thailand":"🇹🇭","Togo":"🇹🇬","TOGO":"🇹🇬",
    "Tunisia":"🇹🇳","Turkey":"🇹🇷","Turkmenistan":"🇹🇲","Uganda":"🇺🇬","Ukraine":"🇺🇦",
    "United Arab Emirates":"🇦🇪","United Kingdom":"🇬🇧","United States":"🇺🇸",
    "Uruguay":"🇺🇾","Uzbekistan":"🇺🇿","Venezuela":"🇻🇪","Vietnam":"🇻🇳",
    "Yemen":"🇾🇪","Zambia":"🇿🇲","Zimbabwe":"🇿🇼",
}

SERVICE_KEYWORDS = {
    "Facebook":["facebook"],"Google":["google","gmail"],"WhatsApp":["whatsapp"],
    "Telegram":["telegram"],"Instagram":["instagram"],"Amazon":["amazon"],
    "Netflix":["netflix"],"LinkedIn":["linkedin"],"Microsoft":["microsoft","outlook","live.com"],
    "Apple":["apple","icloud"],"Twitter":["twitter","x.com"],"Snapchat":["snapchat"],
    "TikTok":["tiktok"],"Discord":["discord"],"Signal":["signal"],"Viber":["viber"],
    "IMO":["imo"],"PayPal":["paypal"],"Binance":["binance"],"Uber":["uber"],
    "Bolt":["bolt"],"Airbnb":["airbnb"],"Yahoo":["yahoo"],"Steam":["steam"],
    "Foodpanda":["foodpanda"],"Messenger":["messenger","meta"],"YouTube":["youtube"],
    "eBay":["ebay"],"AliExpress":["aliexpress"],"Alibaba":["alibaba"],"Flipkart":["flipkart"],
    "Skype":["skype"],"Spotify":["spotify"],"Stripe":["stripe"],"Cash App":["cash app"],
    "Venmo":["venmo"],"Zelle":["zelle"],"Wise":["wise","transferwise"],"Coinbase":["coinbase"],
    "KuCoin":["kucoin"],"Bybit":["bybit"],"OKX":["okx"],"Huobi":["huobi"],
    "Kraken":["kraken"],"MetaMask":["metamask"],"Epic Games":["epic games","epicgames"],
    "PlayStation":["playstation","psn"],"Xbox":["xbox"],"Twitch":["twitch"],
    "Reddit":["reddit"],"ProtonMail":["protonmail","proton"],"Zoho":["zoho"],
    "Indeed":["indeed"],"Upwork":["upwork"],"Fiverr":["fiverr"],
    "Booking.com":["booking.com"],"Careem":["careem"],"Swiggy":["swiggy"],
    "Zomato":["zomato"],"McDonald's":["mcdonalds","mcdonald's"],"KFC":["kfc"],
    "Shein":["shein"],"OnlyFans":["onlyfans"],"Tinder":["tinder"],"Bumble":["bumble"],
    "Line":["line"],"WeChat":["wechat"],"VK":["vk","vkontakte"],
}

SERVICE_EMOJIS = {
    "Telegram":"📩","WhatsApp":"🟢","Facebook":"📘","Instagram":"📸","Messenger":"💬",
    "Google":"🔍","YouTube":"▶️","Twitter":"🐦","TikTok":"🎵","Snapchat":"👻",
    "Amazon":"🛒","eBay":"📦","AliExpress":"📦","Alibaba":"🏭","Flipkart":"📦",
    "Microsoft":"🪟","Outlook":"📧","Skype":"📞","Netflix":"🎬","Spotify":"🎶",
    "Apple":"🍏","PayPal":"💰","Stripe":"💳","Cash App":"💵","Venmo":"💸",
    "Zelle":"🏦","Wise":"🌐","Binance":"🪙","Coinbase":"🪙","KuCoin":"🪙",
    "Bybit":"📈","OKX":"🟠","Huobi":"🔥","Kraken":"🐙","MetaMask":"🦊",
    "Discord":"🗨️","Steam":"🎮","Epic Games":"🕹️","PlayStation":"🎮","Xbox":"🎮",
    "Twitch":"📺","Reddit":"👽","Yahoo":"🟣","ProtonMail":"🔐","LinkedIn":"💼",
    "Indeed":"📋","Upwork":"🧑‍💻","Fiverr":"💻","Airbnb":"🏠","Booking.com":"🛏️",
    "Uber":"🚗","Bolt":"🚖","Careem":"🚗","Swiggy":"🍔","Zomato":"🍽️",
    "Foodpanda":"🍱","McDonald's":"🍟","KFC":"🍗","Shein":"👗","OnlyFans":"🔞",
    "Tinder":"🔥","Bumble":"🐝","Signal":"🔐","Viber":"📞","Line":"💬",
    "WeChat":"💬","VK":"🌐","Unknown":"❓",
}

_pw:      Playwright     | None = None
_context: BrowserContext | None = None
_csrf:    str  = ""
_logged_in: bool = False
_fail_count: int  = 0


def _esc(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+=|{}.!\-\\])', r'\\\1', str(text))

def _load(path: str, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default

def _save(path: str, data) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_chats() -> list:
    d = _load(CHATS_FILE, None)
    if d is None:
        _save(CHATS_FILE, INITIAL_CHATS)
        return list(INITIAL_CHATS)
    return d

def save_chats(chats: list) -> None:
    _save(CHATS_FILE, chats)

def load_seen() -> set:
    return set(_load(STATE_FILE, []))

def mark_seen(uid: str) -> None:
    seen = load_seen()
    seen.add(uid)
    _save(STATE_FILE, list(seen)[-5000:])

def detect_service(text: str) -> str:
    lower = text.lower()
    for name, kws in SERVICE_KEYWORDS.items():
        if any(k in lower for k in kws):
            return name
    return "Unknown"

def extract_code(text: str) -> str:
    m = re.search(r'\b(\d{3}-\d{3})\b', text)
    if m:
        return m.group(1)
    m = re.search(r'\b(\d{4,8})\b', text)
    return m.group(1) if m else "N/A"

def get_flag(country: str) -> str:
    return COUNTRY_FLAGS.get(country, COUNTRY_FLAGS.get(country.title(), "🏴‍☠️"))

def is_admin(uid) -> bool:
    return str(uid) in ADMIN_IDS


async def _launch_browser() -> None:
    global _pw, _context
    log.info("Launching Chromium …")
    _pw = await async_playwright().start()
    _context = await _pw.chromium.launch_persistent_context(
        user_data_dir=os.path.join(DATA_DIR, "chrome_profile"),
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-extensions",
            "--single-process",
        ],
        ignore_https_errors=True,
        java_script_enabled=True,
        bypass_csp=True,
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/New_York",
    )
    await _context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
        window.chrome = {runtime: {}};
    """)
    log.info("Browser ready.")


async def _close_browser() -> None:
    global _pw, _context
    if _context:
        try:
            await _context.close()
        except Exception:
            pass
        _context = None
    if _pw:
        try:
            await _pw.stop()
        except Exception:
            pass
        _pw = None


async def do_login() -> bool:
    global _csrf, _fail_count, _logged_in

    if _context is None:
        await _launch_browser()

    log.info("Logging in to iVAS SMS …")
    page = await _context.new_page()

    try:
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

        # Wait out Cloudflare challenge — up to 30 seconds
        for i in range(6):
            if await page.query_selector('input[name="email"]'):
                break
            log.info("  CF challenge detected, waiting … (%d/6)", i + 1)
            await asyncio.sleep(5)

        email_field = await page.query_selector('input[name="email"]')
        if not email_field:
            log.warning("  Login form not found — Cloudflare blocked us.")
            _fail_count += 1
            _logged_in = False
            return False

        # Type like a human
        await page.fill('input[name="email"]', "")
        await page.type('input[name="email"]', IVAS_EMAIL, delay=80)
        await asyncio.sleep(0.5)
        await page.fill('input[name="password"]', "")
        await page.type('input[name="password"]', IVAS_PASSWORD, delay=60)
        await asyncio.sleep(0.4)
        await page.click('button[type="submit"]')

        try:
            await page.wait_for_url(
                lambda url: "login" not in url,
                timeout=25000,
            )
        except Exception:
            body = await page.inner_text("body")
            if "password" in body.lower() or "invalid" in body.lower():
                log.error("  Wrong credentials — check IVAS_EMAIL / IVAS_PASSWORD.")
            else:
                log.warning("  Login redirect timed out.")
            _fail_count += 1
            _logged_in = False
            return False

        # Grab CSRF from dashboard
        token = await page.evaluate(
            'document.querySelector(\'meta[name="csrf-token"]\')?.content || ""'
        )
        if token:
            _csrf = token

        log.info("  Login successful! CSRF: %s…", _csrf[:12] if _csrf else "none")
        _fail_count = 0
        _logged_in = True
        return True

    except Exception as e:
        log.error("  Login exception: %s", e)
        _fail_count += 1
        _logged_in = False
        return False
    finally:
        await page.close()


async def _refresh_csrf() -> str:
    global _csrf
    if _context is None:
        return ""
    page = await _context.new_page()
    try:
        await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=30000)
        if "login" in page.url:
            _csrf = ""
            return ""
        token = await page.evaluate(
            'document.querySelector(\'meta[name="csrf-token"]\')?.content || ""'
        )
        if token:
            _csrf = token
        return _csrf
    except Exception:
        return _csrf
    finally:
        await page.close()


async def fetch_sms() -> list:
    global _csrf

    if _context is None or not _logged_in:
        return []

    token = _csrf or await _refresh_csrf()
    if not token:
        log.warning("No CSRF token — session expired, will re-login next cycle.")
        return []

    today    = datetime.utcnow()
    from_str = (today - timedelta(days=1)).strftime("%m/%d/%Y")
    to_str   = today.strftime("%m/%d/%Y")

    try:
        resp = await _context.request.post(
            SMS_ENDPOINT,
            form={"from": from_str, "to": to_str, "_token": token},
        )

        if resp.status == 419:
            log.warning("CSRF expired (419), refreshing …")
            _csrf = ""
            await _refresh_csrf()
            return []

        if resp.status == 302 or "login" in resp.url:
            log.warning("Session expired — need re-login.")
            global _logged_in
            _logged_in = False
            return []

        if not resp.ok:
            log.warning("SMS endpoint returned %d", resp.status)
            return []

        soup       = BeautifulSoup(await resp.text(), "html.parser")
        group_divs = soup.find_all("div", {"class": "pointer"})
        if not group_divs:
            return []

        group_ids = []
        for div in group_divs:
            m = re.search(r"getDetials\('(.+?)'\)", div.get("onclick", ""))
            if m:
                group_ids.append(m.group(1))

        messages = []
        for gid in group_ids:
            try:
                num_resp = await _context.request.post(
                    NUMBERS_URL,
                    form={"start": from_str, "end": to_str, "range": gid, "_token": token},
                )
                if not num_resp.ok:
                    continue

                num_soup    = BeautifulSoup(await num_resp.text(), "html.parser")
                number_divs = num_soup.select("div[onclick*='getDetialsNumber']")

                for ndiv in number_divs:
                    phone = ndiv.text.strip()
                    if not phone:
                        continue

                    sms_resp = await _context.request.post(
                        SMS_DETAIL,
                        form={
                            "start": from_str, "end": to_str,
                            "Number": phone, "Range": gid,
                            "_token": token,
                        },
                    )
                    if not sms_resp.ok:
                        continue

                    sms_soup  = BeautifulSoup(await sms_resp.text(), "html.parser")
                    sms_cards = sms_soup.find_all("div", class_="card-body")

                    for card in sms_cards:
                        p = card.find("p", class_="mb-0")
                        if not p:
                            continue
                        sms_text = p.get_text(separator="\n").strip()
                        if not sms_text:
                            continue

                        m2      = re.match(r"([a-zA-Z\s]+)", gid)
                        country = m2.group(1).strip() if m2 else gid.strip()
                        service = detect_service(sms_text)

                        messages.append({
                            "id":      f"{phone}|{sms_text[:80]}",
                            "time":    datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                            "number":  phone,
                            "country": country,
                            "flag":    get_flag(country),
                            "service": service,
                            "emoji":   SERVICE_EMOJIS.get(service, "❓"),
                            "code":    extract_code(sms_text),
                            "sms":     sms_text,
                        })
            except Exception as e:
                log.error("Error processing group %s: %s", gid, e)
                continue

        return messages

    except Exception as e:
        log.error("fetch_sms error: %s", e)
        return []


async def send_otp(bot, chat_id: str, msg: dict) -> None:
    text = (
        f"🔔 *New OTP Received*\n\n"
        f"📞 *Number:* `{_esc(msg['number'])}`\n"
        f"🔑 *Code:* `{_esc(msg['code'])}`\n"
        f"🏆 *Service:* {msg['emoji']} {_esc(msg['service'])}\n"
        f"🌎 *Country:* {_esc(msg['country'])} {msg['flag']}\n"
        f"⏳ *Time:* {_esc(msg['time'])}\n\n"
        f"💬 *Message:*\n{_esc(msg['sms'])}"
    )
    try:
        await bot.send_message(
            chat_id=chat_id, text=text,
            parse_mode="MarkdownV2", reply_markup=BUTTONS,
        )
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        await bot.send_message(
            chat_id=chat_id, text=text,
            parse_mode="MarkdownV2", reply_markup=BUTTONS,
        )
    except Exception:
        try:
            plain = (
                f"New OTP\n\nNumber: {msg['number']}\nCode: {msg['code']}\n"
                f"Service: {msg['service']}\nCountry: {msg['country']} {msg['flag']}\n"
                f"Time: {msg['time']}\n\nMessage:\n{msg['sms']}"
            )
            await bot.send_message(chat_id=chat_id, text=plain, reply_markup=BUTTONS)
        except Exception as e2:
            log.error("Send failed for %s: %s", chat_id, e2)


async def poll_loop(bot) -> None:
    global _fail_count, _logged_in

    # Initial login with retries
    for attempt in range(3):
        if await do_login():
            break
        wait = 30 * (attempt + 1)
        log.warning("Login attempt %d failed, retrying in %ds …", attempt + 1, wait)
        await asyncio.sleep(wait)
    else:
        log.error("All login attempts failed. Will keep retrying every 5 minutes.")

    while True:
        try:
            log.info("[%s] Polling …", datetime.utcnow().strftime("%H:%M:%S"))

            if not _logged_in or _fail_count >= 3:
                log.info("Re-logging in …")
                success = await do_login()
                if not success:
                    backoff = min(60 * max(_fail_count, 1), 300)
                    log.warning("Login failed, backing off %ds.", backoff)
                    await asyncio.sleep(backoff)
                    continue

            messages = await fetch_sms()

            if not messages:
                log.info("  No messages found.")
            else:
                seen      = load_seen()
                chats     = load_chats()
                new_count = 0
                for msg in reversed(messages):
                    if msg["id"] in seen:
                        continue
                    new_count += 1
                    log.info("  → %s | %s | %s", msg["number"], msg["service"], msg["code"])
                    for cid in chats:
                        await send_otp(bot, cid, msg)
                    mark_seen(msg["id"])
                if new_count:
                    log.info("  Dispatched %d new OTP(s).", new_count)
                else:
                    log.info("  All already seen.")

        except Exception as e:
            log.error("poll_loop error: %s", e)
            traceback.print_exc()

        await asyncio.sleep(POLL_SECS)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if is_admin(uid):
        await update.message.reply_text(
            "Welcome Admin\\!\n\n"
            "`/add_chat <id>` — Add a chat ID\n"
            "`/remove_chat <id>` — Remove a chat ID\n"
            "`/list_chats` — List all chats\n"
            "`/status` — Live bot status",
            parse_mode="MarkdownV2",
            reply_markup=BUTTONS,
        )
    else:
        await update.message.reply_text(
            "Not authorized\\.", parse_mode="MarkdownV2", reply_markup=BUTTONS
        )

async def add_chat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("Admins only.")
    if not context.args:
        return await update.message.reply_text("Usage: /add\\_chat \\<id\\>", parse_mode="MarkdownV2")
    cid   = context.args[0]
    chats = load_chats()
    if cid in chats:
        return await update.message.reply_text(f"Already registered\\.", parse_mode="MarkdownV2")
    chats.append(cid)
    save_chats(chats)
    await update.message.reply_text(f"✅ Added `{_esc(cid)}`\\.", parse_mode="MarkdownV2")

async def remove_chat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("Admins only.")
    if not context.args:
        return await update.message.reply_text("Usage: /remove\\_chat \\<id\\>", parse_mode="MarkdownV2")
    cid   = context.args[0]
    chats = load_chats()
    if cid not in chats:
        return await update.message.reply_text(f"Not found\\.", parse_mode="MarkdownV2")
    chats.remove(cid)
    save_chats(chats)
    await update.message.reply_text(f"✅ Removed `{_esc(cid)}`\\.", parse_mode="MarkdownV2")

async def list_chats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("Admins only.")
    chats = load_chats()
    if not chats:
        return await update.message.reply_text("No chats registered.")
    lines = "\n".join(f"• `{_esc(c)}`" for c in chats)
    await update.message.reply_text(
        f"📜 *Registered Chats:*\n\n{lines}", parse_mode="MarkdownV2"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    chats = load_chats()
    seen  = load_seen()
    await update.message.reply_text(
        f"*Bot Status*\n\n"
        f"Browser: {'✅' if _context else '❌'}\n"
        f"Logged in: {'✅' if _logged_in else '❌'}\n"
        f"CSRF: {'✅' if _csrf else '❌'}\n"
        f"Fail count: {_fail_count}\n"
        f"Chats: {len(chats)}\n"
        f"Seen IDs: {len(seen)}\n"
        f"Email: `{_esc(IVAS_EMAIL)}`",
        parse_mode="MarkdownV2",
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, Conflict):
        log.warning("Telegram Conflict — old instance still alive, waiting 30s …")
        await asyncio.sleep(30)
    elif isinstance(err, (TimedOut, NetworkError)):
        log.warning("Telegram network hiccup: %s", err)
    else:
        log.error("Telegram error: %s", err)


async def _main():
    log.info("=" * 50)
    log.info("iVAS SMS Bot starting …")
    log.info("Email : %s", IVAS_EMAIL)
    log.info("Admin : %s", ADMIN_IDS)
    log.info("Chats : %s", load_chats())
    log.info("=" * 50)

    await _launch_browser()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start",       start_cmd))
    app.add_handler(CommandHandler("add_chat",    add_chat_cmd))
    app.add_handler(CommandHandler("remove_chat", remove_chat_cmd))
    app.add_handler(CommandHandler("list_chats",  list_chats_cmd))
    app.add_handler(CommandHandler("status",      status_cmd))
    app.add_error_handler(error_handler)

    async with app:
        await app.start()
        await app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message"],
        )
        log.info("Bot online. Polling SMS every %ds.", POLL_SECS)
        try:
            await poll_loop(app.bot)
        finally:
            await app.updater.stop()
            await app.stop()
            await _close_browser()


if __name__ == "__main__":
    asyncio.run(_main())
