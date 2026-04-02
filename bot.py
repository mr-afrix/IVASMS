import re
import io
import json
import os
import traceback
import asyncio
from urllib.parse import urljoin
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

# ═══════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════
BOT_TOKEN = os.environ["BOT_TOKEN"]

ADMIN_CHAT_IDS   = ["8339856952"]
INITIAL_CHAT_IDS = ["-1003053441379"]

BASE_URL         = "https://www.ivasms.com/"
LOGIN_URL        = "https://www.ivasms.com/login"
SMS_API_ENDPOINT = "https://www.ivasms.com/portal/sms/received/getsms"
NUMBERS_PAGE_URL = "https://www.ivasms.com/portal/numbers"

USERNAME = os.environ.get("IVAS_EMAIL",    "tawandamahachi07@gmail.com")
PASSWORD = os.environ.get("IVAS_PASSWORD", "mahachi2007")

POLLING_INTERVAL = 15          # seconds between SMS checks
MAX_LOGIN_RETRIES = 5
SESSION_CHECK_URL = urljoin(BASE_URL, "portal/sms/received")

DATA_DIR      = "/data" if os.path.exists("/data") else "."
STATE_FILE    = os.path.join(DATA_DIR, "processed_sms_ids.json")
CHAT_IDS_FILE = os.path.join(DATA_DIR, "chat_ids.json")

BANNER_IMAGE_URL = "https://files.catbox.moe/uxh44d.jpg"

# ─── Inline social buttons (shown on every OTP message) ───
SOCIAL_BUTTONS = InlineKeyboardMarkup([
    [InlineKeyboardButton("📱 NUMBER CHANNEL", url="https://t.me/mrafrixtech")],
    [InlineKeyboardButton("📡 BACKUP CHANNEL",  url="https://t.me/auroratechinc")],
    [InlineKeyboardButton("🔑 OTP GROUP",        url="https://t.me/afrixotpgc")],
    [InlineKeyboardButton("👨‍💻 CONTACT DEV",     url="https://t.me/jaden_afrix")],
])

# ─── Cloudflare-proof headers (Chrome 124) ───
CF_HEADERS = {
    "User-Agent":                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                 "AppleWebKit/537.36 (KHTML, like Gecko) "
                                 "Chrome/124.0.0.0 Safari/537.36",
    "Accept":                    "text/html,application/xhtml+xml,application/xml;"
                                 "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language":           "en-US,en;q=0.9",
    "Accept-Encoding":           "gzip, deflate, br",
    "Cache-Control":             "no-cache",
    "Pragma":                    "no-cache",
    "Sec-Ch-Ua":                 '"Chromium";v="124","Google Chrome";v="124","Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile":          "?0",
    "Sec-Ch-Ua-Platform":        '"Windows"',
    "Sec-Fetch-Dest":            "document",
    "Sec-Fetch-Mode":            "navigate",
    "Sec-Fetch-Site":            "same-origin",
    "Sec-Fetch-User":            "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection":                "keep-alive",
}

# ═══════════════════════════════════════════════
#  SESSION STATE  (module-level singletons)
# ═══════════════════════════════════════════════
_session:       AsyncSession | None = None
_csrf_token:    str  = ""
_session_lock        = asyncio.Lock()
_login_retries: int  = 0
_bot_start_time      = datetime.utcnow()


async def _get_session() -> AsyncSession:
    global _session
    if _session is None:
        _session = AsyncSession(
            impersonate="chrome124",
            headers=CF_HEADERS,
            timeout=30,
            verify=True,
        )
    return _session


async def _reset_session() -> None:
    global _session, _csrf_token
    if _session:
        try:
            await _session.close()
        except Exception:
            pass
    _session    = None
    _csrf_token = ""


