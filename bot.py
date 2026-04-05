import re
import json
import os
import asyncio
import traceback
import logging
import sys
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from playwright.async_api import async_playwright
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import Conflict, TimedOut, NetworkError, RetryAfter

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  HARDCODED CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN     = "8678706957:AAGxaNWrM6XLm0jk3-ULBrm4Fbx4AprTdNg"
IVAS_EMAIL    = "tawandamahachi07@gmail.com"
IVAS_PASSWORD = "mahachi2007"
ADMIN_IDS     = ["8339856952"]
INITIAL_CHATS = ["-1003854641278"]

LOGIN_URL    = "https://www.ivasms.com/login"
PORTAL_URL   = "https://www.ivasms.com/portal/sms/received"
SMS_URL      = "https://www.ivasms.com/portal/sms/received/getsms"
NUMBERS_URL  = "https://www.ivasms.com/portal/sms/received/getsms/number"
SMS_DETAIL   = "https://www.ivasms.com/portal/sms/received/getsms/number/sms"

DATA_DIR      = "/data" if os.path.isdir("/data") else "."
STATE_FILE    = os.path.join(DATA_DIR, "seen.json")
CHATS_FILE    = os.path.join(DATA_DIR, "chats.json")
DEBUG_SS      = os.path.join(DATA_DIR, "debug.png")
DEBUG_HTML    = os.path.join(DATA_DIR, "debug.html")

POLL_SECS     = 30

# ─────────────────────────────────────────────
#  TELEGRAM BUTTONS
# ─────────────────────────────────────────────
BUTTONS = InlineKeyboardMarkup([
    [InlineKeyboardButton("📱 NUMBER CHANNEL", url="https://t.me/mrafrixtech")],
    [InlineKeyboardButton("📡 BACKUP CHANNEL",  url="https://t.me/auroratechinc")],
    [InlineKeyboardButton("🔑 OTP GROUP",        url="https://t.me/afrixotpgc")],
    [InlineKeyboardButton("👨‍💻 CONTACT DEV",     url="https://t.me/jaden_afrix")],
])

# ─────────────────────────────────────────────
#  COUNTRY FLAGS
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
#  SERVICE DETECTION
# ─────────────────────────────────────────────
SERVICE_KEYWORDS = {
    "Facebook":    ["facebook"],
    "Google":      ["google","gmail"],
    "WhatsApp":    ["whatsapp"],
    "Telegram":    ["telegram"],
    "Instagram":   ["instagram"],
    "Amazon":      ["amazon"],
    "Netflix":     ["netflix"],
    "LinkedIn":    ["linkedin"],
    "Microsoft":   ["microsoft","outlook","live.com"],
    "Apple":       ["apple","icloud"],
    "Twitter":     ["twitter","x.com"],
    "Snapchat":    ["snapchat"],
    "TikTok":      ["tiktok"],
    "Discord":     ["discord"],
    "Signal":      ["signal"],
    "Viber":       ["viber"],
    "IMO":         ["imo"],
    "PayPal":      ["paypal"],
    "Binance":     ["binance"],
    "Uber":        ["uber"],
    "Bolt":        ["bolt"],
    "Airbnb":      ["airbnb"],
    "Yahoo":       ["yahoo"],
    "Steam":       ["steam"],
    "Foodpanda":   ["foodpanda"],
    "Messenger":   ["messenger","meta"],
    "YouTube":     ["youtube"],
    "eBay":        ["ebay"],
    "AliExpress":  ["aliexpress"],
    "Alibaba":     ["alibaba"],
    "Flipkart":    ["flipkart"],
    "Skype":       ["skype"],
    "Spotify":     ["spotify"],
    "Stripe":      ["stripe"],
    "Cash App":    ["cash app","cashapp"],
    "Venmo":       ["venmo"],
    "Zelle":       ["zelle"],
    "Wise":        ["wise","transferwise"],
    "Coinbase":    ["coinbase"],
    "KuCoin":      ["kucoin"],
    "Bybit":       ["bybit"],
    "OKX":         ["okx"],
    "Huobi":       ["huobi"],
    "Kraken":      ["kraken"],
    "MetaMask":    ["metamask"],
    "Epic Games":  ["epic games","epicgames"],
    "PlayStation": ["playstation","psn"],
    "Xbox":        ["xbox"],
    "Twitch":      ["twitch"],
    "Reddit":      ["reddit"],
    "ProtonMail":  ["protonmail","proton"],
    "Zoho":        ["zoho"],
    "Indeed":      ["indeed"],
    "Upwork":      ["upwork"],
    "Fiverr":      ["fiverr"],
    "Booking.com": ["booking.com"],
    "Careem":      ["careem"],
    "Swiggy":      ["swiggy"],
    "Zomato":      ["zomato"],
    "McDonald's":  ["mcdonalds","mcdonald's"],
    "KFC":         ["kfc"],
    "Shein":       ["shein"],
    "OnlyFans":    ["onlyfans"],
    "Tinder":      ["tinder"],
    "Bumble":      ["bumble"],
    "Line":        ["line app","line:"],
    "WeChat":      ["wechat"],
    "VK":          ["vk.com","vkontakte"],
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

# ─────────────────────────────────────────────
#  GLOBAL STATE
# ─────────────────────────────────────────────
_pw            = None
_browser       = None
_bcontext      = None
_curl_session  = None
_csrf          = ""
_logged_in     = False
_fail_count    = 0
_login_method  = "none"


# ─────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────
def esc(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+=|{}.!\-\\])', r'\\\1', str(text))

def rj(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default

def wj(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_chats():
    d = rj(CHATS_FILE, None)
    if d is None:
        wj(CHATS_FILE, INITIAL_CHATS)
        return list(INITIAL_CHATS)
    return d

def save_chats(chats):
    wj(CHATS_FILE, chats)

def load_seen():
    return set(rj(STATE_FILE, []))

def mark_seen(uid):
    seen = load_seen()
    seen.add(uid)
    wj(STATE_FILE, list(seen)[-5000:])

def detect_service(text):
    lower = text.lower()
    for name, kws in SERVICE_KEYWORDS.items():
        if any(k in lower for k in kws):
            return name
    return "Unknown"

def extract_code(text):
    m = re.search(r'\b(\d{3}-\d{3})\b', text)
    if m:
        return m.group(1)
    m = re.search(r'\b(\d{4,8})\b', text)
    return m.group(1) if m else "N/A"

def get_flag(country):
    return COUNTRY_FLAGS.get(country) or COUNTRY_FLAGS.get(country.title()) or "🏴‍☠️"

def is_admin(uid):
    return str(uid) in ADMIN_IDS

async def save_debug(page):
    """Save screenshot + HTML for admin to review via /debug."""
    try:
        await page.screenshot(path=DEBUG_SS, full_page=True)
    except Exception:
        pass
    try:
        html = await page.content()
        with open(DEBUG_HTML, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        pass


# ─────────────────────────────────────────────
#  PLAYWRIGHT BROWSER
# ─────────────────────────────────────────────
async def start_browser():
    global _pw, _browser, _bcontext
    log.info("[PW] Starting Chromium …")
    _pw = await async_playwright().start()
    _browser = await _pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )
    _bcontext = await _browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/New_York",
        ignore_https_errors=True,
        java_script_enabled=True,
    )
    await _bcontext.add_init_script("""
        Object.defineProperty(navigator, 'webdriver',  {get: () => undefined});
        Object.defineProperty(navigator, 'plugins',    {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages',  {get: () => ['en-US','en']});
        Object.defineProperty(navigator, 'platform',   {get: () => 'Win32'});
        Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
        window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};
        window.outerHeight = 900;
        window.outerWidth  = 1440;
    """)
    log.info("[PW] Browser ready.")


async def stop_browser():
    global _pw, _browser, _bcontext
    for obj in (_bcontext, _browser, _pw):
        if obj:
            try:
                await obj.close()
            except Exception:
                pass
    _pw = _browser = _bcontext = None


# ─────────────────────────────────────────────
#  LOGIN STRATEGY A — Playwright with 3 submit methods
# ─────────────────────────────────────────────
async def _pw_login() -> bool:
    global _csrf, _logged_in, _fail_count, _login_method

    if _bcontext is None:
        await start_browser()

    log.info("[PW] Attempting login …")
    page = await _bcontext.new_page()

    try:
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
        log.info("[PW] Page loaded: %s", page.url)

        # Wait for CF to clear and login form to appear (up to 30s)
        email_input = None
        for i in range(6):
            email_input = await page.query_selector('input[name="email"]')
            if email_input:
                log.info("[PW] Login form visible (attempt %d)", i + 1)
                break
            log.info("[PW] CF challenge active, waiting 5s … (%d/6)", i + 1)
            await asyncio.sleep(5)

        if not email_input:
            log.warning("[PW] Login form never appeared.")
            await save_debug(page)
            _fail_count += 1
            return False

        # Give the page a moment to settle before interacting
        await asyncio.sleep(2)

        # Fill email with human-like delays
        await page.click('input[name="email"]')
        await page.fill('input[name="email"]', "")
        for ch in IVAS_EMAIL:
            await page.keyboard.type(ch, delay=50 + (hash(ch) % 50))
        await asyncio.sleep(0.6)

        # Fill password
        await page.click('input[name="password"]')
        await page.fill('input[name="password"]', "")
        for ch in IVAS_PASSWORD:
            await page.keyboard.type(ch, delay=40 + (hash(ch) % 40))
        await asyncio.sleep(0.4)

        log.info("[PW] Credentials filled. Submitting …")

        # ── Submit strategy 1: Click the button ──
        submit_btn = await page.query_selector('button[type="submit"]')
        if submit_btn:
            await submit_btn.click()
        else:
            # Fallback: press Enter in password field
            await page.keyboard.press("Enter")

        # Wait up to 15s for URL to change
        try:
            await page.wait_for_function(
                "() => !window.location.href.includes('/login')",
                timeout=15_000,
            )
            log.info("[PW] Strategy 1 worked — redirected to: %s", page.url)
        except Exception:
            log.info("[PW] Strategy 1 didn't redirect. Trying Enter key …")

            # ── Submit strategy 2: Press Enter in password field ──
            await page.focus('input[name="password"]')
            await page.keyboard.press("Enter")
            try:
                await page.wait_for_function(
                    "() => !window.location.href.includes('/login')",
                    timeout=12_000,
                )
                log.info("[PW] Strategy 2 worked — redirected to: %s", page.url)
            except Exception:
                log.info("[PW] Strategy 2 didn't redirect. Trying JS form submit …")

                # ── Submit strategy 3: JavaScript form submit ──
                await page.evaluate("""
                    () => {
                        const form = document.querySelector('form');
                        if (form) {
                            form.submit();
                        }
                    }
                """)
                try:
                    await page.wait_for_function(
                        "() => !window.location.href.includes('/login')",
                        timeout=15_000,
                    )
                    log.info("[PW] Strategy 3 worked — redirected to: %s", page.url)
                except Exception:
                    # All 3 strategies failed — save debug info
                    log.warning("[PW] All submit strategies failed. Current URL: %s", page.url)
                    body_text = ""
                    try:
                        body_text = (await page.inner_text("body"))[:400]
                    except Exception:
                        pass
                    log.warning("[PW] Page snippet: %s", body_text)
                    await save_debug(page)
                    _fail_count += 1
                    _logged_in = False
                    return False

        # We're past the login page — extract CSRF token
        await page.wait_for_load_state("domcontentloaded", timeout=15_000)

        token = await page.evaluate(
            'document.querySelector(\'meta[name="csrf-token"]\')?.content ?? ""'
        )
        if token:
            _csrf = token
            log.info("[PW] CSRF: %s…", _csrf[:12])
        else:
            log.warning("[PW] No CSRF meta tag found on dashboard.")

        _fail_count  = 0
        _logged_in   = True
        _login_method = "playwright"
        log.info("[PW] Login SUCCESS ✅")
        return True

    except Exception as exc:
        log.error("[PW] Login exception: %s", exc)
        try:
            await save_debug(page)
        except Exception:
            pass
        _fail_count += 1
        _logged_in = False
        return False
    finally:
        await page.close()


# ─────────────────────────────────────────────
#  LOGIN STRATEGY B — curl_cffi (TLS spoof)
# ─────────────────────────────────────────────
async def _curl_login() -> bool:
    global _csrf, _logged_in, _fail_count, _curl_session, _login_method

    log.info("[CURL] Attempting login with curl_cffi …")

    try:
        if _curl_session:
            try:
                await _curl_session.close()
            except Exception:
                pass

        _curl_session = AsyncSession(
            impersonate="chrome124",
            timeout=30,
            verify=True,
            allow_redirects=True,
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language":           "en-US,en;q=0.9",
            "Accept-Encoding":           "gzip, deflate, br",
            "Cache-Control":             "no-cache",
            "Sec-Ch-Ua":                 '"Chromium";v="124","Google Chrome";v="124"',
            "Sec-Ch-Ua-Mobile":          "?0",
            "Sec-Ch-Ua-Platform":        '"Windows"',
            "Sec-Fetch-Dest":            "document",
            "Sec-Fetch-Mode":            "navigate",
            "Sec-Fetch-Site":            "none",
            "Upgrade-Insecure-Requests": "1",
        }

        # GET login page to harvest CSRF token
        r = await _curl_session.get(LOGIN_URL, headers=headers)
        log.info("[CURL] GET login: HTTP %d", r.status_code)

        if r.status_code not in (200, 302):
            log.warning("[CURL] Unexpected status %d — CF likely blocking.", r.status_code)
            _fail_count += 1
            return False

        soup = BeautifulSoup(r.text, "html.parser")
        field = soup.find("input", {"name": "_token"})
        if not field:
            log.warning("[CURL] CSRF field not found — CF blocking GET.")
            # Save HTML for debugging
            try:
                with open(DEBUG_HTML, "w") as f:
                    f.write(r.text[:5000])
            except Exception:
                pass
            _fail_count += 1
            return False

        csrf_token = field.get("value", "")
        log.info("[CURL] Page CSRF: %s…", csrf_token[:12])

        await asyncio.sleep(1.5)  # human-paced delay

        # POST credentials
        post_headers = {
            **headers,
            "Sec-Fetch-Site": "same-origin",
            "Referer":        LOGIN_URL,
            "Content-Type":   "application/x-www-form-urlencoded",
        }
        resp = await _curl_session.post(
            LOGIN_URL,
            data={
                "email":    IVAS_EMAIL,
                "password": IVAS_PASSWORD,
                "_token":   csrf_token,
            },
            headers=post_headers,
        )
        log.info("[CURL] POST login: HTTP %d, URL: %s", resp.status_code, str(resp.url)[:60])

        if "login" in str(resp.url).lower():
            body_snippet = resp.text[:200]
            log.warning("[CURL] Still on login page. Snippet: %s", body_snippet)
            _fail_count += 1
            _logged_in = False
            return False

        # Extract CSRF from dashboard
        dash = BeautifulSoup(resp.text, "html.parser")
        meta = dash.find("meta", {"name": "csrf-token"})
        if meta:
            _csrf = meta.get("content", "")
            log.info("[CURL] Dashboard CSRF: %s…", _csrf[:12])
        else:
            _csrf = csrf_token
            log.warning("[CURL] No dashboard CSRF meta — using login token.")

        _fail_count   = 0
        _logged_in    = True
        _login_method = "curl"
        log.info("[CURL] Login SUCCESS ✅")
        return True

    except Exception as exc:
        log.error("[CURL] Exception: %s", exc)
        _fail_count += 1
        _logged_in = False
        return False


# ─────────────────────────────────────────────
#  LOGIN ORCHESTRATOR
# ─────────────────────────────────────────────
async def do_login() -> bool:
    global _logged_in

    # Strategy A: Playwright (real browser)
    try:
        if await _pw_login():
            return True
    except Exception as e:
        log.error("PW login crashed: %s", e)

    log.info("Playwright failed → trying curl_cffi …")

    # Strategy B: curl_cffi (TLS spoof, no JS)
    try:
        if await _curl_login():
            return True
    except Exception as e:
        log.error("CURL login crashed: %s", e)

    log.error("Both login strategies failed.")
    _logged_in = False
    return False


# ─────────────────────────────────────────────
#  CSRF REFRESH
# ─────────────────────────────────────────────
async def refresh_csrf() -> str:
    global _csrf, _logged_in

    if _login_method == "playwright" and _bcontext:
        page = await _bcontext.new_page()
        try:
            await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=30_000)
            if "login" in page.url:
                _csrf = ""
                _logged_in = False
                return ""
            token = await page.evaluate(
                'document.querySelector(\'meta[name="csrf-token"]\')?.content ?? ""'
            )
            if token:
                _csrf = token
            return _csrf
        except Exception:
            return _csrf
        finally:
            await page.close()

    elif _login_method == "curl" and _curl_session:
        try:
            r = await _curl_session.get(PORTAL_URL)
            if "login" in str(r.url).lower():
                _csrf = ""
                _logged_in = False
                return ""
            soup = BeautifulSoup(r.text, "html.parser")
            meta = soup.find("meta", {"name": "csrf-token"})
            if meta:
                _csrf = meta.get("content", "")
            return _csrf
        except Exception:
            return _csrf

    return _csrf