async def _do_login() -> bool:
    global _csrf_token, _login_retries
    session = await _get_session()
    try:
        print("🔐 Logging in to iVAS SMS …")

        # 1 – Load login page
        page = await session.get(
            LOGIN_URL,
            headers={**CF_HEADERS, "Sec-Fetch-Site": "none"},
            allow_redirects=True,
        )

        # 2 – Handle Cloudflare JS challenge (rare with curl_cffi)
        for attempt in range(3):
            if "cf-spinner" in page.text or "Checking your browser" in page.text:
                wait = 4 * (attempt + 1)
                print(f"   ⚠️  CF challenge – waiting {wait}s …")
                await asyncio.sleep(wait)
                page = await session.get(LOGIN_URL, allow_redirects=True)
            else:
                break

        soup  = BeautifulSoup(page.text, "html.parser")
        field = soup.find("input", {"name": "_token"})
        if not field:
            print("   ❌ CSRF token not found on login page.")
            _login_retries += 1
            return False

        csrf = field["value"]
        await asyncio.sleep(1.1)   # human-paced pause

        # 3 – POST credentials
        resp = await session.post(
            LOGIN_URL,
            data={"email": USERNAME, "password": PASSWORD, "_token": csrf},
            headers={
                **CF_HEADERS,
                "Content-Type":  "application/x-www-form-urlencoded",
                "Origin":        "https://www.ivasms.com",
                "Referer":       LOGIN_URL,
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document",
            },
            allow_redirects=True,
        )

        if 'name="password"' in resp.text or "Security verification failed" in resp.text:
            print("   ❌ Login rejected (CF or bad credentials).")
            _login_retries += 1
            return False

        # 4 – Extract dashboard CSRF
        dash  = BeautifulSoup(resp.text, "html.parser")
        meta  = dash.find("meta", {"name": "csrf-token"})
        if not meta:
            print("   ❌ Dashboard CSRF not found.")
            _login_retries += 1
            return False

        _csrf_token    = meta["content"]
        _login_retries = 0
        print("   ✅ Login successful!")
        return True

    except Exception as exc:
        print(f"   ❌ Login error: {exc}")
        traceback.print_exc()
        _login_retries += 1
        return False


async def ensure_logged_in() -> bool:
    """Return True when we have a live, authenticated session."""
    global _csrf_token, _login_retries

    if _login_retries >= MAX_LOGIN_RETRIES:
        print(f"⛔ {_login_retries} consecutive failures – cooling down 60 s")
        await asyncio.sleep(60)
        _login_retries = 0

    async with _session_lock:
        if not _csrf_token:
            return await _do_login()

        # Probe session liveness
        try:
            session = await _get_session()
            probe   = await session.get(
                SESSION_CHECK_URL,
                headers={**CF_HEADERS, "Referer": BASE_URL},
                allow_redirects=True,
            )
            if "login" in probe.url or 'name="password"' in probe.text:
                print("🔄 Session expired – re-logging in …")
                _csrf_token = ""
                return await _do_login()
            return True
        except Exception:
            _csrf_token = ""
            return await _do_login()