# ─────────────────────────────────────────────
#  SMS FETCHING
# ─────────────────────────────────────────────
async def _post(url, payload):
    """POST using whichever session is active."""
    if _login_method == "playwright" and _bcontext:
        r = await _bcontext.request.post(url, form=payload)
        status = r.status
        text   = await r.text()
        return status, text, str(r.url)
    elif _login_method == "curl" and _curl_session:
        r = await _curl_session.post(url, data=payload)
        return r.status_code, r.text, str(r.url)
    return 0, "", ""


async def fetch_sms() -> list:
    global _csrf, _logged_in

    if not _logged_in:
        return []

    token = _csrf
    if not token:
        log.info("No CSRF — refreshing …")
        token = await refresh_csrf()
    if not token:
        log.warning("Still no CSRF — skipping.")
        return []

    today    = datetime.utcnow()
    from_str = (today - timedelta(days=1)).strftime("%m/%d/%Y")
    to_str   = today.strftime("%m/%d/%Y")

    try:
        status, text, url = await _post(
            SMS_URL,
            {"from": from_str, "to": to_str, "_token": token},
        )

        if status == 419:
            log.warning("CSRF expired (419)")
            _csrf = ""
            _logged_in = False
            return []

        if "login" in url.lower():
            log.warning("Session expired — redirected to login.")
            _logged_in = False
            return []

        if status not in (200,):
            log.warning("SMS endpoint HTTP %d", status)
            return []

        soup       = BeautifulSoup(text, "html.parser")
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
                ns, nt, _ = await _post(
                    NUMBERS_URL,
                    {"start": from_str, "end": to_str, "range": gid, "_token": token},
                )
                if ns != 200:
                    continue

                for ndiv in BeautifulSoup(nt, "html.parser").select("div[onclick*='getDetialsNumber']"):
                    phone = ndiv.text.strip()
                    if not phone:
                        continue

                    ss, st, _ = await _post(
                        SMS_DETAIL,
                        {"start": from_str, "end": to_str,
                         "Number": phone, "Range": gid, "_token": token},
                    )
                    if ss != 200:
                        continue

                    for card in BeautifulSoup(st, "html.parser").find_all("div", class_="card-body"):
                        p = card.find("p", class_="mb-0")
                        if not p:
                            continue
                        sms = p.get_text(separator="\n").strip()
                        if not sms:
                            continue

                        m2      = re.match(r"([a-zA-Z\s]+)", gid)
                        country = m2.group(1).strip() if m2 else gid.strip()
                        svc     = detect_service(sms)

                        messages.append({
                            "id":      f"{phone}|{sms[:80]}",
                            "time":    datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                            "number":  phone,
                            "country": country,
                            "flag":    get_flag(country),
                            "service": svc,
                            "emoji":   SERVICE_EMOJIS.get(svc, "❓"),
                            "code":    extract_code(sms),
                            "sms":     sms,
                        })
            except Exception as e:
                log.error("Group %s error: %s", gid, e)
                continue

        return messages

    except Exception as e:
        log.error("fetch_sms error: %s", e)
        traceback.print_exc()
        return []


# ─────────────────────────────────────────────
#  SEND OTP MESSAGE
# ─────────────────────────────────────────────
async def send_otp(bot, chat_id, msg):
    text = (
        f"🔔 *New OTP Received*\n\n"
        f"📞 *Number:* `{esc(msg['number'])}`\n"
        f"🔑 *Code:* `{esc(msg['code'])}`\n"
        f"🏆 *Service:* {msg['emoji']} {esc(msg['service'])}\n"
        f"🌎 *Country:* {esc(msg['country'])} {msg['flag']}\n"
        f"⏳ *Time:* {esc(msg['time'])}\n\n"
        f"💬 *Message:*\n{esc(msg['sms'])}"
    )
    try:
        await bot.send_message(
            chat_id=chat_id, text=text,
            parse_mode="MarkdownV2", reply_markup=BUTTONS,
        )
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        try:
            await bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode="MarkdownV2", reply_markup=BUTTONS,
            )
        except Exception:
            pass
    except Exception:
        try:
            plain = (
                f"New OTP\n\nNumber: {msg['number']}\nCode: {msg['code']}\n"
                f"Service: {msg['service']}\nCountry: {msg['country']} {msg['flag']}\n"
                f"Time: {msg['time']}\n\nMessage:\n{msg['sms']}"
            )
            await bot.send_message(chat_id=chat_id, text=plain, reply_markup=BUTTONS)
        except Exception as e2:
            log.error("Send failed %s: %s", chat_id, e2)