# ═══════════════════════════════════════════════
#  LOOKUP TABLES
# ═══════════════════════════════════════════════
COUNTRY_FLAGS: dict[str, str] = {
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

SERVICE_KEYWORDS: dict[str, list[str]] = {
    "Facebook": ["facebook"], "Google": ["google", "gmail"], "WhatsApp": ["whatsapp"],
    "Telegram": ["telegram"], "Instagram": ["instagram"], "Amazon": ["amazon"],
    "Netflix": ["netflix"], "LinkedIn": ["linkedin"],
    "Microsoft": ["microsoft", "outlook", "live.com"], "Apple": ["apple", "icloud"],
    "Twitter": ["twitter"], "Snapchat": ["snapchat"], "TikTok": ["tiktok"],
    "Discord": ["discord"], "Signal": ["signal"], "Viber": ["viber"], "IMO": ["imo"],
    "PayPal": ["paypal"], "Binance": ["binance"], "Uber": ["uber"], "Bolt": ["bolt"],
    "Airbnb": ["airbnb"], "Yahoo": ["yahoo"], "Steam": ["steam"],
    "Foodpanda": ["foodpanda"], "Messenger": ["messenger", "meta"],
    "YouTube": ["youtube"], "eBay": ["ebay"], "AliExpress": ["aliexpress"],
    "Alibaba": ["alibaba"], "Flipkart": ["flipkart"], "Skype": ["skype"],
    "Spotify": ["spotify"], "Stripe": ["stripe"], "Cash App": ["cash app", "square cash"],
    "Venmo": ["venmo"], "Zelle": ["zelle"], "Wise": ["wise", "transferwise"],
    "Coinbase": ["coinbase"], "KuCoin": ["kucoin"], "Bybit": ["bybit"],
    "OKX": ["okx"], "Huobi": ["huobi"], "Kraken": ["kraken"], "MetaMask": ["metamask"],
    "Epic Games": ["epic games", "epicgames"], "PlayStation": ["playstation", "psn"],
    "Xbox": ["xbox"], "Twitch": ["twitch"], "Reddit": ["reddit"],
    "ProtonMail": ["protonmail", "proton"], "Zoho": ["zoho"],
    "Indeed": ["indeed"], "Upwork": ["upwork"], "Fiverr": ["fiverr"],
    "Booking.com": ["booking.com"], "Careem": ["careem"],
    "Swiggy": ["swiggy"], "Zomato": ["zomato"],
    "OnlyFans": ["onlyfans"], "Tinder": ["tinder"], "Bumble": ["bumble"],
    "Line": ["line"], "WeChat": ["wechat"], "VK": ["vk", "vkontakte"],
}

SERVICE_EMOJIS: dict[str, str] = {
    "Telegram": "📩", "WhatsApp": "🟢", "Facebook": "📘", "Instagram": "📸",
    "Messenger": "💬", "Google": "🔍", "YouTube": "▶️", "Twitter": "🐦",
    "TikTok": "🎵", "Snapchat": "👻", "Amazon": "🛒", "Microsoft": "🪟",
    "Netflix": "🎬", "Spotify": "🎶", "Apple": "🍏", "PayPal": "💰",
    "Stripe": "💳", "Cash App": "💵", "Venmo": "💸", "Zelle": "🏦",
    "Wise": "🌐", "Binance": "🪙", "Coinbase": "🪙", "KuCoin": "🪙",
    "Bybit": "📈", "OKX": "🟠", "MetaMask": "🦊", "Discord": "🗨️",
    "Steam": "🎮", "Epic Games": "🕹️", "PlayStation": "🎮", "Xbox": "🎮",
    "Twitch": "📺", "Reddit": "👽", "LinkedIn": "💼", "Upwork": "🧑‍💻",
    "Fiverr": "💻", "Airbnb": "🏠", "Booking.com": "🛏️", "Uber": "🚗",
    "Bolt": "🚖", "OnlyFans": "🔞", "Tinder": "🔥", "Bumble": "🐝",
    "Signal": "🔐", "Viber": "📞", "WeChat": "💬", "VK": "🌐", "Unknown": "❓",
}


# ═══════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════
def esc(text: str) -> str:
    """Escape special chars for MarkdownV2."""
    return re.sub(r'([_*\[\]()~`>#+=|{}.!\-\\])', r'\\\1', str(text))


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_chat_ids() -> list:
    data = load_json(CHAT_IDS_FILE, None)
    if data is None:
        save_json(CHAT_IDS_FILE, INITIAL_CHAT_IDS)
        return list(INITIAL_CHAT_IDS)
    return data


def save_chat_ids(ids: list) -> None:
    save_json(CHAT_IDS_FILE, ids)


def load_processed_ids() -> set:
    return set(load_json(STATE_FILE, []))


def mark_processed(sms_id: str) -> None:
    ids = load_processed_ids()
    ids.add(sms_id)
    save_json(STATE_FILE, list(ids)[-5000:])


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


def is_admin(uid) -> bool:
    return str(uid) in ADMIN_CHAT_IDS


def uptime_str() -> str:
    delta = datetime.utcnow() - _bot_start_time
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}h {m}m {s}s"