# ─────────────────────────────────────────────
#  MAIN POLL LOOP
# ─────────────────────────────────────────────
async def poll_loop(bot):
    global _fail_count, _logged_in

    log.info("Starting poll loop …")

    # Initial login — 3 attempts
    for attempt in range(1, 4):
        if await do_login():
            break
        wait = 30 * attempt
        log.warning("Attempt %d/3 failed — retrying in %ds …", attempt, wait)
        await asyncio.sleep(wait)
    else:
        log.error("All 3 initial login attempts failed. Continuing to retry in loop.")

    while True:
        try:
            log.info("[%s] Polling …", datetime.utcnow().strftime("%H:%M:%S"))

            if not _logged_in or _fail_count >= 3:
                log.info("Re-login needed …")
                _fail_count = 0
                ok = await do_login()
                if not ok:
                    log.warning("Re-login failed — waiting 120s.")
                    await asyncio.sleep(120)
                    continue

            messages = await fetch_sms()

            if not messages:
                log.info("  No messages this cycle.")
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
                    log.info("  Sent %d new OTP(s).", new_count)
                else:
                    log.info("  All already seen.")

        except Exception as e:
            log.error("poll_loop error: %s", e)
            traceback.print_exc()

        await asyncio.sleep(POLL_SECS)


# ─────────────────────────────────────────────
#  TELEGRAM COMMANDS
# ─────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if is_admin(uid):
        await update.message.reply_text(
            "Welcome Admin\\!\n\n"
            "`/status` — Live bot status\n"
            "`/debug` — Browser screenshot \\+ HTML\n"
            "`/relogin` — Force re\\-login now\n"
            "`/add_chat <id>` — Add chat\n"
            "`/remove_chat <id>` — Remove chat\n"
            "`/list_chats` — List chats",
            parse_mode="MarkdownV2",
            reply_markup=BUTTONS,
        )
    else:
        await update.message.reply_text("Not authorized.", reply_markup=BUTTONS)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    pw  = "✅" if _bcontext      else "❌"
    cur = "✅" if _curl_session  else "❌"
    ses = "✅ Logged in" if _logged_in else "❌ Logged out"
    csr = "✅" if _csrf else "❌"
    await update.message.reply_text(
        f"*Bot Status*\n\n"
        f"Playwright: {pw}\n"
        f"curl\\_cffi: {cur}\n"
        f"Session: {ses}\n"
        f"CSRF: {csr}\n"
        f"Method: `{_login_method}`\n"
        f"Fails: {_fail_count}\n"
        f"Chats: {len(load_chats())}\n"
        f"Seen: {len(load_seen())} IDs\n\n"
        f"Email: `{esc(IVAS_EMAIL)}`",
        parse_mode="MarkdownV2",
    )