# ═══════════════════════════════════════════════
#  SMS FETCHER
# ═══════════════════════════════════════════════
async def fetch_sms(session: AsyncSession, csrf: str) -> list[dict]:
    messages: list[dict] = []
    try:
        today      = datetime.utcnow()
        start_date = today - timedelta(days=1)
        from_str   = start_date.strftime('%m/%d/%Y')
        to_str     = today.strftime('%m/%d/%Y')
        ref_sms    = urljoin(BASE_URL, "portal/sms/received")

        resp = await session.post(
            SMS_API_ENDPOINT,
            data={"from": from_str, "to": to_str, "_token": csrf},
            headers={**CF_HEADERS, "Referer": ref_sms, "X-Requested-With": "XMLHttpRequest"},
        )
        resp.raise_for_status()

        soup       = BeautifulSoup(resp.text, "html.parser")
        group_divs = soup.find_all("div", class_="pointer")
        if not group_divs:
            return []

        group_ids = []
        for div in group_divs:
            m = re.search(r"getDetials\('(.+?)'\)", div.get("onclick", ""))
            if m:
                group_ids.append(m.group(1))

        num_url = urljoin(BASE_URL, "portal/sms/received/getsms/number")
        sms_url = urljoin(BASE_URL, "portal/sms/received/getsms/number/sms")

        for gid in group_ids:
            nr = await session.post(
                num_url,
                data={"start": from_str, "end": to_str, "range": gid, "_token": csrf},
                headers={**CF_HEADERS, "Referer": ref_sms},
            )
            ndivs = BeautifulSoup(nr.text, "html.parser").select("div[onclick*='getDetialsNumber']")
            for ndiv in ndivs:
                phone = ndiv.text.strip()
                sr    = await session.post(
                    sms_url,
                    data={"start": from_str, "end": to_str,
                          "Number": phone, "Range": gid, "_token": csrf},
                    headers={**CF_HEADERS, "Referer": ref_sms},
                )
                for card in BeautifulSoup(sr.text, "html.parser").find_all("div", class_="card-body"):
                    p = card.find("p", class_="mb-0")
                    if not p:
                        continue
                    sms_text = p.get_text(separator="\n").strip()
                    m2       = re.match(r'([a-zA-Z\s]+)', gid)
                    country  = m2.group(1).strip() if m2 else gid.strip()
                    flag     = COUNTRY_FLAGS.get(country, COUNTRY_FLAGS.get(country.title(), "🏴‍☠️"))
                    messages.append({
                        "id":       f"{phone}||{sms_text[:80]}",
                        "time":     datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                        "number":   phone,
                        "country":  country,
                        "flag":     flag,
                        "service":  detect_service(sms_text),
                        "code":     extract_code(sms_text),
                        "full_sms": sms_text,
                    })
    except Exception as exc:
        print(f"❌ fetch_sms error: {exc}")
        traceback.print_exc()
    return messages


# ═══════════════════════════════════════════════
#  MY NUMBERS FETCHER
# ═══════════════════════════════════════════════
async def fetch_my_numbers(session: AsyncSession) -> list[str]:
    """Scrape all numbers from /portal/numbers (all pages)."""
    numbers: list[str] = []
    try:
        page_url = NUMBERS_PAGE_URL
        while page_url:
            resp = await session.get(
                page_url,
                headers={**CF_HEADERS, "Referer": BASE_URL},
                allow_redirects=True,
            )
            if "login" in resp.url or 'name="password"' in resp.text:
                return []   # session died – caller will handle

            soup = BeautifulSoup(resp.text, "html.parser")

            # Grab number cells from the table (first <td> in each data row)
            for row in soup.select("table tbody tr"):
                cells = row.find_all("td")
                if cells:
                    num = cells[0].get_text(strip=True)
                    if re.match(r'^\d{7,}$', num):
                        numbers.append(num)

            # Follow pagination  →  look for "Next" link
            next_link = soup.select_one("a.paginate_button.next:not(.disabled)")
            if next_link and next_link.get("href") and next_link["href"] != "#":
                href = next_link["href"]
                page_url = href if href.startswith("http") else urljoin(BASE_URL, href)
            else:
                break

    except Exception as exc:
        print(f"❌ fetch_my_numbers error: {exc}")
        traceback.print_exc()
    return numbers


# ═══════════════════════════════════════════════
#  TELEGRAM SENDERS
# ═══════════════════════════════════════════════
async def send_otp_message(context, chat_id: str, msg: dict) -> None:
    svc   = msg.get("service", "Unknown")
    emoji = SERVICE_EMOJIS.get(svc, "❓")
    flag  = msg.get("flag", "🏴‍☠️")

    caption = (
        f"🔔 *New OTP Received*\n\n"
        f"📞 *Number:* `{esc(msg.get('number','N/A'))}`\n"
        f"🔑 *Code:* `{esc(msg.get('code','N/A'))}`\n"
        f"🏆 *Service:* {emoji} {esc(svc)}\n"
        f"🌎 *Country:* {esc(msg.get('country','N/A'))} {flag}\n"
        f"⏳ *Time \\(UTC\\):* `{esc(msg.get('time','N/A'))}`\n\n"
        f"💬 *Full Message:*\n{esc(msg.get('full_sms','N/A'))}"
    )
    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=BANNER_IMAGE_URL,
            caption=caption,
            parse_mode="MarkdownV2",
            reply_markup=SOCIAL_BUTTONS,
        )
    except Exception as e:
        print(f"⚠️  Photo send failed ({chat_id}): {e} – falling back to text")
        try:
            plain = (
                f"🔔 New OTP Received\n\n"
                f"📞 Number : {msg.get('number')}\n"
                f"🔑 Code   : {msg.get('code')}\n"
                f"🏆 Service: {svc}\n"
                f"🌎 Country: {msg.get('country')} {flag}\n"
                f"⏳ Time   : {msg.get('time')}\n\n"
                f"💬 Message:\n{msg.get('full_sms')}"
            )
            await context.bot.send_message(
                chat_id=chat_id, text=plain, reply_markup=SOCIAL_BUTTONS,
            )
        except Exception as e2:
            print(f"❌ Both sends failed ({chat_id}): {e2}")