async def cmd_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    sent = False
    if os.path.exists(DEBUG_SS):
        try:
            await update.message.reply_photo(
                photo=open(DEBUG_SS, "rb"),
                caption="Last browser screenshot at login failure.",
            )
            sent = True
        except Exception as e:
            await update.message.reply_text(f"Screenshot error: {e}")

    if os.path.exists(DEBUG_HTML):
        try:
            with open(DEBUG_HTML, encoding="utf-8") as f:
                snippet = f.read(1500)
            await update.message.reply_text(
                f"HTML snippet:\n```\n{snippet[:1000]}\n```",
                parse_mode="MarkdownV2",
            )
            sent = True
        except Exception:
            pass

    if not sent:
        await update.message.reply_text(
            "No debug data yet. Login hasn't failed visually, or succeeded."
        )


async def cmd_relogin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    global _fail_count, _logged_in
    _fail_count = 0
    _logged_in  = False
    await update.message.reply_text("Triggering re-login now …")
    ok = await do_login()
    if ok:
        await update.message.reply_text(
            f"✅ Re-login succeeded via `{esc(_login_method)}`\\.",
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text(
            "❌ Re-login failed\\. Send /debug to see what browser saw\\.",
            parse_mode="MarkdownV2",
        )


async def cmd_add_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    if not context.args:
        return await update.message.reply_text("Usage: /add\\_chat \\<id\\>", parse_mode="MarkdownV2")
    cid   = context.args[0]
    chats = load_chats()
    if cid in chats:
        return await update.message.reply_text("Already registered.")
    chats.append(cid)
    save_chats(chats)
    await update.message.reply_text(f"✅ Added `{esc(cid)}`\\.", parse_mode="MarkdownV2")


async def cmd_remove_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    if not context.args:
        return await update.message.reply_text("Usage: /remove\\_chat \\<id\\>", parse_mode="MarkdownV2")
    cid   = context.args[0]
    chats = load_chats()
    if cid not in chats:
        return await update.message.reply_text("Not found.")
    chats.remove(cid)
    save_chats(chats)
    await update.message.reply_text(f"✅ Removed `{esc(cid)}`\\.", parse_mode="MarkdownV2")


async def cmd_list_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    chats = load_chats()
    if not chats:
        return await update.message.reply_text("No chats registered.")
    lines = "\n".join(f"• `{esc(c)}`" for c in chats)
    await update.message.reply_text(
        f"📜 *Registered Chats:*\n\n{lines}", parse_mode="MarkdownV2"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, Conflict):
        log.warning("Telegram Conflict — waiting 30s …")
        await asyncio.sleep(30)
    elif isinstance(err, (TimedOut, NetworkError)):
        log.warning("Telegram network hiccup: %s", err)
    else:
        log.error("Telegram error: %s", err)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
async def main():
    log.info("=" * 55)
    log.info("iVAS SMS Bot v8")
    log.info("Email : %s", IVAS_EMAIL)
    log.info("Admins: %s", ADMIN_IDS)
    log.info("Chats : %s", load_chats())
    log.info("=" * 55)

    await start_browser()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("status",      cmd_status))
    app.add_handler(CommandHandler("debug",       cmd_debug))
    app.add_handler(CommandHandler("relogin",     cmd_relogin))
    app.add_handler(CommandHandler("add_chat",    cmd_add_chat))
    app.add_handler(CommandHandler("remove_chat", cmd_remove_chat))
    app.add_handler(CommandHandler("list_chats",  cmd_list_chats))
    app.add_error_handler(error_handler)

    async with app:
        await app.start()
        await app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message"],
        )
        log.info("Bot online. Polling every %ds.", POLL_SECS)
        try:
            await poll_loop(app.bot)
        finally:
            await app.updater.stop()
            await app.stop()
            await stop_browser()
            if _curl_session:
                try:
                    await _curl_session.close()
                except Exception:
                    pass


if __name__ == "__main__":
    asyncio.run(main())