# ═══════════════════════════════════════════════
#  COMMAND HANDLERS
# ═══════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text(
            "⛔ You are not authorised to use this bot\\.",
            parse_mode="MarkdownV2",
            reply_markup=SOCIAL_BUTTONS,
        )
        return

    menu = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 My Numbers",   callback_data="cmd_mynumbers")],
        [InlineKeyboardButton("📊 Status",       callback_data="cmd_status")],
        [InlineKeyboardButton("📜 List Chats",   callback_data="cmd_listchats")],
        [InlineKeyboardButton("📱 NUMBER CHANNEL", url="https://t.me/mrafrixtech")],
        [InlineKeyboardButton("👨‍💻 CONTACT DEV",   url="https://t.me/jaden_afrix")],
    ])
    await update.message.reply_photo(
        photo=BANNER_IMAGE_URL,
        caption=(
            "👋 *Welcome, Admin\\!*\n\n"
            "🤖 *iVAS SMS → Telegram Bot* \\| v3\\.0\n\n"
            "*Commands:*\n"
            "`/start` — This menu\n"
            "`/status` — Bot health\n"
            "`/mynumbers` — List your iVAS numbers\n"
            "`/add_chat <id>` — Add broadcast chat\n"
            "`/remove_chat <id>` — Remove broadcast chat\n"
            "`/list_chats` — Show all chats\n"
        ),
        parse_mode="MarkdownV2",
        reply_markup=menu,
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.answer()
        send = update.callback_query.message.reply_text
    else:
        send = update.message.reply_text

    if not is_admin(getattr(update.effective_user, "id", 0)):
        await send("⛔ Admins only.")
        return

    logged = "✅ Active" if _csrf_token else "❌ Logged out"
    await send(
        f"🤖 *Bot Status*\n\n"
        f"🔐 Session : {esc(logged)}\n"
        f"🔁 Retries : `{_login_retries}` / `{MAX_LOGIN_RETRIES}`\n"
        f"⏱ Polling  : every `{POLLING_INTERVAL}s`\n"
        f"🕐 Uptime   : `{esc(uptime_str())}`\n"
        f"📡 Chats    : `{len(load_chat_ids())}`",
        parse_mode="MarkdownV2",
    )


async def cmd_add_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admins only.")
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: `/add_chat <chat_id>`", parse_mode="MarkdownV2")
        return
    cid  = context.args[0]
    ids  = load_chat_ids()
    if cid in ids:
        await update.message.reply_text(f"⚠️ `{esc(cid)}` already registered\\.", parse_mode="MarkdownV2")
    else:
        ids.append(cid)
        save_chat_ids(ids)
        await update.message.reply_text(f"✅ Chat `{esc(cid)}` added\\.", parse_mode="MarkdownV2")


async def cmd_remove_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admins only.")
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: `/remove_chat <chat_id>`", parse_mode="MarkdownV2")
        return
    cid = context.args[0]
    ids = load_chat_ids()
    if cid in ids:
        ids.remove(cid)
        save_chat_ids(ids)
        await update.message.reply_text(f"✅ Chat `{esc(cid)}` removed\\.", parse_mode="MarkdownV2")
    else:
        await update.message.reply_text(f"🤔 `{esc(cid)}` not found\\.", parse_mode="MarkdownV2")


async def cmd_list_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.answer()
        send = update.callback_query.message.reply_text
    else:
        send = update.message.reply_text

    if not is_admin(getattr(update.effective_user, "id", 0)):
        await send("⛔ Admins only.")
        return
    ids = load_chat_ids()
    if not ids:
        await send("No chats registered.")
        return
    lines = "\n".join(f"• `{esc(c)}`" for c in ids)
    await send(f"📜 *Registered Chats:*\n\n{lines}", parse_mode="MarkdownV2")


async def cmd_my_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch all numbers from iVAS /portal/numbers and send as a .txt file."""
    if update.callback_query:
        await update.callback_query.answer("Fetching numbers…")
        reply = update.callback_query.message.reply_text
        reply_doc = update.callback_query.message.reply_document
    else:
        reply     = update.message.reply_text
        reply_doc = update.message.reply_document

    if not is_admin(getattr(update.effective_user, "id", 0)):
        await reply("⛔ Admins only.")
        return

    wait_msg = await reply("⏳ Fetching your numbers from iVAS…")

    if not await ensure_logged_in():
        await wait_msg.edit_text("❌ Could not log in to iVAS\\. Try again later\\.", parse_mode="MarkdownV2")
        return

    session = await _get_session()
    numbers = await fetch_my_numbers(session)

    if not numbers:
        await wait_msg.edit_text("⚠️ No numbers found \\(or session issue\\)\\.", parse_mode="MarkdownV2")
        return

    # Remove duplicates, keep order
    unique  = list(dict.fromkeys(numbers))
    total   = len(unique)

    # Build plain-text file  (one number per line)
    content = "\n".join(unique).encode()
    buf     = io.BytesIO(content)
    buf.name = f"iVAS_numbers_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"

    await wait_msg.delete()
    await reply_doc(
        document=buf,
        filename=buf.name,
        caption=(
            f"📋 *My iVAS Numbers*\n\n"
            f"📊 Total: `{total}` numbers\n"
            f"🕐 Fetched: `{esc(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'))}`"
        ),
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="cmd_mynumbers")],
        ]),
    )
    print(f"✅ Sent {total} numbers to admin.")


# ─── Inline-button router ───
async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q  = update.callback_query
    cd = q.data
    if cd == "cmd_mynumbers":
        await cmd_my_numbers(update, context)
    elif cd == "cmd_status":
        await cmd_status(update, context)
    elif cd == "cmd_listchats":
        await cmd_list_chats(update, context)
    else:
        await q.answer("Unknown action.")


# ═══════════════════════════════════════════════
#  BACKGROUND POLLING JOB
# ═══════════════════════════════════════════════
async def sms_poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    global _csrf_token
    ts = datetime.utcnow().strftime('%H:%M:%S')
    print(f"[{ts}] Polling SMS …")

    if not await ensure_logged_in():
        print("   ❌ Login failed – skipping cycle.")
        return

    session = await _get_session()
    try:
        messages = await fetch_sms(session, _csrf_token)
    except Exception as exc:
        print(f"   ❌ Fetch error: {exc}")
        _csrf_token = ""   # force re-login next cycle
        return

    if not messages:
        print("   ✔ No new SMS.")
        return

    processed = load_processed_ids()
    chat_ids  = load_chat_ids()
    new_count = 0

    for msg in reversed(messages):     # oldest first
        if msg["id"] in processed:
            continue
        new_count += 1
        print(f"   → OTP from {msg['number']} ({msg['service']})")
        for cid in chat_ids:
            await send_otp_message(context, cid, msg)
        mark_processed(msg["id"])

    if new_count:
        print(f"   ✅ Forwarded {new_count} new message(s).")
    else:
        print("   ✔ All already processed.")


# ═══════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════
def main() -> None:
    print("🚀 iVAS SMS Bot v3.0 starting …")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("status",      cmd_status))
    app.add_handler(CommandHandler("mynumbers",   cmd_my_numbers))
    app.add_handler(CommandHandler("add_chat",    cmd_add_chat))
    app.add_handler(CommandHandler("remove_chat", cmd_remove_chat))
    app.add_handler(CommandHandler("list_chats",  cmd_list_chats))

    # Inline buttons
    app.add_handler(CallbackQueryHandler(button_router))

    # Background SMS poller
    jq = app.job_queue
    if jq is None:
        print("❌ JobQueue not available.")
        print("   pip install 'python-telegram-bot[job-queue]'")
        return

    jq.run_repeating(sms_poll_job, interval=POLLING_INTERVAL, first=5)
    print(f"✅ SMS polling every {POLLING_INTERVAL}s")
    print("🤖 Bot is live. Ctrl+C to stop.\n")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
