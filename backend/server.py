"""GiftsDates backend — dating, wallet, gifts, escrow dates, video calls, Stripe."""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, UploadFile, File, Request, Form
from fastapi.responses import Response, StreamingResponse, HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from date_ideas_catalog import build_catalog, CAT_IMG
from geo_coords import approx_coords
import asyncio
import os, uuid, logging, bcrypt, jwt, stripe, requests, re, secrets, httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Storage
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "giftsdates"
# Comprehensive list of gender identities accepted across sign-up, main profile and VIP profile.
VALID_GENDERS = (
    "female", "male", "trans_woman", "trans_man", "non_binary",
    "transgender", "transfeminine", "transmasculine",
    "cis_woman", "cis_man", "agender", "genderqueer", "genderfluid",
    "genderless", "gender_nonconforming", "gender_questioning",
    "bigender", "pangender", "demigender", "demigirl", "demiboy",
    "two_spirit", "intersex", "androgyne", "androgynous", "neutrois",
    "gender_variant", "third_gender", "polygender", "omnigender",
    "transsexual", "questioning", "other_gender", "prefer_not_gender",
)
VALID_ORIENTATIONS = (
    "straight", "gay", "lesbian", "bisexual", "pansexual", "omnisexual",
    "polysexual", "asexual", "demisexual", "sapiosexual", "aromantic",
    "transgender", "queer", "fluid", "questioning", "prefer_not",
)
storage_key = None

def init_storage(force: bool = False):
    global storage_key
    if storage_key and not force:
        return storage_key
    try:
        r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
        r.raise_for_status()
        storage_key = r.json()["storage_key"]
    except Exception as e:
        logging.error(f"Storage init failed: {e}")
        raise HTTPException(503, "Storage unavailable")
    return storage_key

def put_object(path: str, data: bytes, content_type: str):
    k = init_storage()
    r = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": k, "Content-Type": content_type}, data=data, timeout=120)
    r.raise_for_status()
    return r.json()

def get_object(path: str):
    k = init_storage()
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": k}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

app = FastAPI()
api = APIRouter(prefix="/api")

# ---------- Constants ----------
COIN_PACKAGES = {
    "small_talk": {"coins": 100,  "amount": 9.99,   "bonus": 0,   "name": "Small Talk"},
    "starter":    {"coins": 300,  "amount": 29.99,  "bonus": 20,  "name": "Starter"},
    "popular":    {"coins": 1000, "amount": 99.99,  "bonus": 100, "name": "Popular Pack"},
    "extra":      {"coins": 2000, "amount": 189.0,  "bonus": 150, "name": "Extra Pack"},
    "vip":        {"coins": 3000, "amount": 295.0,  "bonus": 300, "name": "VIP Pack"},
}
CUSTOM_COINS_PER_USD = 10
CUSTOM_BONUS_PCT = 2
CUSTOM_MIN_USD = 1.0
COINS_PER_USD = 10  # payout rate: 10 coins = $1
MIN_WITHDRAW_USD = 50.0
CANCEL_REFUND_PCT = 0.5  # booker gets 50% back when cancelling a date; the rest compensates the recipient
PREMIUM_PACKAGE = {"lookup": "premium_monthly", "amount": 29.99, "name": "GiftsDates Premium Monthly"}
VIP_PACKAGE = {"lookup": "vip_monthly", "amount": 49.99, "name": "GiftsDates VIP Monthly"}
PREMIUM_LITE_PACKAGE = {"lookup": "premium_lite_monthly", "amount": 14.99, "name": "GiftsDates Premium Lite Monthly"}
PREMIUM_COINS = 300
VIP_COINS = 500
PREMIUM_LITE_COINS = 150
VIP_UNLOCK_COINS = 100  # one-time coins to unlock a single member's private VIP section
VIP_SERVICES = {
    "basic": ["Минет в презервативе", "Поцелуи с языком", "Секс анальный", "Секс вагинальный", "Секс групповой", "Секс лесбийский"],
    "extra": ["Куннилингус", "Минет без резинки", "Минет глубокий", "Окончание в рот", "Окончание на грудь", "Окончание на лицо", "Работаю с девственниками", "Ролевые игры", "Секс игрушки", "Секс по телефону", "Услуги семейной паре", "Фейсситтинг", "Фото/видео съемка", "Эскорт"],
    "massage": ["Массаж Ветка сакуры", "Массаж классический", "Массаж профессиональный", "Массаж расслабляющий", "Массаж тайский", "Массаж точечный", "Массаж урологический", "Массаж эротический"],
    "striptease": ["Лесби откровенное", "Лесби-шоу легкое", "Стриптиз не профи", "Стриптиз профи"],
    "bdsm": ["Бандаж", "Госпожа", "Легкая доминация", "Порка", "Рабыня", "Трамплинг", "Фетиш", "Эротические игры"],
    "extreme": ["Анилингус делаю", "Золотой дождь выдача", "Золотой дождь прием", "Копро выдача", "Страпон", "Фистинг анальный", "Фистинг вагинальный"],
}
VIP_SERVICE_SET = {s for arr in VIP_SERVICES.values() for s in arr}
VIP_PLACES = ["own", "your", "other"]
GIFT_CATALOG = [
    {"id": "rose",       "name_key": "gift_rose",       "icon": "🌹", "cost": 50},
    {"id": "chocolate",  "name_key": "gift_chocolate",  "icon": "🍫", "cost": 100},
    {"id": "champagne",  "name_key": "gift_champagne",  "icon": "🍾", "cost": 200},
    {"id": "dress",      "name_key": "gift_dress",      "icon": "👗", "cost": 400},
    {"id": "perfume",    "name_key": "gift_perfume",    "icon": "🧴", "cost": 800},
    {"id": "watch",      "name_key": "gift_watch",      "icon": "⌚", "cost": 1000},
    {"id": "jewelry",    "name_key": "gift_jewelry",    "icon": "💎", "cost": 1500},
    {"id": "ring",       "name_key": "gift_ring",       "icon": "💍", "cost": 5000},
]
GIFT_COMMISSION = 0.30
VIDEO_RATE_PER_MIN = 10
DATE_MIN_COINS = 150
EXTRA_HOUR_MIN_COINS = 250  # minimum coins per extra-hour slot on VIP dates
REFERRAL_BONUS = 100
MAX_PHOTOS = 6
PHONE_RE = re.compile(r"(?:\+?\d[\s\-\.\(\)_]*){7,}")
PHONE_WORDS_RE = re.compile(r"\b(whatsapp|telegram|viber|wechat|signal|тел[её]фон|ватсап|телеграм)\b", re.I)
MAX_VIOLATIONS = 3
BLOCK_DAYS = 7
FREE_DAILY_LIKES = 15

def contains_phone(text: str) -> bool:
    return bool(PHONE_RE.search(text)) or bool(PHONE_WORDS_RE.search(text) and re.search(r"\d{4,}", text))

DEFAULT_SETTINGS = {
    "gifts": GIFT_CATALOG,
    "coin_packages": [{"id": k, **v} for k, v in COIN_PACKAGES.items()],
    "premium_amount": PREMIUM_PACKAGE["amount"],
    "video_rate": VIDEO_RATE_PER_MIN,
    "date_min_coins": DATE_MIN_COINS,
    "referral_bonus": REFERRAL_BONUS,
    "commission": GIFT_COMMISSION,
    "free_daily_likes": FREE_DAILY_LIKES,
    "custom_coins_per_usd": CUSTOM_COINS_PER_USD,
    "custom_bonus_pct": CUSTOM_BONUS_PCT,
    "custom_min_usd": CUSTOM_MIN_USD,
    "coins_per_usd": COINS_PER_USD,
    "min_withdraw_usd": MIN_WITHDRAW_USD,
    "referral_package_id": "popular",
    "cancel_refund_pct": CANCEL_REFUND_PCT,
    "gift_auto_match_coins": 100,
}

async def ensure_match(a_id: str, b_id: str, reason: str = "like") -> tuple[str, bool]:
    exists = await db.matches.find_one({"users": {"$all": [a_id, b_id]}})
    if exists: return exists["id"], False
    now = datetime.now(timezone.utc).isoformat()
    conv_id = str(uuid.uuid4())
    await db.matches.insert_one({"id": conv_id, "users": [a_id, b_id], "created_at": now, "reason": reason})
    await db.conversations.insert_one({"id": conv_id, "users": [a_id, b_id], "created_at": now, "last_message": None})
    return conv_id, True

async def _date_chat_card(from_id: str, to_id: str, kind: str, ref_id: str, event: str, text: str,
                          action_for: Optional[str] = None, data: Optional[dict] = None):
    """Post a date event card (invite, location, decline…) into the regular chat between the two people."""
    conv = await db.conversations.find_one({"users": {"$all": [from_id, to_id]}}, {"id": 1})
    cid = conv["id"] if conv else (await ensure_match(from_id, to_id, "date"))[0]
    now = datetime.now(timezone.utc).isoformat()
    await db.messages.update_many({"ref_id": ref_id, "type": "date_card"}, {"$set": {"action_for": None}})
    await db.messages.insert_one({"id": str(uuid.uuid4()), "conversation_id": cid, "from_id": from_id, "type": "date_card",
                                  "kind": kind, "ref_id": ref_id, "event": event, "text": text, "action_for": action_for,
                                  "data": data or {}, "created_at": now})
    await db.conversations.update_one({"id": cid}, {"$set": {"last_message": text, "last_at": now}})

async def _close_date_cards(ref_id: str):
    """Hide approve/decline buttons on chat cards once the date moved on."""
    await db.messages.update_many({"ref_id": ref_id, "type": "date_card", "action_for": {"$ne": None}}, {"$set": {"action_for": None}})

def _loc_card(l: dict) -> dict:
    l = l or {}
    return {k: l.get(k) for k in ("venue", "address", "city", "postal_code", "country", "lat", "lng", "unverified")}

async def get_settings() -> dict:
    doc = await db.settings.find_one({"id": "pricing"}, {"_id": 0, "id": 0}) or {}
    return {**DEFAULT_SETTINGS, **doc}

# ---------- Support / chatbot settings ----------
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SUPPORT_DEFAULTS = {
    "agent_enabled": True,
    "timezone": "UTC",
    "hours": [
        {"day": 0, "enabled": True, "open": "09:00", "close": "18:00"},
        {"day": 1, "enabled": True, "open": "09:00", "close": "18:00"},
        {"day": 2, "enabled": True, "open": "09:00", "close": "18:00"},
        {"day": 3, "enabled": True, "open": "09:00", "close": "18:00"},
        {"day": 4, "enabled": True, "open": "09:00", "close": "18:00"},
        {"day": 5, "enabled": False, "open": "10:00", "close": "16:00"},
        {"day": 6, "enabled": False, "open": "10:00", "close": "16:00"},
    ],
    "offline_message": "Our support agents are offline right now. Leave a message and we'll reply by email, or ask me anything meanwhile.",
    "welcome_message": "Hi! I'm the GiftsDates assistant 💛 Ask me anything about coins, dates, safety, Premium and more.",
}

async def get_support_settings() -> dict:
    doc = await db.settings.find_one({"id": "support"}, {"_id": 0, "id": 0}) or {}
    merged = {**SUPPORT_DEFAULTS, **doc}
    if not merged.get("hours"):
        merged["hours"] = SUPPORT_DEFAULTS["hours"]
    return merged

def _support_status(s: dict) -> dict:
    try:
        tz = ZoneInfo(s.get("timezone") or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    now = datetime.now(tz)
    wd = now.weekday()
    row = next((h for h in s.get("hours", []) if h.get("day") == wd), None)
    is_open = False
    if s.get("agent_enabled", True) and row and row.get("enabled"):
        try:
            oh, om = map(int, str(row["open"]).split(":"))
            ch, cm = map(int, str(row["close"]).split(":"))
            mins = now.hour * 60 + now.minute
            is_open = (oh * 60 + om) <= mins < (ch * 60 + cm)
        except Exception:
            is_open = False
    return {"is_open": is_open, "server_time": now.strftime("%a %H:%M"), "weekday": wd, "timezone": s.get("timezone") or "UTC"}

SUPPORT_SYSTEM = (
    "You are the GiftsDates support assistant for a luxury worldwide dating platform. "
    "Answer only questions about GiftsDates. Be warm, concise (2-5 sentences), and helpful. Never invent policies. "
    "If asked something unrelated or that needs an account action you cannot do, suggest using the app or contacting a human agent via the 'Contact an agent' button.\n\n"
    "KEY FACTS:\n"
    "- Users must be 18+ and verified. Registration is free.\n"
    "- Coins (🪙) power the platform. Top-up packs: Small Talk 🪙100 ($9.99), Starter 🪙300+20 ($29.99), Popular Pack 🪙1000+100 ($99.99), Extra Pack 🪙2000+150 ($189), VIP Pack 🪙3000+300 ($295), or custom at $1=10🪙 +2% bonus.\n"
    "- A gift of 100+ coins automatically opens a chat (instant match).\n"
    "- Safety: keep contact & meeting plans on-platform; phone numbers and chat photos unlock only after a confirmed date; off-platform meetings aren't protected and can lead to a block.\n"
    "- Withdrawals: after bank approval, minus 30% commission; 10 coins = $1; escrow unlocks after a confirmed date.\n"
    "- Dates: invite someone, pick location, pay date price in coins (held in escrow). The invited side can request a taxi fee; if the inviter approves it, the date is auto-confirmed.\n"
    "- Cancellations: if the inviter cancels, 50% of booking+taxi is refunded and 50% compensates the invited user; if the invited user cancels, all coins go back to the inviter.\n"
    "- Photo proof: submit within 24h to get 100%; after 24h with no photo and no complaint, the invited user can claim 50% and the platform keeps 50%. The 'Get 50% now' button unlocks 24h after the date starts.\n"
    "- Premium: unlimited likes, top placement, advanced filters, see who liked you, priority support; auto-renews monthly until cancelled from the profile page.\n"
    "- Invite a friend: earn 🪙100 when a friend buys their first Popular Pack.\n"
    "- Manage/delete account from the profile page. Support email: help@GiftsDates.com.\n"
    "- Helpful pages: /faq, /help, /safety, /terms-of-use, /privacy, /fraud-prevention.\n"
    "Do not ask for passwords, card numbers, or one-time codes."
)

_support_chats: dict = {}

def is_premium(u: dict) -> bool:
    pu = u.get("premium_until")
    if not pu: return False
    try: return datetime.fromisoformat(pu.replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except Exception: return False

def is_vip(u: dict) -> bool:
    vu = u.get("vip_until")
    if not vu: return False
    try: return datetime.fromisoformat(vu.replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except Exception: return False

def is_premium_lite(u: dict) -> bool:
    pu = u.get("premium_lite_until")
    if not pu: return False
    try: return datetime.fromisoformat(pu.replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except Exception: return False

def has_premium(u: dict) -> bool:
    """Baseline premium perks: unlimited likes, advanced filters, see who liked you, boosted placement.
    Granted to Premium-lite, Premium and VIP. VIP-content access is gated separately by is_premium/is_vip."""
    return is_premium(u) or is_premium_lite(u) or is_vip(u)

async def spend_coins(uid: str, amount: int):
    """Spend from main coins first, then from withdrawable. Withdrawable is spendable but not withdrawable from main."""
    amount = int(amount)
    if amount <= 0: return
    u = await db.users.find_one({"id": uid}, {"_id": 0, "coins": 1, "withdrawable": 1})
    coins = int(u.get("coins", 0) or 0)
    wd = float(u.get("withdrawable", 0) or 0)
    if coins + wd < amount:
        raise HTTPException(400, "Insufficient coins")
    from_coins = min(coins, amount)
    from_wd = amount - from_coins
    await db.users.update_one({"id": uid}, {"$inc": {"coins": -from_coins, "withdrawable": -from_wd}})

async def record_txn(user_id: str, ttype: str, amount: int, date_id: str | None = None, description: str = "", status: str = "completed"):
    """Append a coin ledger entry. amount is signed (negative=debit). balance = spendable (coins+withdrawable)."""
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "coins": 1, "withdrawable": 1})
    before = int((u.get("coins") or 0) + (u.get("withdrawable") or 0)) if u else 0
    after = before + int(amount)
    doc = {"id": str(uuid.uuid4()), "user_id": user_id, "date_id": date_id, "type": ttype,
           "amount": int(amount), "balance_before": before, "balance_after": after,
           "status": status, "description": description, "created_at": datetime.now(timezone.utc).isoformat()}
    await db.coin_transactions.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}

def extend_until(cur, days=30):
    s = datetime.now(timezone.utc)
    if cur:
        try:
            c = datetime.fromisoformat(cur.replace("Z", "+00:00"))
            if c > s: s = c
        except Exception: pass
    return (s + timedelta(days=days)).isoformat()

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "GiftsDates")

# ---------- SMS (Twilio) ----------
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM", "")  # e.g. +15551234567 or a Messaging Service SID (MG...)

async def send_sms(*, to: str, body: str) -> str:
    """Send an SMS via Twilio if configured. Returns delivery status.
    When Twilio creds are absent it returns 'not_configured' (no fake success)
    so texting activates automatically once creds are added."""
    to = (to or "").strip()
    if not to:
        return "no_number"
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM):
        return "not_configured"
    try:
        data = {"To": to, "Body": body}
        if TWILIO_FROM.startswith("MG"):
            data["MessagingServiceSid"] = TWILIO_FROM
        else:
            data["From"] = TWILIO_FROM
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), data=data)
        r.raise_for_status()
        return "sent"
    except Exception as e:
        logging.error(f"SMS send failed: {e}")
        return "failed"


def _email_safe(subject: str, html: str) -> bool:
    low = f"{subject}\n{html}".lower()
    if any(tag in low for tag in ("<form", "<input", "<textarea", "<select")): return False
    import re as _re
    for url in _re.findall(r'(?:href|src)\s*=\s*["\']([^"\']+)', html, _re.I):
        u = url.strip().lower()
        if u.startswith(("mailto:", "tel:", "cid:", "#")): continue
        if not u.startswith("https://"): return False
    return True

async def send_email(*, to: str, subject: str, html: str) -> bool:
    if not EMAIL_KEY or not _email_safe(subject, html): return False
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                   headers={"X-Email-Key": EMAIL_KEY},
                                   json={"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME})
        r.raise_for_status()
        return True
    except Exception as e:
        logging.error(f"Email send failed: {e}")
        return False

EMAIL_FOOTER_EN = "Sent by GiftsDates · Luxury Dating. We never ask for your password or card details by email."
RTL_LANGS = {"ar", "ur", "fa", "he", "ps", "sd", "ckb", "yi", "ug", "dv", "ks", "bal", "syr"}

def _email_html(title: str, body: str, footer: str | None = None, rtl: bool = False) -> str:
    from html import escape as _esc
    footer = footer or EMAIL_FOOTER_EN
    return (f'<table role="presentation" width="100%" dir="{"rtl" if rtl else "ltr"}" style="background:#0d0b12;padding:24px"><tr><td align="center">'
            f'<table role="presentation" width="480" style="background:#161320;border-radius:16px;'
            f'border:1px solid rgba(212,175,55,0.25);font-family:Arial,sans-serif;color:#f4f1f7">'
            f'<tr><td style="padding:24px 28px">'
            f'<div style="font-size:20px;font-weight:700;color:#f3e5ab;margin-bottom:6px">GiftsDates</div>'
            f'<div style="font-size:17px;font-weight:600;margin:14px 0 6px">{_esc(title)}</div>'
            f'<div style="font-size:14px;line-height:1.5;color:#c9c4d4">{_esc(body)}</div>'
            f'<div style="font-size:11px;color:#8a8598;margin-top:22px;border-top:1px solid rgba(255,255,255,0.08);padding-top:12px">'
            f'{_esc(footer)}</div>'
            f'</td></tr></table></td></tr></table>')

_bg_tasks: set = set()

def _spawn(coro):
    t = asyncio.create_task(coro); _bg_tasks.add(t); t.add_done_callback(_bg_tasks.discard)
    return t

async def localize_message(lang: str, title: str, body: str, cta: str | None = None, sms_body: str | None = None) -> dict:
    """Translate a notification (email + SMS parts) into the recipient's language. Falls back to English."""
    code = (lang or "en").strip() or "en"
    parts = [title or "", body or "", cta or "", EMAIL_FOOTER_EN, sms_body or ""]
    if code.lower() != "en":
        try:
            if not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,4})?", code): raise ValueError("bad lang")
            parts = await localize_texts(parts, code, ui=False)
        except Exception as e:
            logging.error(f"localize_message failed ({code}): {e}")
    t_title, t_body, t_cta, t_footer, t_sms = parts
    return {"lang": code, "rtl": code.split("-")[0].lower() in RTL_LANGS, "title": t_title, "body": t_body,
            "cta": t_cta or None, "footer": t_footer, "sms_body": t_sms or None}

async def _deliver(user_id: str, title: str, body: str, link: str | None, cta: str, email: bool, want_sms: bool, sms_body: str | None, now: str):
    try:
        u = await db.users.find_one({"id": user_id}, {"email": 1, "phone": 1, "sms_notifications_enabled": 1, "language": 1})
        if not u: return
        do_email = bool(email and u.get("email"))
        do_sms = bool(want_sms and u.get("phone") and u.get("sms_notifications_enabled"))
        if not (do_email or do_sms): return
        email_live = bool(EMAIL_KEY)
        sms_live = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM)
        # Only spend AI translation when a message will actually be delivered.
        lang = u.get("language") or "en"
        loc = await localize_message(lang, title, body, cta, sms_body) if ((do_email and email_live) or (do_sms and sms_live)) \
            else {"lang": "en", "rtl": False, "title": title, "body": body, "cta": cta, "footer": None, "sms_body": sms_body}
        if do_email:
            html = (_email_cta_html(loc["title"], loc["body"], link, loc["cta"] or cta, loc["footer"], loc["rtl"]) if link
                    else _email_html(loc["title"], loc["body"], loc["footer"], loc["rtl"]))
            sent = await send_email(to=u["email"], subject=f"{loc['title']} · GiftsDates", html=html)
            await db.email_outbox.insert_one({"id": str(uuid.uuid4()), "to": u["email"], "subject": loc["title"], "body": loc["body"],
                                              "lang": loc["lang"], "status": "sent" if sent else "failed", "created_at": now})
        if do_sms:
            text = (loc["sms_body"] or f"{loc['title']} — {loc['body']}")
            if link:
                text = f"{text} {link}"
            status = await send_sms(to=u["phone"], body=text[:600])
            await db.sms_outbox.insert_one({"id": str(uuid.uuid4()), "to": u["phone"], "body": text, "lang": loc["lang"],
                                            "status": status, "created_at": now})
    except Exception:
        logging.exception("notification delivery failed")

async def notify(user_id: str, ntype: str, title: str, body: str, data: dict | None = None, email: bool = False, link: str | None = None, cta: str = "View on GiftsDates", sms: bool | None = None, sms_body: str | None = None):
    """Multi-channel notification: always records an in-app (push) notification, and
    fans out to Email and SMS in the recipient's chosen language (in the background).
    SMS defaults to ON whenever an email is sent, but only reaches users who have a
    phone number AND opted in (sms_notifications_enabled)."""
    now = datetime.now(timezone.utc).isoformat()
    await db.notifications.insert_one({"id": str(uuid.uuid4()), "user_id": user_id, "type": ntype, "title": title,
                                       "body": body, "data": data or {}, "read": False, "created_at": now})
    want_sms = email if sms is None else sms
    if email or want_sms:
        _spawn(_deliver(user_id, title, body, link, cta, email, want_sms, sms_body, now))

# Fixed inbox that receives admin alerts (new signups, ID-approval requests, etc.)
ADMIN_NOTIFY_EMAIL = os.environ.get("ADMIN_NOTIFY_EMAIL", "giftsdates@gmail.com")

async def notify_admin_email(subject: str, title: str, body: str, link: str | None = None, cta: str = "Open Admin Panel", note: str = ""):
    """Send an alert email to the fixed admin inbox and record it in the outbox."""
    now = datetime.now(timezone.utc).isoformat()
    html = _email_cta_html(title, body, link, cta) if link else _email_html(title, body)
    sent = await send_email(to=ADMIN_NOTIFY_EMAIL, subject=subject, html=html)
    await db.email_outbox.insert_one({"id": str(uuid.uuid4()), "to": ADMIN_NOTIFY_EMAIL, "subject": subject,
                                      "body": body, "note": note, "status": "sent" if sent else "failed", "created_at": now})
    return sent


# ---------- Auth helpers ----------
def hash_pwd(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_pwd(p: str, h: str) -> bool:
    try: return bcrypt.checkpw(p.encode(), h.encode())
    except Exception: return False
def make_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=30)}, JWT_SECRET, algorithm=JWT_ALG)

async def get_current_user(authorization: Optional[str] = Header(None), auth: Optional[str] = None):
    tok = None
    if authorization and authorization.startswith("Bearer "):
        tok = authorization.split(" ", 1)[1]
    elif auth:
        tok = auth
    if not tok:
        raise HTTPException(401, "Missing token")
    try:
        payload = jwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(401, "User not found")
    bu = user.get("blocked_until")
    if bu and datetime.fromisoformat(bu.replace("Z", "+00:00")) > datetime.now(timezone.utc):
        raise HTTPException(403, f"BLOCKED:{bu}")
    if not user.get("referral_code"):
        user["referral_code"] = user["id"][:8].upper()
        await db.users.update_one({"id": user["id"]}, {"$set": {"referral_code": user["referral_code"]}})
    now = datetime.now(timezone.utc)
    ls = user.get("last_seen")
    if not ls or (now - datetime.fromisoformat(ls.replace("Z", "+00:00"))).total_seconds() > 60:
        user["last_seen"] = now.isoformat()
        await db.users.update_one({"id": user["id"]}, {"$set": {"last_seen": user["last_seen"]}})
    return user

async def have_met(a: str, b: str) -> bool:
    return bool(await db.date_bookings.find_one({"status": {"$in": ["confirmed", "released"]}, "$or": [{"from_id": a, "to_id": b}, {"from_id": b, "to_id": a}]}))

# ---------- Models ----------
ZODIAC_RANGES = [
    ((1, 20), "aquarius"), ((2, 19), "pisces"), ((3, 21), "aries"), ((4, 20), "taurus"),
    ((5, 21), "gemini"), ((6, 21), "cancer"), ((7, 23), "leo"), ((8, 23), "virgo"),
    ((9, 23), "libra"), ((10, 23), "scorpio"), ((11, 22), "sagittarius"), ((12, 22), "capricorn"),
]

def zodiac_sign(month: int, day: int) -> Optional[str]:
    try:
        month = int(month); day = int(day)
    except (TypeError, ValueError):
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    sign = "capricorn"  # Dec 22 - Jan 19 wraps to capricorn
    for (m, d), name in ZODIAC_RANGES:
        if month == m and day >= d:
            sign = name
        elif month == m and day < d:
            break
        elif month > m:
            sign = name
    return sign

def age_from_birth(year: int, month: int, day: int) -> Optional[int]:
    try:
        today = datetime.now(timezone.utc).date()
        a = today.year - int(year) - ((today.month, today.day) < (int(month), int(day)))
        return a if 0 < a < 120 else None
    except (TypeError, ValueError):
        return None

class RegisterReq(BaseModel):
    email: EmailStr
    password: str
    name: str
    age: int
    gender: str
    genders: Optional[List[str]] = None
    interested_in: str
    orientation: Optional[str] = "straight"
    orientations: Optional[List[str]] = None
    city: str
    country: str
    bio: Optional[str] = ""
    phone: Optional[str] = None
    referral_code: Optional[str] = None
    spin_token: Optional[str] = None
    language: Optional[str] = "en"
    sms_notifications_enabled: Optional[bool] = False
    birth_year: Optional[int] = None
    birth_month: Optional[int] = None
    birth_day: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

class LoginReq(BaseModel):
    email: EmailStr
    password: str

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    birth_year: Optional[int] = None
    birth_month: Optional[int] = None
    birth_day: Optional[int] = None
    bio: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    hide_distance: Optional[bool] = None
    passport_cities: Optional[List[dict]] = None
    interests: Optional[List[str]] = None
    photos: Optional[List[str]] = None
    language: Optional[str] = None
    relationship_intent: Optional[List[str]] = None
    orientation: Optional[str] = None
    orientations: Optional[List[str]] = None
    gender: Optional[str] = None
    genders: Optional[List[str]] = None
    hobbies: Optional[List[str]] = None
    height: Optional[int] = None
    weight: Optional[int] = None
    languages_spoken: Optional[List[str]] = None
    job_title: Optional[str] = None
    income: Optional[str] = None
    phone: Optional[str] = None
    income_custom: Optional[str] = None
    kids: Optional[str] = None
    smoking: Optional[str] = None
    drinking: Optional[str] = None
    religion: Optional[str] = None
    bust_size: Optional[str] = None
    bust_type: Optional[str] = None
    penis_size: Optional[str] = None
    dick_girth: Optional[str] = None
    date_price: Optional[int] = None
    video_rate: Optional[int] = None  # coins per minute, >= global video_rate
    video_calls_enabled: Optional[bool] = None  # if False, others cannot start a video call
    availability: Optional[List[str]] = None  # ISO dates YYYY-MM-DD when user is open for dates
    availability_time: Optional[dict] = None  # {"from": "18:00", "to": "23:00"} default window
    availability_slots: Optional[dict] = None  # {"YYYY-MM-DD": {"from": "..", "to": ".."}} per-day overrides
    availability_ranges: Optional[dict] = None  # {"YYYY-MM-DD": [{"from","to"}, ...]} multiple ranges per specific day
    availability_weekly: Optional[dict] = None  # {"0".."6" (Mon..Sun): [{"from","to"}, ...]} recurring weekly
    sms_notifications_enabled: Optional[bool] = None

class LikeReq(BaseModel):
    target_id: str

class GiftReq(BaseModel):
    target_id: str
    gift_id: str  # catalog id or "custom"
    message: Optional[str] = ""
    custom_icon: Optional[str] = None
    custom_cost: Optional[int] = None
    conversation_id: Optional[str] = None

CUSTOM_GIFT_MIN = 10

class VideoCallReq(BaseModel):
    target_id: str
    minutes: int

class DateBookingReq(BaseModel):
    address_confirmed: bool = False
    unverified: Optional[bool] = None
    target_id: str
    venue: str
    city: str
    scheduled_at: str  # ISO
    coins: int
    local_time: Optional[str] = None  # HH:MM in booker's local time, used for availability window check
    local_day: Optional[str] = None  # YYYY-MM-DD availability day the slot belongs to
    address: Optional[str] = ""
    postal_code: Optional[str] = ""
    country: Optional[str] = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    place: Optional[str] = None  # VIP: own | your | other
    extra_hours: int = 0  # VIP: extra hour slots added on top of the chosen duration
    vip_length: Optional[int] = None  # VIP: chosen base length in hours (1/2/3) priced from the VIP's rates
    activities: Optional[List[str]] = None  # exactly 3 custom date-idea options proposed by the inviter

class DateConfirmReq(BaseModel):
    booking_id: str
    photo_url: str

class WithdrawReq(BaseModel):
    amount: float

class PayoutAccountReq(BaseModel):
    # recipient
    tax_id: str
    holder_name: str  # full name
    recipient_street: str
    recipient_city: str
    recipient_province: str
    recipient_postal_code: str
    country: str  # recipient country
    recipient_email: str
    # bank
    iban: str  # account number / IBAN
    swift: str
    routing_number: Optional[str] = ""
    bank_name: str
    bank_street: str
    bank_city: str
    bank_province: str
    bank_postal_code: str
    bank_country: str
    document_path: Optional[str] = None
    bank_statement_path: Optional[str] = None
    proof_of_address_path: Optional[str] = None

class AdminVerifyReq(BaseModel):
    approve: bool
    reason: Optional[str] = ""

REPORT_REASONS = {
    "underage": "Underage user",
    "illegal": "Illegal activity",
    "harassment": "Abuse or harassment",
    "hate": "Hate speech",
    "nonconsensual": "Non-consensual / intimate images",
    "impersonation": "Fake profile / impersonation",
    "scam": "Scam or fraud",
    "spam": "Spam or advertising",
    "offplatform": "Pushing off-platform contact",
    "other": "Other violation",
}

class ReportReq(BaseModel):
    target_id: str
    reason: str
    details: Optional[str] = ""

ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
def is_admin(u: dict) -> bool:
    return u.get("is_admin") is True or u["email"].lower() in ADMIN_EMAILS
async def get_admin(user=Depends(get_current_user)):
    if not is_admin(user): raise HTTPException(403, "Admin only")
    return user

class CheckoutReq(BaseModel):
    package_id: str  # coin package id, "custom" or "premium_monthly"
    origin_url: str
    usd_amount: Optional[float] = None  # for custom

class MessageReq(BaseModel):
    conversation_id: str
    text: str

# ---------- Startup ----------
@app.on_event("startup")
async def _startup():
    init_storage()
    await db.users.create_index("email", unique=True)
    await db.ui_translations.create_index([("lang", 1), ("h", 1)], unique=True)
    await db.users.create_index("id", unique=True)
    await db.users.create_index("phone")
    await db.users.create_index("created_at")
    await db.new_users_list.create_index("registered_at")
    await db.new_users_list.create_index("email")
    await db.new_users_list.create_index("user_id", unique=True)
    await db.likes.create_index([("from_id", 1), ("to_id", 1)], unique=True)
    await db.notifications.create_index([("user_id", 1), ("read", 1)])
    await db.spins.create_index("token", unique=True)
    await db.spins.create_index([("ip", 1), ("used", 1)])
    await db.date_ideas.create_index("id", unique=True)
    await db.coin_transactions.create_index([("user_id", 1), ("created_at", -1)])
    await db.vip_avail.create_index([("vip_id", 1), ("date", 1)])
    await db.vip_sched.create_index([("vip_id", 1), ("date", 1), ("status", 1)])
    await db.vip_sched.create_index([("requester_id", 1), ("status", 1)])
    for idea in build_catalog():
        await db.date_ideas.update_one({"id": idea["id"]}, {"$setOnInsert": idea}, upsert=True)
    import asyncio
    asyncio.create_task(_vs_reminder_loop())
    asyncio.create_task(_date_lifecycle_loop())
    asyncio.create_task(_account_purge_loop())
    logging.info("GiftsDates backend ready")

# ---------- Meta ----------
@api.get("/meta")
async def meta():
    s = await get_settings()
    return {
        "gifts": s["gifts"],
        "coin_packages": s["coin_packages"],
        "premium": {**PREMIUM_PACKAGE, "amount": s["premium_amount"]},
        "vip": {**VIP_PACKAGE},
        "premium_lite": {**PREMIUM_LITE_PACKAGE},
        "premium_coins": PREMIUM_COINS,
        "vip_coins": VIP_COINS,
        "premium_lite_coins": PREMIUM_LITE_COINS,
        "video_rate": s["video_rate"],
        "gift_commission": s["commission"],
        "date_min_coins": s["date_min_coins"],
        "extra_hour_min_coins": EXTRA_HOUR_MIN_COINS,
        "referral_bonus": s["referral_bonus"],
        "referral_package": next((p for p in s["coin_packages"] if p["id"] == s.get("referral_package_id")), None),
        "free_daily_likes": s["free_daily_likes"],
        "custom_coins": {"per_usd": s["custom_coins_per_usd"], "bonus_pct": s["custom_bonus_pct"], "min_usd": s["custom_min_usd"]},
        "coins_per_usd": s["coins_per_usd"],
        "cancel_refund_pct": s.get("cancel_refund_pct", CANCEL_REFUND_PCT),
        "gift_auto_match_coins": s.get("gift_auto_match_coins", 100),
        "max_photos": MAX_PHOTOS,
    }

# ---------- Support chatbot / tickets ----------
class SupportChatReq(BaseModel):
    session_id: str
    message: str
    lang: Optional[str] = "en"

LANG_NAMES = {"ru": "Russian", "en": "English", "es": "Spanish", "fr": "French", "de": "German",
              "pt": "Portuguese", "zh": "Chinese", "hi": "Hindi", "bn": "Bengali", "ur": "Urdu", "ar": "Arabic"}
from world_languages import WORLD_LANG_NAMES
LANG_NAMES = {**WORLD_LANG_NAMES, **LANG_NAMES}

class SupportTicketReq(BaseModel):
    name: Optional[str] = ""
    email: EmailStr
    message: str

@api.get("/support/config")
async def support_config():
    s = await get_support_settings()
    st = _support_status(s)
    return {
        "welcome_message": s["welcome_message"],
        "offline_message": s["offline_message"],
        "agent_enabled": s.get("agent_enabled", True),
        "hours": [{"day": h["day"], "day_name": DAY_NAMES[h["day"]], "enabled": h.get("enabled", False),
                   "open": h.get("open"), "close": h.get("close")} for h in sorted(s["hours"], key=lambda x: x["day"])],
        **st,
    }

@api.post("/support/chat")
async def support_chat(req: SupportChatReq):
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(503, "Assistant unavailable")
    text = (req.message or "").strip()[:1000]
    if not text:
        raise HTTPException(400, "Empty message")
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
    if len(_support_chats) > 500:
        _support_chats.clear()
    lang_name = LANG_NAMES.get((req.lang or "en").lower(), "English")
    cached = _support_chats.get(req.session_id)
    chat = cached[0] if cached and cached[1] == lang_name else None
    if chat is None:
        sys_msg = SUPPORT_SYSTEM + f"\n\nAlways reply in {lang_name}, regardless of the language of the question."
        chat = LlmChat(api_key=key, session_id=req.session_id, system_message=sys_msg).with_model("gemini", "gemini-3-flash-preview")
        _support_chats[req.session_id] = (chat, lang_name)

    async def gen():
        try:
            async for ev in chat.stream_message(UserMessage(text=text)):
                if isinstance(ev, TextDelta):
                    yield ev.content
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:
            logging.error(f"support chat error: {e}")
            yield "Sorry, I had trouble answering just now. Please try again, or use 'Contact an agent'."

    return StreamingResponse(gen(), media_type="text/plain",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@api.post("/support/ticket")
async def create_support_ticket(req: SupportTicketReq, authorization: Optional[str] = Header(None)):
    msg = (req.message or "").strip()
    if len(msg) < 5:
        raise HTTPException(400, "MESSAGE_TOO_SHORT")
    uid = None
    try:
        if authorization and authorization.startswith("Bearer "):
            uid = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALG]).get("sub")
    except Exception:
        uid = None
    now = datetime.now(timezone.utc).isoformat()
    st = _support_status(await get_support_settings())
    doc = {"id": str(uuid.uuid4()), "name": (req.name or "").strip()[:120], "email": req.email,
           "message": msg[:4000], "user_id": uid, "status": "open",
           "created_while_open": st["is_open"], "created_at": now}
    await db.support_tickets.insert_one(doc)
    for a_email in ADMIN_EMAILS:
        adm = await db.users.find_one({"email": a_email}, {"_id": 0, "id": 1})
        if adm:
            await notify(adm["id"], "support", "New support message 📨",
                         f"{req.email}: {msg[:120]}", {"ticket_id": doc["id"]}, email=True)
    return {"created": True, "is_open": st["is_open"]}

# ---------- Spin-to-win: 8-sector wheel (weighted, server-side) ----------
# Listed weights honor the intended distribution: "Try Again"/No-Win dominant,
# VIP rarest. A single secure weighted draw picks one sector.
SPIN_PRIZES = [
    {"index": 0, "type": "none",         "weight": 80, "label": "Try Again"},
    {"index": 1, "type": "premium_lite", "weight": 25, "days": 7, "label": "Premium-Lite"},
    {"index": 2, "type": "none",         "weight": 80, "label": "Try Again"},
    {"index": 3, "type": "premium",      "weight": 15, "days": 7, "label": "Premium"},
    {"index": 4, "type": "none",         "weight": 80, "label": "Try Again"},
    {"index": 5, "type": "vip",          "weight": 10, "days": 7, "label": "VIP"},
    {"index": 6, "type": "none",         "weight": 80, "label": "Try Again"},
    {"index": 7, "type": "coins",        "weight": 80, "coins": 10, "label": "10 Coins"},
]

def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff: return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _pick_spin_prize() -> dict:
    total = sum(p["weight"] for p in SPIN_PRIZES)
    r = secrets.randbelow(total)
    acc = 0
    for p in SPIN_PRIZES:
        acc += p["weight"]
        if r < acc: return p
    return SPIN_PRIZES[0]

def _spin_public(p: dict) -> dict:
    return {"index": p["index"], "type": p["type"], "coins": p.get("coins"), "days": p.get("days"), "label": p["label"]}

@api.get("/spin/config")
async def spin_config():
    return {"prizes": [_spin_public(p) for p in SPIN_PRIZES]}

# ---------- Date idea catalog & coin ledger ----------
@api.get("/date-ideas")
async def list_date_ideas(search: Optional[str] = None, category: Optional[str] = None,
    budget: Optional[str] = None, duration: Optional[str] = None, environment: Optional[str] = None,
    indoor: bool = False, outdoor: bool = False, casual: bool = False, romantic: bool = False,
    creative: bool = False, active: bool = False, food: bool = False, conversation: bool = False,
    entertainment: bool = False, free: bool = False, limit: int = 600, user=Depends(get_current_user)):
    conds = [{"active": True}]
    if search: conds.append({"name": {"$regex": re.escape(search.strip()), "$options": "i"}})
    if category: conds.append({"$or": [{"category": category}, {"all_categories": category}]})
    if budget: conds.append({"budget_level": budget})
    if duration: conds.append({"duration": duration})
    if environment: conds.append({"environment": {"$in": [environment, "both"]}})
    if indoor: conds.append({"indoor": True})
    if outdoor: conds.append({"outdoor": True})
    for field, val in [("casual", casual), ("romantic", romantic), ("creative", creative), ("style_active", active),
                       ("food", food), ("conversation", conversation), ("entertainment", entertainment), ("free", free)]:
        if val: conds.append({field: True})
    items = await db.date_ideas.find({"$and": conds}, {"_id": 0}).sort("name", 1).to_list(limit)
    for it in items:
        it["category_image"] = CAT_IMG.get(it.get("category"))
    cat_docs = await db.date_ideas.find({"active": True}, {"_id": 0, "category": 1, "category_label": 1}).to_list(1000)
    seen, categories = set(), []
    for c in cat_docs:
        if c["category"] not in seen:
            seen.add(c["category"]); categories.append({"key": c["category"], "label": c["category_label"]})
    categories.sort(key=lambda x: x["label"])
    return {"items": items, "total": len(items), "categories": categories}

@api.get("/coins/ledger")
async def coin_ledger(user=Depends(get_current_user)):
    txns = await db.coin_transactions.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(300)
    return {"transactions": txns}

# ---------- Auth ----------
@api.post("/auth/register")
async def register(req: RegisterReq):
    if await db.users.find_one({"email": req.email.lower()}):
        raise HTTPException(400, "Email already registered")
    uid = str(uuid.uuid4())
    referrer = None
    if req.referral_code:
        referrer = await db.users.find_one({"referral_code": req.referral_code.strip().upper()}, {"id": 1})
    birth_date = None
    zodiac = None
    age = req.age
    if req.birth_year and req.birth_month and req.birth_day:
        birth_date = f"{int(req.birth_year):04d}-{int(req.birth_month):02d}-{int(req.birth_day):02d}"
        zodiac = zodiac_sign(req.birth_month, req.birth_day)
        computed = age_from_birth(req.birth_year, req.birth_month, req.birth_day)
        if computed:
            age = computed
    _genders = [g for g in (req.genders or []) if g in VALID_GENDERS]
    if not _genders and req.gender in VALID_GENDERS:
        _genders = [req.gender]
    _orientations = [o for o in (req.orientations or []) if o in VALID_ORIENTATIONS]
    if not _orientations and req.orientation in VALID_ORIENTATIONS:
        _orientations = [req.orientation]
    if not _orientations:
        raise HTTPException(400, "ORIENTATION_REQUIRED")
    doc = {
        "id": uid, "email": req.email.lower(), "password": hash_pwd(req.password),
        "name": req.name, "age": age, "gender": (_genders[0] if _genders else req.gender), "genders": _genders,
        "birth_date": birth_date, "zodiac": zodiac,
        "interested_in": req.interested_in, "orientation": _orientations[0], "orientations": _orientations, "city": req.city, "country": req.country,
        "lat": req.lat, "lng": req.lng,
        "bio": req.bio or "", "interests": [], "photos": [], "language": req.language or "en",
        "phone": (req.phone or "").strip() or None,
        "sms_notifications_enabled": bool(req.sms_notifications_enabled),
        "coins": 0,  # no welcome bonus (Spin & Win only)
        "escrow": 0.0, "withdrawable": 0.0,
        "premium_until": None, "verified": False,
        "account_status": "ACTIVE",
        "welcome_spin_done": False,
        "referral_code": uid[:8].upper(), "referred_by": referrer["id"] if referrer else None,
        "referral_rewarded": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    fresh = await db.users.find_one({"id": uid})
    # Chronological audit log of every new registration (indexed on created_at).
    try:
        await db.new_users_list.insert_one({
            "id": str(uuid.uuid4()), "user_id": uid, "name": doc["name"], "email": doc["email"],
            "country": doc.get("country"), "city": doc.get("city"), "language": doc.get("language"),
            "phone": doc.get("phone"), "referral_code": (req.referral_code or "").upper().strip() or None,
            "referred_by": doc.get("referred_by"), "sms_notifications_enabled": doc["sms_notifications_enabled"],
            "registered_at": doc["created_at"],
        })
    except Exception as e:
        logging.error(f"new_users_list log failed: {e}")
    # Instant admin email on every new registration (subject exactly "New User").
    try:
        from html import escape as _esc
        used_ref = (req.referral_code or "").upper().strip() or "—"
        rows = [
            ("User ID", uid), ("Name", doc["name"]), ("Email", doc["email"]),
            ("Country", doc.get("country") or "—"), ("City", doc.get("city") or "—"),
            ("Registered", doc["created_at"]), ("Referral Code", used_ref),
        ]
        body_html = (
            '<table role="presentation" width="100%" style="background:#0f0d16;border-radius:12px;'
            'border:1px solid rgba(255,255,255,0.08)">'
            + "".join(
                f'<tr><td style="padding:6px 12px;color:#8a8598;font-size:13px">{_esc(k)}</td>'
                f'<td style="padding:6px 12px;color:#f4f1f7;font-size:13px;font-weight:600">{_esc(str(v))}</td></tr>'
                for k, v in rows)
            + "</table>"
        )
        html = _email_html("New user registered", "A new member just joined GiftsDates:") + body_html
        sent = await send_email(to=ADMIN_NOTIFY_EMAIL, subject="New User", html=html)
        await db.email_outbox.insert_one({"id": str(uuid.uuid4()), "to": ADMIN_NOTIFY_EMAIL, "subject": "New User",
                                          "body": f"New user {doc['name']} ({doc['email']}) from {doc.get('country') or '—'}",
                                          "note": "new user", "status": "sent" if sent else "failed",
                                          "created_at": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logging.error(f"admin signup email failed: {e}")
    return {"token": make_token(uid), "user": {k: v for k, v in fresh.items() if k not in ("password", "_id")}, "spin_bonus": None}

@api.post("/auth/login")
async def login(req: LoginReq):
    u = await db.users.find_one({"email": req.email.lower()})
    if not u or not verify_pwd(req.password, u["password"]):
        raise HTTPException(401, "Invalid credentials")
    bu = u.get("blocked_until")
    if bu and datetime.fromisoformat(bu.replace("Z", "+00:00")) > datetime.now(timezone.utc):
        raise HTTPException(403, f"BLOCKED:{bu}")
    # Taking a break: logging back in instantly reactivates a PAUSED account (no data lost).
    if u.get("account_status") == "PAUSED":
        await db.users.update_one({"id": u["id"]}, {"$set": {"account_status": "ACTIVE"}, "$unset": {"paused_at": ""}})
        u["account_status"] = "ACTIVE"
    # PENDING_DELETION accounts stay logged in so the user can choose to Restore within the 30-day window.
    return {"token": make_token(u["id"]), "user": {k: v for k, v in u.items() if k not in ("password", "_id")}}

@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    user["is_premium"] = is_premium(user)
    user["is_vip"] = is_vip(user)
    user["is_premium_lite"] = is_premium_lite(user)
    return user

@api.patch("/auth/me")
async def update_me(patch: ProfileUpdate, user=Depends(get_current_user)):
    upd = {k: v for k, v in patch.model_dump().items() if v is not None}
    if "genders" in upd:
        gs = [g for g in (upd["genders"] or []) if g in VALID_GENDERS]
        upd["genders"] = gs
        if gs:
            upd["gender"] = gs[0]
    if "orientations" in upd:
        os_ = [o for o in (upd["orientations"] or []) if o in VALID_ORIENTATIONS]
        upd["orientations"] = os_
        if os_:
            upd["orientation"] = os_[0]
    if "orientation" in upd and upd.get("orientation") and "orientations" not in upd:
        if upd["orientation"] in VALID_ORIENTATIONS:
            upd["orientations"] = [upd["orientation"]]
    if "hide_distance" in upd and upd["hide_distance"] and not (is_premium(user) or is_vip(user)):
        raise HTTPException(403, "PREMIUM_REQUIRED")
    if "height" in upd and not (100 <= upd["height"] <= 250): raise HTTPException(400, "Height must be 100-250 cm")
    if "weight" in upd and not (30 <= upd["weight"] <= 300): raise HTTPException(400, "Weight must be 30-300 kg")
    if "date_price" in upd:
        mn = (await get_settings())["date_min_coins"]
        if upd["date_price"] < mn: raise HTTPException(400, f"Date price must be at least {mn} coins")
    if "photos" in upd and len(upd["photos"]) > MAX_PHOTOS:
        raise HTTPException(400, f"Max {MAX_PHOTOS} photos")
    if "video_rate" in upd:
        mn = (await get_settings())["video_rate"]
        if upd["video_rate"] < mn: raise HTTPException(400, f"Video rate must be at least {mn} coins/min")
    if "passport_cities" in upd:
        cleaned = []
        for c in (upd["passport_cities"] or [])[:8]:
            try:
                if isinstance(c, dict) and c.get("city") and c.get("lat") is not None and c.get("lng") is not None:
                    cleaned.append({"city": str(c["city"])[:80], "lat": float(c["lat"]), "lng": float(c["lng"])})
            except Exception:
                continue
        upd["passport_cities"] = cleaned
    if "availability" in upd:
        upd["availability"] = sorted({d[:10] for d in upd["availability"] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d[:10])})
    def _win_ok(w): return isinstance(w, dict) and re.fullmatch(r"\d{2}:\d{2}", str(w.get("from", ""))) and re.fullmatch(r"\d{2}:\d{2}", str(w.get("to", ""))) and w["from"] != w["to"]  # to <= from means the window runs past midnight into the next day
    if "availability_time" in upd and upd["availability_time"] and not _win_ok(upd["availability_time"]): raise HTTPException(400, "Invalid time window")
    if "availability_slots" in upd:
        upd["availability_slots"] = {k[:10]: v for k, v in (upd["availability_slots"] or {}).items() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k[:10]) and _win_ok(v)}
    def _ranges_ok(lst): return [{"from": w["from"], "to": w["to"]} for w in (lst or [])[:8] if _win_ok(w)]
    if "availability_ranges" in upd:
        upd["availability_ranges"] = {k[:10]: r for k, v in (upd["availability_ranges"] or {}).items()
                                      if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k[:10]) and (r := _ranges_ok(v))}
    if "availability_weekly" in upd:
        upd["availability_weekly"] = {k: r for k, v in (upd["availability_weekly"] or {}).items()
                                      if k in {"0", "1", "2", "3", "4", "5", "6"} and (r := _ranges_ok(v))}
    by, bm, bd = upd.pop("birth_year", None), upd.pop("birth_month", None), upd.pop("birth_day", None)
    if by and bm and bd:
        upd["birth_date"] = f"{int(by):04d}-{int(bm):02d}-{int(bd):02d}"
        upd["zodiac"] = zodiac_sign(bm, bd)
        computed = age_from_birth(by, bm, bd)
        if computed: upd["age"] = computed
    if upd:
        await db.users.update_one({"id": user["id"]}, {"$set": upd})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password": 0})
    return fresh

@api.get("/admin/new-users")
async def admin_new_users(country: Optional[str] = None, referral_code: Optional[str] = None,
                          since: Optional[str] = None, limit: int = 200, admin=Depends(get_admin)):
    """Chronological audit list of new registrations with optional filters."""
    q: dict = {}
    if country: q["country"] = country
    if referral_code: q["referral_code"] = referral_code.upper().strip()
    if since: q["registered_at"] = {"$gte": since}
    total = await db.new_users_list.count_documents(q)
    rows = await db.new_users_list.find(q, {"_id": 0}).sort("registered_at", -1).limit(min(max(limit, 1), 500)).to_list(500)
    return {"total": total, "users": rows}


# ---------- Uploads ----------
@api.post("/upload")
async def upload(file: UploadFile = File(...), user=Depends(get_current_user)):
    ext = (file.filename.split(".")[-1] if "." in file.filename else "bin").lower()
    path = f"{APP_NAME}/uploads/{user['id']}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    ct = file.content_type or "application/octet-stream"
    result = put_object(path, data, ct)
    await db.files.insert_one({
        "id": str(uuid.uuid4()), "storage_path": result["path"],
        "user_id": user["id"], "content_type": ct, "size": result["size"],
        "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"path": result["path"], "url": f"/api/files/{result['path']}"}

@api.post("/profile/photos")
async def add_photo(file: UploadFile = File(...), user=Depends(get_current_user)):
    photos = user.get("photos") or []
    if len(photos) >= MAX_PHOTOS: raise HTTPException(400, f"Max {MAX_PHOTOS} photos")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400, "Only images allowed")
    ext = (file.filename.split(".")[-1] if "." in file.filename else "jpg").lower()
    path = f"{APP_NAME}/photos/{user['id']}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type)
    await db.files.insert_one({"id": str(uuid.uuid4()), "storage_path": result["path"], "user_id": user["id"],
                               "content_type": file.content_type, "size": result["size"], "is_deleted": False,
                               "created_at": datetime.now(timezone.utc).isoformat()})
    photos.append(result["path"])
    await db.users.update_one({"id": user["id"]}, {"$set": {"photos": photos}})
    return {"photos": photos}

# ---------- News feed (stories) ----------
FEED_TEXT_COINS = 100
FEED_VIDEO_COINS = 150
FEED_MAX = 50
FEED_VIDEO_MAX_BYTES = 120 * 1024 * 1024

@api.get("/feed")
async def get_feed(country: Optional[str] = None, city: Optional[str] = None, user=Depends(get_current_user)):
    q = {}
    if country: q["user_country"] = {"$regex": country, "$options": "i"}
    if city: q["user_city"] = {"$regex": city, "$options": "i"}
    return await db.feed.find(q, {"_id": 0}).sort("created_at", -1).to_list(FEED_MAX)

@api.post("/feed")
async def create_feed(text: str = Form(""), video: Optional[UploadFile] = File(None), user=Depends(get_current_user)):
    text = (text or "").strip()[:80]
    has_video = video is not None
    if not text and not has_video:
        raise HTTPException(400, "EMPTY_POST")
    cost = (FEED_TEXT_COINS if text else 0) + (FEED_VIDEO_COINS if has_video else 0)
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "coins": 1, "withdrawable": 1, "photos": 1, "name": 1, "age": 1, "city": 1, "country": 1, "gender": 1})
    if ((fresh.get("coins") or 0) + (fresh.get("withdrawable") or 0)) < cost:
        raise HTTPException(400, "INSUFFICIENT_COINS")
    video_path = None
    if has_video:
        data = await video.read()
        if len(data) > FEED_VIDEO_MAX_BYTES:
            raise HTTPException(400, "VIDEO_TOO_LARGE")
        ct = video.content_type or "video/mp4"
        if not ct.startswith("video/"):
            raise HTTPException(400, "NOT_VIDEO")
        ext = (video.filename.split(".")[-1] if video.filename and "." in video.filename else "mp4").lower()
        path = f"{APP_NAME}/feed/{user['id']}/{uuid.uuid4()}.{ext}"
        result = put_object(path, data, ct)
        video_path = result["path"]
        await db.files.insert_one({"id": str(uuid.uuid4()), "storage_path": video_path, "user_id": user["id"],
                                   "content_type": ct, "size": result["size"], "is_deleted": False, "private": False,
                                   "created_at": datetime.now(timezone.utc).isoformat()})
    await spend_coins(user["id"], cost)
    now = datetime.now(timezone.utc).isoformat()
    photos = fresh.get("photos") or []
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "user_name": fresh.get("name"),
           "user_avatar": photos[0] if photos else None, "text": text or None,
           "user_age": fresh.get("age"), "user_city": fresh.get("city"), "user_country": fresh.get("country"),
           "gender": fresh.get("gender"),
           "video_path": video_path, "has_video": has_video, "created_at": now}
    await db.feed.insert_one({**doc})
    await db.transactions.insert_one({"id": str(uuid.uuid4()), "user_id": user["id"], "type": "feed_post",
                                      "coins": -cost, "created_at": now})
    extras = await db.feed.find({}, {"_id": 0, "id": 1}).sort("created_at", -1).skip(FEED_MAX).to_list(1000)
    if extras:
        await db.feed.delete_many({"id": {"$in": [e["id"] for e in extras]}})
    return {"posted": True, "cost": cost, "item": doc}

@api.delete("/feed/{fid}")
async def delete_feed(fid: str, user=Depends(get_current_user)):
    it = await db.feed.find_one({"id": fid})
    if not it:
        raise HTTPException(404, "Not found")
    if it["user_id"] != user["id"] and not is_admin(user):
        raise HTTPException(403, "Forbidden")
    await db.feed.delete_one({"id": fid})
    if it.get("video_path"):
        await db.files.update_one({"storage_path": it["video_path"]}, {"$set": {"is_deleted": True}})
    return {"deleted": True}

class PhotoReq(BaseModel):
    path: str

@api.delete("/profile/photos")
async def delete_photo(req: PhotoReq, user=Depends(get_current_user)):
    photos = [p for p in (user.get("photos") or []) if p != req.path]
    await db.users.update_one({"id": user["id"]}, {"$set": {"photos": photos}})
    await db.files.update_one({"storage_path": req.path, "user_id": user["id"]}, {"$set": {"is_deleted": True}})
    return {"photos": photos}

@api.post("/profile/photos/primary")
async def primary_photo(req: PhotoReq, user=Depends(get_current_user)):
    photos = user.get("photos") or []
    if req.path not in photos: raise HTTPException(404, "Photo not found")
    photos = [req.path] + [p for p in photos if p != req.path]
    await db.users.update_one({"id": user["id"]}, {"$set": {"photos": photos}})
    return {"photos": photos}

# ---------- Identity verification (ID + selfie) ----------
VERIFY_ALLOWED_CT = {"image/jpeg", "image/jpg", "image/png", "application/pdf"}
VERIFY_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

@api.post("/verification/upload")
async def verification_upload(kind: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    if kind not in ("id", "selfie"): raise HTTPException(400, "kind must be id or selfie")
    ct = (file.content_type or "").lower()
    if ct not in VERIFY_ALLOWED_CT: raise HTTPException(400, "Only JPG, PNG or PDF files are allowed")
    data = await file.read()
    if not data: raise HTTPException(400, "Empty file")
    if len(data) > VERIFY_MAX_BYTES: raise HTTPException(400, "File too large — maximum size is 10MB")
    v = user.get("verification") or {}
    if v.get("status") == "verified": raise HTTPException(400, "Already verified")
    ext = (file.filename.split(".")[-1] if file.filename and "." in file.filename else ("pdf" if ct == "application/pdf" else "jpg")).lower()
    path = f"{APP_NAME}/verification/{user['id']}/{kind}-{uuid.uuid4()}.{ext}"
    result = put_object(path, data, ct)
    await db.files.insert_one({"id": str(uuid.uuid4()), "storage_path": result["path"], "user_id": user["id"], "private": True,
                               "content_type": ct, "size": result["size"], "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat()})
    v[f"{kind}_path"] = result["path"]
    v[f"{kind}_type"] = ct
    v["status"] = "pending" if v.get("id_path") and v.get("selfie_path") else "incomplete"
    v["reason"] = ""
    if v["status"] == "pending":
        v["submitted_at"] = datetime.now(timezone.utc).isoformat()
        # single-use, time-limited token for email Approve/Decline links
        v["review_token"] = secrets.token_urlsafe(32)
        v["review_token_used"] = False
        v["review_token_exp"] = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    await db.users.update_one({"id": user["id"]}, {"$set": {"verification": v}})
    # When both ID + selfie are in, email the admin inbox with secure Approve/Decline links.
    if v["status"] == "pending":
        try:
            await send_id_verification_email(user, v)
        except Exception as e:
            logging.error(f"admin id-approval email failed: {e}")
    return {k: val for k, val in v.items() if k not in ("review_token", "review_token_used", "review_token_exp")}


def _id_review_email_html(user: dict, v: dict, approve_url: str, decline_url: str, id_doc_url: str, selfie_url: str) -> str:
    """Server-side template for the admin ID-review email. No forms; all links https + first-party."""
    from html import escape as _esc
    name = _esc(str(user.get("name") or "—"))
    uid = _esc(str(user.get("id") or "—"))
    email = _esc(str(user.get("email") or "—"))
    reg = user.get("created_at") or ""
    try:
        reg_fmt = datetime.fromisoformat(reg.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M UTC") if reg else "—"
    except Exception:
        reg_fmt = _esc(str(reg)) or "—"
    id_type = "PDF" if (v.get("id_type") == "application/pdf") else "Image"
    selfie_type = "PDF" if (v.get("selfie_type") == "application/pdf") else "Image"
    row = lambda k, val: (f'<tr><td style="padding:6px 12px;color:#8a8598;font-size:13px">{k}</td>'
                          f'<td style="padding:6px 12px;color:#f4f1f7;font-size:13px;font-weight:600">{val}</td></tr>')
    doc_btn = lambda label, url: (f'<a href="{url}" style="display:inline-block;background:rgba(255,255,255,0.06);'
                                  f'border:1px solid rgba(212,175,55,0.35);color:#f3e5ab;text-decoration:none;'
                                  f'padding:10px 18px;border-radius:10px;font-weight:600;font-family:Arial;'
                                  f'font-size:13px;margin:4px 6px 4px 0">{label} &rarr;</a>')
    return (
        f'<table role="presentation" width="100%" style="background:#0d0b12;padding:24px"><tr><td align="center">'
        f'<table role="presentation" width="560" style="background:#161320;border-radius:16px;'
        f'border:1px solid rgba(212,175,55,0.25);font-family:Arial,sans-serif;color:#f4f1f7">'
        f'<tr><td style="padding:26px 30px">'
        f'<div style="font-size:20px;font-weight:700;color:#f3e5ab;margin-bottom:4px">GiftsDates</div>'
        f'<div style="font-size:17px;font-weight:700;margin:12px 0 6px">New ID verification to review 🪪</div>'
        f'<div style="font-size:14px;line-height:1.5;color:#c9c4d4;margin-bottom:16px">'
        f'A member submitted an ID document and a selfie. Review the documents below, then Approve or Decline.</div>'
        f'<table role="presentation" width="100%" style="background:#0f0d16;border-radius:12px;border:1px solid rgba(255,255,255,0.08);margin-bottom:18px">'
        f'{row("Username", name)}{row("User ID", uid)}{row("Email", email)}{row("Registered", reg_fmt)}</table>'
        f'<div style="font-size:13px;color:#8a8598;margin-bottom:6px">Submitted documents</div>'
        f'<div style="margin-bottom:20px">{doc_btn(f"View ID document ({id_type})", id_doc_url)}{doc_btn(f"View selfie ({selfie_type})", selfie_url)}</div>'
        f'<div style="text-align:center;margin:8px 0 4px">'
        f'<a href="{approve_url}" style="display:inline-block;background:#059669;color:#fff;text-decoration:none;'
        f'padding:13px 30px;border-radius:999px;font-weight:700;font-family:Arial;margin:4px 8px">Approve &#10003;</a>'
        f'<a href="{decline_url}" style="display:inline-block;background:#e11d48;color:#fff;text-decoration:none;'
        f'padding:13px 30px;border-radius:999px;font-weight:700;font-family:Arial;margin:4px 8px">Decline &#10007;</a>'
        f'</div>'
        f'<div style="font-size:11px;color:#8a8598;margin-top:22px;border-top:1px solid rgba(255,255,255,0.08);padding-top:12px">'
        f'These action links are single-use and expire in 30 days. Sent by GiftsDates. '
        f'We never ask for your password or card details by email.</div>'
        f'</td></tr></table></td></tr></table>')


async def send_id_verification_email(user: dict, v: dict) -> bool:
    """Email the fixed admin inbox with secure single-use Approve/Decline links for an ID submission."""
    tok = v.get("review_token")
    base = (PUBLIC_APP_URL or "").rstrip("/")
    approve_url = f"{base}/api/verification/review?token={tok}&action=approve"
    decline_url = f"{base}/api/verification/review?token={tok}&action=decline"
    id_doc_url = f"{base}/api/verification/doc?token={tok}&kind=id"
    selfie_url = f"{base}/api/verification/doc?token={tok}&kind=selfie"
    subject = f"ID verification - {user.get('name') or 'Member'} / {user.get('id')}"
    html = _id_review_email_html(user, v, approve_url, decline_url, id_doc_url, selfie_url)
    sent = await send_email(to=ADMIN_NOTIFY_EMAIL, subject=subject, html=html)
    await db.email_outbox.insert_one({"id": str(uuid.uuid4()), "to": ADMIN_NOTIFY_EMAIL, "subject": subject,
                                      "body": f"ID review for {user.get('name')} ({user.get('email')})", "note": "id approval",
                                      "status": "sent" if sent else "failed", "created_at": datetime.now(timezone.utc).isoformat()})
    return sent

@api.get("/verification")
async def verification_status(user=Depends(get_current_user)):
    v = user.get("verification") or {"status": "none"}
    return {k: val for k, val in v.items() if k not in ("review_token", "review_token_used", "review_token_exp")}

@api.get("/admin/verifications")
async def admin_verifications(status: str = "pending", admin=Depends(get_admin)):
    q = {"verification.status": status} if status != "all" else {"verification": {"$exists": True}}
    users = await db.users.find(q, {"_id": 0, "id": 1, "name": 1, "email": 1, "age": 1, "city": 1, "country": 1, "verification": 1, "verified": 1}).sort("verification.submitted_at", -1).to_list(200)
    return users

@api.post("/admin/verifications/{user_id}/verify")
async def admin_verify_identity(user_id: str, req: AdminVerifyReq, admin=Depends(get_admin)):
    u = await db.users.find_one({"id": user_id})
    if not u or not u.get("verification"): raise HTTPException(404, "Not found")
    status = "verified" if req.approve else "rejected"
    await db.users.update_one({"id": user_id}, {"$set": {"verified": req.approve, "verification.status": status, "verification.reason": req.reason or "",
                                                          "verification.reviewed_at": datetime.now(timezone.utc).isoformat(), "verification.reviewed_by": admin["id"]}})
    await notify(user_id, "identity", "Identity verified ✅" if req.approve else "Identity verification rejected",
                 "Your profile now has the verified badge." if req.approve else (req.reason or "Please upload clearer photos of your ID and selfie."), email=True)
    return {"status": status}

# ---------- Email-based ID review (secure single-use token links) ----------
def _review_page(title: str, message: str, ok: bool = True) -> HTMLResponse:
    color = "#059669" if ok else "#e11d48"
    icon = "&#10003;" if ok else "&#10007;"
    from html import escape as _esc
    html = (
        f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>GiftsDates · {_esc(title)}</title></head>'
        f'<body style="margin:0;background:#0d0b12;font-family:Arial,Helvetica,sans-serif;color:#f4f1f7">'
        f'<div style="max-width:480px;margin:60px auto;background:#161320;border:1px solid rgba(212,175,55,0.25);'
        f'border-radius:16px;padding:36px 30px;text-align:center">'
        f'<div style="font-size:22px;font-weight:700;color:#f3e5ab;margin-bottom:18px">GiftsDates</div>'
        f'<div style="width:64px;height:64px;border-radius:50%;background:{color};color:#fff;font-size:30px;'
        f'line-height:64px;margin:0 auto 18px">{icon}</div>'
        f'<div style="font-size:20px;font-weight:700;margin-bottom:8px">{_esc(title)}</div>'
        f'<div style="font-size:14px;line-height:1.6;color:#c9c4d4">{message}</div>'
        f'</div></body></html>')
    return HTMLResponse(content=html)


def _decline_form_page(token: str) -> HTMLResponse:
    from html import escape as _esc
    action = f"{(PUBLIC_APP_URL or '').rstrip('/')}/api/verification/review/decline"
    html = (
        f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>GiftsDates · Decline verification</title></head>'
        f'<body style="margin:0;background:#0d0b12;font-family:Arial,Helvetica,sans-serif;color:#f4f1f7">'
        f'<div style="max-width:480px;margin:56px auto;background:#161320;border:1px solid rgba(212,175,55,0.25);'
        f'border-radius:16px;padding:34px 30px">'
        f'<div style="font-size:22px;font-weight:700;color:#f3e5ab;margin-bottom:14px;text-align:center">GiftsDates</div>'
        f'<div style="font-size:19px;font-weight:700;margin-bottom:8px">Decline this verification?</div>'
        f'<div style="font-size:14px;line-height:1.5;color:#c9c4d4;margin-bottom:18px">'
        f'Optionally add a reason. The member will be asked to re-submit clearer documents.</div>'
        f'<form method="POST" action="{action}">'
        f'<input type="hidden" name="token" value="{_esc(token)}" />'
        f'<textarea name="reason" rows="3" placeholder="Reason (optional) — e.g. blurry photo, ID expired" '
        f'style="width:100%;box-sizing:border-box;background:#0f0d16;border:1px solid rgba(255,255,255,0.12);'
        f'border-radius:10px;color:#f4f1f7;padding:12px;font-size:14px;font-family:Arial;margin-bottom:16px"></textarea>'
        f'<button type="submit" style="width:100%;background:#e11d48;color:#fff;border:0;padding:13px;'
        f'border-radius:999px;font-weight:700;font-size:15px;cursor:pointer">Confirm decline</button>'
        f'</form></div></body></html>')
    return HTMLResponse(content=html)


async def _find_pending_by_token(token: str):
    if not token:
        return None
    return await db.users.find_one({"verification.review_token": token})


async def _apply_review_decision(u: dict, approve: bool, reason: str = ""):
    uid = u["id"]
    status = "verified" if approve else "rejected"
    await db.users.update_one({"id": uid}, {"$set": {
        "verified": approve,
        "verification.status": status,
        "verification.reason": reason or "",
        "verification.reviewed_at": datetime.now(timezone.utc).isoformat(),
        "verification.reviewed_by": "email-link",
        "verification.review_token_used": True,
    }})
    await notify(uid, "identity",
                 "Identity verified ✅" if approve else "Identity verification declined",
                 "Your account has been successfully verified — your profile now shows the verified badge." if approve
                 else (reason or "Please re-upload clearer photos of your ID and a selfie holding it."),
                 email=True)


@api.get("/verification/review")
async def verification_review(token: str, action: str):
    if action not in ("approve", "decline"):
        return _review_page("Invalid request", "Unknown action.", ok=False)
    u = await _find_pending_by_token(token)
    if not u:
        return _review_page("Link not valid", "This review link is invalid or has already been used.", ok=False)
    v = u.get("verification") or {}
    if v.get("review_token_used"):
        return _review_page("Already reviewed", "This verification has already been reviewed. No further action is needed.", ok=False)
    exp = v.get("review_token_exp")
    try:
        if exp and datetime.fromisoformat(exp.replace("Z", "+00:00")) < datetime.now(timezone.utc):
            return _review_page("Link expired", "This review link has expired. Ask the member to re-submit their documents.", ok=False)
    except Exception:
        pass
    if action == "decline":
        return _decline_form_page(token)
    await _apply_review_decision(u, True)
    return _review_page("Member approved", f"<b>{u.get('name')}</b> is now <b>Verified</b> and has received the verified badge.", ok=True)


@api.post("/verification/review/decline")
async def verification_review_decline(token: str = Form(...), reason: str = Form("")):
    u = await _find_pending_by_token(token)
    if not u:
        return _review_page("Link not valid", "This review link is invalid or has already been used.", ok=False)
    v = u.get("verification") or {}
    if v.get("review_token_used"):
        return _review_page("Already reviewed", "This verification has already been reviewed.", ok=False)
    await _apply_review_decision(u, False, (reason or "").strip())
    return _review_page("Member declined", f"<b>{u.get('name')}</b>'s verification was declined and they've been notified to re-submit.", ok=False)


@api.get("/verification/doc")
async def verification_doc(token: str, kind: str):
    if kind not in ("id", "selfie"):
        raise HTTPException(400, "Invalid document kind")
    u = await _find_pending_by_token(token)
    if not u:
        raise HTTPException(403, "Invalid or expired link")
    v = u.get("verification") or {}
    exp = v.get("review_token_exp")
    try:
        if exp and datetime.fromisoformat(exp.replace("Z", "+00:00")) < datetime.now(timezone.utc):
            raise HTTPException(403, "Link expired")
    except HTTPException:
        raise
    except Exception:
        pass
    path = v.get(f"{kind}_path")
    if not path:
        raise HTTPException(404, "Document not found")
    data, ct = get_object(path)
    return Response(content=data, media_type=v.get(f"{kind}_type") or ct)



@api.post("/reports")
async def create_report(req: ReportReq, user=Depends(get_current_user)):
    if req.reason not in REPORT_REASONS:
        raise HTTPException(400, "INVALID_REASON")
    if req.target_id == user["id"]:
        raise HTTPException(400, "CANNOT_REPORT_SELF")
    target = await db.users.find_one({"id": req.target_id}, {"_id": 0, "id": 1, "name": 1})
    if not target:
        raise HTTPException(404, "User not found")
    now = datetime.now(timezone.utc).isoformat()
    existing = await db.reports.find_one({"reporter_id": user["id"], "target_id": req.target_id, "status": "open"})
    if existing:
        raise HTTPException(409, "ALREADY_REPORTED")
    await db.reports.insert_one({
        "id": str(uuid.uuid4()), "reporter_id": user["id"], "reporter_name": user.get("name"),
        "target_id": req.target_id, "target_name": target.get("name"),
        "reason": req.reason, "reason_label": REPORT_REASONS[req.reason],
        "details": (req.details or "").strip()[:2000], "status": "open", "created_at": now,
    })
    for a_email in ADMIN_EMAILS:
        adm = await db.users.find_one({"email": a_email}, {"_id": 0, "id": 1})
        if adm:
            await notify(adm["id"], "report", "New user report 🚩",
                         f"{user.get('name')} reported {target.get('name')} · {REPORT_REASONS[req.reason]}",
                         {"target_id": req.target_id})
    return {"reported": True}

@api.get("/admin/reports")
async def admin_reports(status: str = "open", admin=Depends(get_admin)):
    q = {} if status == "all" else {"status": status}
    reports = await db.reports.find(q, {"_id": 0}).sort("created_at", -1).to_list(300)
    return reports

@api.post("/admin/reports/{rid}/resolve")
async def admin_resolve_report(rid: str, admin=Depends(get_admin)):
    r = await db.reports.find_one({"id": rid})
    if not r:
        raise HTTPException(404, "Not found")
    await db.reports.update_one({"id": rid}, {"$set": {"status": "resolved",
                                "resolved_at": datetime.now(timezone.utc).isoformat(), "resolved_by": admin["id"]}})
    return {"status": "resolved"}

@api.post("/admin/reports/{rid}/block")
async def admin_block_from_report(rid: str, admin=Depends(get_admin)):
    r = await db.reports.find_one({"id": rid})
    if not r:
        raise HTTPException(404, "Not found")
    new_until = datetime.now(timezone.utc) + timedelta(days=BLOCK_DAYS)
    target = await db.users.find_one({"id": r["target_id"]}, {"_id": 0, "blocked_until": 1})
    existing = target.get("blocked_until") if target else None
    if existing:
        try:
            ex = datetime.fromisoformat(existing.replace("Z", "+00:00"))
            if ex > new_until:
                new_until = ex
        except Exception:
            pass
    until = new_until.isoformat()
    await db.users.update_one({"id": r["target_id"]}, {"$set": {"blocked_until": until}})
    await db.reports.update_one({"id": rid}, {"$set": {"status": "resolved", "action": "blocked",
                                "resolved_at": datetime.now(timezone.utc).isoformat(), "resolved_by": admin["id"]}})
    await notify(r["target_id"], "blocked", "Account blocked 🚫",
                 f"Your account was blocked for {BLOCK_DAYS} days following a policy violation report.", {"until": until}, email=True)
    return {"status": "resolved", "action": "blocked", "until": until}

@api.get("/files/{path:path}")
async def download(path: str, authorization: Optional[str] = Header(None), auth: Optional[str] = None):
    rec = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not rec:
        raise HTTPException(404, "Not found")
    if rec.get("private"):
        token = auth or (authorization.split(" ", 1)[1] if authorization and " " in authorization else None)
        try: uid = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])["sub"] if token else None
        except Exception: uid = None
        viewer = await db.users.find_one({"id": uid}) if uid else None
        if not viewer or (viewer["id"] != rec["user_id"] and viewer["id"] not in (rec.get("viewers") or []) and not is_admin(viewer)): raise HTTPException(403, "Private file")
    data, ct = get_object(path)
    return Response(content=data, media_type=rec.get("content_type") or ct)

# ---------- Profiles / Search ----------
def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in km between two lat/lng points, or None if any missing."""
    if lat1 is None or lng1 is None or lat2 is None or lng2 is None:
        return None
    try:
        from math import radians, sin, cos, asin, sqrt
        rlat1, rlat2 = radians(float(lat1)), radians(float(lat2))
        dlat = rlat2 - rlat1
        dlng = radians(float(lng2) - float(lng1))
        a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlng / 2) ** 2
        return round(2 * 6371.0088 * asin(sqrt(a)), 2)
    except Exception:
        return None

def visible_distance(vlat, vlng, target: dict):
    """Distance in km from a viewer to a target, honoring the target's hide_distance privacy flag.
    Falls back to the target's approximate coords (city/country) so every user shows a rough distance."""
    if target.get("hide_distance"):
        return None
    tlat, tlng = approx_coords(target)
    return haversine_km(vlat, vlng, tlat, tlng)

@api.get("/profiles")
async def list_profiles(
    q: Optional[str] = None, city: Optional[str] = None, country: Optional[str] = None,
    min_age: int = 18, max_age: int = 99, gender: Optional[str] = None, genders: Optional[str] = None,
    intent: Optional[str] = None, min_height: Optional[int] = None, max_height: Optional[int] = None,
    kids: Optional[str] = None, smoking: Optional[str] = None, religion: Optional[str] = None, orientation: Optional[str] = None,
    drinking: Optional[str] = None, income: Optional[str] = None, language: Optional[str] = None,
    hobby: Optional[str] = None, job: Optional[str] = None, min_weight: Optional[int] = None, max_weight: Optional[int] = None,
    bust_size: Optional[str] = None, penis_size: Optional[str] = None, min_date_price: Optional[int] = None, max_date_price: Optional[int] = None, min_video_rate: Optional[int] = None, max_video_rate: Optional[int] = None,
    zodiac: Optional[str] = None, available_date: Optional[str] = None, video_calls: bool = False,
    premium_only: bool = False, vip_only: bool = False, with_photos: bool = False, verified_only: bool = False, online_now: bool = False, video_now: bool = False,
    vip_categories: Optional[str] = None, vip_services: Optional[str] = None, vip_min_price: Optional[int] = None, vip_max_price: Optional[int] = None, vip_date: Optional[str] = None,
    vip_eye_color: Optional[str] = None, vip_hair_color: Optional[str] = None, vip_intimate_haircut: Optional[str] = None, vip_breast_size: Optional[str] = None,
    vip_min_height: Optional[int] = None, vip_max_height: Optional[int] = None, vip_min_weight: Optional[int] = None, vip_max_weight: Optional[int] = None,
    vip_min_dick: Optional[int] = None, vip_max_dick: Optional[int] = None, vip_min_girth: Optional[int] = None, vip_max_girth: Optional[int] = None,
    vip_price1h_min: Optional[int] = None, vip_price1h_max: Optional[int] = None,
    vip_price2h_min: Optional[int] = None, vip_price2h_max: Optional[int] = None,
    vip_price3h_min: Optional[int] = None, vip_price3h_max: Optional[int] = None,
    max_distance: Optional[int] = None, sort: Optional[str] = None,
    origin_lat: Optional[float] = None, origin_lng: Optional[float] = None,
    online_nearby: bool = False,
    min_income: Optional[float] = None, max_income: Optional[float] = None,
    min_penis: Optional[float] = None, max_penis: Optional[float] = None,
    hobbies: Optional[str] = None,
    limit: int = 40, page: int = 1, user=Depends(get_current_user)
):
    conds = [{"id": {"$ne": user["id"]}}, {"age": {"$gte": min_age, "$lte": max_age}},
             {"account_status": {"$nin": ["PAUSED", "PENDING_DELETION"]}}]
    online_nearby = False  # "Online nearby" filter removed from search
    # Free: country, city, gender, min/max age.
    # Premium-Lite (and above): looking for (intent), distance, available on date, date price up to.
    lite_used = any(v not in (None, "", "all", False, 0) for v in (intent, max_distance, available_date, min_date_price, max_date_price, min_video_rate, max_video_rate, video_calls)) or sort in ("coins_asc", "coins_desc", "video_asc", "video_desc")
    if lite_used and not has_premium(user): raise HTTPException(403, "PREMIUM_LITE_REQUIRED")
    # Full Premium / VIP: search by name + every other advanced filter.
    advanced_used = any(v not in (None, "", "all", False) for v in (q, hobbies, min_income, max_income, min_penis, max_penis, min_height, max_height, kids, smoking, religion, drinking, income, language, orientation,
                                                                   hobby, job, min_weight, max_weight, bust_size, penis_size, premium_only, with_photos, verified_only, online_now, video_now,
                                                                   zodiac,
                                                                   vip_categories, vip_min_price, vip_max_price, vip_date))
    if advanced_used and not (is_premium(user) or is_vip(user)): raise HTTPException(403, "PREMIUM_REQUIRED")
    vip_adv = bool(vip_categories or vip_services or (vip_min_price is not None) or (vip_max_price is not None) or vip_date
                   or vip_eye_color or vip_hair_color or vip_intimate_haircut or vip_breast_size
                   or (vip_min_height is not None) or (vip_max_height is not None) or (vip_min_weight is not None) or (vip_max_weight is not None)
                   or (vip_min_dick is not None) or (vip_max_dick is not None) or (vip_min_girth is not None) or (vip_max_girth is not None)
                   or (vip_price1h_min is not None) or (vip_price1h_max is not None)
                   or (vip_price2h_min is not None) or (vip_price2h_max is not None)
                   or (vip_price3h_min is not None) or (vip_price3h_max is not None))
    if vip_adv and not is_vip(user): raise HTTPException(403, "VIP_REQUIRED")
    vip_filter = bool(vip_only or vip_adv)
    if city and city.strip().lower() != "global":
        conds.append({"$or": [{"city": {"$regex": re.escape(city.strip()), "$options": "i"}}, {"city": {"$regex": "^global$", "$options": "i"}}]})
    if country and country.strip().lower() != "global":
        conds.append({"$or": [{"country": {"$regex": re.escape(country.strip()), "$options": "i"}}, {"country": {"$regex": "^global$", "$options": "i"}}]})
    if gender and gender != "all": conds.append({"gender": gender})
    if genders:
        glist = [g.strip() for g in genders.split(",") if g.strip() and g.strip() != "all"]
        if glist:
            conds.append({"$or": [{"gender": {"$in": glist}}, {"genders": {"$in": glist}}]})
    if q: conds.append({"$or": [{"name": {"$regex": q, "$options": "i"}}, {"bio": {"$regex": q, "$options": "i"}}]})
    # Multi-select: kids/smoking/drinking/religion accept a comma-separated list, match ANY.
    for field, val in (("kids", kids), ("smoking", smoking), ("religion", religion), ("drinking", drinking)):
        if val and val != "all":
            vlist = [x.strip() for x in val.split(",") if x.strip() and x.strip() != "all"]
            if vlist: conds.append({field: {"$in": vlist}})
    for field, val in (("income", income), ("penis_size", penis_size)):
        if val and val != "all": conds.append({field: val})
    if bust_size and bust_size != "all":
        # Multi-select: comma-separated bust sizes, match ANY
        blist = [b.strip() for b in bust_size.split(",") if b.strip() and b.strip() != "all"]
        if blist: conds.append({"bust_size": {"$in": blist}})
    # Orientation & relationship-intent are multi-select profile fields (stored as arrays),
    # with a legacy single value kept for backward compatibility — match either.
    if intent and intent != "all":
        # Multi-select: comma-separated list, match profiles whose intent is ANY of the chosen values.
        # $in matches both a legacy single-string field and an array field.
        ilist = [i.strip() for i in intent.split(",") if i.strip() and i.strip() != "all"]
        if ilist:
            conds.append({"relationship_intent": {"$in": ilist}})
    if orientation and orientation != "all":
        # Multi-select: comma-separated list, match profiles having ANY of the chosen orientations
        olist = [o.strip() for o in orientation.split(",") if o.strip() and o.strip() != "all"]
        if olist:
            conds.append({"$or": [{"orientation": {"$in": olist}}, {"orientations": {"$in": olist}}]})
    if language and language != "all":
        # Multi-select: comma-separated language codes, match profiles speaking ANY of them
        llist = [l.strip() for l in language.split(",") if l.strip() and l.strip() != "all"]
        if llist: conds.append({"languages_spoken": {"$in": llist}})
    if zodiac and zodiac != "all":
        # Multi-select: comma-separated zodiac signs, match ANY
        zlist = [z.strip() for z in zodiac.split(",") if z.strip() and z.strip() != "all"]
        if zlist: conds.append({"zodiac": {"$in": zlist}})
    if available_date:
        try: _wd = str(datetime.fromisoformat(available_date[:10]).weekday())
        except ValueError: _wd = "x"
        conds.append({"$or": [{"availability": available_date}, {f"availability_ranges.{available_date[:10]}.0": {"$exists": True}},
                              {f"availability_weekly.{_wd}.0": {"$exists": True}}]})
    if video_calls: conds.append({"video_calls_enabled": {"$ne": False}})
    if hobby: conds.append({"hobbies": {"$elemMatch": {"$regex": re.escape(hobby), "$options": "i"}}})
    if hobbies:
        # Multi-select from the profile hobby catalog ("||"-separated), match profiles having ANY of them
        hlist = [h.strip() for h in hobbies.split("||") if h.strip()][:10]  # max 10, same as profile
        if hlist: conds.append({"hobbies": {"$in": hlist}})
    if job: conds.append({"job_title": {"$regex": re.escape(job), "$options": "i"}})
    for field, lo, hi in (("height", min_height, max_height), ("weight", min_weight, max_weight)):
        if lo or hi:
            r = {}
            if lo: r["$gte"] = lo
            if hi: r["$lte"] = hi
            conds.append({field: r})
    # Date coins range. Profiles without their own amount use the platform minimum.
    if min_date_price or max_date_price:
        dmin = (await get_settings())["date_min_coins"]
        unset = [{"date_price": None}, {"date_price": {"$exists": False}}]
        unset_ok = (not min_date_price or dmin >= min_date_price) and (not max_date_price or dmin <= max_date_price)
        rng = {}
        if min_date_price: rng["$gte"] = min_date_price
        if max_date_price: rng["$lte"] = max_date_price
        conds.append({"$or": [{"date_price": rng}, *(unset if unset_ok else [])]})
    # Video call coins/min range on the effective rate (own rate, never below the platform rate); only callable members.
    if min_video_rate or max_video_rate:
        vmin = (await get_settings())["video_rate"]
        eff = {"$max": [{"$ifNull": ["$video_rate", 0]}, vmin]}
        parts = []
        if min_video_rate: parts.append({"$gte": [eff, min_video_rate]})
        if max_video_rate: parts.append({"$lte": [eff, max_video_rate]})
        conds.append({"video_calls_enabled": {"$ne": False}})
        conds.append({"$expr": {"$and": parts}})
    if with_photos: conds.append({"photos.0": {"$exists": True}})
    if verified_only: conds.append({"verified": True})
    if online_now: conds.append({"last_seen": {"$gt": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()}})
    # Available for a video call now: online in the last 5 minutes AND video calls switched on.
    if video_now:
        conds.append({"last_seen": {"$gt": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()}})
        conds.append({"video_calls_enabled": {"$ne": False}})
    if online_nearby: conds.append({"last_seen": {"$gt": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()}})
    now_iso = datetime.now(timezone.utc).isoformat()
    if premium_only: conds.append({"premium_until": {"$gt": now_iso}})
    if vip_filter:
        conds.append({"vip_until": {"$gt": now_iso}}); conds.append({"vip.published": {"$ne": False}})
        # members with "Show VIP on my main profile" off are only discoverable as VIP by VIP viewers
        if not is_vip(user): conds.append({"vip.show_on_main": {"$ne": False}})
    if vip_categories:
        cats = [c.strip() for c in vip_categories.split(",") if c.strip() in VIP_SERVICES]
        names = [s for c in cats for s in VIP_SERVICES[c]]
        if names: conds.append({"vip.services": {"$in": names}})
    if vip_services:
        chosen = [s.strip() for s in vip_services.split("||") if s.strip() in VIP_SERVICE_SET]
        if chosen: conds.append({"vip.services": {"$in": chosen}})
    if vip_min_price is not None or vip_max_price is not None:
        checks = []
        if vip_min_price is not None: checks.append({"$gte": ["$$p.v", vip_min_price]})
        if vip_max_price is not None: checks.append({"$lte": ["$$p.v", vip_max_price]})
        conds.append({"$expr": {"$anyElementTrue": {"$map": {"input": {"$objectToArray": {"$ifNull": ["$vip.prices", {}]}}, "as": "p", "in": {"$and": checks}}}}})
    if vip_date:
        conds.append({"vip.availability": {"$elemMatch": {"date": vip_date}}})
    for field, val in (("vip.eye_color", vip_eye_color), ("vip.hair_color", vip_hair_color), ("vip.intimate_haircut", vip_intimate_haircut), ("vip.breast_size", vip_breast_size)):
        if val: conds.append({field: val})
    for field, lo, hi in (("vip.height", vip_min_height, vip_max_height), ("vip.weight", vip_min_weight, vip_max_weight)):
        if lo or hi:
            r = {}
            if lo: r["$gte"] = lo
            if hi: r["$lte"] = hi
            conds.append({field: r})
    # Per-duration price ranges (coins): 1h -> vip.prices.hour, 2h -> vip.prices.h2, 3h -> vip.prices.h3
    for field, lo, hi in (("vip.prices.hour", vip_price1h_min, vip_price1h_max),
                          ("vip.prices.h2", vip_price2h_min, vip_price2h_max),
                          ("vip.prices.h3", vip_price3h_min, vip_price3h_max)):
        if lo is not None or hi is not None:
            r = {}
            if lo is not None: r["$gte"] = lo
            if hi is not None: r["$lte"] = hi
            conds.append({field: r})
    # Penis size & girth (cm) ranges — stored as free text, so extract the leading number for comparison.
    def _num_range_cond(path, lo, hi):
        val = {"$let": {"vars": {"m": {"$regexFind": {"input": {"$ifNull": [path, ""]}, "regex": "[0-9]+([.][0-9]+)?"}}},
                        "in": {"$cond": [{"$eq": ["$$m", None]}, None, {"$toDouble": "$$m.match"}]}}}
        checks = [{"$ne": [val, None]}]
        if lo is not None: checks.append({"$gte": [val, lo]})
        if hi is not None: checks.append({"$lte": [val, hi]})
        return {"$expr": {"$and": checks}}
    if vip_min_dick is not None or vip_max_dick is not None:
        conds.append(_num_range_cond("$vip.dick_size", vip_min_dick, vip_max_dick))
    if vip_min_girth is not None or vip_max_girth is not None:
        conds.append(_num_range_cond("$vip.dick_girth", vip_min_girth, vip_max_girth))
    # 🍆 size (cm) range — profile stores a cm number as text; legacy s/m/l/xl codes map to approximate cm
    if min_penis is not None or max_penis is not None:
        _ps = {"$switch": {"branches": [
            {"case": {"$eq": ["$penis_size", "s"]}, "then": "12"}, {"case": {"$eq": ["$penis_size", "m"]}, "then": "14.5"},
            {"case": {"$eq": ["$penis_size", "l"]}, "then": "17.5"}, {"case": {"$eq": ["$penis_size", "xl"]}, "then": "20"}],
            "default": {"$toString": {"$ifNull": ["$penis_size", ""]}}}}
        conds.append(_num_range_cond(_ps, min_penis, max_penis))
    # Income ($/month) range — profile stores a free-text amount in income_custom
    if min_income is not None or max_income is not None:
        conds.append(_num_range_cond({"$replaceAll": {"input": {"$toString": {"$ifNull": ["$income_custom", ""]}}, "find": ",", "replacement": ""}}, min_income, max_income))
    proj = {"_id": 0, "password": 0, "email": 0, "referred_by": 0, "referral_code": 0}
    _not_premium = [{"$or": [{"premium_until": None}, {"premium_until": {"$lte": now_iso}}, {"premium_until": {"$exists": False}}]}]
    _not_lite = [{"$or": [{"premium_lite_until": None}, {"premium_lite_until": {"$lte": now_iso}}, {"premium_lite_until": {"$exists": False}}]}]
    # Top placement: Premium + VIP (both carry premium_until). Then Premium-lite placement. Then everyone else.
    # Pagination: page size depends on the viewer's tier (server-enforced). Free 2 · Premium-Lite 4 · Premium 8 · VIP 12.
    page_size = 12 if is_vip(user) else 8 if is_premium(user) else 4 if is_premium_lite(user) else 2
    page = max(int(page or 1), 1)
    limit = 1000  # candidate pool; ordered (top -> lite -> rest) then sliced per page below
    top = await db.users.find({"$and": conds + [{"premium_until": {"$gt": now_iso}}]}, proj).sort("id", 1).limit(limit).to_list(limit)
    lite_limit = max(limit - len(top), 0)
    lite = await db.users.find({"$and": conds + [{"premium_lite_until": {"$gt": now_iso}}] + _not_premium}, proj).sort("id", 1).limit(lite_limit).to_list(lite_limit) if lite_limit else []
    rest_limit = max(limit - len(top) - len(lite), 0)
    rest = await db.users.find({"$and": conds + _not_premium + _not_lite}, proj).sort("id", 1).limit(rest_limit).to_list(rest_limit) if rest_limit else []
    for p in top: p["is_premium"] = True; p["is_vip"] = is_vip(p); p["is_premium_lite"] = False
    for p in lite: p["is_premium"] = False; p["is_vip"] = is_vip(p); p["is_premium_lite"] = True
    for p in rest: p["is_premium"] = False; p["is_vip"] = is_vip(p); p["is_premium_lite"] = False
    results = top + lite + rest
    if vip_filter:
        # In the VIP section, listings posted "separately" appear as their own anonymous card
        results = [_vip_listing_card(p) for p in results]
    else:
        # On the main feed, hide the VIP status of members who turned "Show VIP on my main profile" off (VIP viewers still see it)
        for p in results:
            v = p.get("vip") or {}
            if not is_vip(user) and not v.get("show_on_main", True) and p.get("is_vip"):
                p["is_vip"] = False; p["is_premium"] = True
    # Distance from the viewer (or a Travel-mode origin) to each profile (km). Exact coords are never exposed.
    if origin_lat is not None and origin_lng is not None:
        vlat, vlng = origin_lat, origin_lng
    else:
        vlat, vlng = approx_coords(user)
    for p in results:
        d = visible_distance(vlat, vlng, p)
        if d is not None:
            p["distance_km"] = d
        p.pop("lat", None)
        p.pop("lng", None)
        p.pop("hide_distance", None)
    # Radius filter: only keep profiles within max_distance km (requires origin + target coords).
    # Online-nearby applies a sensible default radius when the member hasn't picked one.
    eff_max = max_distance or (100 if online_nearby else None)
    if eff_max and vlat is not None and vlng is not None:
        results = [p for p in results if p.get("distance_km") is not None and p["distance_km"] <= eff_max]
    # Nearby sort: closest first (profiles without a distance go last)
    if (sort == "nearby" or online_nearby) and vlat is not None and vlng is not None:
        results.sort(key=lambda p: p.get("distance_km") if p.get("distance_km") is not None else float("inf"))
    # Date coins sort (members without their own amount count as the platform minimum).
    # Stable sort keeps Premium/VIP placement order among equal amounts.
    if sort in ("coins_asc", "coins_desc"):
        dmin = (await get_settings())["date_min_coins"]
        results.sort(key=lambda p: int(p.get("date_price") or dmin), reverse=(sort == "coins_desc"))
    # Video call coins/min sort (effective rate = max(own rate, platform rate)); video calls turned off always go last.
    if sort in ("video_asc", "video_desc"):
        vmin = (await get_settings())["video_rate"]
        on = [p for p in results if p.get("video_calls_enabled") is not False]
        off = [p for p in results if p.get("video_calls_enabled") is False]
        on.sort(key=lambda p: max(int(p.get("video_rate") or 0), vmin), reverse=(sort == "video_desc"))
        results = on + off
    total = len(results)
    start = (page - 1) * page_size
    # Totals are intentionally not exposed — only whether a next page exists.
    return {"items": results[start:start + page_size], "page": page, "page_size": page_size,
            "has_more": start + page_size < total}

# ---------- Saved searches (Premium / VIP) ----------
SAVED_SEARCH_LIMIT = 20

class SavedSearchReq(BaseModel):
    name: str
    filters: dict

def _require_full_premium(user: dict):
    if not (is_premium(user) or is_vip(user)): raise HTTPException(403, "PREMIUM_REQUIRED")

@api.get("/saved-searches")
async def list_saved_searches(user=Depends(get_current_user)):
    _require_full_premium(user)
    return await db.saved_searches.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).sort("created_at", -1).to_list(SAVED_SEARCH_LIMIT)

@api.post("/saved-searches")
async def create_saved_search(req: SavedSearchReq, user=Depends(get_current_user)):
    _require_full_premium(user)
    name = (req.name or "").strip()[:40]
    if not name: raise HTTPException(400, "NAME_REQUIRED")
    if await db.saved_searches.count_documents({"user_id": user["id"]}) >= SAVED_SEARCH_LIMIT:
        raise HTTPException(400, f"SAVED_SEARCH_LIMIT:{SAVED_SEARCH_LIMIT}")
    # Keep only simple JSON values (str/num/bool/list of str) — no nested objects
    clean = {k: v for k, v in (req.filters or {}).items()
             if isinstance(k, str) and len(k) <= 40 and (isinstance(v, (str, int, float, bool)) or (isinstance(v, list) and all(isinstance(x, str) for x in v)))}
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "name": name, "filters": clean, "created_at": datetime.now(timezone.utc).isoformat()}
    await db.saved_searches.insert_one(doc)
    doc.pop("_id", None); doc.pop("user_id", None)
    return doc

@api.delete("/saved-searches/{sid}")
async def delete_saved_search(sid: str, user=Depends(get_current_user)):
    _require_full_premium(user)
    r = await db.saved_searches.delete_one({"id": sid, "user_id": user["id"]})
    if not r.deleted_count: raise HTTPException(404, "NOT_FOUND")
    return {"ok": True}

def _vip_listing_card(p: dict) -> dict:
    """Build a browse card for a VIP listing. Separate listings are fully anonymised
    (own nickname/photos/age/city) so they can't be linked to the owner's main profile."""
    v = p.get("vip") or {}
    if v.get("post_mode") != "separate":
        return p
    return {
        "id": v.get("public_id") or p.get("id"),
        "name": (v.get("nickname") or "").strip() or "VIP",
        "age": v.get("age") or p.get("age"),
        "city": v.get("city") or p.get("city"),
        "country": v.get("country") or p.get("country"),
        "gender": v.get("gender") or p.get("gender"),
        "bio": v.get("bio") or "",
        "photos": v.get("photos") or [],
        "height": v.get("height"), "weight": v.get("weight"),
        "eye_color": v.get("eye_color") or "", "hair_color": v.get("hair_color") or "",
        "intimate_haircut": v.get("intimate_haircut") or "", "breast_size": v.get("breast_size") or "",
        "dick_size": v.get("dick_size") or "", "dick_girth": v.get("dick_girth") or "",
        "is_vip": True, "is_premium": bool(p.get("is_premium")), "is_premium_lite": bool(p.get("is_premium_lite")),
        "vip_listing": True, "verified": False, "last_seen": None,
    }

@api.get("/profiles/{pid}")
async def profile_detail(pid: str, user=Depends(get_current_user)):
    p = await db.users.find_one({"id": pid}, {"_id": 0, "password": 0, "email": 0, "referred_by": 0, "referral_code": 0})
    if not p:
        # Might be a standalone (separate) VIP listing referenced by its public id
        owner = await db.users.find_one({"vip.public_id": pid}, {"_id": 0, "id": 1, "age": 1, "city": 1, "country": 1, "gender": 1, "vip": 1})
        v = (owner or {}).get("vip") or {}
        if owner and v.get("post_mode") == "separate" and v.get("published") is not False:
            return {
                "id": v.get("public_id"), "name": (v.get("nickname") or "").strip() or "VIP",
                "age": v.get("age") or owner.get("age"), "city": v.get("city") or owner.get("city"),
                "country": v.get("country") or owner.get("country"), "gender": v.get("gender") or owner.get("gender"),
                "genders": v.get("genders") or ([v.get("gender")] if v.get("gender") else ([owner.get("gender")] if owner.get("gender") else [])),
                "bio": v.get("bio") or "", "photos": v.get("photos") or [],
                "is_vip": True, "is_premium": False, "vip_listing": True,
                "liked_by_me": False, "conversation_id": None,
                "gifts_total": 0, "gifts_count": 0, "top_givers": [],
            }
        raise HTTPException(404, "Not found")
    # Hide profiles that are on a break or scheduled for deletion from everyone except the owner.
    if p.get("account_status") in ("PAUSED", "PENDING_DELETION") and pid != user["id"]:
        raise HTTPException(404, "Not found")
    p["is_premium"] = is_premium(p)
    p["is_vip"] = is_vip(p)
    p["is_premium_lite"] = is_premium_lite(p)
    # Hide the VIP status on the main profile when "Show VIP on my main profile" is off
    _v = p.get("vip") or {}
    if pid != user["id"] and not is_vip(user) and not _v.get("show_on_main", True) and p["is_vip"]:
        p["is_vip"] = False; p["is_premium"] = True
    p["liked_by_me"] = bool(await db.likes.find_one({"from_id": user["id"], "to_id": pid}))
    m = await db.matches.find_one({"users": {"$all": [user["id"], pid]}})
    p["conversation_id"] = m["id"] if m else None
    agg = await db.transactions.aggregate([{"$match": {"to_id": pid, "type": "gift"}}, {"$group": {"_id": "$from_id", "total": {"$sum": "$cost"}, "count": {"$sum": 1}}}, {"$sort": {"total": -1}}]).to_list(1000)
    p["gifts_total"] = sum(a["total"] for a in agg)
    p["gifts_count"] = sum(a["count"] for a in agg)
    top = []
    for a in agg[:3]:
        g = await db.users.find_one({"id": a["_id"]}, {"_id": 0, "id": 1, "name": 1, "photos": 1})
        if g: top.append({"id": g["id"], "name": g["name"], "photo": (g.get("photos") or [None])[0], "total": a["total"], "count": a["count"]})
    p["top_givers"] = top
    _vlat, _vlng = approx_coords(user)
    d = visible_distance(_vlat, _vlng, p)
    if d is not None:
        p["distance_km"] = d
    # Approximate location for a map preview: rounded to ~1 decimal (~11 km grid) to protect privacy
    if not p.get("hide_distance") and p.get("lat") is not None and p.get("lng") is not None:
        p["approx_lat"] = round(float(p["lat"]), 1)
        p["approx_lng"] = round(float(p["lng"]), 1)
    p.pop("lat", None)
    p.pop("lng", None)
    p.pop("hide_distance", None)
    return p

# ---------- Likes / Matches ----------
@api.post("/likes")
async def like(req: LikeReq, user=Depends(get_current_user)):
    if req.target_id == user["id"]: raise HTTPException(400, "Cannot like yourself")
    now = datetime.now(timezone.utc).isoformat()
    already = await db.likes.find_one({"from_id": user["id"], "to_id": req.target_id})
    if not already and not has_premium(user):
        limit = (await get_settings())["free_daily_likes"]
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        used = await db.likes.count_documents({"from_id": user["id"], "created_at": {"$gte": day_start}})
        if used >= limit: raise HTTPException(429, f"LIKE_LIMIT:{limit}")
    try:
        await db.likes.insert_one({"from_id": user["id"], "to_id": req.target_id, "created_at": now})
    except Exception:
        pass
    reverse = await db.likes.find_one({"from_id": req.target_id, "to_id": user["id"]})
    matched = False
    if reverse:
        matched = True
        conv_id, created = await ensure_match(user["id"], req.target_id)
        if created:
            other = await db.users.find_one({"id": req.target_id}, {"name": 1})
            await notify(req.target_id, "match", "It's a match! 💘", f"You and {user['name']} liked each other. Say hello!", {"conversation_id": conv_id, "user_id": user["id"], "name": user["name"]}, email=True)
            await notify(user["id"], "match", "It's a match! 💘", f"You and {other['name']} liked each other. Say hello!", {"conversation_id": conv_id, "user_id": req.target_id, "name": other["name"]}, email=True)
    elif not already:
        await notify(req.target_id, "like", "Someone likes you ❤️", f"{user['name']} liked your profile. Like back to match!", {"user_id": user["id"], "name": user["name"]}, email=True)
    return {"liked": True, "matched": matched}

@api.get("/likes/received")
async def likes_received(user=Depends(get_current_user)):
    likes = await db.likes.find({"to_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    matched = {u for m in await db.matches.find({"users": user["id"]}, {"_id": 0, "users": 1}).to_list(500) for u in m["users"]}
    premium = has_premium(user)
    items = []
    for lk in likes:
        if lk["from_id"] in matched: continue
        u = await db.users.find_one({"id": lk["from_id"]}, {"_id": 0, "id": 1, "name": 1, "age": 1, "city": 1, "country": 1, "photos": 1})
        if not u: continue
        if premium: items.append({**u, "liked_at": lk["created_at"]})
        else: items.append({"id": u["id"], "photos": u.get("photos", [])[:1], "liked_at": lk["created_at"]})
    return {"premium": premium, "count": len(items), "items": items}

@api.get("/likes/quota")
async def likes_quota(user=Depends(get_current_user)):
    limit = (await get_settings())["free_daily_likes"]
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    used = await db.likes.count_documents({"from_id": user["id"], "created_at": {"$gte": day_start}})
    prem = has_premium(user)
    return {"premium": prem, "limit": None if prem else limit, "used": used, "remaining": None if prem else max(limit - used, 0)}

# ---------- Notifications ----------
@api.get("/notifications")
async def list_notifications(unread_only: bool = False, user=Depends(get_current_user)):
    q = {"user_id": user["id"]}
    if unread_only: q["read"] = False
    items = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)
    unread = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"items": items, "unread": unread}

@api.post("/notifications/read")
async def read_notifications(user=Depends(get_current_user)):
    await db.notifications.update_many({"user_id": user["id"], "read": False}, {"$set": {"read": True}})
    return {"ok": True}

# ---------- Referrals ----------
@api.get("/referrals")
async def referrals(user=Depends(get_current_user)):
    invited = await db.users.find({"referred_by": user["id"]}, {"_id": 0, "name": 1, "created_at": 1, "referral_rewarded": 1}).to_list(200)
    earned = await db.transactions.find({"to_id": user["id"], "type": "referral_bonus"}, {"_id": 0}).to_list(500)
    s = await get_settings()
    pkg = next((p for p in s["coin_packages"] if p["id"] == s.get("referral_package_id")), None)
    return {"code": user["referral_code"], "bonus": s["referral_bonus"], "package": pkg, "invited": invited,
            "earned": sum(t["cost"] for t in earned), "rewarded_count": len(earned)}

async def _reward_referrer(buyer_id: str):
    buyer = await db.users.find_one({"id": buyer_id})
    if not buyer or not buyer.get("referred_by") or buyer.get("referral_rewarded"): return
    res = await db.users.update_one({"id": buyer_id, "referral_rewarded": {"$ne": True}}, {"$set": {"referral_rewarded": True}})
    if res.modified_count == 0: return
    bonus = (await get_settings())["referral_bonus"]
    await db.users.update_one({"id": buyer["referred_by"]}, {"$inc": {"coins": bonus}})
    await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "referral_bonus", "from_id": buyer_id, "to_id": buyer["referred_by"],
                                      "cost": bonus, "net": bonus, "created_at": datetime.now(timezone.utc).isoformat()})
    await notify(buyer["referred_by"], "referral", f"+{bonus} 🪙 referral bonus", f"{buyer['name']} bought their first pack. Thanks for inviting!", {"user_id": buyer_id})

@api.get("/matches")
async def my_matches(user=Depends(get_current_user)):
    matches = await db.matches.find({"users": user["id"]}, {"_id": 0}).to_list(200)
    result = []
    for m in matches:
        other_id = [u for u in m["users"] if u != user["id"]][0]
        other = await db.users.find_one({"id": other_id}, {"_id": 0, "password": 0, "email": 0})
        if other:
            _vlat, _vlng = approx_coords(user)
            d = visible_distance(_vlat, _vlng, other)
            if d is not None:
                other["distance_km"] = d
            other.pop("lat", None)
            other.pop("lng", None)
            other.pop("hide_distance", None)
            result.append({"conversation_id": m["id"], "user": other, "created_at": m["created_at"], "can_share_media": await have_met(user["id"], other_id)})
    return result

@api.post("/conversations/{cid}/photo")
async def send_chat_photo(cid: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    conv = await db.conversations.find_one({"id": cid})
    if not conv or user["id"] not in conv["users"]: raise HTTPException(403, "No access")
    other_id = [u for u in conv["users"] if u != user["id"]][0]
    if not await have_met(user["id"], other_id): raise HTTPException(403, "MEDIA_LOCKED")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400, "Only images allowed")
    ext = (file.filename.split(".")[-1] if "." in file.filename else "jpg").lower()
    path = f"{APP_NAME}/chat/{cid}/{uuid.uuid4()}.{ext}"
    result = put_object(path, await file.read(), file.content_type)
    now = datetime.now(timezone.utc).isoformat()
    await db.files.insert_one({"id": str(uuid.uuid4()), "storage_path": result["path"], "user_id": user["id"], "viewers": conv["users"], "private": True,
                               "content_type": file.content_type, "size": result["size"], "is_deleted": False, "created_at": now})
    msg = {"id": str(uuid.uuid4()), "conversation_id": cid, "from_id": user["id"], "text": "", "type": "image", "image_path": result["path"], "created_at": now}
    await db.messages.insert_one(dict(msg))
    await db.conversations.update_one({"id": cid}, {"$set": {"last_message": "📷", "last_at": now}})
    return msg

# ---------- Chat auto-translate (Gemini via Emergent LLM key) ----------
class TranslateReq(BaseModel):
    lang: str

_translate_locks: dict = {}

async def _llm_translate_batch(items: List[dict], lang_name: str) -> dict:
    """items: [{id, text}] -> {id: translated_text}. Unchanged text is returned when already in the target language."""
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key or not items: return {}
    import json as _json
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    sys_msg = (f"You are a translation engine for a dating app chat. Translate each message into {lang_name}. "
               "Keep the tone, emojis, names and line breaks. Do not add explanations. "
               "If a message is already in the target language, return it unchanged. "
               "Reply ONLY with a JSON object mapping each id to its translation.")
    chat = LlmChat(api_key=key, session_id=f"tr-{uuid.uuid4()}", system_message=sys_msg).with_model("gemini", "gemini-3-flash-preview")
    payload = _json.dumps({it["id"]: it["text"] for it in items}, ensure_ascii=False)
    raw = (await chat.send_message(UserMessage(text=payload)) or "").strip()
    try:
        data = _json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        logging.error(f"translate parse error: {raw[:200]}")
        return {}
    return {k: str(v) for k, v in data.items() if isinstance(k, str) and v is not None}

@api.post("/conversations/{cid}/translate")
async def translate_conversation(cid: str, req: TranslateReq, user=Depends(get_current_user)):
    """Translate the partner's text messages in this conversation into `lang`. Results are cached per message."""
    conv = await db.conversations.find_one({"id": cid})
    if not conv or user["id"] not in conv["users"]: raise HTTPException(403, "No access")
    code = (req.lang or "en").lower()[:10]
    if not re.fullmatch(r"[a-z]{2,3}(-[a-z0-9]{2,4})?", code): raise HTTPException(400, "BAD_LANG")
    lang_name = LANG_NAMES.get(code) or f"the language with ISO 639 code '{code}'"
    field = f"translations.{code}"
    q = {"conversation_id": cid, "from_id": {"$ne": user["id"]}, "type": {"$in": ["text", "gift"]}, "text": {"$nin": ["", None]}}
    lock = _translate_locks.setdefault(f"{cid}:{code}", asyncio.Lock())
    async with lock:
        pending = await db.messages.find({**q, field: {"$exists": False}}, {"_id": 0, "id": 1, "text": 1}).sort("created_at", -1).to_list(40)
        if pending:
            try:
                out = await _llm_translate_batch([{"id": m["id"], "text": m["text"][:2000]} for m in pending], lang_name)
            except Exception as e:
                logging.error(f"translate error: {e}")
                raise HTTPException(503, "TRANSLATE_UNAVAILABLE")
            for m in pending:
                if m["id"] in out:
                    await db.messages.update_one({"id": m["id"]}, {"$set": {field: out[m["id"]]}})
    done = await db.messages.find({**q, field: {"$exists": True}}, {"_id": 0, "id": 1, "text": 1, "translations": 1}).to_list(500)
    # Only return real translations (skip messages already in the reader's language)
    return {m["id"]: m["translations"][code] for m in done
            if (m.get("translations") or {}).get(code) and m["translations"][code].strip() != (m.get("text") or "").strip()}

# ---------- Site-wide UI auto-translation (any world language, cached in Mongo) ----------
import hashlib as _hashlib

class UiTranslateReq(BaseModel):
    lang: str
    texts: List[str]

_UI_SYS = ("You are a professional localization engine for GiftsDates, a luxury international dating website. "
           "Translate each UI string (buttons, menus, dropdown options, labels, headings, notices, paragraphs) into {lang}. "
           "Rules: keep it natural and concise like real app UI; preserve placeholders such as {{o}}, {{n}}, {{name}}, numbers, "
           "currency symbols, emojis, punctuation, URLs and e-mail addresses exactly; keep the brand 'GiftsDates' and people's names untranslated; "
           "if a string is already in {lang} or is a proper name/code, return it unchanged. "
           "Reply ONLY with a JSON object mapping each id to its translation, no commentary.")

_ui_llm_sem = asyncio.Semaphore(1)  # LLM key allows one concurrent request — serialize calls

async def _ui_llm_chunk(chunk: List[tuple], lang_name: str) -> dict:
    import json as _json
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key: return {}
    payload = _json.dumps({str(i): t for i, t in chunk}, ensure_ascii=False)
    for attempt in range(5):
        try:
            async with _ui_llm_sem:
                chat = LlmChat(api_key=key, session_id=f"ui-{uuid.uuid4()}", system_message=_UI_SYS.format(lang=lang_name)).with_model("gemini", "gemini-3-flash-preview")
                raw = (await chat.send_message(UserMessage(text=payload)) or "").strip()
            data = _json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            return {int(k): str(v) for k, v in data.items() if str(k).isdigit() and v is not None}
        except Exception as e:
            msg = str(e)
            logging.error(f"ui translate error (attempt {attempt + 1}): {msg[:160]}")
            if "429" in msg or "concurrent" in msg.lower() or "rate" in msg.lower():
                await asyncio.sleep(1.5 * (attempt + 1))
            elif attempt >= 1:
                break
    return {}

def _h(t: str) -> str:
    return _hashlib.sha1(t.encode("utf-8")).hexdigest()

def _norm_lang(code: str) -> str:
    code = (code or "en").strip()[:12]
    if not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,4})?", code): raise HTTPException(400, "BAD_LANG")
    return code

def _lang_name(code: str) -> str:
    return LANG_NAMES.get(code) or LANG_NAMES.get(code.split("-")[0]) or f"the language with BCP-47 code '{code}'"

def _chunks_by_budget(items: List[tuple], max_items: int = 60, max_chars: int = 6000):
    out, cur, size = [], [], 0
    for it in items:
        if cur and (len(cur) >= max_items or size + len(it[1]) > max_chars):
            out.append(cur); cur, size = [], 0
        cur.append(it); size += len(it[1])
    if cur: out.append(cur)
    return out

async def localize_texts(texts: List[str], code: str, ui: bool = True) -> List[str]:
    """Translate English strings into `code` using the shared cache, calling the AI only for misses."""
    if not texts or code.lower() == "en": return list(texts)
    hashes = [_h(t) for t in texts]
    found = {}
    async for d in db.ui_translations.find({"lang": code, "h": {"$in": list(set(hashes))}}, {"_id": 0, "h": 1, "out": 1}):
        found[d["h"]] = d["out"]
    missing, seen = [], set()
    for i, (t, h) in enumerate(zip(texts, hashes)):
        if h not in found and h not in seen and t.strip():
            seen.add(h); missing.append((i, t))
    if missing:
        lang_name = _lang_name(code)
        now = datetime.now(timezone.utc).isoformat()
        for chunk in _chunks_by_budget(missing):
            res = await _ui_llm_chunk(chunk, lang_name)
            for i, t in chunk:
                out = res.get(i)
                if not out: continue
                found[hashes[i]] = out
                try:
                    await db.ui_translations.update_one({"lang": code, "h": hashes[i]},
                        {"$set": {"lang": code, "h": hashes[i], "src": t, "out": out, "ui": ui, "at": now}}, upsert=True)
                except Exception:
                    pass
    return [found.get(h, t) for t, h in zip(texts, hashes)]

async def _register_sources(texts: List[str]):
    now = datetime.now(timezone.utc).isoformat()
    for t in set(texts):
        t = t.strip()
        if 2 <= len(t) <= 400:
            try:
                await db.ui_sources.update_one({"h": _h(t)}, {"$setOnInsert": {"h": _h(t), "src": t, "at": now}, "$inc": {"seen": 1}}, upsert=True)
            except Exception:
                pass

@api.post("/i18n/translate")
async def ui_translate(req: UiTranslateReq):
    """Translate UI strings into any world language. Shared cache, so each string is only translated once per language."""
    code = _norm_lang(req.lang)
    texts = [str(t)[:800] for t in (req.texts or [])][:150]
    if code.lower() == "en" or not texts: return {"translations": texts}
    out = await localize_texts(texts, code, ui=True)
    asyncio.create_task(_register_sources(texts))
    return {"translations": out}

@api.get("/i18n/bundle/{code}")
async def ui_bundle(code: str):
    """All pre-translated UI strings for a language — lets the site open instantly in that language."""
    code = _norm_lang(code)
    if code.lower() == "en": return {"lang": code, "count": 0, "translations": {}}
    tr = {}
    async for d in db.ui_translations.find({"lang": code, "ui": {"$ne": False}}, {"_id": 0, "src": 1, "out": 1}):
        if d.get("src") and d.get("out"): tr[d["src"]] = d["out"]
    return {"lang": code, "count": len(tr), "translations": tr}

# ---------- Admin: pre-translate the whole site for the main markets ----------
PRETRANSLATE_LANGS = ["es", "fr", "de", "pt", "ru", "zh", "ar", "hi", "ja", "ko", "it", "tr", "uk", "pl"]
_UI_STRINGS_CACHE: dict = {}

def _ui_strings() -> dict:
    if not _UI_STRINGS_CACHE:
        import json as _json
        try:
            _UI_STRINGS_CACHE.update(_json.loads((ROOT_DIR / "ui_strings.json").read_text(encoding="utf-8")))
        except Exception as e:
            logging.error(f"ui_strings.json missing: {e}")
            _UI_STRINGS_CACHE.update({"dictionary": {}, "static": []})
    return _UI_STRINGS_CACHE

async def _all_sources() -> List[str]:
    us = _ui_strings()
    src = {v["en"].strip() for v in us["dictionary"].values() if v.get("en", "").strip()}
    src |= {s.strip() for s in us["static"] if s.strip()}
    async for d in db.ui_sources.find({}, {"_id": 0, "src": 1}).sort("seen", -1).limit(5000):
        src.add(d["src"])
    return sorted(src)

_pt_job: dict = {"running": False}
_pt_task_ref: dict = {}

async def _run_pretranslate(langs: List[str]):
    job = _pt_job
    try:
        sources = await _all_sources()
        dictionary = _ui_strings()["dictionary"]
        now = datetime.now(timezone.utc).isoformat()
        for code in langs:
            if job.get("cancel"): break
            st = job["langs"][code]
            st["status"] = "seeding"; job["current"] = code
            # 1) seed curated / generated translations already shipped with the app (no AI cost)
            seeded = 0
            for v in dictionary.values():
                en, tr = (v.get("en") or "").strip(), (v.get(code) or "").strip()
                if en and tr:
                    try:
                        r = await db.ui_translations.update_one({"lang": code, "h": _h(en)},
                            {"$setOnInsert": {"lang": code, "h": _h(en), "src": en, "out": tr, "ui": True, "origin": "curated", "at": now}}, upsert=True)
                        seeded += 1 if r.upserted_id else 0
                    except Exception:
                        pass
            st["seeded"] = seeded
            # 2) AI-translate everything still missing
            have = set()
            async for d in db.ui_translations.find({"lang": code}, {"_id": 0, "h": 1}): have.add(d["h"])
            todo = [s for s in sources if _h(s) not in have]
            st.update({"total": len(sources), "done": len(sources) - len(todo), "status": "translating"})
            for chunk in _chunks_by_budget(list(enumerate(todo))):
                if job.get("cancel"): break
                texts = [t for _, t in chunk]
                before = len(texts)
                await localize_texts(texts, code, ui=True)
                ok = await db.ui_translations.count_documents({"lang": code, "h": {"$in": [_h(t) for t in texts]}})
                st["done"] += ok; st["failed"] = st.get("failed", 0) + (before - ok)
            st["status"] = "cancelled" if job.get("cancel") else "done"
        job["finished_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        logging.exception("pretranslate failed")
        job["error"] = str(e)[:300]
    finally:
        job["running"] = False; job["current"] = None
        try:
            await db.i18n_jobs.replace_one({"id": "pretranslate"}, {"id": "pretranslate", **{k: v for k, v in job.items() if k != "cancel"}}, upsert=True)
        except Exception:
            pass

class PretranslateReq(BaseModel):
    langs: Optional[List[str]] = None

@api.post("/admin/i18n/pretranslate")
async def admin_pretranslate(req: PretranslateReq, admin=Depends(get_admin)):
    if _pt_job.get("running"): raise HTTPException(409, "ALREADY_RUNNING")
    langs = [_norm_lang(c) for c in (req.langs or PRETRANSLATE_LANGS) if c != "en"]
    _pt_job.clear()
    _pt_job.update({"running": True, "cancel": False, "started_at": datetime.now(timezone.utc).isoformat(), "finished_at": None,
                    "error": None, "current": None, "order": langs,
                    "langs": {c: {"code": c, "name": _lang_name(c), "status": "queued", "total": 0, "done": 0, "seeded": 0, "failed": 0} for c in langs}})
    _pt_task_ref["t"] = asyncio.create_task(_run_pretranslate(langs))
    return {"ok": True, "langs": langs}

@api.post("/admin/i18n/cancel")
async def admin_pretranslate_cancel(admin=Depends(get_admin)):
    if _pt_job.get("running"): _pt_job["cancel"] = True
    return {"ok": True}

class NotifPreviewReq(BaseModel):
    lang: str
    title: str = "It's a match! 💘"
    body: str = "You and Anna liked each other. Say hello!"
    cta: str = "View on GiftsDates"
    link: Optional[str] = "https://giftsdates.com/chats"

@api.post("/admin/i18n/preview-notification")
async def admin_preview_notification(req: NotifPreviewReq, admin=Depends(get_admin)):
    """Preview exactly what a user with language `lang` receives by email and SMS."""
    code = _norm_lang(req.lang)
    loc = await localize_message(code, req.title, req.body, req.cta)
    html = _email_cta_html(loc["title"], loc["body"], req.link, loc["cta"] or req.cta, loc["footer"], loc["rtl"]) if req.link \
        else _email_html(loc["title"], loc["body"], loc["footer"], loc["rtl"])
    sms = f"{loc['title']} — {loc['body']}" + (f" {req.link}" if req.link else "")
    return {"lang": code, "subject": f"{loc['title']} · GiftsDates", "html": html, "sms": sms[:600], "rtl": loc["rtl"],
            "email_configured": bool(EMAIL_KEY), "sms_configured": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM)}

@api.get("/admin/i18n/status")
async def admin_pretranslate_status(admin=Depends(get_admin)):
    job = {k: v for k, v in _pt_job.items() if k != "cancel"}
    if not job.get("langs"):
        last = await db.i18n_jobs.find_one({"id": "pretranslate"}, {"_id": 0})
        if last: job = {**last, "running": False}
    sources = await _all_sources()
    coverage = []
    for c in PRETRANSLATE_LANGS:
        n = await db.ui_translations.count_documents({"lang": c, "ui": {"$ne": False}})
        coverage.append({"code": c, "name": _lang_name(c), "cached": n})
    return {"job": job, "total_sources": len(sources), "default_langs": PRETRANSLATE_LANGS, "coverage": coverage}

# ---------- Chat ----------
@api.get("/conversations/{cid}/messages")
async def get_messages(cid: str, user=Depends(get_current_user)):
    conv = await db.conversations.find_one({"id": cid})
    if not conv or user["id"] not in conv["users"]: raise HTTPException(403, "No access")
    msgs = await db.messages.find({"conversation_id": cid}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return msgs

@api.post("/conversations/messages")
async def send_message(req: MessageReq, user=Depends(get_current_user)):
    conv = await db.conversations.find_one({"id": req.conversation_id})
    if not conv or user["id"] not in conv["users"]: raise HTTPException(403, "No access")
    now = datetime.now(timezone.utc).isoformat()
    if contains_phone(req.text):
        other_id = [u for u in conv["users"] if u != user["id"]][0]
        met = await db.date_bookings.find_one({"status": {"$in": ["confirmed", "released"]}, "$or": [
            {"from_id": user["id"], "to_id": other_id}, {"from_id": other_id, "to_id": user["id"]}]})
        if not met:
            violations = (user.get("violations") or 0) + 1
            upd = {"$set": {"violations": violations}}
            blocked = violations >= MAX_VIOLATIONS
            if blocked:
                until = (datetime.now(timezone.utc) + timedelta(days=BLOCK_DAYS)).isoformat()
                upd["$set"]["blocked_until"] = until
                upd["$set"]["violations"] = 0
            await db.users.update_one({"id": user["id"]}, upd)
            await db.moderation_log.insert_one({"id": str(uuid.uuid4()), "user_id": user["id"], "conversation_id": req.conversation_id,
                                                "text": req.text, "violation_no": violations, "blocked": blocked, "created_at": now})
            if blocked:
                await notify(user["id"], "blocked", "Account blocked 🚫", f"Repeated attempts to share a phone number before a date. Blocked for {BLOCK_DAYS} days.", {"until": until}, email=True)
                raise HTTPException(403, f"BLOCKED:{until}")
            await notify(user["id"], "warning", "Warning ⚠️", f"Sharing phone numbers before a confirmed date is not allowed. Warning {violations}/{MAX_VIOLATIONS} — next violations lead to a block.", {"violations": violations})
            raise HTTPException(400, f"PHONE_BLOCKED:{violations}:{MAX_VIOLATIONS}")
    msg = {"id": str(uuid.uuid4()), "conversation_id": req.conversation_id, "from_id": user["id"], "text": req.text, "created_at": now, "type": "text"}
    await db.messages.insert_one(dict(msg))
    await db.conversations.update_one({"id": req.conversation_id}, {"$set": {"last_message": req.text, "last_at": now}})
    other_id = [u for u in conv["users"] if u != user["id"]][0]
    preview = (req.text[:60] + "…") if len(req.text) > 60 else req.text
    await notify(other_id, "message", f"New message from {user['name']} 💬", preview, {"conversation_id": req.conversation_id, "user_id": user["id"], "name": user["name"]}, email=True)
    return msg

# ---------- Gifts ----------
async def _find_gift(gid):
    return next((g for g in (await get_settings())["gifts"] if g["id"] == gid), None)

@api.post("/gifts/send")
async def send_gift(req: GiftReq, user=Depends(get_current_user)):
    if req.gift_id == "custom":
        icon = (req.custom_icon or "🎁").strip()[:4] or "🎁"
        if not req.custom_cost or req.custom_cost < CUSTOM_GIFT_MIN: raise HTTPException(400, f"Minimum {CUSTOM_GIFT_MIN} coins")
        gift = {"id": "custom", "name_key": "gift_custom", "icon": icon, "cost": int(req.custom_cost)}
    else:
        gift = await _find_gift(req.gift_id)
    if not gift: raise HTTPException(400, "Unknown gift")
    if (user.get("coins", 0) + user.get("withdrawable", 0)) < gift["cost"]: raise HTTPException(400, "Insufficient coins")
    target = await db.users.find_one({"id": req.target_id})
    if not target: raise HTTPException(404, "Recipient not found")
    # full value credited to recipient; 30% commission is withheld at withdrawal time
    net = gift["cost"]
    commission = round(gift["cost"] * (await get_settings())["commission"], 2)
    now = datetime.now(timezone.utc).isoformat()
    await spend_coins(user["id"], gift["cost"])
    await db.users.update_one({"id": req.target_id}, {"$inc": {"withdrawable": net}})
    tx = {"id": str(uuid.uuid4()), "type": "gift", "from_id": user["id"], "to_id": req.target_id,
          "gift_id": gift["id"], "gift_icon": gift["icon"], "cost": gift["cost"],
          "commission": commission, "net": net, "message": req.message, "created_at": now}
    await db.transactions.insert_one(tx)
    s = await get_settings()
    conv_id = req.conversation_id
    auto_matched = False
    if gift["cost"] >= s.get("gift_auto_match_coins", 100):
        conv_id, auto_matched = await ensure_match(user["id"], req.target_id, reason="gift")
    if not conv_id:
        m = await db.matches.find_one({"users": {"$all": [user["id"], req.target_id]}})
        conv_id = m["id"] if m else None
    if conv_id:
        conv = await db.conversations.find_one({"id": conv_id})
        if conv and user["id"] in conv.get("users", []) and req.target_id in conv.get("users", []):
            label = f"{gift['icon']} 🪙 {gift['cost']}"
            await db.messages.insert_one({"id": str(uuid.uuid4()), "conversation_id": conv_id, "from_id": user["id"],
                                          "text": (req.message or "").strip(), "type": "gift", "gift_icon": gift["icon"], "gift_cost": gift["cost"], "tx_id": tx["id"], "created_at": now})
            await db.conversations.update_one({"id": conv_id}, {"$set": {"last_message": label, "last_at": now}})
    await notify(req.target_id, "gift", f"{gift['icon']} Gift from {user['name']}",
                 f"{user['name']} sent you {gift['icon']} worth {gift['cost']} coins" + (f": “{req.message.strip()}”" if (req.message or "").strip() else ""),
                 {"from_id": user["id"], "name": user["name"], "gift_icon": gift["icon"], "cost": gift["cost"], "conversation_id": conv_id, "auto_matched": auto_matched}, email=True)
    if auto_matched:
        await notify(req.target_id, "match", "It's a match! 💘", f"{user['name']} sent you a gift — you're now matched. Say hello!", {"conversation_id": conv_id, "user_id": user["id"], "name": user["name"]}, email=True)
        await notify(user["id"], "match", "It's a match! 💘", f"Your gift to {target['name']} opened a chat. Say hello!", {"conversation_id": conv_id, "user_id": req.target_id, "name": target["name"]}, email=True)
    return {"ok": True, "commission": commission, "net_to_recipient": net, "conversation_id": conv_id, "auto_matched": auto_matched}

class GiftThanksReq(BaseModel):
    message_id: str
    reaction: Optional[str] = "❤️"

@api.post("/gifts/thanks")
async def gift_thanks(req: GiftThanksReq, user=Depends(get_current_user)):
    m = await db.messages.find_one({"id": req.message_id, "type": "gift"})
    if not m or m["from_id"] == user["id"]: raise HTTPException(404, "Gift message not found")
    conv = await db.conversations.find_one({"id": m["conversation_id"]})
    if not conv or user["id"] not in conv["users"]: raise HTTPException(403, "No access")
    if m.get("thanks"): return {"ok": True, "already": True}
    reaction = (req.reaction or "❤️").strip()[:4] or "❤️"
    now = datetime.now(timezone.utc).isoformat()
    await db.messages.update_one({"id": m["id"]}, {"$set": {"thanks": reaction, "thanks_at": now}})
    await db.messages.insert_one({"id": str(uuid.uuid4()), "conversation_id": m["conversation_id"], "from_id": user["id"], "text": f"Thank you {reaction}", "type": "thanks", "reaction": reaction, "gift_message_id": m["id"], "created_at": now})
    await db.conversations.update_one({"id": m["conversation_id"]}, {"$set": {"last_message": f"Thank you {reaction}", "last_at": now}})
    await notify(m["from_id"], "gift_thanks", f"{user['name']} said thanks {reaction}", f"{user['name']} thanked you for your gift {m.get('gift_icon','')}", {"conversation_id": m["conversation_id"], "user_id": user["id"]})
    return {"ok": True}

@api.get("/gifts/received")
async def gifts_received(user=Depends(get_current_user)):
    return await db.transactions.find({"to_id": user["id"], "type": "gift"}, {"_id": 0}).sort("created_at", -1).to_list(200)

@api.get("/gifts/sent")
async def gifts_sent(user=Depends(get_current_user)):
    return await db.transactions.find({"from_id": user["id"], "type": "gift"}, {"_id": 0}).sort("created_at", -1).to_list(200)

# ---------- Video calls ----------
RING_SECONDS = 30

def _online(u: dict) -> bool:
    ls = u.get("last_seen")
    return bool(ls and ls > (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat())

def _call_out(c: dict) -> dict:
    return {k: c.get(k) for k in ("id", "caller_id", "callee_id", "caller", "callee", "minutes", "rate", "cost", "status", "created_at", "accepted_at", "ended_at", "reason")}

async def _expire_ringing(c: dict) -> dict:
    if c.get("status") == "ringing" and _pdt(c["created_at"]) and (_now() - _pdt(c["created_at"])).total_seconds() > RING_SECONDS:
        await db.calls.update_one({"id": c["id"], "status": "ringing"}, {"$set": {"status": "missed", "ended_at": _iso()}})
        c["status"] = "missed"
    return c

async def _my_call(cid: str, user: dict) -> dict:
    c = await db.calls.find_one({"id": cid}, {"_id": 0})
    if not c or user["id"] not in (c["caller_id"], c["callee_id"]): raise HTTPException(404, "CALL_NOT_FOUND")
    return await _expire_ringing(c)

@api.post("/videocalls/start")
async def start_call(req: VideoCallReq, user=Depends(get_current_user)):
    """Ring the recipient. Nothing is charged until they accept (with their camera allowed)."""
    target = await db.users.find_one({"id": req.target_id})
    if not target: raise HTTPException(404, "Recipient not found")
    if target["id"] == user["id"]: raise HTTPException(400, "CANNOT_CALL_SELF")
    if target.get("video_calls_enabled") is False: raise HTTPException(403, "VIDEO_CALLS_DISABLED")
    if not _online(target): raise HTTPException(403, "USER_OFFLINE")
    minutes = max(1, min(int(req.minutes or 1), 60))
    rate = max(target.get("video_rate") or 0, (await get_settings())["video_rate"])
    cost = minutes * rate
    if (user.get("coins", 0) + user.get("withdrawable", 0)) < cost: raise HTTPException(400, "Insufficient coins")
    # Cancel any older ringing calls from this caller
    await db.calls.update_many({"caller_id": user["id"], "status": "ringing"}, {"$set": {"status": "cancelled", "ended_at": _iso()}})
    c = {"id": str(uuid.uuid4()), "caller_id": user["id"], "callee_id": target["id"],
         "caller": {"id": user["id"], "name": user.get("name"), "photo": (user.get("photos") or [None])[0]},
         "callee": {"id": target["id"], "name": target.get("name"), "photo": (target.get("photos") or [None])[0]},
         "minutes": minutes, "rate": rate, "cost": cost, "status": "ringing", "created_at": _iso()}
    await db.calls.insert_one(dict(c))
    return _call_out(c)

@api.get("/videocalls/incoming")
async def incoming_calls(user=Depends(get_current_user)):
    since = (_now() - timedelta(seconds=RING_SECONDS)).isoformat()
    docs = await db.calls.find({"callee_id": user["id"], "status": "ringing", "created_at": {"$gt": since}}, {"_id": 0}).sort("created_at", -1).to_list(3)
    return [_call_out(c) for c in docs]

@api.get("/videocalls/{cid}")
async def get_call(cid: str, user=Depends(get_current_user)):
    return _call_out(await _my_call(cid, user))

@api.post("/videocalls/{cid}/accept")
async def accept_call(cid: str, user=Depends(get_current_user)):
    """Callee accepts (only after allowing camera). The caller is charged now."""
    c = await _my_call(cid, user)
    if c["callee_id"] != user["id"]: raise HTTPException(403, "ONLY_RECEIVER_CAN_ACCEPT")
    if c["status"] != "ringing": raise HTTPException(409, f"CALL_{c['status'].upper()}")
    caller = await db.users.find_one({"id": c["caller_id"]})
    if not caller or (caller.get("coins", 0) + caller.get("withdrawable", 0)) < c["cost"]:
        await db.calls.update_one({"id": cid}, {"$set": {"status": "failed", "reason": "CALLER_INSUFFICIENT_COINS", "ended_at": _iso()}})
        raise HTTPException(400, "CALLER_INSUFFICIENT_COINS")
    r = await db.calls.update_one({"id": cid, "status": "ringing"}, {"$set": {"status": "active", "accepted_at": _iso()}})
    if not r.modified_count: raise HTTPException(409, "CALL_NOT_RINGING")
    await spend_coins(c["caller_id"], c["cost"])
    await db.users.update_one({"id": c["callee_id"]}, {"$inc": {"withdrawable": c["cost"]}})
    await db.transactions.insert_one({"id": cid, "type": "videocall", "from_id": c["caller_id"], "to_id": c["callee_id"], "minutes": c["minutes"],
                                      "cost": c["cost"], "rate": c["rate"], "net": c["cost"], "created_at": _iso()})
    c["status"] = "active"
    return _call_out(c)

@api.post("/videocalls/{cid}/decline")
async def decline_call(cid: str, user=Depends(get_current_user)):
    c = await _my_call(cid, user)
    if c["status"] == "ringing":
        st = "declined" if user["id"] == c["callee_id"] else "cancelled"
        await db.calls.update_one({"id": cid, "status": "ringing"}, {"$set": {"status": st, "ended_at": _iso()}})
    return {"ok": True}

@api.post("/videocalls/{cid}/end")
async def end_call(cid: str, user=Depends(get_current_user)):
    c = await _my_call(cid, user)
    if c["status"] in ("ringing", "active"):
        await db.calls.update_one({"id": cid}, {"$set": {"status": "ended" if c["status"] == "active" else "cancelled", "ended_at": _iso(), "ended_by": user["id"]}})
    return {"ok": True}

class CallSignalReq(BaseModel):
    type: str
    data: dict

@api.post("/videocalls/{cid}/signal")
async def call_signal(cid: str, req: CallSignalReq, user=Depends(get_current_user)):
    """WebRTC signaling relay (offer / answer / ICE candidates) between the two members of an active call."""
    c = await _my_call(cid, user)
    if c["status"] != "active": raise HTTPException(409, "CALL_NOT_ACTIVE")
    if req.type not in ("offer", "answer", "ice"): raise HTTPException(400, "BAD_SIGNAL")
    to_id = c["callee_id"] if user["id"] == c["caller_id"] else c["caller_id"]
    await db.call_signals.insert_one({"id": str(uuid.uuid4()), "call_id": cid, "from_id": user["id"], "to_id": to_id,
                                      "type": req.type, "data": req.data, "at": _iso(), "ts": _now().timestamp()})
    return {"ok": True}

@api.get("/videocalls/{cid}/signals")
async def call_signals(cid: str, after: float = 0, user=Depends(get_current_user)):
    c = await _my_call(cid, user)
    sigs = await db.call_signals.find({"call_id": cid, "to_id": user["id"], "ts": {"$gt": after}}, {"_id": 0, "type": 1, "data": 1, "ts": 1}).sort("ts", 1).to_list(200)
    return {"status": c["status"], "signals": sigs}

# ---------- Date bookings with escrow ----------
DATE_SLOT_HOURS = 2.5  # each date lasts 2.5 hours
DATE_SLOT_MINUTES = 150  # 2.5-hour date duration
DATE_BUFFER = 15  # minutes locked automatically BEFORE and AFTER each date (total block = 150 + 2*15 = 180m)

def _hm_to_min(s):
    try:
        h, m = str(s).split(":")[:2]; return int(h) * 60 + int(m)
    except Exception:
        return 0

def _min_to_hm(x):
    # Wrap around the clock so minutes past midnight (e.g. 1530 = 25:30) display as the next-day time (01:30).
    x = int(x) % (24 * 60); return f"{x // 60:02d}:{x % 60:02d}"

def _win_end_min(win):
    """End minute of a window, extended past 1440 when it runs into the next day (to <= from)."""
    win = win or {"from": "18:00", "to": "23:00"}
    start = _hm_to_min(win.get("from", "18:00"))
    end = _hm_to_min(win.get("to", "23:00"))
    if end <= start:
        end += 24 * 60
    return start, end

AVAIL_FIELDS = {"availability": 1, "availability_time": 1, "availability_slots": 1, "availability_ranges": 1, "availability_weekly": 1}
START_STEP = 15  # inviter can start a date on any 15-minute mark

def day_windows(u, day):
    """Time ranges a user is open on `day`. None = no restriction set; [] = unavailable."""
    ranges = (u.get("availability_ranges") or {}).get(day)
    if ranges: return ranges
    days = u.get("availability") or []
    if day in days:
        w = (u.get("availability_slots") or {}).get(day) or u.get("availability_time")
        return [w] if w else None
    weekly = u.get("availability_weekly") or {}
    try: wd = str(datetime.fromisoformat(day).weekday())
    except ValueError: return []
    if weekly.get(wd): return weekly[wd]
    if days or u.get("availability_ranges") or any(weekly.values()): return []
    w = u.get("availability_time")
    return [w] if w else None

def fit_start(wins, start_min):
    """Effective start minute (may be >=1440 for after-midnight) if a full date fits in one window, else None."""
    for w in wins:
        ws, we = _win_end_min(w)
        s = start_min + 24 * 60 if (we > 24 * 60 and start_min < ws) else start_min
        if ws <= s and s + DATE_SLOT_MINUTES <= we: return s
    return None

def wins_label(wins): return ", ".join(f"{w['from']}-{w['to']}" for w in wins)

def free_starts(wins, taken):
    """All valid start minutes (15-min steps) that fit a window and avoid taken lock blocks."""
    def _lock(t):
        lf, lt = _hm_to_min(t["lock_from"]), _hm_to_min(t["lock_to"])
        return lf, lt + 24 * 60 if lt <= lf else lt
    locks = [_lock(t) for t in taken]
    out = []
    for w in wins:
        ws, we = _win_end_min(w)
        s = ws + (-ws % START_STEP)
        while s + DATE_SLOT_MINUTES <= we:
            if not any(lf < s + DATE_SLOT_MINUTES and s < lt for lf, lt in locks): out.append(s)
            s += START_STEP
    return out

def gen_slots(win):
    """Split an availability window into consecutive 2.5-hour slots.
    e.g. win 12:00-21:00 -> [12:00-14:30, 14:30-17:00, ...]. Windows whose
    end is <= start run past midnight (e.g. 22:00-02:00) into the next day."""
    start, end = _win_end_min(win)
    step = DATE_SLOT_MINUTES
    slots = []
    s = start
    while s < end:
        e = min(s + step, end)
        slots.append({"from": _min_to_hm(s), "to": _min_to_hm(e)})
        s += step
    return slots

def _booking_start_min(b):
    if b.get("slot_from"):
        return _hm_to_min(b["slot_from"])
    if b.get("local_time"):
        return _hm_to_min(b["local_time"])
    try:
        return _hm_to_min(datetime.fromisoformat(b["scheduled_at"].replace("Z", "+00:00")).strftime("%H:%M"))
    except Exception:
        return 0

def _booking_end_min(b):
    if b.get("slot_to"):
        e = _hm_to_min(b["slot_to"]); s = _booking_start_min(b)
        if e <= s: e += 24 * 60  # date ends after midnight (next day)
        return e
    return _booking_start_min(b) + DATE_SLOT_MINUTES

@api.post("/dates/book")
async def book_date(req: DateBookingReq, user=Depends(get_current_user)):
    min_coins = (await get_settings())["date_min_coins"]
    if req.coins < min_coins: raise HTTPException(400, f"Minimum {min_coins} coins")
    if (user.get("coins", 0) + user.get("withdrawable", 0)) < req.coins: raise HTTPException(400, "Insufficient coins")
    target = await db.users.find_one({"id": req.target_id})
    if not target: raise HTTPException(404, "Recipient not found")
    if target.get("account_status") in ("PAUSED", "PENDING_DELETION"): raise HTTPException(400, "RECIPIENT_UNAVAILABLE")
    now = datetime.now(timezone.utc).isoformat()
    # 3 mandatory custom date-idea options proposed by the inviter
    activities = [str(a).strip() for a in (req.activities or [])]
    activities = [a for a in activities if a]
    if len(activities) != 3:
        raise HTTPException(400, "ACTIVITIES_REQUIRED")
    activities = [a[:120] for a in activities]
    await _apply_geo(req, venue=req.venue)
    day = (req.local_day or req.scheduled_at)[:10]
    wins = day_windows(target, day)
    if wins is not None and not wins: raise HTTPException(400, "DAY_UNAVAILABLE")
    try:
        local_t = datetime.fromisoformat(req.scheduled_at.replace("Z", "+00:00")).strftime("%H:%M") if req.local_time is None else req.local_time
    except Exception:
        local_t = req.local_time or "00:00"
    start_min = _hm_to_min(local_t)
    if wins:
        # The full 2.5h date must fit inside one of the day's ranges (which may run past midnight).
        eff = fit_start(wins, start_min)
        if eff is None: raise HTTPException(400, f"TIME_UNAVAILABLE:{wins_label(wins)}")
        start_min = eff
    end_min = start_min + DATE_SLOT_MINUTES
    slot_from, slot_to = _min_to_hm(start_min), _min_to_hm(end_min)
    await _assert_slot_free(target, day, start_min, _pdt(req.scheduled_at))
    booking_id = str(uuid.uuid4())
    doc = {"id": booking_id, "from_id": user["id"], "to_id": req.target_id,
           "venue": req.venue, "city": req.city, "address": (req.address or "").strip(), "postal_code": (req.postal_code or "").strip(), "country": (req.country or "").strip(), "lat": req.lat, "lng": req.lng, "unverified": bool(req.unverified), "scheduled_at": req.scheduled_at,
           "local_time": local_t, "local_day": day, "slot_from": slot_from, "slot_to": slot_to,
           "coins": req.coins, "status": "escrow", "photo_url": None,
           "activities": activities, "selected_activity": None,
           "release_at": None, "created_at": now}
    await spend_coins(user["id"], req.coins)
    # hold in escrow of recipient
    await db.users.update_one({"id": req.target_id}, {"$inc": {"escrow": req.coins}})
    await db.date_bookings.insert_one(doc)
    await notify(req.target_id, "date_request", "New date request 📅", f"{user['name']} invited you to {req.venue}, {req.city} · 🪙 {req.coins}. Accept or decline in Dates.", {"booking_id": booking_id}, email=True)
    await _date_chat_card(user["id"], req.target_id, "booking", booking_id, "invite", f"📅 Date invitation · {req.venue}", req.target_id,
                          {"when": req.scheduled_at, "coins": req.coins, "options": activities, "location": _loc_card(doc)})
    return {"booking_id": booking_id, "status": "escrow"}

def _decline_reason(r: Optional[str]) -> Optional[str]:
    r = (r or "").strip()[:300]
    return r or None

def _reason_line(r: Optional[str]) -> str:
    return f' Reason: "{r}"' if r else ""

@api.post("/dates/respond/{bid}")
async def respond_date(bid: str, accept: bool, selected_activity: Optional[str] = None, reason: Optional[str] = None, user=Depends(get_current_user)):
    b = await db.date_bookings.find_one({"id": bid})
    if not b: raise HTTPException(404, "Not found")
    if b["to_id"] != user["id"]: raise HTTPException(403, "Only recipient can respond")
    if b["status"] != "escrow": raise HTTPException(400, "Cannot respond")
    now = datetime.now(timezone.utc).isoformat()
    if accept:
        opts = b.get("activities") or []
        # the invitee must pick one of the inviter's 3 proposed date ideas
        if opts:
            chosen = (selected_activity or "").strip()
            if chosen not in opts:
                raise HTTPException(400, "SELECT_ACTIVITY")
            await db.date_bookings.update_one({"id": bid}, {"$set": {"status": "accepted", "accepted_at": now, "selected_activity": chosen}})
            await notify(b["from_id"], "date_accepted", "Date accepted 💃", f"{user['name']} accepted your date at {b['venue']} and chose: {chosen}.", {"booking_id": bid}, email=True)
            await db.messages.update_many({"ref_id": bid, "type": "date_card", "event": "invite"}, {"$set": {"data.chosen": chosen}})
            await _date_chat_card(user["id"], b["from_id"], "booking", bid, "accepted", f"✅ Date accepted · {chosen}", data={"option": chosen})
            return {"status": "accepted", "selected_activity": chosen}
        await db.date_bookings.update_one({"id": bid}, {"$set": {"status": "accepted", "accepted_at": now}})
        await notify(b["from_id"], "date_accepted", "Date accepted 💃", f"{user['name']} accepted your date at {b['venue']}.", {"booking_id": bid}, email=True)
        await _date_chat_card(user["id"], b["from_id"], "booking", bid, "accepted", "✅ Date accepted")
        return {"status": "accepted"}
    await db.users.update_one({"id": b["from_id"]}, {"$inc": {"coins": b["coins"]}})
    await db.users.update_one({"id": user["id"]}, {"$inc": {"escrow": -b["coins"]}})
    reason = _decline_reason(reason)
    await db.date_bookings.update_one({"id": bid}, {"$set": {"status": "declined", "declined_at": now, "decline_reason": reason}})
    await notify(b["from_id"], "date_declined", "Date declined", f"{user['name']} declined your date at {b['venue']}. 🪙 {b['coins']} refunded." + _reason_line(reason), {"booking_id": bid}, email=True)
    await _date_chat_card(user["id"], b["from_id"], "booking", bid, "declined", "❌ Date declined", data={"reason": reason, "refunded": b["coins"]})
    return {"status": "declined", "refunded": b["coins"]}

INVITE_ACTIVE = ["INVITATION_SENT", "DATE_ACTIVITY_SELECTED", "LOCATION_PROPOSED", "TAXI_REQUESTED", "PICKUP_ADDRESS_PENDING",
                 "PICKUP_ADDRESS_SELECTED", "DATE_CONFIRMED", "DATE_COMPLETED_PENDING_VERIFICATION", "PHOTO_VERIFICATION_PENDING"]
INVITE_CANCELLED = ["CANCELLED", "CANCELLED_TRANSPORTATION", "REFUNDED"]

def _block(day, start_min, reason, end_min=None):
    end_min = end_min if end_min is not None else start_min + DATE_SLOT_MINUTES
    return day, {"from": _min_to_hm(start_min), "to": _min_to_hm(end_min), "reason": reason,
                 "lock_from": _min_to_hm(max(0, start_min - DATE_BUFFER)), "lock_to": _min_to_hm(end_min + DATE_BUFFER)}

async def _taken_blocks(u):
    """Every locked block per local day for a user: other dates (booked) and cancelled dates/slots (cancelled)."""
    uid, out = u["id"], {}
    unlocked = set(u.get("unlocked_slots") or [])
    def add(day, start, reason, end=None):
        d, b = _block(day, start, reason, end)
        if reason == "cancelled" and f"{d}|{b['from']}" in unlocked: return
        out.setdefault(d, []).append(b)
    async for b in db.date_bookings.find({"status": {"$in": ["escrow", "accepted", "confirmed", "cancelled"]}, "$or": [{"to_id": uid}, {"from_id": uid}]},
                                         {"_id": 0, "status": 1, "scheduled_at": 1, "slot_from": 1, "slot_to": 1, "local_time": 1, "local_day": 1}):
        add((b.get("local_day") or b["scheduled_at"])[:10], _booking_start_min(b), "cancelled" if b["status"] == "cancelled" else "booked", _booking_end_min(b))
    async for d in db.dates.find({"status": {"$in": INVITE_ACTIVE + INVITE_CANCELLED}, "$or": [{"inviter_id": uid}, {"recipient_id": uid}]},
                                 {"_id": 0, "status": 1, "location": 1, "proposed_start": 1, "local_day": 1, "local_time": 1}):
        st = _pdt((d.get("location") or {}).get("scheduled_start") or d.get("proposed_start"))
        if not st: continue
        day = d.get("local_day") or st.strftime("%Y-%m-%d")
        add(day, _hm_to_min(d.get("local_time") or st.strftime("%H:%M")), "cancelled" if d["status"] in INVITE_CANCELLED else "booked")
    for ls in (u.get("locked_slots") or []):
        st = _pdt(ls.get("start"))
        if st: add(ls.get("date") or st.strftime("%Y-%m-%d"), st.hour * 60 + st.minute, "cancelled")
    # de-duplicate identical blocks (e.g. a rejected invite also stored in locked_slots)
    return {k: [dict(t) for t in {tuple(sorted(x.items())) for x in v}] for k, v in out.items()}

async def _assert_slot_free(u, day, start_min, start_dt):
    """Reject past start times and any overlap with another date or a cancelled (locked) slot, incl. 15-min buffer."""
    if start_dt and start_dt.tzinfo is None: start_dt = start_dt.replace(tzinfo=timezone.utc)
    if start_dt and start_dt <= _now(): raise HTTPException(400, "TIME_PASSED")
    end_min = start_min + DATE_SLOT_MINUTES
    for b in (await _taken_blocks(u)).get(day, []):
        lf, lt = _hm_to_min(b["lock_from"]), _hm_to_min(b["lock_to"])
        if lt <= lf: lt += 24 * 60
        if start_min < lt and lf < end_min:
            raise HTTPException(400, f"{'SLOT_LOCKED' if b['reason'] == 'cancelled' else 'SLOT_BUSY'}:{b['from']}-{b['to']}")

class UnlockSlotReq(BaseModel):
    day: str
    time: str

@api.get("/me/locked-slots")
async def my_locked_slots(user=Depends(get_current_user)):
    """Upcoming times locked by a cancelled or refused date, which subscribers can reopen."""
    today = _now().strftime("%Y-%m-%d")
    blocks = await _taken_blocks(user)
    items = sorted(({"day": d, "from": b["from"], "to": b["to"]} for d, v in blocks.items() if d >= today for b in v if b["reason"] == "cancelled"),
                   key=lambda x: (x["day"], x["from"]))
    return {"items": items, "can_unlock": has_premium(user)}

@api.post("/me/locked-slots/unlock")
async def unlock_slot(req: UnlockSlotReq, user=Depends(get_current_user)):
    if not has_premium(user): raise HTTPException(403, "PREMIUM_REQUIRED")
    day, tm = req.day[:10], req.time[:5]
    if not any(b["from"] == tm and b["reason"] == "cancelled" for b in (await _taken_blocks(user)).get(day, [])):
        raise HTTPException(404, "Locked slot not found")
    await db.users.update_one({"id": user["id"]}, {"$addToSet": {"unlocked_slots": f"{day}|{tm}"}})
    return {"ok": True}

@api.post("/me/locked-slots/unlock-all")
async def unlock_all_slots(user=Depends(get_current_user)):
    if not has_premium(user): raise HTTPException(403, "PREMIUM_REQUIRED")
    today = _now().strftime("%Y-%m-%d")
    keys = [f"{d}|{b['from']}" for d, v in (await _taken_blocks(user)).items() if d >= today for b in v if b["reason"] == "cancelled"]
    if keys: await db.users.update_one({"id": user["id"]}, {"$addToSet": {"unlocked_slots": {"$each": keys}}})
    return {"ok": True, "count": len(keys)}

class LiveLocReq(BaseModel):
    lat: float
    lng: float
    sharing: bool = True
    to_date: bool = True
    to_support: bool = False

async def _live_target(kind, did, uid):
    if kind == "invite":
        d = await db.dates.find_one({"id": did}, {"_id": 0, "inviter_id": 1, "recipient_id": 1, "status": 1, "location": 1, "live_location": 1})
        if not d: raise HTTPException(404, "Not found")
        parties, start, ok = (d["inviter_id"], d["recipient_id"]), _pdt((d.get("location") or {}).get("scheduled_start")), d["status"] == "DATE_CONFIRMED"
        coll = db.dates
    elif kind == "booking":
        d = await db.date_bookings.find_one({"id": did}, {"_id": 0, "from_id": 1, "to_id": 1, "status": 1, "scheduled_at": 1, "live_location": 1})
        if not d: raise HTTPException(404, "Not found")
        parties, start, ok = (d["from_id"], d["to_id"]), _pdt(d.get("scheduled_at")), d["status"] in ("accepted", "confirmed")
        coll = db.date_bookings
    else: raise HTTPException(404, "Not found")
    if uid not in parties: raise HTTPException(403, "Forbidden")
    if start and start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
    return coll, d, parties, start, ok

@api.post("/live-location/{kind}/{did}")
async def share_live_location(kind: str, did: str, req: LiveLocReq, user=Depends(get_current_user)):
    """Optional: share your current position with your date from 2h before the start until the date ends."""
    coll, d, _, start, ok = await _live_target(kind, did, user["id"])
    if not req.sharing or not (req.to_date or req.to_support):
        await coll.update_one({"id": did}, {"$unset": {f"live_location.{user['id']}": ""}})
        return {"ok": True, "sharing": False}
    if not ok or not start or not (start - timedelta(hours=2) <= _now() <= start + timedelta(minutes=DATE_SLOT_MINUTES)):
        raise HTTPException(400, "LIVE_LOCATION_CLOSED")
    if not (-90 <= req.lat <= 90 and -180 <= req.lng <= 180): raise HTTPException(400, "Invalid coordinates")
    await coll.update_one({"id": did}, {"$set": {f"live_location.{user['id']}": {"lat": req.lat, "lng": req.lng, "at": _iso(),
        "to_date": req.to_date, "to_support": req.to_support}}})
    return {"ok": True, "sharing": True}

@api.get("/live-location/{kind}/{did}")
async def get_live_location(kind: str, did: str, user=Depends(get_current_user)):
    _, d, parties, start, ok = await _live_target(kind, did, user["id"])
    other = parties[1] if parties[0] == user["id"] else parties[0]
    live = d.get("live_location") or {}
    open_ = bool(ok and start and start - timedelta(hours=2) <= _now() <= start + timedelta(minutes=DATE_SLOT_MINUTES))
    return {"open": open_, "opens_at": _iso(start - timedelta(hours=2)) if start else None, "me": live.get(user["id"]),
            "other": live.get(other) if open_ and (live.get(other) or {}).get("to_date", True) else None}

@api.get("/admin/live-locations")
async def admin_live_locations(admin=Depends(get_admin)):
    """Live locations users chose to share with support (updated in the last 3h)."""
    since = _iso(_now() - timedelta(hours=3))
    out, uids = [], set()
    for kind, coll, a, b in (("invite", db.dates, "inviter_id", "recipient_id"), ("booking", db.date_bookings, "from_id", "to_id")):
        async for d in coll.find({"live_location": {"$exists": True, "$ne": {}}}, {"_id": 0, "id": 1, a: 1, b: 1, "live_location": 1, "location": 1, "venue": 1, "address": 1, "city": 1}):
            for uid, loc in (d.get("live_location") or {}).items():
                if not loc.get("to_support") or (loc.get("at") or "") < since: continue
                other = d[b] if uid == d[a] else d[a]
                uids.update([uid, other])
                v = d.get("location") or d
                venue = ", ".join(x for x in (v.get("venue"), v.get("address"), v.get("city")) if x)
                out.append({"kind": kind, "date_id": d["id"], "user_id": uid, "other_id": other, "lat": loc["lat"], "lng": loc["lng"],
                            "at": loc["at"], "to_date": loc.get("to_date", True), "venue": venue})
    names = {u["id"]: u.get("name") async for u in db.users.find({"id": {"$in": list(uids)}}, {"_id": 0, "id": 1, "name": 1})}
    for o in out: o["user_name"], o["other_name"] = names.get(o["user_id"]), names.get(o["other_id"])
    return sorted(out, key=lambda o: o["at"], reverse=True)

@api.get("/profiles/{pid}/availability")
async def profile_availability(pid: str, user=Depends(get_current_user)):
    p = await db.users.find_one({"id": pid}, {"_id": 0, "locked_slots": 1, "unlocked_slots": 1, **AVAIL_FIELDS})
    if not p: raise HTTPException(404, "Not found")
    time_window = p.get("availability_time")
    day_slots = p.get("availability_slots") or {}
    p["id"] = pid
    busy_slots = await _taken_blocks(p)
    locked_days = {d: c for d, v in busy_slots.items() if (c := [x for x in v if x["reason"] == "cancelled"])}
    # per-day open ranges for the next 120 days (specific days, weekly schedule or default window)
    today = datetime.now(timezone.utc).date() - timedelta(days=1)
    day_wins = {}
    for n in range(121):
        d = (today + timedelta(days=n)).isoformat()
        w = day_windows(p, d)
        if w: day_wins[d] = w
    # a day is fully booked only when no free 15-min start time is left (incl. buffer)
    fully_booked = sorted(d for d, taken in busy_slots.items() if (day_wins.get(d) or day_windows(p, d)) and not free_starts(day_wins.get(d) or day_windows(p, d), taken))
    return {"available_days": p.get("availability") or [], "busy_days": fully_booked,
            "time_window": time_window, "slots": day_slots, "locked_days": locked_days,
            "day_windows": day_wins, "restricted": day_windows(p, "1970-01-01") is not None, "weekly": p.get("availability_weekly") or {},
            "start_step": START_STEP, "slot_minutes": DATE_SLOT_MINUTES,
            "busy_slots": busy_slots, "slot_hours": DATE_SLOT_HOURS, "buffer": DATE_BUFFER}

@api.get("/dates")
async def list_dates(user=Depends(get_current_user)):
    # trigger release for any past release_at
    now_dt = datetime.now(timezone.utc)
    to_release = await db.date_bookings.find({"to_id": user["id"], "status": "confirmed"}).to_list(200)
    for b in to_release:
        if b.get("release_at") and not _report_open(b):
            try: ra = datetime.fromisoformat(b["release_at"].replace("Z", "+00:00"))
            except Exception: continue
            if ra <= now_dt:
                coins = b["coins"]
                if b.get("photo_url"):
                    rec, cut = coins, 0
                else:
                    rec = int(round(coins * 0.5)); cut = coins - rec
                await db.users.update_one({"id": user["id"]}, {"$inc": {"escrow": -coins, "withdrawable": rec}})
                await db.date_bookings.update_one({"id": b["id"]}, {"$set": {"status": "released", "released_net": rec, "platform_cut": cut}})
                if cut:
                    await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "platform_fee_no_photo", "from_id": user["id"], "to_id": "platform", "cost": cut, "net": cut, "created_at": now_dt.isoformat()})
    outgoing = await db.date_bookings.find({"from_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    incoming = await db.date_bookings.find({"to_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for b in outgoing + incoming:
        r = b.get("report")
        if r:  # parties never see the other side's evidence, photos or reply text
            b["report"] = {k: r.get(k) for k in ("reporter_id", "reporter_role", "reasons", "details", "status", "reply_deadline", "created_at")}
            b["report"]["reply"] = ({"at": r["reply"].get("at")} if r.get("reply") else None)
    for b in outgoing:
        if b.get("vip"):
            _hide_own_address(b, b["status"] not in ("escrow", "cancelled", "declined"))
            b["extra_hour_price"] = vip_extra_price(await db.users.find_one({"id": b["to_id"]}, {"_id": 0, "vip.prices": 1}) or {})
    return {"outgoing": outgoing, "incoming": incoming}

@api.post("/dates/confirm")
async def confirm_date(req: DateConfirmReq, user=Depends(get_current_user)):
    b = await db.date_bookings.find_one({"id": req.booking_id})
    if not b: raise HTTPException(404, "Not found")
    if b["to_id"] != user["id"]: raise HTTPException(403, "Only recipient can confirm")
    if b["status"] not in ("escrow", "accepted") and not (b["status"] == "confirmed" and b.get("auto_confirmed") and not b.get("photo_url")):
        raise HTTPException(400, "Cannot confirm")
    now_dt = datetime.now(timezone.utc)
    try: sched = datetime.fromisoformat(b["scheduled_at"].replace("Z", "+00:00"))
    except Exception: sched = now_dt
    if sched.tzinfo is None: sched = sched.replace(tzinfo=timezone.utc)
    if now_dt < sched: raise HTTPException(400, "DATE_NOT_YET")
    set_fields = {"photo_url": req.photo_url, "confirmed_at": datetime.now(timezone.utc).isoformat()}
    if b["status"] in ("escrow", "accepted"):
        set_fields["status"] = "confirmed"
        set_fields["release_at"] = max(sched + timedelta(days=1), now_dt).isoformat()
    await db.date_bookings.update_one({"id": req.booking_id}, {"$set": set_fields})
    return {"status": "confirmed", "release_at": set_fields.get("release_at", b.get("release_at"))}

@api.post("/dates/release-half/{bid}")
async def release_half(bid: str, user=Depends(get_current_user)):
    b = await db.date_bookings.find_one({"id": bid})
    if not b: raise HTTPException(404, "Not found")
    if b["to_id"] != user["id"]: raise HTTPException(403, "Only the recipient can claim")
    if b["status"] not in ("accepted", "confirmed"): raise HTTPException(400, "Cannot release")
    if b.get("photo_url"): raise HTTPException(400, "Already photo-confirmed")
    if _report_open(b): raise HTTPException(400, "UNDER_REVIEW")
    now_dt = datetime.now(timezone.utc)
    try: sched = datetime.fromisoformat(b["scheduled_at"].replace("Z", "+00:00"))
    except Exception: sched = now_dt
    if sched.tzinfo is None: sched = sched.replace(tzinfo=timezone.utc)
    if now_dt < sched + timedelta(hours=24): raise HTTPException(400, "CLAIM_NOT_YET")
    coins = b["coins"]
    rec = int(round(coins * 0.5)); cut = coins - rec
    await db.users.update_one({"id": user["id"]}, {"$inc": {"escrow": -coins, "withdrawable": rec}})
    await db.date_bookings.update_one({"id": bid}, {"$set": {"status": "released", "released_net": rec, "platform_cut": cut, "released_at": now_dt.isoformat()}})
    if cut:
        await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "platform_fee_no_photo", "from_id": user["id"], "to_id": "platform", "cost": cut, "net": cut, "created_at": now_dt.isoformat()})
    await notify(b["from_id"], "date_declined", "Date closed without photo", f"The date at {b['venue']} was closed without a photo. The recipient received 50% (🪙 {rec}); the platform kept 🪙 {cut}.", {"booking_id": bid})
    return {"status": "released", "recipient": rec, "platform_cut": cut}

@api.post("/dates/cancel/{bid}")
async def cancel_date(bid: str, user=Depends(get_current_user)):
    await _close_date_cards(bid)
    b = await db.date_bookings.find_one({"id": bid})
    if not b: raise HTTPException(404, "Not found")
    if user["id"] not in (b["from_id"], b["to_id"]): raise HTTPException(403, "No access")
    if _report_open(b): raise HTTPException(400, "UNDER_REVIEW")
    if b["status"] not in ("escrow", "accepted") and not (b["status"] == "confirmed" and b.get("auto_confirmed")):
        raise HTTPException(400, "Cannot cancel")
    now = datetime.now(timezone.utc).isoformat()
    taxi = b.get("taxi") or {}
    taxi_sent = taxi.get("status") == "sent"
    tcoins = int(taxi.get("coins", 0)) if taxi_sent else 0
    base = b["coins"] + tcoins
    taxi_set = {"taxi.status": "refunded"} if taxi_sent else {}
    if b["status"] != "escrow" and _pdt(b.get("scheduled_at")) and _aware(_pdt(b["scheduled_at"])) <= datetime.now(timezone.utc):
        raise HTTPException(400, "DATE_STARTED")
    if user["id"] == b["from_id"]:
        # inviter cannot cancel during the 24h window after the date has started
        try: sched = datetime.fromisoformat(b["scheduled_at"].replace("Z", "+00:00"))
        except Exception: sched = datetime.now(timezone.utc)
        if sched.tzinfo is None: sched = sched.replace(tzinfo=timezone.utc)
        now_dt = datetime.now(timezone.utc)
        if sched <= now_dt < sched + timedelta(hours=24): raise HTTPException(400, "CANCEL_LOCKED_24H")
        # inviter cancels -> date coins: 50% back, 25% to invitee, 25% platform; taxi coins always refunded in full
        dc = int(b["coins"])
        refund = int(round(dc * 0.5)) + tcoins
        invitee_comp = int(round(dc * 0.25))
        platform_fee = dc - int(round(dc * 0.5)) - invitee_comp
        await db.users.update_one({"id": b["from_id"]}, {"$inc": {"coins": refund}})
        await db.users.update_one({"id": b["to_id"]}, {"$inc": {"escrow": -b["coins"], "withdrawable": invitee_comp - tcoins}})
        await db.date_bookings.update_one({"id": bid}, {"$set": {"status": "cancelled", "refund": refund, "compensation": invitee_comp, "platform_fee": platform_fee, "cancelled_at": now, "cancelled_by": "inviter", **taxi_set}})
        if invitee_comp:
            await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "date_cancel_fee", "from_id": b["from_id"], "to_id": b["to_id"], "cost": invitee_comp, "net": invitee_comp, "created_at": now})
        if platform_fee:
            await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "date_cancel_platform_fee", "from_id": b["from_id"], "to_id": "platform", "cost": platform_fee, "net": platform_fee, "created_at": now})
        for uid in (b["from_id"], b["to_id"]):
            await notify(uid, "date_cancelled", "Date cancelled", f"The date at {b['venue']} was cancelled by the inviter. 🪙 {refund} refunded to the inviter, 🪙 {invitee_comp} to the invited person, 🪙 {platform_fee} platform fee.", {"booking_id": bid}, email=True)
        return {"status": "cancelled", "refund": refund, "compensation": invitee_comp, "platform_fee": platform_fee}
    # invited person cancels -> full refund to the inviter
    await db.users.update_one({"id": b["from_id"]}, {"$inc": {"coins": base}})
    await db.users.update_one({"id": b["to_id"]}, {"$inc": {"escrow": -b["coins"], "withdrawable": -tcoins}})
    await db.date_bookings.update_one({"id": bid}, {"$set": {"status": "cancelled", "refund": base, "compensation": 0, "cancelled_at": now, "cancelled_by": "invited", **taxi_set}})
    await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "date_cancel_refund", "from_id": b["to_id"], "to_id": b["from_id"], "cost": base, "net": base, "created_at": now})
    for uid in (b["from_id"], b["to_id"]):
        await notify(uid, "date_cancelled", "Date cancelled", f"The date at {b['venue']} was cancelled by the invited person. All coins (🪙 {base}) were refunded to the inviter.", {"booking_id": bid}, email=True)
    return {"status": "cancelled", "refund": base, "compensation": 0}

class InviteReportReq(BaseModel):
    reasons: list[str] = []
    details: str
    evidence: Optional[str] = None
    photos: list[str] = []

async def _report_photos(user, photos):
    """Keep only the reporter's own uploads (max 6) and make them private (admins only)."""
    photos = [p for p in (photos or [])[:6] if isinstance(p, str)]
    owned = [f["storage_path"] async for f in db.files.find({"storage_path": {"$in": photos}, "user_id": user["id"]}, {"storage_path": 1})]
    if owned: await db.files.update_many({"storage_path": {"$in": owned}}, {"$set": {"private": True}})
    return owned
class ReportReplyReq(BaseModel):
    details: str
    photos: list[str] = []

def _report_view(r, viewer_id):
    """What a party may see about a report: the reported side sees reasons/details (never the photos)."""
    if not r: return None
    reply = r.get("reply")
    return {"by_me": r.get("reporter_id") == viewer_id, "reasons": r.get("reasons") or [], "details": r.get("details"),
            "status": r.get("status") or "open", "replied": bool(reply), "reply_at": (reply or {}).get("at"),
            "reply_deadline": r.get("reply_deadline"), "reporter_role": r.get("reporter_role"), "outcome": r.get("outcome")}

REPORT_REPLY_HOURS = 24

def _reply_closed(r) -> bool:
    dl = _pdt((r or {}).get("reply_deadline"))
    return bool(dl and _now() > _aware(dl))

def _reported_msg(role: str) -> str:
    """Text for the reported person: 24h to reply, default outcome, admin decides."""
    who = "the coins will be refunded to the person who invited you" if role == "inviter" else "all coins from this date will go to the invited person"
    return (f"Your date was reported to our support team. Nothing has been cancelled yet. You have {REPORT_REPLY_HOURS} hours to reply with your side and photo proofs. "
            f"If you don't reply or there is no strong evidence, {who}. Support reviews every report before any coins move.")

async def _save_reply(coll, did, rep_doc, parties, user, req, label):
    if not rep_doc: raise HTTPException(404, "No report")
    if user["id"] not in parties or rep_doc.get("reporter_id") == user["id"]: raise HTTPException(403, "Only the reported person can reply")
    if rep_doc.get("reply"): raise HTTPException(409, "ALREADY_REPLIED")
    if (rep_doc.get("status") or "open") != "open": raise HTTPException(400, "REPORT_CLOSED")
    if _reply_closed(rep_doc): raise HTTPException(400, "REPLY_WINDOW_CLOSED")
    if len((req.details or "").strip()) < 10: raise HTTPException(400, "Please describe your side (min 10 chars)")
    reply = {"by": user["id"], "details": req.details.strip(), "photos": await _report_photos(user, req.photos), "at": _iso()}
    await coll.update_one({"id": did}, {"$set": {"report.reply": reply}})
    await notify(rep_doc["reporter_id"], "date_request", "The other person replied to your report", "Support received their side of the story and will review both.", {"date_id": did}, link=DATES_LINK, cta="View Date")
    for aid in await _admin_ids():
        await notify(aid, "date_request", "Report reply received", f"{user['name']} replied to the report on {label} ({did}).", {"date_id": did}, email=True, link=f"{PUBLIC_APP_URL}/admin", cta="View Case")
    return {"ok": True, "replied": True}

@api.post("/dates/report/{bid}/reply")
async def booking_report_reply(bid: str, req: ReportReplyReq, user=Depends(get_current_user)):
    b = await db.date_bookings.find_one({"id": bid}, {"_id": 0})
    if not b: raise HTTPException(404, "Not found")
    return await _save_reply(db.date_bookings, bid, b.get("report"), (b["from_id"], b["to_id"]), user, req, "a booked date")

@api.post("/invites/{did}/report/reply")
async def invite_report_reply(did: str, req: ReportReplyReq, user=Depends(get_current_user)):
    d = await db.dates.find_one({"id": did}, {"_id": 0})
    if not d: raise HTTPException(404, "Not found")
    return await _save_reply(db.dates, did, d.get("report"), (d["inviter_id"], d["recipient_id"]), user, req, "a date")

class SosReq(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    message: Optional[str] = ""

@api.post("/sos/{kind}/{did}")
async def sos_alert(kind: str, did: str, req: SosReq, user=Depends(get_current_user)):
    """Emergency: alert support immediately with the member's position (if available)."""
    _, d, parties, start, _ = await _live_target(kind, did, user["id"])
    if req.lat is not None and not (-90 <= req.lat <= 90 and -180 <= (req.lng or 0) <= 180): raise HTTPException(400, "Invalid coordinates")
    other = parties[1] if parties[0] == user["id"] else parties[0]
    o = await db.users.find_one({"id": other}, {"_id": 0, "name": 1})
    alert = {"id": str(uuid.uuid4()), "kind": kind, "date_id": did, "user_id": user["id"], "user_name": user.get("name"),
             "user_phone": user.get("phone"), "user_email": user.get("email"), "other_id": other, "other_name": (o or {}).get("name"),
             "lat": req.lat, "lng": req.lng, "message": (req.message or "").strip()[:500], "status": "open", "created_at": _iso()}
    alert["public_token"] = secrets.token_urlsafe(24)
    await db.sos_alerts.insert_one(dict(alert))
    contacts_alerted = await _alert_trusted_contacts(user, alert)
    where = f" Location: https://www.google.com/maps/search/?api=1&query={req.lat},{req.lng}" if req.lat is not None else " (no location available)"
    for aid in await _admin_ids():
        await notify(aid, "sos", "SOS — member needs help", f"{user.get('name')} pressed SOS during a date with {alert['other_name']}.{where}", {"sos_id": alert["id"]}, email=True, link=f"{PUBLIC_APP_URL}/admin", cta="Open SOS")
    return {"ok": True, "id": alert["id"], "contacts_alerted": contacts_alerted}

class TrustedContact(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
class TrustedContactsReq(BaseModel):
    contacts: list[TrustedContact] = []
MAX_TRUSTED = 3

@api.get("/me/trusted-contacts")
async def get_trusted_contacts(user=Depends(get_current_user)):
    return {"contacts": user.get("trusted_contacts") or [], "max": MAX_TRUSTED}

@api.put("/me/trusted-contacts")
async def put_trusted_contacts(req: TrustedContactsReq, user=Depends(get_current_user)):
    if len(req.contacts) > MAX_TRUSTED: raise HTTPException(400, f"Up to {MAX_TRUSTED} trusted contacts")
    out = []
    for c in req.contacts:
        name, phone = c.name.strip()[:60], re.sub(r"[^\d+]", "", c.phone or "")[:20]
        if not name: raise HTTPException(400, "Contact name is required")
        if not c.email and not phone: raise HTTPException(400, "Add an email or phone for each contact")
        if phone and not re.fullmatch(r"\+?\d{7,15}", phone): raise HTTPException(400, "Invalid phone number")
        out.append({"name": name, "email": (c.email or "").lower() or None, "phone": phone or None})
    await db.users.update_one({"id": user["id"]}, {"$set": {"trusted_contacts": out}})
    return {"contacts": out}

async def _alert_trusted_contacts(user, alert):
    """Email (and SMS when configured) each trusted contact a link to the live SOS page. Max once per 5 min per user."""
    contacts = user.get("trusted_contacts") or []
    if not contacts: return 0
    since = _iso(_now() - timedelta(minutes=5))
    if await db.sos_alerts.count_documents({"user_id": user["id"], "contacts_notified": True, "created_at": {"$gte": since}}): return 0
    link = f"{PUBLIC_APP_URL}/sos/{alert['public_token']}"
    name = user.get("name") or "Your friend"
    body = (f"{name} added you as a trusted contact on GiftsDates and just pressed the SOS button during a date. "
            f"Open the link to see their location. Our support team has also been alerted. If you think they are in danger, call local emergency services.")
    for c in contacts:
        if c.get("email"):
            _spawn(send_email(to=c["email"], subject=f"SOS from {name} on GiftsDates",
                              html=_email_cta_html(f"{name} needs help", body, link, cta="See their location")))
        if c.get("phone"):
            _spawn(send_sms(to=c["phone"], body=f"GiftsDates SOS: {name} pressed SOS during a date. Location: {link}"))
    await db.sos_alerts.update_one({"id": alert["id"]}, {"$set": {"contacts_notified": True}})
    return len(contacts)

@api.get("/sos/public/{token}")
async def sos_public(token: str):
    """Public page for trusted contacts: latest position of the member for 24h (or until resolved)."""
    a = await db.sos_alerts.find_one({"public_token": token}, {"_id": 0})
    if not a or (a.get("created_at") or "") < _iso(_now() - timedelta(hours=24)): raise HTTPException(404, "Not found")
    lat, lng, at = a.get("lat"), a.get("lng"), a.get("created_at")
    coll = db.dates if a["kind"] == "invite" else db.date_bookings
    d = await coll.find_one({"id": a["date_id"]}, {"_id": 0, "live_location": 1})
    live = ((d or {}).get("live_location") or {}).get(a["user_id"])
    if live and live.get("to_support") and live.get("at", "") > (at or ""): lat, lng, at = live["lat"], live["lng"], live["at"]
    return {"name": a.get("user_name"), "status": a.get("status"), "created_at": a.get("created_at"), "lat": lat, "lng": lng, "updated_at": at}

@api.get("/admin/sos")
async def admin_sos(admin=Depends(get_admin)):
    return await db.sos_alerts.find({}, {"_id": 0, "public_token": 0}).sort("created_at", -1).to_list(100)

@api.post("/admin/sos/{sid}/resolve")
async def admin_sos_resolve(sid: str, admin=Depends(get_admin)):
    r = await db.sos_alerts.update_one({"id": sid, "status": "open"}, {"$set": {"status": "resolved", "resolved_at": _iso(), "resolved_by": admin["id"]}})
    if not r.matched_count: raise HTTPException(404, "No open alert")
    return {"ok": True}

def _aware(dt): return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
def _report_open(b): return bool(b.get("report")) and (b["report"].get("status") or "open") == "open"
BOOKING_REPORT_HOURS = 24

@api.post("/dates/report/{bid}")
async def booking_report(bid: str, req: InviteReportReq, user=Depends(get_current_user)):
    b = await db.date_bookings.find_one({"id": bid}, {"_id": 0})
    if not b: raise HTTPException(404, "Not found")
    if user["id"] not in (b["from_id"], b["to_id"]): raise HTTPException(403, "No access")
    if b["status"] not in ("accepted", "confirmed"): raise HTTPException(400, "Report not available")
    if _report_open(b): raise HTTPException(409, "ALREADY_REPORTED")
    sched = _aware(_pdt(b.get("scheduled_at")) or _now())
    if not (sched <= _now() <= sched + timedelta(hours=BOOKING_REPORT_HOURS)): raise HTTPException(400, "REPORT_WINDOW_CLOSED")
    if len((req.details or "").strip()) < 10: raise HTTPException(400, "Please describe what happened (min 10 chars)")
    role = "inviter" if user["id"] == b["from_id"] else "recipient"
    rep = {"reporter_id": user["id"], "reporter_role": role, "reasons": req.reasons, "details": req.details.strip(), "evidence": req.evidence,
           "photos": await _report_photos(user, req.photos), "status": "open", "created_at": _iso(),
           "reply_deadline": _iso(_now() + timedelta(hours=REPORT_REPLY_HOURS))}
    await db.date_bookings.update_one({"id": bid}, {"$set": {"report": rep}})
    other = b["to_id"] if user["id"] == b["from_id"] else b["from_id"]
    await notify(other, "date_request", "Your date was reported — reply within 24h", _reported_msg(role), {"booking_id": bid}, email=True, link=DATES_LINK, cta="Reply now")
    for aid in await _admin_ids():
        await notify(aid, "date_request", "Date report submitted", f"A booked date ({bid}) was reported. Review the case in admin.", {"booking_id": bid}, email=True, link=f"{PUBLIC_APP_URL}/admin", cta="View Case")
    return {"ok": True, "reported": True}

@api.get("/admin/booking-reports")
async def admin_booking_reports(admin=Depends(get_admin)):
    docs = await db.date_bookings.find({"report": {"$ne": None, "$exists": True}}, {"_id": 0}).sort("report.created_at", -1).to_list(300)
    for b in docs: b["inviter"], b["recipient"] = await _mini(b["from_id"]), await _mini(b["to_id"])
    return {"bookings": docs}

@api.post("/admin/booking-reports/{bid}/resolve")
async def admin_booking_resolve(bid: str, action: str, admin=Depends(get_admin)):
    b = await db.date_bookings.find_one({"id": bid}, {"_id": 0})
    if not b or not _report_open(b): raise HTTPException(404, "No open report")
    now = _iso()
    if action == "refund_booker":
        if b["status"] not in ("accepted", "confirmed"): raise HTTPException(400, "Coins already settled")
        taxi = b.get("taxi") or {}
        tcoins = int(taxi.get("coins", 0)) if taxi.get("status") == "sent" else 0
        base = b["coins"] + tcoins
        await db.users.update_one({"id": b["from_id"]}, {"$inc": {"coins": base}})
        await db.users.update_one({"id": b["to_id"]}, {"$inc": {"escrow": -b["coins"], "withdrawable": -tcoins}})
        await db.date_bookings.update_one({"id": bid}, {"$set": {"status": "cancelled", "refund": base, "compensation": 0, "cancelled_at": now, "cancelled_by": "support",
            "report.status": "refunded", "report.resolved_at": now, **({"taxi.status": "refunded"} if tcoins else {})}})
        await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "date_report_refund", "from_id": b["to_id"], "to_id": b["from_id"], "cost": base, "net": base, "created_at": now})
        msg = f"Support reviewed the report for the date at {b.get('venue') or ''}. 🪙 {base} were refunded to the person who booked."
    elif action == "release_recipient":
        if b["status"] not in ("accepted", "confirmed"): raise HTTPException(400, "Coins already settled")
        await db.users.update_one({"id": b["to_id"]}, {"$inc": {"escrow": -b["coins"], "withdrawable": b["coins"]}})
        await db.date_bookings.update_one({"id": bid}, {"$set": {"status": "released", "released_net": b["coins"], "platform_cut": 0, "released_at": now,
            "report.status": "released", "report.resolved_at": now}})
        await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "date_report_release", "from_id": b["from_id"], "to_id": b["to_id"], "cost": b["coins"], "net": b["coins"], "created_at": now})
        msg = f"Support reviewed the report for the date at {b.get('venue') or ''}. All 🪙 {b['coins']} were released to the invited person."
    elif action == "dismiss":
        await db.date_bookings.update_one({"id": bid}, {"$set": {"report.status": "dismissed", "report.resolved_at": now}})
        msg = f"Support reviewed the report for the date at {b.get('venue') or ''} and closed it. The date continues as normal."
    else: raise HTTPException(400, "Unknown action")
    for uid in (b["from_id"], b["to_id"]):
        await notify(uid, "date_request", "Date report resolved", msg, {"booking_id": bid}, email=True, link=DATES_LINK, cta="View Date")
    return {"ok": True}

# ---------- Taxi gift for a date ----------
class TaxiRequestReq(BaseModel):
    coins: int

@api.post("/dates/taxi/request/{bid}")
async def request_taxi(bid: str, req: TaxiRequestReq, user=Depends(get_current_user)):
    b = await db.date_bookings.find_one({"id": bid})
    if not b: raise HTTPException(404, "Not found")
    if b["to_id"] != user["id"]: raise HTTPException(403, "Only the invited person can request a taxi")
    if b["status"] not in ("escrow", "accepted", "confirmed"): raise HTTPException(400, "Cannot request taxi")
    if req.coins < 1: raise HTTPException(400, "Invalid amount")
    if (b.get("taxi") or {}).get("status") == "pending": raise HTTPException(400, "TAXI_PENDING")
    now = datetime.now(timezone.utc).isoformat()
    taxi = {"coins": int(req.coins), "status": "pending", "requested_at": now}
    await db.date_bookings.update_one({"id": bid}, {"$set": {"taxi": taxi}})
    await notify(b["from_id"], "date_taxi", "Taxi requested 🚕", f"{user['name']} asks for 🪙 {req.coins} for a taxi to your date at {b['venue']}. Send it in Dates.", {"booking_id": bid, "coins": req.coins}, email=True)
    return {"ok": True, "taxi": taxi}

@api.post("/dates/taxi/send/{bid}")
async def send_taxi(bid: str, user=Depends(get_current_user)):
    b = await db.date_bookings.find_one({"id": bid})
    if not b: raise HTTPException(404, "Not found")
    if b["from_id"] != user["id"]: raise HTTPException(403, "Only the booker can send a taxi")
    if b["status"] not in ("escrow", "accepted", "confirmed"): raise HTTPException(400, "Cannot send taxi")
    taxi = b.get("taxi")
    if not taxi or taxi.get("status") != "pending": raise HTTPException(400, "No pending taxi request")
    coins = int(taxi["coins"])
    if (user.get("coins", 0) + user.get("withdrawable", 0)) < coins: raise HTTPException(400, "Insufficient coins")
    now = datetime.now(timezone.utc).isoformat()
    commission = round(coins * (await get_settings())["commission"], 2)
    await spend_coins(user["id"], coins)
    await db.users.update_one({"id": b["to_id"]}, {"$inc": {"withdrawable": coins}})
    await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "gift", "from_id": user["id"], "to_id": b["to_id"],
                                      "gift_id": "taxi", "gift_icon": "🚕", "cost": coins, "commission": commission, "net": coins, "message": "Taxi", "created_at": now})
    set_fields = {"taxi.status": "sent", "taxi.sent_at": now}
    auto_confirmed = False
    if b["status"] in ("escrow", "accepted"):
        try: sched = datetime.fromisoformat(b["scheduled_at"].replace("Z", "+00:00"))
        except Exception: sched = datetime.now(timezone.utc)
        if sched.tzinfo is None: sched = sched.replace(tzinfo=timezone.utc)
        release_at = max(sched + timedelta(days=1), datetime.now(timezone.utc)).isoformat()
        set_fields.update({"status": "confirmed", "confirmed_at": now, "release_at": release_at, "auto_confirmed": True})
        auto_confirmed = True
    await db.date_bookings.update_one({"id": bid}, {"$set": set_fields})
    recv_msg = f"{user['name']} sent you 🪙 {coins} for a taxi to your date at {b['venue']}."
    if auto_confirmed: recv_msg += " The date is now confirmed."
    await notify(b["to_id"], "date_taxi", "🚕 Taxi received", recv_msg, {"booking_id": bid, "coins": coins}, email=True)
    if auto_confirmed:
        await notify(user["id"], "date_taxi", "Date confirmed ✅", f"Your taxi auto-confirmed the date at {b['venue']}. If you cancel, all taxi + date coins are refunded to you.", {"booking_id": bid}, email=True)
    return {"ok": True, "coins": coins, "auto_confirmed": auto_confirmed}

@api.post("/dates/taxi/decline/{bid}")
async def decline_taxi(bid: str, user=Depends(get_current_user)):
    b = await db.date_bookings.find_one({"id": bid})
    if not b: raise HTTPException(404, "Not found")
    if b["from_id"] != user["id"]: raise HTTPException(403, "Only the booker can decline")
    taxi = b.get("taxi")
    if not taxi or taxi.get("status") != "pending": raise HTTPException(400, "No pending taxi request")
    now = datetime.now(timezone.utc).isoformat()
    await db.date_bookings.update_one({"id": bid}, {"$set": {"taxi.status": "declined", "taxi.declined_at": now}})
    await notify(b["to_id"], "date_taxi", "Taxi request declined", f"{user['name']} declined your taxi request for the date at {b['venue']}.", {"booking_id": bid})
    return {"ok": True}

# ---------- Share meeting location (host shares address when they host) ----------
class MeetLocationReq(BaseModel):
    address_confirmed: bool = False
    address: str
    city: Optional[str] = ""
    postal_code: Optional[str] = ""
    country: Optional[str] = ""
    lat: Optional[float] = None
    lng: Optional[float] = None

@api.post("/dates/meet-location/{bid}")
async def share_meet_location(bid: str, req: MeetLocationReq, user=Depends(get_current_user)):
    b = await db.date_bookings.find_one({"id": bid})
    if not b: raise HTTPException(404, "Not found")
    if b["to_id"] != user["id"]: raise HTTPException(403, "Only the host can share the meeting location")
    if b["status"] not in ("escrow", "accepted", "confirmed"): raise HTTPException(400, "Cannot share location")
    geo = await _geocode_address(req.address, req.city, req.postal_code, req.country, venue=None, confirmed=req.address_confirmed)
    meet = {"address": req.address.strip(), "city": (req.city or "").strip(), "postal_code": (req.postal_code or "").strip(),
            "country": (req.country or "").strip(), "lat": geo["lat"], "lng": geo["lng"], "unverified": geo["unverified"], "shared_at": datetime.now(timezone.utc).isoformat()}
    await db.date_bookings.update_one({"id": bid}, {"$set": {"meet": meet}})
    await notify(b["from_id"], "date_request", "📍 Meeting location shared", f"{user['name']} shared the meeting address for your VIP date. See it in Dates.", {"booking_id": bid}, email=True)
    return {"ok": True, "meet": meet}

# ---------- Wallet / Withdraw ----------
@api.get("/wallet")
async def wallet(user=Depends(get_current_user)):
    txs = await db.transactions.find({"$or": [{"from_id": user["id"]}, {"to_id": user["id"]}]}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    withdrawals = await db.withdrawals.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    acct = await db.payout_accounts.find_one({"user_id": user["id"]}, {"_id": 0})
    s = await get_settings()
    return {"coins": user["coins"], "escrow": user.get("escrow", 0), "withdrawable": user.get("withdrawable", 0),
            "transactions": txs, "withdrawals": withdrawals, "payout_account": acct, "withdraw_commission": s["commission"], "coins_per_usd": s["coins_per_usd"], "min_withdraw_usd": s["min_withdraw_usd"], "is_admin": is_admin(user)}

@api.get("/wallet/payout-account")
async def get_payout_account(user=Depends(get_current_user)):
    return await db.payout_accounts.find_one({"user_id": user["id"]}, {"_id": 0})

@api.post("/wallet/payout-account")
async def submit_payout_account(req: PayoutAccountReq, user=Depends(get_current_user)):
    iban = req.iban.replace(" ", "").upper()
    if len(iban) < 8: raise HTTPException(400, "Invalid account number")
    data = {k: (v.strip() if isinstance(v, str) else v) for k, v in req.model_dump().items()}
    required = [k for k in data if k not in ("routing_number", "document_path", "bank_statement_path", "proof_of_address_path")]
    missing = [k for k in required if not data[k]]
    if missing: raise HTTPException(400, f"Missing: {', '.join(missing)}")
    if "@" not in data["recipient_email"]: raise HTTPException(400, "Invalid recipient email")
    if not data.get("bank_statement_path"): raise HTTPException(400, "BANK_STATEMENT_REQUIRED")
    if not data.get("proof_of_address_path"): raise HTTPException(400, "PROOF_OF_ADDRESS_REQUIRED")
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "user_name": user["name"], "user_email": user["email"],
           **data, "iban": iban, "status": "pending", "reason": "",
           "submitted_at": datetime.now(timezone.utc).isoformat(), "verified_at": None}
    await db.payout_accounts.replace_one({"user_id": user["id"]}, doc, upsert=True)
    # Send the recipient/bank details + documents to the admin inbox for approval.
    try:
        await notify_admin_email(
            subject="Payout approval · GiftsDates",
            title="Payout account pending approval 🏦",
            body=(f"(payout approval) {user.get('name')} ({user.get('email')}) submitted bank/recipient details, "
                  f"a bank statement and a proof of address. Open the Admin panel to review the documents and "
                  f"press Approve or Decline. Recipient: {data.get('holder_name')} · Bank: {data.get('bank_name')} ····{iban[-4:]}."),
            link=f"{PUBLIC_APP_URL}/admin",
            cta="Review Payout Documents",
            note="payout approval",
        )
    except Exception as e:
        logging.error(f"admin payout email failed: {e}")
    return {k: v for k, v in doc.items() if k != "_id"}

@api.post("/wallet/payout-document")
async def upload_payout_document(kind: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    if kind not in ("bank_statement", "proof_of_address"):
        raise HTTPException(400, "kind must be bank_statement or proof_of_address")
    ct = (file.content_type or "")
    if not (ct.startswith("image/") or ct == "application/pdf"):
        raise HTTPException(400, "Only images or PDF allowed")
    ext = (file.filename.split(".")[-1] if "." in (file.filename or "") else "jpg").lower()
    path = f"{APP_NAME}/payout/{user['id']}/{kind}-{uuid.uuid4()}.{ext}"
    result = put_object(path, await file.read(), ct)
    await db.files.insert_one({"id": str(uuid.uuid4()), "storage_path": result["path"], "user_id": user["id"], "private": True,
                               "content_type": ct, "size": result["size"], "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat()})
    return {"path": result["path"], "kind": kind}

@api.post("/wallet/withdraw")
async def withdraw(req: WithdrawReq, user=Depends(get_current_user)):
    # withdrawable is in coins; coins_per_usd (default 10 coins = $1); commission withheld here
    if req.amount <= 0: raise HTTPException(400, "Invalid amount")
    if not user.get("verified"): raise HTTPException(400, "IDENTITY_NOT_VERIFIED")
    if user.get("withdrawable", 0) < req.amount: raise HTTPException(400, "Insufficient withdrawable balance")
    acct = await db.payout_accounts.find_one({"user_id": user["id"]})
    if not acct or acct["status"] != "verified": raise HTTPException(400, "Bank account not verified")
    s = await get_settings()
    fee = round(req.amount * s["commission"], 2)
    net = round(req.amount - fee, 2)
    usd = round(net / s["coins_per_usd"], 2)
    if usd < s["min_withdraw_usd"]: raise HTTPException(400, f"MIN_WITHDRAW:{s['min_withdraw_usd']}")
    now = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"id": user["id"]}, {"$inc": {"withdrawable": -req.amount}})
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "amount": req.amount, "fee": fee, "net": net, "usd": usd, "rate": s["coins_per_usd"],
           "method": "bank", "destination": f"{acct['bank_name']} ····{acct['iban'][-4:]}", "status": "pending", "created_at": now}
    await db.withdrawals.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}

# ---------- Admin ----------
class GiftItem(BaseModel):
    id: str
    name_key: str
    icon: str
    cost: int

class CoinPackageItem(BaseModel):
    id: str
    coins: int
    amount: float
    bonus: int = 0
    name: str

class SettingsReq(BaseModel):
    gifts: List[GiftItem]
    coin_packages: List[CoinPackageItem]
    premium_amount: float
    video_rate: int
    date_min_coins: int
    referral_bonus: int
    commission: float
    free_daily_likes: int = FREE_DAILY_LIKES
    custom_coins_per_usd: int = CUSTOM_COINS_PER_USD
    custom_bonus_pct: float = CUSTOM_BONUS_PCT
    custom_min_usd: float = CUSTOM_MIN_USD
    coins_per_usd: int = COINS_PER_USD
    min_withdraw_usd: float = MIN_WITHDRAW_USD
    referral_package_id: Optional[str] = "popular"
    cancel_refund_pct: float = CANCEL_REFUND_PCT
    gift_auto_match_coins: int = 100

@api.get("/admin/settings")
async def admin_get_settings(admin=Depends(get_admin)):
    return await get_settings()

@api.put("/admin/settings")
async def admin_put_settings(req: SettingsReq, admin=Depends(get_admin)):
    if not (0 <= req.commission < 1): raise HTTPException(400, "Commission must be 0–0.99")
    if any(g.cost <= 0 for g in req.gifts) or any(p.amount <= 0 or p.coins <= 0 for p in req.coin_packages): raise HTTPException(400, "Values must be positive")
    doc = {"id": "pricing", **req.model_dump(), "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": admin["id"]}
    await db.settings.replace_one({"id": "pricing"}, doc, upsert=True)
    return await get_settings()

@api.get("/admin/payout-accounts")
async def admin_payout_accounts(status: str = "pending", admin=Depends(get_admin)):
    q = {} if status == "all" else {"status": status}
    return await db.payout_accounts.find(q, {"_id": 0}).sort("submitted_at", -1).to_list(200)

@api.post("/admin/payout-accounts/{user_id}/verify")
async def admin_verify_account(user_id: str, req: AdminVerifyReq, admin=Depends(get_admin)):
    acct = await db.payout_accounts.find_one({"user_id": user_id})
    if not acct: raise HTTPException(404, "Not found")
    status = "verified" if req.approve else "rejected"
    await db.payout_accounts.update_one({"user_id": user_id}, {"$set": {"status": status, "reason": req.reason or "", "verified_at": datetime.now(timezone.utc).isoformat(), "verified_by": admin["id"]}})
    await notify(user_id, "payout_account", "Bank account verified ✅" if req.approve else "Bank account rejected",
                 "You can now withdraw your earnings." if req.approve else (req.reason or "Please re-submit your bank details."), email=True)
    return {"status": status}

@api.get("/admin/withdrawals")
async def admin_withdrawals(admin=Depends(get_admin)):
    return await db.withdrawals.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)

@api.post("/admin/withdrawals/{wid}/{action}")
async def admin_withdrawal_action(wid: str, action: str, admin=Depends(get_admin)):
    if action not in ("paid", "rejected"): raise HTTPException(400, "Bad action")
    w = await db.withdrawals.find_one({"id": wid})
    if not w or w["status"] != "pending": raise HTTPException(400, "Not pending")
    if action == "rejected":
        await db.users.update_one({"id": w["user_id"]}, {"$inc": {"withdrawable": w["amount"]}})
    await db.withdrawals.update_one({"id": wid}, {"$set": {"status": action, "processed_at": datetime.now(timezone.utc).isoformat()}})
    await notify(w["user_id"], "withdrawal", f"Withdrawal {action}", f"${w['usd']} → {w['destination']}", email=True)
    return {"status": action}

# ---------- Admin: support ----------
class SupportHoursRow(BaseModel):
    day: int
    enabled: bool = False
    open: str = "09:00"
    close: str = "18:00"

class SupportSettingsReq(BaseModel):
    agent_enabled: bool = True
    timezone: str = "UTC"
    hours: List[SupportHoursRow]
    offline_message: str
    welcome_message: str

@api.get("/admin/support/settings")
async def admin_get_support(admin=Depends(get_admin)):
    return await get_support_settings()

@api.put("/admin/support/settings")
async def admin_put_support(req: SupportSettingsReq, admin=Depends(get_admin)):
    try:
        ZoneInfo(req.timezone)
    except Exception:
        raise HTTPException(400, "INVALID_TIMEZONE")
    doc = {"id": "support", **req.model_dump(), "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.settings.replace_one({"id": "support"}, doc, upsert=True)
    return await get_support_settings()

@api.get("/admin/support/tickets")
async def admin_support_tickets(status: str = "open", admin=Depends(get_admin)):
    q = {} if status == "all" else {"status": status}
    return await db.support_tickets.find(q, {"_id": 0}).sort("created_at", -1).to_list(300)

@api.post("/admin/support/tickets/{tid}/resolve")
async def admin_resolve_ticket(tid: str, admin=Depends(get_admin)):
    r = await db.support_tickets.find_one({"id": tid})
    if not r:
        raise HTTPException(404, "Not found")
    await db.support_tickets.update_one({"id": tid}, {"$set": {"status": "resolved",
                                        "resolved_at": datetime.now(timezone.utc).isoformat(), "resolved_by": admin["id"]}})
    return {"status": "resolved"}


# ---------- Stripe checkout ----------
class VipProfileReq(BaseModel):
    services: List[str] = []
    services_note: str = ""
    price_hour: int = 0
    price_2h: int = 0
    price_3h: int = 0
    price_night: int = 0
    price_extra_hour: int = EXTRA_HOUR_MIN_COINS
    places: List[str] = []
    client_wants: str = ""
    availability: List[dict] = []
    published: bool = True
    nickname: str = ""
    post_mode: str = "together"  # "together" = attached to main profile | "separate" = standalone under nickname
    # Independent anonymous details used when the VIP profile is posted "separately"
    age: Optional[int] = None
    city: str = ""
    country: str = ""
    gender: str = ""
    genders: List[str] = []
    bio: str = ""
    # Standalone anonymous appearance details
    height: Optional[int] = None
    weight: Optional[int] = None
    eye_color: str = ""
    hair_color: str = ""
    intimate_haircut: str = ""
    breast_size: List[str] = []
    dick_size: str = ""
    dick_girth: str = ""
    show_on_main: bool = True  # when "separate", whether to also show a VIP hint on the main profile

@api.get("/vip/catalog")
async def vip_catalog(user=Depends(get_current_user)):
    return {"services": VIP_SERVICES, "places": VIP_PLACES}

@api.put("/vip/profile")
async def put_vip_profile(req: VipProfileReq, user=Depends(get_current_user)):
    # Anyone can fill in and save their VIP profile; publishing it requires an active VIP subscription
    can_publish = is_vip(user)
    services = [s for s in req.services if s in VIP_SERVICE_SET][:80]
    places = [p for p in req.places if p in VIP_PLACES]
    slots = []
    for a in (req.availability or [])[:300]:
        d = str(a.get("date", ""))[:10]; f = str(a.get("from", "")); tt = str(a.get("to", ""))
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) and re.fullmatch(r"\d{2}:\d{2}", f) and re.fullmatch(r"\d{2}:\d{2}", tt) and f < tt:
            slots.append({"date": d, "from": f, "to": tt})
    slots.sort(key=lambda x: (x["date"], x["from"]))
    post_mode = req.post_mode if req.post_mode in ("together", "separate") else "together"
    _genders = [g for g in (req.genders or []) if g in VALID_GENDERS]
    if not _genders and req.gender in VALID_GENDERS:
        _genders = [req.gender]
    _age = None
    if req.age:
        try: _age = max(18, min(99, int(req.age)))
        except Exception: _age = None
    _height = None
    if req.height:
        try: _height = max(100, min(250, int(req.height)))
        except Exception: _height = None
    _weight = None
    if req.weight:
        try: _weight = max(30, min(400, int(req.weight)))
        except Exception: _weight = None
    vip = {"services": services,
           "services_note": (req.services_note or "").strip()[:500],
           "prices": {"hour": max(EXTRA_HOUR_MIN_COINS, req.price_hour), "h2": max(EXTRA_HOUR_MIN_COINS, req.price_2h), "h3": max(EXTRA_HOUR_MIN_COINS, req.price_3h), "night": max(0, req.price_night), "extra": max(EXTRA_HOUR_MIN_COINS, req.price_extra_hour or 0)},
           "places": places, "client_wants": (req.client_wants or "").strip()[:1000],
           "nickname": (req.nickname or "").strip()[:40], "post_mode": post_mode,
           "age": _age, "city": (req.city or "").strip()[:80], "country": (req.country or "").strip()[:80],
           "gender": _genders[0] if _genders else "",
           "genders": _genders,
           "height": _height, "weight": _weight,
           "eye_color": (req.eye_color or "").strip()[:60],
           "hair_color": (req.hair_color or "").strip()[:60],
           "intimate_haircut": (req.intimate_haircut or "").strip()[:60],
           "breast_size": [s.strip()[:60] for s in (req.breast_size or []) if isinstance(s, str) and s.strip()][:12],
           "dick_size": (req.dick_size or "").strip()[:60],
           "dick_girth": (req.dick_girth or "").strip()[:60],
           "bio": (req.bio or "").strip()[:1000], "show_on_main": bool(req.show_on_main),
           "availability": slots, "published": bool(req.published) and can_publish, "updated_at": datetime.now(timezone.utc).isoformat()}
    # preserve previously uploaded photos (managed by separate photo endpoints)
    existing = await db.users.find_one({"id": user["id"]}, {"_id": 0, "vip.photos": 1, "vip.private_photos": 1, "vip.public_id": 1})
    if existing and existing.get("vip", {}).get("photos"):
        vip["photos"] = existing["vip"]["photos"]
    if existing and existing.get("vip", {}).get("private_photos"):
        vip["private_photos"] = existing["vip"]["private_photos"]
    # stable public identifier for the standalone (separate) VIP listing — never reveals the real user id
    vip["public_id"] = (existing or {}).get("vip", {}).get("public_id") or ("v" + secrets.token_hex(8))
    await db.users.update_one({"id": user["id"]}, {"$set": {"vip": vip}})
    return {"saved": True, "vip": vip, "can_publish": can_publish}

@api.get("/vip/profile/{uid}")
async def get_vip_profile(uid: str, preview: Optional[str] = None, user=Depends(get_current_user)):
    proj = {"_id": 0, "id": 1, "name": 1, "city": 1, "country": 1, "age": 1, "gender": 1, "vip": 1}
    owner = await db.users.find_one({"id": uid}, proj)
    accessed_by_uid = bool(owner)
    if not owner:
        owner = await db.users.find_one({"vip.public_id": uid}, proj)
    if not owner or not owner.get("vip"):
        raise HTTPException(404, "No VIP profile")
    vip = owner["vip"]
    real_owner = owner["id"] == user["id"]
    # "preview=nonvip" lets the owner see exactly what a non-VIP / non-premium visitor sees
    # "preview=vip" lets the owner see the fully unlocked view as a paying VIP/premium member sees it
    force_guest = preview == "nonvip"
    force_vip = preview == "vip"
    is_owner = real_owner and not force_guest and not force_vip
    eff_premium = (is_premium(user) or force_vip) and not force_guest
    # Per-profile one-time unlock: a non-premium visitor who paid coins to unlock this member's VIP section
    eff_unlocked = False
    if not is_owner and not eff_premium and not force_guest:
        _u = await db.vip_unlocks.find_one({"viewer_id": user["id"], "owner_id": owner["id"]})
        eff_unlocked = bool(_u)
    separate = vip.get("post_mode") == "separate"
    # Unpublished VIP profiles are only visible to their owner (allow the owner's own previews)
    if vip.get("published") is False and not is_owner and not real_owner:
        raise HTTPException(404, "No VIP profile")
    # A separate listing accessed via the real user id (from the main profile page) is only
    # shown when the owner chose to reveal a VIP hint on their main profile
    if separate and accessed_by_uid and not is_owner and not real_owner and not vip.get("show_on_main", True):
        raise HTTPException(404, "No VIP profile")
    # Display identity: separate listings show the nickname + independent details, never the real name
    if separate:
        display_name = (vip.get("nickname") or "").strip() or "VIP"
        display_city = vip.get("city") or owner.get("city")
        display_country = vip.get("country") or owner.get("country")
        display_age = vip.get("age") or owner.get("age")
        display_gender = vip.get("gender") or owner.get("gender")
        display_genders = vip.get("genders") or ([vip.get("gender")] if vip.get("gender") else ([owner.get("gender")] if owner.get("gender") else []))
    else:
        display_name = owner.get("name")
        display_city = owner.get("city")
        display_country = owner.get("country")
        display_age = owner.get("age")
        display_gender = owner.get("gender")
        display_genders = [owner.get("gender")] if owner.get("gender") else []
    # target used for booking: public_id for separate listings so the real id stays hidden
    target_id = vip.get("public_id") if (separate and not is_owner) else owner["id"]
    if is_owner or eff_premium or eff_unlocked:
        return {"locked": False, "user_id": target_id, "name": display_name,
                "real_name": (None if (separate and not is_owner) else owner.get("name")),
                "nickname": vip.get("nickname") or "", "post_mode": vip.get("post_mode") or "together",
                "separate": separate, "show_on_main": vip.get("show_on_main", True),
                "city": display_city, "country": display_country, "age": display_age, "gender": display_gender, "genders": display_genders,
                "vip": vip, "is_owner": is_owner, "unlocked_via_coins": eff_unlocked}
    _p = vip.get("photos") or []
    return {"locked": True, "teaser_photo": _p[0] if _p else None, "name": display_name if separate else None,
            "post_mode": vip.get("post_mode") or "together", "separate": separate,
            "city": display_city if separate else None, "age": display_age if separate else None,
            "services_count": len(vip.get("services") or []),
            "unlock_price": VIP_UNLOCK_COINS, "can_unlock": (not real_owner)}

@api.post("/vip/unlock/{uid}")
async def vip_unlock(uid: str, user=Depends(get_current_user)):
    """One-time unlock of a single member's private VIP section for VIP_UNLOCK_COINS coins.
    The owner earns 50% (credited to withdrawable); the platform keeps the other 50%. Premium/VIP members never need this."""
    owner = await db.users.find_one({"id": uid})
    if not owner:
        owner = await db.users.find_one({"vip.public_id": uid})
    if not owner or not owner.get("vip"):
        raise HTTPException(404, "No VIP profile")
    vip = owner["vip"]
    if vip.get("published") is False:
        raise HTTPException(404, "No VIP profile")
    if owner["id"] == user["id"]:
        raise HTTPException(400, "CANNOT_UNLOCK_SELF")
    # Premium/VIP already have unlimited access
    if is_premium(user):
        return {"unlocked": True, "already": True}
    existing = await db.vip_unlocks.find_one({"viewer_id": user["id"], "owner_id": owner["id"]})
    if existing:
        return {"unlocked": True, "already": True}
    price = VIP_UNLOCK_COINS
    if (int(user.get("coins", 0) or 0) + float(user.get("withdrawable", 0) or 0)) < price:
        raise HTTPException(400, "Insufficient coins")
    await spend_coins(user["id"], price)
    await record_txn(user["id"], "vip_unlock", -price, description="Unlocked a private VIP section")
    # 50/50 split: half the coins go to the owner (withdrawable), half is kept by the platform
    owner_share = price // 2
    platform_share = price - owner_share
    await db.users.update_one({"id": owner["id"]}, {"$inc": {"withdrawable": owner_share}})
    await record_txn(owner["id"], "vip_unlock_earned", owner_share, description="A member unlocked your private VIP section (50% share)")
    await db.vip_unlocks.insert_one({"id": str(uuid.uuid4()), "viewer_id": user["id"], "owner_id": owner["id"],
                                     "coins": price, "owner_share": owner_share, "platform_share": platform_share,
                                     "created_at": datetime.now(timezone.utc).isoformat()})
    await notify(owner["id"], "vip_unlock", "🔓 VIP content unlocked",
                 f"A member unlocked your private VIP section · you earned 🪙 {owner_share} (50%).", {}, email=False)
    return {"unlocked": True, "coins_spent": price, "owner_share": owner_share, "platform_share": platform_share}

def vip_extra_price(target: dict) -> int:
    return max(EXTRA_HOUR_MIN_COINS, int(((target.get("vip") or {}).get("prices") or {}).get("extra") or 0))

VIP_RATE_KEYS = {1: "hour", 2: "h2", 3: "h3"}

def vip_rates(target: dict) -> dict:
    p = (target.get("vip") or {}).get("prices") or {}
    return {h: max(EXTRA_HOUR_MIN_COINS, int(p.get(k) or 0)) for h, k in VIP_RATE_KEYS.items()}

def vip_total(target: dict, length: int, extra_hours: int) -> int:
    """Coins for a VIP date: the VIP's own 1h/2h/3h rate + extra hours at the VIP's extra-hour rate."""
    if length not in VIP_RATE_KEYS or extra_hours < 0:
        raise HTTPException(400, "BAD_DURATION")
    return vip_rates(target)[length] + extra_hours * vip_extra_price(target)

@api.post("/vip/book")
async def vip_book(req: DateBookingReq, user=Depends(get_current_user)):
    if req.coins <= 0 or req.extra_hours < 0:
        raise HTTPException(400, "Invalid amount")
    target = await db.users.find_one({"id": req.target_id})
    if not target:
        target = await db.users.find_one({"vip.public_id": req.target_id})
    if not target:
        raise HTTPException(404, "Recipient not found")
    extra_coins = req.extra_hours * vip_extra_price(target)
    if req.place in ("your", "other"):
        await _apply_geo(req)
    if req.place == "own":
        for k, v in _booking_location(target, "own", req).items():
            setattr(req, k, v if v is not None else ("" if k not in ("lat", "lng") else None))
        req.city = req.city or target.get("city") or "-"
    if req.vip_length:
        req.coins = vip_total(target, req.vip_length, req.extra_hours)
    else:
        req.coins += extra_coins
    if (user.get("coins", 0) + user.get("withdrawable", 0)) < req.coins:
        raise HTTPException(400, "Insufficient coins")
    dur_min = 60 * ((req.vip_length or 1) + req.extra_hours) if req.vip_length else None
    sched_dt = _pdt(req.scheduled_at)
    if sched_dt and (sched_dt if sched_dt.tzinfo else sched_dt.replace(tzinfo=timezone.utc)) <= datetime.now(timezone.utc) - timedelta(hours=14):
        raise HTTPException(400, "TIME_PASSED")
    recipient_id = target["id"]
    if recipient_id == user["id"]:
        raise HTTPException(400, "CANNOT_BOOK_SELF")
    now = datetime.now(timezone.utc).isoformat()
    bid = str(uuid.uuid4())
    doc = {"id": bid, "from_id": user["id"], "to_id": recipient_id, "venue": req.venue or "VIP", "city": req.city or "-",
           "address": (req.address or "").strip(), "postal_code": (req.postal_code or "").strip(), "country": (req.country or "").strip(),
           "lat": req.lat, "lng": req.lng, "unverified": bool(req.unverified), "place": req.place, "scheduled_at": req.scheduled_at,
           "coins": req.coins, "extra_hours": req.extra_hours, "extra_coins": extra_coins,
           **({"duration_min": dur_min, "vip_length": req.vip_length, "local_day": req.scheduled_at[:10],
               "slot_from": req.scheduled_at[11:16], "slot_to": _min_to_hm(_hm_to_min(req.scheduled_at[11:16]) + dur_min)} if dur_min else {}),
           "status": "escrow", "photo_url": None, "release_at": None, "vip": True, "created_at": now}
    await spend_coins(user["id"], req.coins)
    await db.users.update_one({"id": recipient_id}, {"$inc": {"escrow": req.coins}})
    await db.date_bookings.insert_one(doc)
    await notify(recipient_id, "date_request", "New VIP booking 📅", f"{user['name']} booked you · 🪙 {req.coins}. Manage in Dates.", {"booking_id": bid}, email=True)
    return {"booking_id": bid, "status": "escrow"}

# ==================== VIP Scheduling (Availability Calendar + Bookings) ====================
# Separate slot-based booking layer for VIP profiles with a 15-minute buffer, statuses and
# double-booking protection. Times are stored as HH:MM in the VIP's own local timezone.
VIP_SCHED_BUFFER = 15  # minutes locked before AND after each booking
VIP_SCHED_ACTIVE = ["pending", "confirmed"]  # statuses that hold/lock a slot

class VipAvailReq(BaseModel):
    date: str            # YYYY-MM-DD
    start: str           # HH:MM
    end: str             # HH:MM
    slot_len: int = 60   # minutes per bookable slot (VIP chooses)
    tz: Optional[str] = None

class VipSchedBookReq(BaseModel):
    address_confirmed: bool = False
    unverified: Optional[bool] = None
    date: str
    start: str
    end: str
    coins: int = 0
    length: int = 0  # base length in hours (1/2/3); hours beyond it are extra hours
    activity: Optional[str] = ""
    venue: Optional[str] = ""
    tz: Optional[str] = None
    place: Optional[str] = None  # own (VIP's place) | your | other
    address: str = ""
    city: str = ""
    postal_code: str = ""
    country: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None

LOC_KEYS = ("address", "city", "postal_code", "country", "lat", "lng", "unverified")

class VipOwnPlaceReq(BaseModel):
    address_confirmed: bool = False
    address: str = ""
    city: str = ""
    postal_code: str = ""
    country: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None

@api.get("/vip/own-place")
async def vip_get_own_place(user=Depends(get_current_user)):
    return user.get("vip_own_place") or {}

@api.put("/vip/own-place")
async def vip_set_own_place(req: VipOwnPlaceReq, user=Depends(get_current_user)):
    geo = await _geocode_address(req.address, req.city, req.postal_code, req.country, venue=None, confirmed=req.address_confirmed)
    loc = {k: (v.strip() if isinstance(v, str) else v) for k, v in req.model_dump().items() if k != "address_confirmed"}
    loc.update({"lat": geo["lat"], "lng": geo["lng"], "unverified": geo["unverified"]})
    await db.users.update_one({"id": user["id"]}, {"$set": {"vip_own_place": loc}})
    return loc

def _booking_location(target: dict, place: Optional[str], src) -> dict:
    """'own' = the VIP's saved address (filled automatically); otherwise the address the client entered."""
    if place == "own":
        op = target.get("vip_own_place") or {}
        return {k: op.get(k) for k in LOC_KEYS}
    return {k: getattr(src, k, None) for k in LOC_KEYS}

def _hide_own_address(b: dict, visible: bool) -> dict:
    """The VIP's home address is shown to the client only once the date is confirmed."""
    if b.get("place") == "own" and not visible:
        for k in LOC_KEYS:
            b.pop(k, None)
        b.pop("location", None)
        b["address_hidden"] = True
    return b

def _vs_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _vs_win(block):
    """Start/end minutes of a VIP availability block. End is extended past 1440
    when the window runs into the next day (end <= start)."""
    S = _hm_to_min(block["start"]); E = _hm_to_min(block["end"])
    if E <= S: E += 24 * 60
    return S, E

def _vs_norm(b, ref_start):
    """Normalise a booking's [start,end] HH:MM into the day-frame of a block whose start
    is ref_start. Times before ref_start (or an end <= start) roll into the next day."""
    bs, be = _hm_to_min(b["start"]), _hm_to_min(b["end"])
    if bs < ref_start: bs += 24 * 60
    if be <= bs: be += 24 * 60
    return bs, be

def _vs_conflict(ns: int, ne: int, existing: list, ref_start: int = 0) -> bool:
    """A candidate [ns,ne] conflicts if it comes within VIP_SCHED_BUFFER minutes of any
    existing active booking [bs,be]. This enforces a 15-min gap on both sides. Existing
    bookings are normalised so past-midnight windows compare correctly."""
    for b in existing:
        bs, be = _vs_norm(b, ref_start)
        if ns < be + VIP_SCHED_BUFFER and bs < ne + VIP_SCHED_BUFFER:
            return True
    return False

def _vs_gen_slots(block: dict, bookings: list):
    """Split a VIP availability block into consecutive slots of block.slot_len and tag each
    with a visual state: available / pending / confirmed / locked. Windows whose end is
    <= start run past midnight into the next day."""
    S, E = _vs_win(block)
    L = max(15, int(block.get("slot_len") or 60))
    out = []
    s = S
    while s + L <= E:
        e = s + L
        sf, st = _min_to_hm(s), _min_to_hm(e)
        exact = next((b for b in bookings if _vs_norm(b, S) == (s, e)), None)
        if exact and exact["status"] == "confirmed":
            state = "confirmed"
        elif exact and exact["status"] == "pending":
            state = "pending"
        elif _vs_conflict(s, e, bookings, ref_start=S):
            state = "locked"
        else:
            state = "available"
        out.append({"start": sf, "end": st, "state": state, "slot_len": L, "next_day": e > 24 * 60})
        s += L
    return out

VIP_DURATIONS = (60, 120, 180)

async def _vs_normal_locks(vip_id, date):
    """Normal-date lock windows (already include the 15-min buffer) of the VIP on a day."""
    u = await db.users.find_one({"id": vip_id}, {"_id": 0})
    return [b for b in (await _taken_blocks(u)).get(date, []) if b["reason"] != "cancelled"] if u else []

async def _vs_extra_checks(vip_id, date, cs, ce):
    if ce - cs < 60 or (ce - cs) % 60: raise HTTPException(400, "BAD_DURATION")
    for b in await _vs_normal_locks(vip_id, date):
        lf, lt = _hm_to_min(b["lock_from"]), _hm_to_min(b["lock_to"])
        if lt <= lf: lt += 24 * 60
        if cs < lt and lf < ce: raise HTTPException(409, "SLOT_TAKEN")

async def _vs_requester_card(uid: str) -> dict:
    u = await db.users.find_one({"id": uid}, {"_id": 0, "id": 1, "name": 1, "age": 1, "city": 1, "country": 1, "photos": 1})
    if not u:
        return {"id": uid, "name": "User", "photo": None}
    return {"id": u["id"], "name": u.get("name") or "User", "age": u.get("age"),
            "city": u.get("city"), "country": u.get("country"),
            "photo": (u.get("photos") or [None])[0]}

def _vs_clean(b: dict) -> dict:
    return {k: v for k, v in b.items() if k != "_id"}

async def _vs_autocomplete(vip_id: str):
    """Lazily mark confirmed bookings whose end time has passed as completed and release escrow."""
    now = datetime.now(timezone.utc)
    conf = await db.vip_sched.find({"vip_id": vip_id, "status": "confirmed"}).to_list(500)
    for b in conf:
        try:
            end_date = b["date"]
            if str(b.get("end", "")) <= str(b.get("start", "")):  # ends after midnight → next calendar day
                end_date = (datetime.fromisoformat(b["date"]) + timedelta(days=1)).strftime("%Y-%m-%d")
            end_dt = datetime.fromisoformat(f"{end_date}T{b['end']}:00+00:00")
        except Exception:
            continue
        if end_dt <= now:
            coins = int(b.get("coins") or 0)
            await db.vip_sched.update_one({"id": b["id"]}, {"$set": {"status": "completed", "completed_at": now.isoformat()}})
            if coins:
                await db.users.update_one({"id": vip_id}, {"$inc": {"escrow": -coins, "withdrawable": coins}})
            await notify(b["requester_id"], "vs_completed", "Date completed ✅",
                         f"Your date on {b['date']} at {b['start']} is marked completed.", {"booking_id": b["id"]})

@api.get("/vip/schedule/me")
async def vs_my_schedule(user=Depends(get_current_user)):
    """VIP dashboard: my availability blocks (today onward) + my incoming bookings grouped."""
    await _vs_autocomplete(user["id"])
    today = _vs_today()
    blocks = await db.vip_avail.find({"vip_id": user["id"], "date": {"$gte": today}}, {"_id": 0}).sort([("date", 1), ("start", 1)]).to_list(500)
    raw = await db.vip_sched.find({"vip_id": user["id"]}, {"_id": 0}).sort([("date", 1), ("start", 1)]).to_list(1000)
    bookings = []
    for b in raw:
        b["requester"] = await _vs_requester_card(b["requester_id"])
        bookings.append(b)
    pending = [b for b in bookings if b["status"] == "pending"]
    confirmed = [b for b in bookings if b["status"] in ("confirmed", "reported")]
    past = [b for b in bookings if b["status"] in ("completed", "declined", "cancelled")]
    return {"is_vip": is_vip(user), "blocks": blocks,
            "pending": pending, "confirmed": confirmed, "past": past,
            "pending_count": len(pending), "buffer": VIP_SCHED_BUFFER, "earnings": await _vs_earnings(user["id"], bookings)}

async def _vs_earnings(vip_id: str, bookings: list) -> dict:
    """Coins earned this calendar month (completed dates + late-cancel compensation) and coins still held in escrow."""
    now = datetime.now(timezone.utc)
    months = []
    y, m = now.year, now.month
    for _ in range(6):
        months.insert(0, f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    by = {k: 0 for k in months}
    def add(ts, n):
        k = str(ts or "")[:7]
        if k in by: by[k] += int(n or 0)
    for b in bookings:
        if b["status"] == "completed": add(b.get("completed_at"), b.get("coins"))
        elif b["status"] == "cancelled": add(b.get("cancelled_at"), b.get("compensation"))
    held = sum(int(b.get("coins") or 0) for b in bookings if b["status"] in ("pending", "confirmed", "reported"))
    async for d in db.date_bookings.find({"to_id": vip_id, "vip": True}, {"_id": 0, "status": 1, "coins": 1, "released_net": 1, "released_at": 1}):
        if d["status"] == "released": add(d.get("released_at"), d.get("released_net"))
        elif d["status"] in ("escrow", "accepted", "confirmed"): held += int(d.get("coins") or 0)
    return {"month": months[-1], "earned": by[months[-1]], "held": held, "by_month": [{"month": k, "earned": by[k]} for k in months]}

@api.get("/vip/schedule/pending-count")
async def vs_pending_count(user=Depends(get_current_user)):
    n = await db.vip_sched.count_documents({"vip_id": user["id"], "status": "pending"})
    return {"count": n}

@api.post("/vip/schedule/availability")
async def vs_add_availability(req: VipAvailReq, user=Depends(get_current_user)):
    if not is_vip(user):
        raise HTTPException(403, "VIP_REQUIRED")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", req.date):
        raise HTTPException(400, "Invalid date")
    if req.date < _vs_today():
        raise HTTPException(400, "DATE_PAST")
    s, e = _hm_to_min(req.start), _hm_to_min(req.end)
    if s == e:
        raise HTTPException(400, "BAD_WINDOW")
    span = e - s if e > s else e + 24 * 60 - s  # window may run past midnight into the next day
    slot_len = max(15, min(240, int(req.slot_len or 60)))
    if span < slot_len:
        raise HTTPException(400, "WINDOW_TOO_SHORT")
    if await _vs_overlaps(user["id"], req.date, s, span):
        raise HTTPException(400, "TIME_OVERLAP")
    doc = {"id": str(uuid.uuid4()), "vip_id": user["id"], "date": req.date,
           "start": _min_to_hm(s), "end": _min_to_hm(e), "slot_len": slot_len,
           "tz": (req.tz or user.get("timezone") or "UTC"),
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.vip_avail.insert_one(doc)
    return _vs_clean(doc)

@api.delete("/vip/schedule/availability")
async def vs_del_all_availability(date: Optional[str] = None, user=Depends(get_current_user)):
    """Remove every time window of the VIP (or of one day), except days that still have active bookings."""
    busy = await db.vip_sched.distinct("date", {"vip_id": user["id"], "status": {"$in": VIP_SCHED_ACTIVE}})
    if date and date in busy: raise HTTPException(400, "HAS_BOOKINGS")
    res = await db.vip_avail.delete_many({"vip_id": user["id"], "date": date if date else {"$nin": busy}})
    kept = await db.vip_avail.count_documents({"vip_id": user["id"]})
    return {"deleted": res.deleted_count, "kept": kept}

@api.delete("/vip/schedule/availability/{aid}")
async def vs_del_availability(aid: str, user=Depends(get_current_user)):
    blk = await db.vip_avail.find_one({"id": aid})
    if not blk:
        raise HTTPException(404, "Not found")
    if blk["vip_id"] != user["id"]:
        raise HTTPException(403, "Not owner")
    active = await db.vip_sched.find_one({"vip_id": user["id"], "date": blk["date"], "status": {"$in": VIP_SCHED_ACTIVE}})
    if active:
        raise HTTPException(400, "HAS_BOOKINGS")
    await db.vip_avail.delete_one({"id": aid})
    return {"ok": True}

@api.get("/vip/schedule/{vip_id}/slots")
async def vs_public_slots(vip_id: str, user=Depends(get_current_user)):
    """Public: bookable slots for a VIP, grouped by date, each tagged with a visual state."""
    target = await db.users.find_one({"id": vip_id}, {"_id": 0, "id": 1, "timezone": 1, "vip.prices": 1, "vip.places": 1})
    if not target:
        raise HTTPException(404, "Not found")
    await _vs_autocomplete(vip_id)
    today = _vs_today()
    blocks = await db.vip_avail.find({"vip_id": vip_id, "date": {"$gte": today}}, {"_id": 0}).sort([("date", 1), ("start", 1)]).to_list(500)
    active = await db.vip_sched.find({"vip_id": vip_id, "status": {"$in": VIP_SCHED_ACTIVE}},
                                     {"_id": 0, "date": 1, "start": 1, "end": 1, "status": 1}).to_list(1000)
    by_date = {}
    tz = blocks[0]["tz"] if blocks else (target.get("timezone") or "UTC")
    for blk in blocks:
        day_bk = [b for b in active if b["date"] == blk["date"]]
        slots = _vs_gen_slots(blk, day_bk)
        by_date.setdefault(blk["date"], {"date": blk["date"], "tz": blk.get("tz") or tz, "slots": []})
        by_date[blk["date"]]["slots"].extend(slots)
    for blk in blocks:
        dd = by_date[blk["date"]]
        dd.setdefault("windows", []).append({"from": blk["start"], "to": blk["end"]})
    for dd in by_date.values():
        taken = [{"from": b["start"], "to": b["end"], "status": b["status"],
                  "lock_from": _min_to_hm(max(0, _hm_to_min(b["start"]) - VIP_SCHED_BUFFER)),
                  "lock_to": _min_to_hm(_hm_to_min(b["end"]) + VIP_SCHED_BUFFER)}
                 for b in active if b["date"] == dd["date"]]
        taken += [{"from": b["from"], "to": b["to"], "status": "date", "lock_from": b["lock_from"], "lock_to": b["lock_to"]}
                  for b in await _vs_normal_locks(vip_id, dd["date"])]
        dd["taken"] = taken
    days = sorted(by_date.values(), key=lambda d: d["date"])
    return {"tz": tz, "buffer": VIP_SCHED_BUFFER, "durations": list(VIP_DURATIONS), "extra_hour_price": vip_extra_price(target),
            "rates": {str(h): c for h, c in vip_rates(target).items()}, "places": (target.get("vip") or {}).get("places") or [], "days": days}

@api.post("/vip/schedule/{vip_id}/book")
async def vs_book(vip_id: str, req: VipSchedBookReq, user=Depends(get_current_user)):
    if vip_id == user["id"]:
        raise HTTPException(400, "CANNOT_BOOK_SELF")
    target = await db.users.find_one({"id": vip_id})
    if not target:
        raise HTTPException(404, "Recipient not found")
    ns, ne = _hm_to_min(req.start), _hm_to_min(req.end)
    if ns == ne:
        raise HTTPException(400, "BAD_TIME")
    if req.place in ("your", "other"):
        await _apply_geo(req)
    # 1) the requested slot must fall inside one of the VIP's availability blocks (which may run past midnight)
    blocks = await db.vip_avail.find({"vip_id": vip_id, "date": req.date}, {"_id": 0}).to_list(200)
    ref_start = None; cs = ce = None
    for b in blocks:
        S, E = _vs_win(b)
        a = ns + 24 * 60 if ns < S else ns
        z = ne
        if z < S or z <= a: z += 24 * 60
        if S <= a and z <= E and a < z:
            ref_start, cs, ce = S, a, z
            break
    if ref_start is None:
        raise HTTPException(400, "TIME_UNAVAILABLE")
    # 2) re-validate against active bookings immediately before creating (double-booking guard)
    active = await db.vip_sched.find({"vip_id": vip_id, "date": req.date, "status": {"$in": VIP_SCHED_ACTIVE}},
                                     {"_id": 0, "start": 1, "end": 1}).to_list(500)
    if _vs_conflict(cs, ce, active, ref_start=ref_start):
        raise HTTPException(409, "SLOT_TAKEN")
    await _vs_extra_checks(vip_id, req.date, cs, ce)
    hours = (ce - cs) // 60
    length = req.length if req.length in VIP_RATE_KEYS else min(3, hours)
    if length > hours:
        raise HTTPException(400, "BAD_DURATION")
    extra_hours = hours - length
    extra_coins = extra_hours * vip_extra_price(target)
    req.coins = vip_total(target, length, extra_hours)
    if _vs_start_dt({"date": req.date, "start": req.start, "tz": req.tz or (blocks[0].get("tz") if blocks else "UTC")}) <= datetime.now(timezone.utc):
        raise HTTPException(400, "TIME_PASSED")
    if (user.get("coins", 0) + user.get("withdrawable", 0)) < req.coins:
        raise HTTPException(400, "Insufficient coins")
    now = datetime.now(timezone.utc)
    tz = req.tz or (blocks[0]["tz"] if blocks else (target.get("timezone") or "UTC"))
    bid = str(uuid.uuid4())
    doc = {"id": bid, "vip_id": vip_id, "requester_id": user["id"],
           "date": req.date, "start": req.start, "end": req.end,
           "lock_start": _min_to_hm(max(0, cs - VIP_SCHED_BUFFER)),
           "lock_end": _min_to_hm(ce + VIP_SCHED_BUFFER),
           "activity": (req.activity or "").strip(), "venue": (req.venue or "").strip(),
           "place": req.place if req.place in ("own", "your", "other") else None,
           "location": _booking_location(target, req.place, req),
           "coins": int(req.coins), "hours": hours, "length": length, "extra_hours": extra_hours, "extra_coins": extra_coins, "status": "pending", "tz": tz,
           "created_at": now.isoformat(), "scheduled_at": f"{req.date}T{req.start}:00"}
    # atomic-ish: guard collection has a unique index on (vip_id,date,start) for active rows via a lock doc
    await spend_coins(user["id"], req.coins)
    await db.users.update_one({"id": vip_id}, {"$inc": {"escrow": req.coins}})
    await db.vip_sched.insert_one(doc)
    await notify(vip_id, "vs_request", "New date request 📅",
                 f"{user['name']} requested a date on {req.date} · {req.start}–{req.end} · 🪙 {req.coins}. Review in VIP Bookings.",
                 {"booking_id": bid}, email=True, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
    await notify(user["id"], "vs_submitted", "Request sent 📨",
                 f"Your date request on {req.date} · {req.start}–{req.end} is pending confirmation.", {"booking_id": bid})
    await _date_chat_card(user["id"], vip_id, "vip", bid, "invite", "👑 VIP date request", vip_id,
                          {"when": f"{req.date}T{req.start}:00", "end": req.end, "coins": int(req.coins), "place": req.place,
                           "location": _loc_card(doc.get("location")) if req.place != "own" else {}})
    return {"booking_id": bid, "status": "pending"}

@api.post("/vip/schedule/bookings/{bid}/confirm")
async def vs_confirm(bid: str, user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid})
    if not b:
        raise HTTPException(404, "Not found")
    if b["vip_id"] != user["id"]:
        raise HTTPException(403, "Only the VIP can confirm")
    if b["status"] != "pending":
        raise HTTPException(400, "NOT_PENDING")
    now = datetime.now(timezone.utc).isoformat()
    await db.vip_sched.update_one({"id": bid}, {"$set": {"status": "confirmed", "confirmed_at": now}})
    await notify(b["requester_id"], "vs_confirmed", "Date confirmed 💃",
                 f"{user['name']} confirmed your date on {b['date']} · {b['start']}–{b['end']}.",
                 {"booking_id": bid}, email=True)
    await _date_chat_card(user["id"], b["requester_id"], "vip", bid, "accepted", "✅ VIP date confirmed", data={"when": f"{b['date']}T{b['start']}:00", "end": b["end"]})
    return {"status": "confirmed"}

async def _vs_release(b: dict, actor_name: str, reason: str):
    """Refund the requester and release the VIP's escrow, freeing the slot."""
    coins = int(b.get("coins") or 0)
    if coins:
        await db.users.update_one({"id": b["requester_id"]}, {"$inc": {"coins": coins}})
        await db.users.update_one({"id": b["vip_id"]}, {"$inc": {"escrow": -coins}})

@api.post("/vip/schedule/bookings/{bid}/decline")
async def vs_decline(bid: str, reason: Optional[str] = None, user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid})
    if not b:
        raise HTTPException(404, "Not found")
    if b["vip_id"] != user["id"]:
        raise HTTPException(403, "Only the VIP can decline")
    if b["status"] not in ("pending", "confirmed"):
        raise HTTPException(400, "CANNOT_DECLINE")
    now = datetime.now(timezone.utc).isoformat()
    await _vs_release(b, user["name"], "declined")
    reason = _decline_reason(reason)
    await db.vip_sched.update_one({"id": bid}, {"$set": {"status": "declined", "declined_at": now, "decline_reason": reason}})
    await notify(b["requester_id"], "vs_declined", "Date declined",
                 f"{user['name']} declined your date on {b['date']} · {b['start']}–{b['end']}. 🪙 {b.get('coins', 0)} refunded." + _reason_line(reason),
                 {"booking_id": bid}, email=True)
    await _date_chat_card(user["id"], b["requester_id"], "vip", bid, "declined", "❌ VIP date declined", data={"reason": reason, "refunded": b.get("coins", 0)})
    return {"status": "declined", "refunded": b.get("coins", 0)}

# ---- Taxi for VIP calendar bookings: VIP requests, requester pays (held in escrow with the date coins) ----
@api.post("/vip/schedule/bookings/{bid}/taxi/request")
async def vs_taxi_request(bid: str, req: TaxiRequestReq, user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b: raise HTTPException(404, "Not found")
    # date at the VIP's place → the inviter travels and may ask the VIP; otherwise the VIP travels and asks the inviter
    by = "client" if b.get("place") == "own" else "vip"
    if user["id"] != (b["requester_id"] if by == "client" else b["vip_id"]):
        raise HTTPException(403, "Only the person travelling to the date can request a taxi")
    if b["status"] not in ("pending", "confirmed"): raise HTTPException(400, "Cannot request taxi")
    if req.coins < 1: raise HTTPException(400, "Invalid amount")
    if (b.get("taxi") or {}).get("status") in ("pending", "sent"): raise HTTPException(400, "TAXI_PENDING")
    taxi = {"coins": int(req.coins), "status": "pending", "by": by, "requested_at": datetime.now(timezone.utc).isoformat()}
    await db.vip_sched.update_one({"id": bid}, {"$set": {"taxi": taxi}})
    if by == "client":
        await notify(b["vip_id"], "vs_taxi", "Taxi requested 🚕",
                     f"{user['name']} asks for 🪙 {req.coins} for a taxi to your place for the date on {b['date']} · {b['start']}. Send it in VIP Bookings.",
                     {"booking_id": bid, "coins": req.coins}, email=True, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
        return {"ok": True, "taxi": taxi}
    await notify(b["requester_id"], "vs_taxi", "Taxi requested 🚕",
                 f"{user['name']} asks for 🪙 {req.coins} for a taxi to and from your date on {b['date']} · {b['start']}. Send it in VIP Bookings.",
                 {"booking_id": bid, "coins": req.coins}, email=True, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
    return {"ok": True, "taxi": taxi}

@api.post("/vip/schedule/bookings/{bid}/taxi/send")
async def vs_taxi_send(bid: str, user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b: raise HTTPException(404, "Not found")
    taxi = b.get("taxi") or {}
    payer = b["vip_id"] if taxi.get("by") == "client" else b["requester_id"]
    if payer != user["id"]: raise HTTPException(403, "Only the other person can send the taxi coins")
    if b["status"] not in ("pending", "confirmed"): raise HTTPException(400, "Cannot send taxi")
    if taxi.get("status") != "pending": raise HTTPException(400, "No pending taxi request")
    coins = int(taxi["coins"])
    if (user.get("coins", 0) + user.get("withdrawable", 0)) < coins: raise HTTPException(400, "Insufficient coins")
    now = datetime.now(timezone.utc).isoformat()
    if taxi.get("by") == "client":  # VIP pays the inviter's taxi to the VIP's place
        await spend_coins(user["id"], coins)
        await db.users.update_one({"id": b["requester_id"]}, {"$inc": {"withdrawable": coins}})
        await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "vip_taxi_to_client", "from_id": user["id"], "to_id": b["requester_id"], "cost": coins, "net": coins, "created_at": now})
        await db.vip_sched.update_one({"id": bid}, {"$set": {"taxi.status": "sent", "taxi.sent_at": now}})
        await notify(b["requester_id"], "vs_taxi", "🚕 Taxi sent", f"{user['name']} sent you 🪙 {coins} for your taxi to the date.", {"booking_id": bid, "coins": coins}, email=True)
        return {"ok": True, "coins": coins, "auto_confirmed": False}
    await spend_coins(user["id"], coins)
    await db.users.update_one({"id": b["vip_id"]}, {"$inc": {"escrow": coins}})
    sets = {"taxi.status": "sent", "taxi.sent_at": now}
    if (b.get("pickup") or {}).get("status") in ("offered", "address_set"):
        sets["pickup.status"] = "taxi_instead"
    auto = b["status"] == "pending"
    if auto:
        sets.update({"status": "confirmed", "confirmed_at": now, "auto_confirmed": True})
    await db.vip_sched.update_one({"id": bid}, {"$set": sets, "$inc": {"coins": coins, "taxi_coins": coins}})
    await notify(b["vip_id"], "vs_taxi", "🚕 Taxi sent", f"{user['name']} sent 🪙 {coins} for your taxi." + (" The date is now confirmed." if auto else ""),
                 {"booking_id": bid, "coins": coins}, email=True)
    return {"ok": True, "coins": coins, "auto_confirmed": auto}

@api.post("/vip/schedule/bookings/{bid}/taxi/decline")
async def vs_taxi_decline(bid: str, user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b: raise HTTPException(404, "Not found")
    by_client = (b.get("taxi") or {}).get("by") == "client"
    if user["id"] != (b["vip_id"] if by_client else b["requester_id"]): raise HTTPException(403, "Only the other person can decline")
    if (b.get("taxi") or {}).get("status") != "pending": raise HTTPException(400, "No pending taxi request")
    await db.vip_sched.update_one({"id": bid}, {"$set": {"taxi.status": "declined", "taxi.declined_at": datetime.now(timezone.utc).isoformat()}})
    await notify(b["requester_id"] if by_client else b["vip_id"], "vs_taxi", "Taxi request declined", f"{user['name']} declined your taxi request for {b['date']} · {b['start']}.", {"booking_id": bid})
    return {"ok": True}

# ---- VIP proposes a pick-up instead of refusing; inviter accepts or declines ----
class VipPickupReq(BaseModel):
    address_confirmed: bool = False
    address: str
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    time: Optional[str] = None  # HH:MM pick-up time, defaults to the date start
    note: Optional[str] = None

async def _vs_pickup_booking(bid: str):
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b: raise HTTPException(404, "Not found")
    if b["status"] not in ("pending", "confirmed"): raise HTTPException(400, "Only active dates")
    return b

@api.post("/vip/schedule/bookings/{bid}/pickup/offer")
async def vs_pickup_offer(bid: str, user=Depends(get_current_user)):
    """Step 1 — inviter offers to pick the VIP up instead of paying the requested taxi fee."""
    b = await _vs_pickup_booking(bid)
    if b["requester_id"] != user["id"]: raise HTTPException(403, "Only the inviter can offer a pick-up")
    if (b.get("taxi") or {}).get("status") != "pending": raise HTTPException(400, "NO_TAXI_REQUEST")
    if (b.get("pickup") or {}).get("status") in ("offered", "address_set"): raise HTTPException(400, "PICKUP_PENDING")
    pickup = {"status": "offered", "offered_at": datetime.now(timezone.utc).isoformat()}
    await db.vip_sched.update_one({"id": bid}, {"$set": {"pickup": pickup}})
    await notify(b["vip_id"], "vs_pickup", "Pick-up offered 🚗",
                 f"Instead of the taxi fee, {user['name']} offers to pick you up for your date on {b['date']} · {b['start']}. Add where you'd like to be picked up in VIP Bookings.",
                 {"booking_id": bid}, email=True, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Add pick-up location")
    return {"ok": True, "pickup": pickup}

@api.post("/vip/schedule/bookings/{bid}/pickup/address")
async def vs_pickup_address(bid: str, req: VipPickupReq, user=Depends(get_current_user)):
    """Step 2 — the invited VIP fills in the desired pick-up location and time."""
    b = await _vs_pickup_booking(bid)
    if b["vip_id"] != user["id"]: raise HTTPException(403, "Only the invited VIP can set the pick-up location")
    if (b.get("pickup") or {}).get("status") not in ("offered", "address_set"): raise HTTPException(400, "NO_PICKUP_OFFER")
    geo = await _apply_geo(req)
    tm = req.time if req.time and re.fullmatch(r"\d{2}:\d{2}", req.time) else b["start"]
    pickup = {**b["pickup"], **req.model_dump(exclude={"time", "address_confirmed"}), "address": req.address.strip()[:300], "note": (req.note or "")[:300],
              "time": tm, "unverified": geo["unverified"], "status": "address_set", "address_at": datetime.now(timezone.utc).isoformat()}
    await db.vip_sched.update_one({"id": bid}, {"$set": {"pickup": pickup}})
    await notify(b["requester_id"], "vs_pickup", "Pick-up location added 📍",
                 f"{user['name']} would like to be picked up at {pickup['address']} at {tm} on {b['date']}. Confirm the pick-up, send the taxi fee instead, or cancel the date in VIP Bookings.",
                 {"booking_id": bid}, email=True, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
    return {"ok": True, "pickup": pickup}

@api.post("/vip/schedule/bookings/{bid}/pickup/accept")
async def vs_pickup_accept(bid: str, user=Depends(get_current_user)):
    """Step 3 — inviter confirms the pick-up location: taxi request withdrawn, date confirmed."""
    b = await _vs_pickup_booking(bid)
    if b["requester_id"] != user["id"]: raise HTTPException(403, "Only the inviter can confirm the pick-up")
    if (b.get("pickup") or {}).get("status") != "address_set": raise HTTPException(400, "NO_PICKUP_ADDRESS")
    now = datetime.now(timezone.utc).isoformat()
    sets = {"pickup.status": "accepted", "pickup.answered_at": now, "taxi.status": "replaced"}
    if b["status"] == "pending":
        sets.update({"status": "confirmed", "confirmed_at": now})
    await db.vip_sched.update_one({"id": bid}, {"$set": sets})
    await notify(b["vip_id"], "vs_pickup", "Pick-up confirmed ✅",
                 f"{user['name']} will pick you up at {b['pickup']['address']} at {b['pickup']['time']} on {b['date']}. The date is confirmed.", {"booking_id": bid}, email=True)
    return {"ok": True, "status": "confirmed"}

# ---- Client reports a VIP no-show: full refund of date + taxi coins, evidence kept for admin review ----
@api.post("/vip/schedule/bookings/{bid}/no-show")
async def vs_no_show(bid: str, note: str = Form(""), photo: Optional[UploadFile] = File(None), user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b: raise HTTPException(404, "Not found")
    if b["requester_id"] != user["id"]: raise HTTPException(403, "Only the client can report a no-show")
    now = datetime.now(timezone.utc)
    if b["status"] != "confirmed" or not (_vs_start_dt(b) + timedelta(minutes=15) <= now < _vs_end_dt(b)): raise HTTPException(400, "NO_SHOW_WINDOW")
    note = (note or "").strip()[:1000]
    photo_path = None
    if photo is not None and photo.filename:
        ct = photo.content_type or ""
        if not ct.startswith("image/"): raise HTTPException(400, "IMAGE_ONLY")
        data = await photo.read()
        if len(data) > 10 * 1024 * 1024: raise HTTPException(400, "FILE_TOO_LARGE")
        ext = (photo.filename.rsplit(".", 1)[-1] if "." in photo.filename else "jpg").lower()[:5]
        res = put_object(f"{APP_NAME}/no-show/{bid}/{uuid.uuid4()}.{ext}", data, ct)
        photo_path = res["path"]
        await db.files.insert_one({"id": str(uuid.uuid4()), "storage_path": photo_path, "user_id": user["id"], "content_type": ct,
                                   "size": res["size"], "private": True, "is_deleted": False, "created_at": now.isoformat()})
    if not note and not photo_path: raise HTTPException(400, "EVIDENCE_REQUIRED")
    # Nothing is cancelled or refunded here: coins stay on hold, the VIP gets 24h to reply, then an admin decides.
    report = {"note": note, "photo": photo_path, "created_at": now.isoformat(), "status": "open", "reporter_role": "inviter",
              "reply_deadline": (now + timedelta(hours=REPORT_REPLY_HOURS)).isoformat()}
    await db.vip_sched.update_one({"id": bid}, {"$set": {"status": "reported", "no_show": True, "no_show_report": report, "reported_at": now.isoformat()}})
    await notify(b["vip_id"], "vs_no_show", "No-show reported — reply within 24h",
                 f"{user['name']} reported that you did not show up for the date on {b['date']} · {b['start']}. " + _reported_msg("inviter"),
                 {"booking_id": bid}, email=True, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Reply now")
    for aid in await _admin_ids():
        await notify(aid, "vs_no_show", "VIP no-show reported", f"Booking {bid} was reported as a no-show. The VIP has 24h to reply.", {"booking_id": bid}, email=True, link=f"{PUBLIC_APP_URL}/admin", cta="View Case")
    return {"status": "reported"}

@api.post("/vip/schedule/bookings/{bid}/no-show/reply")
async def vs_no_show_reply(bid: str, note: str = Form(""), photo: Optional[UploadFile] = File(None), user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b: raise HTTPException(404, "Not found")
    r = b.get("no_show_report") or {}
    if b["vip_id"] != user["id"]: raise HTTPException(403, "Only the VIP can reply")
    if r.get("status") != "open" or b["status"] != "reported": raise HTTPException(400, "REPORT_CLOSED")
    if r.get("reply"): raise HTTPException(409, "ALREADY_REPLIED")
    if _reply_closed(r): raise HTTPException(400, "REPLY_WINDOW_CLOSED")
    note = (note or "").strip()[:1000]
    if len(note) < 10: raise HTTPException(400, "Please describe your side (min 10 chars)")
    photo_path = None
    if photo is not None and photo.filename:
        if not (photo.content_type or "").startswith("image/"): raise HTTPException(400, "IMAGE_ONLY")
        data = await photo.read()
        if len(data) > 10 * 1024 * 1024: raise HTTPException(400, "FILE_TOO_LARGE")
        ext = (photo.filename.rsplit(".", 1)[-1] if "." in photo.filename else "jpg").lower()[:5]
        res = put_object(f"{APP_NAME}/no-show/{bid}/{uuid.uuid4()}.{ext}", data, photo.content_type)
        photo_path = res["path"]
        await db.files.insert_one({"id": str(uuid.uuid4()), "storage_path": photo_path, "user_id": user["id"], "content_type": photo.content_type,
                                   "size": res["size"], "private": True, "is_deleted": False, "created_at": _iso()})
    await db.vip_sched.update_one({"id": bid}, {"$set": {"no_show_report.reply": {"by": user["id"], "details": note, "photos": [photo_path] if photo_path else [], "at": _iso()}}})
    await notify(b["requester_id"], "vs_no_show", "The VIP replied to your report", "Support received their side and will review both.", {"booking_id": bid}, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
    for aid in await _admin_ids():
        await notify(aid, "vs_no_show", "No-show reply received", f"{user['name']} replied to the no-show report ({bid}).", {"booking_id": bid}, email=True, link=f"{PUBLIC_APP_URL}/admin", cta="View Case")
    return {"ok": True}

@api.get("/admin/no-show-reports")
async def admin_no_show_reports(admin=Depends(get_admin)):
    docs = await db.vip_sched.find({"no_show_report": {"$exists": True}}, {"_id": 0}).sort("no_show_report.created_at", -1).to_list(300)
    for b in docs: b["client"], b["vip"] = await _mini(b["requester_id"]), await _mini(b["vip_id"])
    return {"reports": docs}

@api.post("/admin/no-show-reports/{bid}/resolve")
async def admin_no_show_resolve(bid: str, action: str, admin=Depends(get_admin)):
    """valid: keep the refund. reversed: the VIP did show up — take the refund back from the client and pay the VIP."""
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b or (b.get("no_show_report") or {}).get("status") != "open": raise HTTPException(404, "No open report")
    if action not in ("valid", "reversed"): raise HTTPException(400, "Bad action")
    now = datetime.now(timezone.utc).isoformat()
    sets = {"no_show_report.status": action, "no_show_report.resolved_at": now, "no_show_report.resolved_by": admin["id"]}
    coins = int(b.get("coins") or 0)
    if b["status"] == "reported":
        # coins are still on hold — the admin decision is the only thing that moves them
        if action == "valid":
            await _vs_release(b, "support", "no_show")
            sets.update({"status": "cancelled", "cancelled_at": now, "cancelled_by": "support", "refund": coins, "compensation": 0, "platform_fee": 0})
            msg_c, msg_v = f"Support upheld your no-show report. 🪙 {coins} were refunded to you.", f"After review, the no-show report for {b['date']} · {b['start']} was upheld. The coins were refunded to the client."
        else:
            if coins: await db.users.update_one({"id": b["vip_id"]}, {"$inc": {"escrow": -coins, "withdrawable": coins}})
            sets.update({"status": "completed", "completed_at": now})
            msg_c, msg_v = f"After review, the date on {b['date']} · {b['start']} was counted as attended. 🪙 {coins} were paid to the VIP.", f"After review you were paid 🪙 {coins} for the date on {b['date']}."
        await db.vip_sched.update_one({"id": bid}, {"$set": sets})
        await notify(b["requester_id"], "vs_no_show", "No-show report resolved", msg_c, {"booking_id": bid}, email=True)
        await notify(b["vip_id"], "vs_no_show", "No-show report resolved", msg_v, {"booking_id": bid}, email=True)
        return {"ok": True, "status": action}
    if action == "reversed":
        client = await db.users.find_one({"id": b["requester_id"]}, {"_id": 0, "coins": 1})
        amount = min(int(b.get("refund") or 0), int((client or {}).get("coins") or 0))
        if amount:
            await db.users.update_one({"id": b["requester_id"]}, {"$inc": {"coins": -amount}})
            await db.users.update_one({"id": b["vip_id"]}, {"$inc": {"withdrawable": amount}})
        sets.update({"status": "completed", "completed_at": now, "no_show_reversed_coins": amount})
        await notify(b["requester_id"], "vs_no_show", "No-show report reversed",
                     f"After review, the date on {b['date']} · {b['start']} was counted as attended. 🪙 {amount} were paid to the VIP.", {"booking_id": bid}, email=True)
        await notify(b["vip_id"], "vs_no_show", "No-show report reversed ✅", f"After review you were paid 🪙 {amount} for the date on {b['date']}.", {"booking_id": bid}, email=True)
    else:
        await notify(b["vip_id"], "vs_no_show", "No-show report upheld", f"After review, the no-show report for {b['date']} · {b['start']} was upheld.", {"booking_id": bid}, email=True)
    await db.vip_sched.update_one({"id": bid}, {"$set": sets})
    return {"ok": True, "status": action}

# ---- VIP running late: instant heads-up to the client ----
class VipLateReq(BaseModel):
    minutes: int = 10

@api.post("/vip/schedule/bookings/{bid}/late")
async def vs_running_late(bid: str, req: VipLateReq, user=Depends(get_current_user)):
    """Either side sends a 'running late' heads-up; the other side is notified instantly."""
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b: raise HTTPException(404, "Not found")
    if user["id"] not in (b["vip_id"], b["requester_id"]): raise HTTPException(403, "Not your booking")
    if req.minutes not in (5, 10, 15, 20, 30, 45, 60): raise HTTPException(400, "BAD_MINUTES")
    now = datetime.now(timezone.utc)
    if b["status"] != "confirmed" or not (_vs_start_dt(b) - timedelta(hours=3) <= now < _vs_end_dt(b)): raise HTTPException(400, "NOT_DATE_TIME")
    is_vip_side = user["id"] == b["vip_id"]
    field, other, who = ("late", b["requester_id"], "Your VIP") if is_vip_side else ("client_late", b["vip_id"], "Your client")
    late = {"minutes": req.minutes, "at": now.isoformat()}
    await db.vip_sched.update_one({"id": bid}, {"$set": {field: late}})
    await notify(other, "vs_late", f"{who} is running {req.minutes} min late ⏱",
                 f"{user['name']} is running about {req.minutes} minutes late for your date at {b['start']}. Hang tight!", {"booking_id": bid, "minutes": req.minutes},
                 email=True, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
    return {"ok": True, field: late}

# ---- Arrival check-in: client taps "I've arrived" ----
@api.post("/vip/schedule/bookings/{bid}/arrived")
async def vs_arrived(bid: str, user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b: raise HTTPException(404, "Not found")
    if b["requester_id"] != user["id"]: raise HTTPException(403, "Only the client can check in")
    now = datetime.now(timezone.utc)
    if b["status"] != "confirmed" or not (_vs_start_dt(b) - timedelta(hours=2) <= now < _vs_end_dt(b)): raise HTTPException(400, "NOT_DATE_TIME")
    if b.get("arrived_at"): return {"ok": True, "arrived_at": b["arrived_at"]}
    at = now.isoformat()
    await db.vip_sched.update_one({"id": bid}, {"$set": {"arrived_at": at}})
    where = (b.get("pickup") or {}).get("address") if (b.get("pickup") or {}).get("status") == "accepted" else ((b.get("location") or {}).get("address") or "the date location")
    await notify(b["vip_id"], "vs_arrived", "Your date has arrived 📍", f"{user['name']} has arrived at {where}.", {"booking_id": bid}, email=True,
                 link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
    return {"ok": True, "arrived_at": at}

@api.post("/vip/schedule/bookings/{bid}/cancel")
async def vs_cancel(bid: str, user=Depends(get_current_user)):
    await _close_date_cards(bid)
    b = await db.vip_sched.find_one({"id": bid})
    if not b:
        raise HTTPException(404, "Not found")
    if user["id"] not in (b["requester_id"], b["vip_id"]):
        raise HTTPException(403, "Not your booking")
    if b["status"] not in ("pending", "confirmed"):
        raise HTTPException(400, "CANNOT_CANCEL")
    now = datetime.now(timezone.utc).isoformat()
    other = b["vip_id"] if user["id"] == b["requester_id"] else b["requester_id"]
    coins = int(b.get("coins") or 0)
    if user["id"] == b["requester_id"] and coins:
        # requester cancels -> date coins: 50% back, 25% to the VIP, 25% platform fee; taxi coins always fully refunded
        taxi_c = int(b.get("taxi_coins") or 0)
        base = coins - taxi_c
        refund, comp = int(round(base * 0.5)), int(round(base * 0.25))
        fee = base - refund - comp
        refund += taxi_c
        await db.users.update_one({"id": b["requester_id"]}, {"$inc": {"coins": refund}})
        await db.users.update_one({"id": b["vip_id"]}, {"$inc": {"escrow": -coins, "withdrawable": comp}})
        await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "date_cancel_fee", "from_id": b["requester_id"], "to_id": b["vip_id"], "cost": comp, "net": comp, "created_at": now})
        if fee:
            await db.transactions.insert_one({"id": str(uuid.uuid4()), "type": "platform_cancel_fee", "from_id": b["requester_id"], "to_id": None, "cost": fee, "net": fee, "created_at": now})
        msg = f"🪙 {refund} refunded to the requester, 🪙 {comp} to the VIP, 🪙 {fee} platform fee."
    else:
        await _vs_release(b, user["name"], "cancelled")
        refund, comp, fee = coins, 0, 0
        msg = f"All coins (🪙 {coins}) were refunded to the requester."
    await db.vip_sched.update_one({"id": bid}, {"$set": {"status": "cancelled", "cancelled_at": now, "cancelled_by": user["id"],
                                                         "refund": refund, "compensation": comp, "platform_fee": fee}})
    await notify(other, "vs_cancelled", "Date cancelled",
                 f"{user['name']} cancelled the date on {b['date']} · {b['start']}–{b['end']}. {msg}", {"booking_id": bid}, email=True)
    return {"status": "cancelled", "refunded": refund, "compensation": comp, "platform_fee": fee}

@api.get("/vip/schedule/bookings/mine")
async def vs_my_requests(user=Depends(get_current_user)):
    """Bookings I (as a requester) made, grouped."""
    raw = await db.vip_sched.find({"requester_id": user["id"]}, {"_id": 0}).sort([("date", 1), ("start", 1)]).to_list(500)
    out = []
    for b in raw:
        vip = await db.users.find_one({"id": b["vip_id"]}, {"_id": 0, "id": 1, "name": 1, "photos": 1, "vip.prices": 1})
        b["extra_hour_price"] = vip_extra_price(vip or {})
        b["vip_card"] = {"id": b["vip_id"], "name": (vip or {}).get("name") or "VIP", "photo": ((vip or {}).get("photos") or [None])[0]}
        out.append(_hide_own_address(b, b["status"] in ("confirmed", "completed")))
    return {"requests": out}

# ---- Recurring weekly availability ----
class VipRecurringReq(BaseModel):
    weekdays: List[int]        # 0=Mon .. 6=Sun
    start: str                 # HH:MM
    end: str                   # HH:MM
    slot_len: int = 60
    weeks: int = 8             # how many weeks ahead to generate
    tz: Optional[str] = None

@api.post("/vip/schedule/availability/recurring")
async def vs_add_recurring(req: VipRecurringReq, user=Depends(get_current_user)):
    if not is_vip(user):
        raise HTTPException(403, "VIP_REQUIRED")
    wds = sorted({int(w) for w in (req.weekdays or []) if 0 <= int(w) <= 6})
    if not wds:
        raise HTTPException(400, "NO_WEEKDAYS")
    s, e = _hm_to_min(req.start), _hm_to_min(req.end)
    if s == e:
        raise HTTPException(400, "BAD_WINDOW")
    span = e - s if e > s else e + 24 * 60 - s  # window may run past midnight into the next day
    slot_len = max(15, min(240, int(req.slot_len or 60)))
    if span < slot_len:
        raise HTTPException(400, "WINDOW_TOO_SHORT")
    weeks = max(1, min(26, int(req.weeks or 8)))
    tz = (req.tz or user.get("timezone") or "UTC")
    today = datetime.now(timezone.utc).date()
    created = []
    for i in range(weeks * 7 + 1):
        d = today + timedelta(days=i)
        if d.weekday() not in wds:
            continue
        dk = d.strftime("%Y-%m-%d")
        if await _vs_overlaps(user["id"], dk, s, e - s if e > s else e + 1440 - s):
            continue
        doc = {"id": str(uuid.uuid4()), "vip_id": user["id"], "date": dk,
               "start": _min_to_hm(s), "end": _min_to_hm(e), "slot_len": slot_len, "tz": tz,
               "recurring": True, "created_at": datetime.now(timezone.utc).isoformat()}
        await db.vip_avail.insert_one(doc)
        created.append(_vs_clean(doc))
    return {"created": len(created), "blocks": created}

# ---- Bulk availability: several days x several time ranges, or a weekly schedule ----
class VipRange(BaseModel):
    start: str
    end: str

class VipBulkAvailReq(BaseModel):
    dates: List[str] = []
    ranges: List[VipRange] = []
    slot_len: int = 60
    tz: Optional[str] = None

class VipWeeklyAvailReq(BaseModel):
    weekly: Dict[str, List[VipRange]] = {}  # "0"(Mon)..."6"(Sun) -> ranges
    weeks: int = 8
    slot_len: int = 60
    tz: Optional[str] = None

async def _vs_overlaps(vip_id: str, dk: str, a: int, span: int) -> bool:
    """True if [a, a+span) on day dk overlaps an existing window (incl. overnight windows from the day before/after)."""
    d0 = datetime.strptime(dk, "%Y-%m-%d")
    near = {(d0 + timedelta(days=k)).strftime("%Y-%m-%d"): k * 1440 for k in (-1, 0, 1)}
    async for x in db.vip_avail.find({"vip_id": vip_id, "date": {"$in": list(near)}}, {"_id": 0, "date": 1, "start": 1, "end": 1}):
        xs, xe = _hm_to_min(x["start"]), _hm_to_min(x["end"])
        xa = xs + near[x["date"]]
        xz = xa + (xe - xs if xe > xs else xe + 1440 - xs)
        if a < xz and xa < a + span: return True
    return False

async def _vs_insert_blocks(user, items, slot_len, tz, recurring=False):
    """items: [(date, start, end)]; skips past days, empty/too-short windows and duplicates."""
    slot_len = max(15, min(240, int(slot_len or 60)))
    today, created, overlaps = _vs_today(), [], 0
    for dk, st, en in items:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dk) or dk < today:
            continue
        a, z = _hm_to_min(st), _hm_to_min(en)
        if a == z or ((z - a) if z > a else z + 1440 - a) < slot_len:
            continue
        st, en = _min_to_hm(a), _min_to_hm(z)
        if await _vs_overlaps(user["id"], dk, a, (z - a) if z > a else z + 1440 - a):
            overlaps += 1  # same or overlapping time already on that day
            continue
        doc = {"id": str(uuid.uuid4()), "vip_id": user["id"], "date": dk, "start": st, "end": en, "slot_len": slot_len,
               "tz": tz or user.get("timezone") or "UTC", "recurring": recurring, "created_at": datetime.now(timezone.utc).isoformat()}
        await db.vip_avail.insert_one(doc)
        created.append(_vs_clean(doc))
    return {"created": len(created), "blocks": created, "skipped_overlap": overlaps}

@api.post("/vip/schedule/availability/bulk")
async def vs_add_bulk(req: VipBulkAvailReq, user=Depends(get_current_user)):
    if not is_vip(user):
        raise HTTPException(403, "VIP_REQUIRED")
    if not req.dates or not req.ranges:
        raise HTTPException(400, "NOTHING_TO_ADD")
    items = [(d, r.start, r.end) for d in sorted(set(req.dates))[:120] for r in req.ranges[:8]]
    return await _vs_insert_blocks(user, items, req.slot_len, req.tz)

@api.post("/vip/schedule/availability/weekly")
async def vs_add_weekly(req: VipWeeklyAvailReq, user=Depends(get_current_user)):
    if not is_vip(user):
        raise HTTPException(403, "VIP_REQUIRED")
    weekly = {int(k): v[:8] for k, v in req.weekly.items() if k.isdigit() and 0 <= int(k) <= 6 and v}
    if not weekly:
        raise HTTPException(400, "NO_WEEKDAYS")
    today = datetime.now(timezone.utc).date()
    items = []
    for i in range(max(1, min(26, int(req.weeks or 8))) * 7):
        d = today + timedelta(days=i)
        for r in weekly.get(d.weekday(), []):
            items.append((d.strftime("%Y-%m-%d"), r.start, r.end))
    return await _vs_insert_blocks(user, items, req.slot_len, req.tz, recurring=True)

# ---- Add extra hours while a VIP date is in progress ----
class VipExtendReq(BaseModel):
    hours: int = 1

async def _charge_extension(user, vip_id, hours):
    if hours < 1 or hours > 24:
        raise HTTPException(400, "BAD_HOURS")
    vip = await db.users.find_one({"id": vip_id})
    cost = hours * vip_extra_price(vip or {})
    if (user.get("coins", 0) + user.get("withdrawable", 0)) < cost:
        raise HTTPException(400, "Insufficient coins")
    await spend_coins(user["id"], cost)
    await db.users.update_one({"id": vip_id}, {"$inc": {"escrow": cost}})
    return cost

@api.post("/vip/schedule/bookings/{bid}/extend")
async def vs_extend(bid: str, req: VipExtendReq, user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b or b["requester_id"] != user["id"]:
        raise HTTPException(404, "Not found")
    now = datetime.now(timezone.utc)
    if b["status"] != "confirmed" or not (_vs_start_dt(b) <= now < _vs_end_dt(b)):
        raise HTTPException(400, "NOT_IN_PROGRESS")
    S = _hm_to_min(b["start"]); E = _hm_to_min(b["end"])
    if E <= S: E += 1440
    ne = E + 60 * req.hours
    others = await db.vip_sched.find({"vip_id": b["vip_id"], "date": b["date"], "status": {"$in": VIP_SCHED_ACTIVE}, "id": {"$ne": bid}},
                                     {"_id": 0, "start": 1, "end": 1}).to_list(500)
    if _vs_conflict(E, ne, others, ref_start=S):
        raise HTTPException(409, "SLOT_TAKEN")
    for lk in await _vs_normal_locks(b["vip_id"], b["date"]):
        lf, lt = _hm_to_min(lk["lock_from"]), _hm_to_min(lk["lock_to"])
        if lt <= lf: lt += 1440
        if E < lt and lf < ne: raise HTTPException(409, "SLOT_TAKEN")
    cost = await _charge_extension(user, b["vip_id"], req.hours)
    await db.vip_sched.update_one({"id": bid}, {"$set": {"end": _min_to_hm(ne), "lock_end": _min_to_hm(ne + VIP_SCHED_BUFFER)},
                                                "$inc": {"coins": cost, "hours": req.hours, "extra_hours": req.hours, "extra_coins": cost}})
    await notify(b["vip_id"], "vs_extended", "Date extended ⏳",
                 f"{user['name']} added {req.hours}h to your date · new end {_min_to_hm(ne)} · +🪙 {cost}.", {"booking_id": bid}, email=True)
    return {"end": _min_to_hm(ne), "cost": cost}

@api.post("/vip/book/{bid}/extend")
async def vip_book_extend(bid: str, req: VipExtendReq, user=Depends(get_current_user)):
    b = await db.date_bookings.find_one({"id": bid, "vip": True}, {"_id": 0})
    if not b or b["from_id"] != user["id"]:
        raise HTTPException(404, "Not found")
    start = _pdt(b["scheduled_at"])
    start = start if start and start.tzinfo else (start.replace(tzinfo=timezone.utc) if start else None)
    dur = int(b.get("duration_min") or DATE_SLOT_MINUTES)
    now = datetime.now(timezone.utc)
    if b["status"] not in ("escrow", "accepted", "confirmed") or not start or not (start - timedelta(hours=14) <= now < start + timedelta(minutes=dur) + timedelta(hours=14)):
        raise HTTPException(400, "NOT_IN_PROGRESS")
    cost = await _charge_extension(user, b["to_id"], req.hours)
    nd = dur + 60 * req.hours
    sf = b.get("slot_from") or b["scheduled_at"][11:16]
    await db.date_bookings.update_one({"id": bid}, {"$set": {"duration_min": nd, "slot_from": sf, "slot_to": _min_to_hm(_hm_to_min(sf) + nd)},
                                                    "$inc": {"coins": cost, "extra_hours": req.hours, "extra_coins": cost}})
    await notify(b["to_id"], "vs_extended", "Date extended ⏳", f"{user['name']} added {req.hours}h to your VIP date · +🪙 {cost}.", {"booking_id": bid}, email=True)
    return {"duration_min": nd, "cost": cost}

# ---- Reschedule a pending request ----
class VipRescheduleReq(BaseModel):
    date: str
    start: str
    end: str

async def _vs_check_new_time(b: dict, date: str, start: str, end: str):
    """Validate a new time against the VIP's availability and other bookings; returns (cs, ce)."""
    ns, ne = _hm_to_min(start), _hm_to_min(end)
    if ns == ne:
        raise HTTPException(400, "BAD_TIME")
    vip_id = b["vip_id"]
    blocks = await db.vip_avail.find({"vip_id": vip_id, "date": date}, {"_id": 0}).to_list(200)
    ref_start = None; cs = ce = None
    for bl in blocks:
        S, E = _vs_win(bl)
        a = ns + 24 * 60 if ns < S else ns
        z = ne
        if z < S or z <= a: z += 24 * 60
        if S <= a and z <= E and a < z:
            ref_start, cs, ce = S, a, z
            break
    if ref_start is None:
        raise HTTPException(400, "TIME_UNAVAILABLE")
    active = await db.vip_sched.find({"vip_id": vip_id, "date": date, "status": {"$in": VIP_SCHED_ACTIVE}, "id": {"$ne": b["id"]}},
                                     {"_id": 0, "start": 1, "end": 1}).to_list(500)
    if _vs_conflict(cs, ce, active, ref_start=ref_start):
        raise HTTPException(409, "SLOT_TAKEN")
    await _vs_extra_checks(vip_id, date, cs, ce)
    if "hours" in b and (ce - cs) // 60 != b["hours"]:
        raise HTTPException(400, "DURATION_CHANGED")
    return cs, ce

async def _vs_apply_time(b: dict, date: str, start: str, end: str, cs: int, ce: int):
    await db.vip_sched.update_one({"id": b["id"]}, {"$set": {
        "date": date, "start": start, "end": end,
        "lock_start": _min_to_hm(max(0, cs - VIP_SCHED_BUFFER)), "lock_end": _min_to_hm(ce + VIP_SCHED_BUFFER),
        "scheduled_at": f"{date}T{start}:00", "rescheduled_at": _iso(), "reminder_24_sent": False, "reminder_1h_sent": False},
        "$unset": {"reschedule_proposal": ""}})

@api.post("/vip/schedule/bookings/{bid}/reschedule")
async def vs_reschedule(bid: str, req: VipRescheduleReq, user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Not found")
    link = dict(link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
    if b["vip_id"] == user["id"]:
        # the invited VIP proposes a new time — the inviter must accept before it changes
        if b["status"] not in ("pending", "confirmed"):
            raise HTTPException(400, "NOT_ACTIVE")
        await _vs_check_new_time(b, req.date, req.start, req.end)
        prop = {"date": req.date, "start": req.start, "end": req.end, "by": "vip", "at": _iso()}
        await db.vip_sched.update_one({"id": bid}, {"$set": {"reschedule_proposal": prop}})
        await notify(b["requester_id"], "vs_rescheduled", "New time proposed 🔁",
                     f"{user['name']} asks to move your date to {req.date} · {req.start}–{req.end}. Accept or decline in VIP Bookings.",
                     {"booking_id": bid}, email=True, **link)
        return {"status": b["status"], "proposal": prop}
    if b["requester_id"] != user["id"]:
        raise HTTPException(403, "Only the requester or the VIP can reschedule")
    if b["status"] != "pending":
        raise HTTPException(400, "NOT_PENDING")
    cs, ce = await _vs_check_new_time(b, req.date, req.start, req.end)
    await _vs_apply_time(b, req.date, req.start, req.end, cs, ce)
    await notify(b["vip_id"], "vs_rescheduled", "Date request updated 🔁",
                 f"{user['name']} proposed a new time: {req.date} · {req.start}–{req.end}. Confirm or decline in VIP Bookings.",
                 {"booking_id": bid}, email=True, **link)
    return {"status": "pending", "date": req.date, "start": req.start, "end": req.end}

@api.post("/vip/schedule/bookings/{bid}/reschedule/{answer}")
async def vs_reschedule_answer(bid: str, answer: str, user=Depends(get_current_user)):
    b = await db.vip_sched.find_one({"id": bid}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Not found")
    if b["requester_id"] != user["id"]:
        raise HTTPException(403, "Only the inviter can answer")
    p = b.get("reschedule_proposal")
    if not p or b["status"] not in ("pending", "confirmed"):
        raise HTTPException(400, "NO_PROPOSAL")
    if answer == "accept":
        cs, ce = await _vs_check_new_time(b, p["date"], p["start"], p["end"])
        await _vs_apply_time(b, p["date"], p["start"], p["end"], cs, ce)
        await notify(b["vip_id"], "vs_rescheduled", "New time accepted ✅", f"{user['name']} accepted the new time: {p['date']} · {p['start']}–{p['end']}.",
                     {"booking_id": bid}, email=True, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
        return {"ok": True, "date": p["date"], "start": p["start"], "end": p["end"]}
    if answer != "decline":
        raise HTTPException(400, "Unknown answer")
    await db.vip_sched.update_one({"id": bid}, {"$unset": {"reschedule_proposal": ""}})
    await notify(b["vip_id"], "vs_rescheduled", "New time declined", f"{user['name']} kept the original time: {b['date']} · {b['start']}–{b['end']}.",
                 {"booking_id": bid}, email=True, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
    return {"ok": True}

# ---- Background loop: 30-min reminders + auto-complete ----
def _vs_start_dt(b: dict):
    try:
        tzinfo = ZoneInfo(b.get("tz") or "UTC")
    except Exception:
        tzinfo = ZoneInfo("UTC")
    try:
        return datetime.fromisoformat(f"{b['date']}T{b['start']}:00").replace(tzinfo=tzinfo).astimezone(timezone.utc)
    except Exception:
        return None

def _vs_end_dt(b: dict):
    try:
        tzinfo = ZoneInfo(b.get("tz") or "UTC")
    except Exception:
        tzinfo = ZoneInfo("UTC")
    try:
        end_date = b["date"]
        if str(b.get("end", "")) <= str(b.get("start", "")):  # ends after midnight → next calendar day
            end_date = (datetime.fromisoformat(b["date"]) + timedelta(days=1)).strftime("%Y-%m-%d")
        return datetime.fromisoformat(f"{end_date}T{b['end']}:00").replace(tzinfo=tzinfo).astimezone(timezone.utc)
    except Exception:
        return None

async def _vs_tick():
    """Fire 30-minute reminders to both parties and auto-complete finished confirmed dates."""
    now = datetime.now(timezone.utc)
    conf = await db.vip_sched.find({"status": "confirmed"}, {"_id": 0}).to_list(1000)
    for b in conf:
        start_dt = _vs_start_dt(b)
        end_dt = _vs_end_dt(b)
        # day-before and 1-hour reminders (in-app + email) to both sides
        for flag, ahead, title in (("reminder_24_sent", timedelta(hours=24), "Your VIP date is tomorrow 📅"),
                                   ("reminder_1h_sent", timedelta(hours=1), "Your VIP date starts in 1 hour ⏰")):
            if start_dt and not b.get(flag) and (start_dt - ahead) <= now < start_dt:
                when = f"{b['date']} · {b['start']}–{b['end']} ({b.get('tz', 'UTC')})"
                for uid in (b["vip_id"], b["requester_id"]):
                    await notify(uid, "vs_reminder", title, f"Reminder: your date is at {when}.", {"booking_id": b["id"]},
                                 email=True, link=f"{PUBLIC_APP_URL}/vip-bookings", cta="Open VIP Bookings")
                await db.vip_sched.update_one({"id": b["id"]}, {"$set": {flag: True}})
                b[flag] = True
        # auto-complete
        if end_dt and end_dt <= now:
            coins = int(b.get("coins") or 0)
            await db.vip_sched.update_one({"id": b["id"]}, {"$set": {"status": "completed", "completed_at": now.isoformat()}})
            if coins:
                await db.users.update_one({"id": b["vip_id"]}, {"$inc": {"escrow": -coins, "withdrawable": coins}})
            await notify(b["requester_id"], "vs_completed", "Date completed ✅",
                         f"Your date on {b['date']} at {b['start']} is marked completed.", {"booking_id": b["id"]})

async def _vs_reminder_loop():
    import asyncio
    while True:
        try:
            await _vs_tick()
        except Exception as ex:
            logging.error(f"vip-schedule reminder loop error: {ex}")
        await asyncio.sleep(60)
# ==================== end VIP Scheduling ====================



class CoinPremiumReq(BaseModel):
    tier: str = "premium"

class GiftPremiumReq(BaseModel):
    target_id: str
    tier: str = "premium"

@api.get("/premium/coin-prices")
async def premium_coin_prices(user=Depends(get_current_user)):
    return {"premium": PREMIUM_COINS, "vip": VIP_COINS, "premium_lite": PREMIUM_LITE_COINS}

@api.post("/premium/buy-with-coins")
async def buy_premium_coins(req: CoinPremiumReq, user=Depends(get_current_user)):
    tier = req.tier if req.tier in ("premium", "vip", "premium_lite") else "premium"
    cost = VIP_COINS if tier == "vip" else (PREMIUM_LITE_COINS if tier == "premium_lite" else PREMIUM_COINS)
    await spend_coins(user["id"], cost)
    u = await db.users.find_one({"id": user["id"]})
    if tier == "premium_lite":
        upd = {"premium_lite_until": extend_until(u.get("premium_lite_until"))}
    else:
        upd = {"premium_until": extend_until(u.get("premium_until"))}
        if tier == "vip":
            upd["vip_until"] = extend_until(u.get("vip_until"))
    await db.users.update_one({"id": user["id"]}, {"$set": upd})
    return {"ok": True, "tier": tier, **upd}

@api.post("/premium/gift")
async def gift_premium(req: GiftPremiumReq, user=Depends(get_current_user)):
    if req.target_id == user["id"]:
        raise HTTPException(400, "CANNOT_GIFT_SELF")
    tier = req.tier if req.tier in ("premium", "vip", "premium_lite") else "premium"
    cost = VIP_COINS if tier == "vip" else (PREMIUM_LITE_COINS if tier == "premium_lite" else PREMIUM_COINS)
    target = await db.users.find_one({"id": req.target_id}, {"_id": 0, "id": 1, "name": 1, "premium_until": 1, "vip_until": 1, "premium_lite_until": 1})
    if not target:
        raise HTTPException(404, "Recipient not found")
    await spend_coins(user["id"], cost)
    # Gifting premium: the sender spends the coins and the platform keeps 100% of them —
    # the recipient receives only the premium/VIP time, never any coins.
    if tier == "premium_lite":
        upd = {"premium_lite_until": extend_until(target.get("premium_lite_until"))}
        label = "Premium Lite"
    else:
        upd = {"premium_until": extend_until(target.get("premium_until"))}
        if tier == "vip":
            upd["vip_until"] = extend_until(target.get("vip_until"))
        label = "VIP Premium" if tier == "vip" else "Premium"
    await db.users.update_one({"id": req.target_id}, {"$set": upd})
    await record_txn(user["id"], "premium_gift", -cost, description=f"Gifted 30 days of {label} to {target.get('name','a member')}")
    await notify(req.target_id, "premium_gift", f"You received {label}! 👑", f"{user['name']} gifted you 30 days of {label}.", {}, email=True)
    return {"ok": True, "tier": tier, "coins_spent": cost}

@api.post("/vip/photo")
async def vip_add_photo(photo: UploadFile = File(...), private: bool = False, user=Depends(get_current_user)):
    # Uploading photos is part of filling in the VIP profile; publishing still requires a subscription
    field = "private_photos" if private else "photos"
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "vip": 1})
    vip = u.get("vip") or {}
    photos = vip.get(field) or []
    limit = 12 if private else 8
    if len(photos) >= limit:
        raise HTTPException(400, "MAX_PHOTOS")
    data = await photo.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(400, "TOO_LARGE")
    ct = photo.content_type or "image/jpeg"
    if not ct.startswith("image/"):
        raise HTTPException(400, "NOT_IMAGE")
    ext = (photo.filename.split(".")[-1] if photo.filename and "." in photo.filename else "jpg").lower()
    path = f"{APP_NAME}/vipphotos/{user['id']}/{uuid.uuid4()}.{ext}"
    result = put_object(path, data, ct)
    await db.files.insert_one({"id": str(uuid.uuid4()), "storage_path": result["path"], "user_id": user["id"],
                               "content_type": ct, "size": result["size"], "is_deleted": False, "private": False,
                               "created_at": datetime.now(timezone.utc).isoformat()})
    photos.append(result["path"])
    vip[field] = photos
    await db.users.update_one({"id": user["id"]}, {"$set": {"vip": vip}})
    return {"photos": vip.get("photos") or [], "private_photos": vip.get("private_photos") or []}

@api.delete("/vip/photo")
async def vip_del_photo(path: str, private: bool = False, user=Depends(get_current_user)):
    field = "private_photos" if private else "photos"
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "vip": 1})
    vip = u.get("vip") or {}
    photos = [p for p in (vip.get(field) or []) if p != path]
    vip[field] = photos
    await db.users.update_one({"id": user["id"]}, {"$set": {"vip": vip}})
    await db.files.update_one({"storage_path": path}, {"$set": {"is_deleted": True}})
    return {"photos": vip.get("photos") or [], "private_photos": vip.get("private_photos") or []}

class VipPhotoOrderReq(BaseModel):
    photos: List[str]

@api.post("/vip/photos/reorder")
async def vip_reorder_photos(req: VipPhotoOrderReq, user=Depends(get_current_user)):
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "vip": 1})
    vip = u.get("vip") or {}
    cur = set(vip.get("photos") or [])
    new = [p for p in req.photos if p in cur]
    if set(new) != cur:
        raise HTTPException(400, "MISMATCH")
    vip["photos"] = new
    await db.users.update_one({"id": user["id"]}, {"$set": {"vip": vip}})
    return {"photos": new}

# ---------- Stripe checkout ----------
class AutoRenewReq(BaseModel):
    enabled: bool

@api.post("/premium/auto-renew")
async def set_auto_renew(req: AutoRenewReq, user=Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": {"premium_auto_renew": req.enabled}})
    return {"premium_auto_renew": req.enabled}

@api.get("/vip/subscription")
async def vip_subscription_status(user=Depends(get_current_user)):
    """Status of the member's recurring VIP card subscription."""
    return {
        "vip_active": is_vip(user),
        "vip_until": user.get("vip_until"),
        "auto_renew": bool(user.get("vip_auto_renew")) and bool(user.get("stripe_subscription_id")),
        "has_subscription": bool(user.get("stripe_subscription_id")),
        "amount": VIP_PACKAGE["amount"],
    }

@api.post("/vip/cancel-subscription")
async def vip_cancel_subscription(user=Depends(get_current_user)):
    """Stop the monthly card charge. VIP stays active until the current period ends, then expires."""
    sub_id = user.get("stripe_subscription_id")
    if not sub_id:
        # Nothing on Stripe to cancel — just clear the flag
        await db.users.update_one({"id": user["id"]}, {"$set": {"vip_auto_renew": False}})
        return {"cancelled": True, "auto_renew": False}
    try:
        # Cancel at period end so the member keeps VIP until vip_until, but is never charged again
        stripe.Subscription.modify(sub_id, cancel_at_period_end=True)
    except stripe.error.StripeError as e:
        raise HTTPException(500, f"Stripe error: {e.user_message or str(e)}")
    await db.users.update_one({"id": user["id"]}, {"$set": {"vip_auto_renew": False}})
    return {"cancelled": True, "auto_renew": False, "vip_until": user.get("vip_until")}

ACCOUNT_GRACE_DAYS = 30

async def _purge_user(uid: str):
    """Permanently remove a user and all their related data from the database."""
    await db.likes.delete_many({"$or": [{"from_id": uid}, {"to_id": uid}]})
    await db.matches.delete_many({"$or": [{"a_id": uid}, {"b_id": uid}, {"users": uid}]})
    await db.notifications.delete_many({"user_id": uid})
    await db.conversations.delete_many({"participants": uid})
    await db.messages.delete_many({"$or": [{"from_id": uid}, {"to_id": uid}]})
    await db.spins.delete_many({"used_by": uid})
    await db.payout_accounts.delete_many({"user_id": uid})
    await db.vip_avail.delete_many({"vip_id": uid})
    await db.vip_sched.delete_many({"$or": [{"vip_id": uid}, {"requester_id": uid}]})
    await db.date_bookings.delete_many({"$or": [{"from_id": uid}, {"to_id": uid}]})
    await db.users.delete_one({"id": uid})

@api.delete("/account")
async def delete_account(user=Depends(get_current_user)):
    """Immediate hard delete (kept for compatibility). The UI now uses /account/delete-request."""
    await _purge_user(user["id"])
    return {"deleted": True}

@api.get("/account/status")
async def account_status(user=Depends(get_current_user)):
    return {"account_status": user.get("account_status") or "ACTIVE",
            "deletion_scheduled_at": user.get("deletion_scheduled_at")}

@api.post("/account/pause")
async def account_pause(user=Depends(get_current_user)):
    """Take a break: hide the profile everywhere but keep all data. Logging back in reactivates it."""
    await db.users.update_one({"id": user["id"]},
        {"$set": {"account_status": "PAUSED", "paused_at": datetime.now(timezone.utc).isoformat()},
         "$unset": {"deletion_scheduled_at": "", "deletion_requested_at": ""}})
    return {"account_status": "PAUSED"}

@api.post("/account/delete-request")
async def account_delete_request(user=Depends(get_current_user)):
    """Schedule the account for permanent deletion after a 30-day grace period."""
    now = datetime.now(timezone.utc)
    purge_at = (now + timedelta(days=ACCOUNT_GRACE_DAYS)).isoformat()
    await db.users.update_one({"id": user["id"]},
        {"$set": {"account_status": "PENDING_DELETION",
                  "deletion_scheduled_at": purge_at,
                  "deletion_requested_at": now.isoformat()}})
    return {"account_status": "PENDING_DELETION", "deletion_scheduled_at": purge_at,
            "grace_days": ACCOUNT_GRACE_DAYS}

@api.post("/account/restore")
async def account_restore(user=Depends(get_current_user)):
    """Cancel a pending deletion (or a break) and set the account back to ACTIVE."""
    await db.users.update_one({"id": user["id"]},
        {"$set": {"account_status": "ACTIVE"},
         "$unset": {"deletion_scheduled_at": "", "deletion_requested_at": "", "paused_at": ""}})
    return {"account_status": "ACTIVE"}

@api.post("/payments/checkout")
async def create_checkout(req: CheckoutReq, user=Depends(get_current_user)):
    s = await get_settings()
    if req.package_id == "premium_monthly":
        pkg_name = PREMIUM_PACKAGE["name"]; amount = int(round(s["premium_amount"] * 100)); mode = "payment"
        metadata = {"user_id": user["id"], "package_id": "premium_monthly", "type": "premium"}
    elif req.package_id == "premium_lite_monthly":
        pkg_name = PREMIUM_LITE_PACKAGE["name"]; amount = int(round(PREMIUM_LITE_PACKAGE["amount"] * 100)); mode = "payment"
        metadata = {"user_id": user["id"], "package_id": "premium_lite_monthly", "type": "premium_lite"}
    elif req.package_id == "vip_monthly":
        pkg_name = VIP_PACKAGE["name"]; amount = int(round(VIP_PACKAGE["amount"] * 100)); mode = "subscription"
        metadata = {"user_id": user["id"], "package_id": "vip_monthly", "type": "vip"}
    elif req.package_id == "custom":
        usd = round(float(req.usd_amount or 0), 2)
        if usd < s["custom_min_usd"]: raise HTTPException(400, f"Minimum ${s['custom_min_usd']}")
        base = int(usd * s["custom_coins_per_usd"])
        bonus = int(base * s["custom_bonus_pct"] / 100)
        pkg_name = f"Custom {base} coins (+{bonus} bonus)"; amount = int(round(usd * 100)); mode = "payment"
        metadata = {"user_id": user["id"], "package_id": "custom", "type": "coins", "coins": str(base + bonus)}
    else:
        pkg = next((p for p in s["coin_packages"] if p["id"] == req.package_id), None)
        if not pkg: raise HTTPException(400, "Unknown package")
        pkg_name = pkg["name"]; amount = int(round(pkg["amount"] * 100)); mode = "payment"
        metadata = {"user_id": user["id"], "package_id": req.package_id, "type": "coins", "coins": str(pkg["coins"] + pkg["bonus"])}
    try:
        # Tax code for Stripe-managed payments: SaaS for premium/VIP, general-digital for coins
        _tax_code = "txcd_10103001" if metadata.get("type") in ("premium", "premium_lite", "vip") else "txcd_10000000"
        _price_data = {"currency": "usd", "product_data": {"name": pkg_name, "tax_code": _tax_code}, "unit_amount": amount}
        _extra = {}
        if mode == "subscription":
            _price_data["recurring"] = {"interval": "month"}
            # carry metadata onto the subscription so recurring invoices can be attributed
            _extra["subscription_data"] = {"metadata": metadata}
        _base = dict(
            line_items=[{"price_data": _price_data, "quantity": 1}],
            mode=mode,
            # Omitting payment_method_types lets Stripe show every method enabled in the Dashboard for the buyer's country.
            customer_email=user.get("email"),
            locale="auto",
            success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{req.origin_url}/payment/cancel",
            metadata=metadata,
            **_extra,
        )
        if mode == "payment":
            # Emergent-managed Stripe payments (SMP): Stripe handles tax calculation, collection,
            # filing & remittance plus fraud/dispute handling. Fall back to Stripe Tax if ineligible.
            try:
                session = stripe.checkout.Session.create(**_base, managed_payments={"enabled": True})
            except stripe.error.InvalidRequestError as e:
                msg = (e.user_message or "").lower()
                if "managed payments" in msg or "ineligible" in msg:
                    session = stripe.checkout.Session.create(**_base, automatic_tax={"enabled": True}, billing_address_collection="required")
                else:
                    raise
        else:
            # Subscriptions bill the saved card monthly (SMP doesn't cover recurring billing)
            session = stripe.checkout.Session.create(**_base, billing_address_collection="auto")
    except stripe.error.StripeError as e:
        raise HTTPException(500, f"Stripe error: {e.user_message or str(e)}")
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["id"], "package_id": req.package_id,
        "amount": amount / 100, "currency": "usd", "status": "initiated",
        "payment_status": "pending", "metadata": metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"checkout_url": session.url, "session_id": session.id}

async def _fulfill(session_id: str, meta: dict):
    """Idempotent — grants coins/premium once."""
    rec = await db.payment_transactions.find_one({"session_id": session_id})
    if not rec or rec.get("fulfilled"):
        return
    user_id = meta.get("user_id") or rec.get("user_id")
    if meta.get("type") == "coins":
        coins = int(meta.get("coins", 0))
        await db.users.update_one({"id": user_id}, {"$inc": {"coins": coins}})
        req_pkg = (await get_settings()).get("referral_package_id")
        if not req_pkg or meta.get("package_id") == req_pkg:
            await _reward_referrer(user_id)
    elif meta.get("type") == "premium":
        u = await db.users.find_one({"id": user_id})
        start = datetime.now(timezone.utc)
        cur = u.get("premium_until")
        if cur:
            try:
                cur_dt = datetime.fromisoformat(cur.replace("Z", "+00:00"))
                if cur_dt > start: start = cur_dt
            except Exception: pass
        new_until = (start + timedelta(days=30)).isoformat()
        await db.users.update_one({"id": user_id}, {"$set": {"premium_until": new_until, "premium_auto_renew": True}})
    elif meta.get("type") == "premium_lite":
        u = await db.users.find_one({"id": user_id})
        await db.users.update_one({"id": user_id}, {"$set": {"premium_lite_until": extend_until(u.get("premium_lite_until"))}})
    elif meta.get("type") == "vip":
        u = await db.users.find_one({"id": user_id})
        def _ext(cur):
            s0 = datetime.now(timezone.utc)
            if cur:
                try:
                    c = datetime.fromisoformat(cur.replace("Z", "+00:00"))
                    if c > s0: s0 = c
                except Exception: pass
            return (s0 + timedelta(days=30)).isoformat()
        await db.users.update_one({"id": user_id}, {"$set": {
            "premium_until": _ext(u.get("premium_until")), "vip_until": _ext(u.get("vip_until")),
            "premium_auto_renew": True, "vip_auto_renew": True}})
    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"fulfilled": True}})

@api.get("/payments/status/{session_id}")
async def payment_status(session_id: str):
    rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not rec: raise HTTPException(404, "Transaction not found")
    if rec.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await db.payment_transactions.update_one(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": "paid",
                              "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                await _fulfill(session_id, rec.get("metadata") or {})
                rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        except stripe.error.StripeError:
            pass
    return {"session_id": rec["session_id"], "status": rec["status"], "payment_status": rec["payment_status"]}

@api.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t == "checkout.session.completed":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"),
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        # For recurring VIP, persist the Stripe subscription + customer so we can renew / cancel it later
        meta = obj.get("metadata") or {}
        if obj.get("mode") == "subscription" and meta.get("user_id"):
            await db.users.update_one({"id": meta["user_id"]}, {"$set": {
                "stripe_subscription_id": obj.get("subscription"),
                "stripe_customer_id": obj.get("customer"),
                "vip_auto_renew": True}})
        await _fulfill(obj["id"], meta)
    elif t == "invoice.paid":
        # Recurring monthly charge succeeded on the saved bank card -> extend VIP by 30 days
        sub_id = obj.get("subscription")
        cust_id = obj.get("customer")
        u = None
        if sub_id:
            u = await db.users.find_one({"stripe_subscription_id": sub_id})
        if not u and cust_id:
            u = await db.users.find_one({"stripe_customer_id": cust_id})
        # Skip the very first invoice (already granted via checkout.session.completed)
        if u and obj.get("billing_reason") not in ("subscription_create",):
            await db.users.update_one({"id": u["id"]}, {"$set": {
                "premium_until": extend_until(u.get("premium_until")),
                "vip_until": extend_until(u.get("vip_until")),
                "vip_auto_renew": True}})
            await notify(u["id"], "vip_renewed", "VIP renewed 👑",
                         "Your VIP subscription was renewed for another month on your saved card.", {}, email=True)
    elif t == "invoice.payment_failed":
        # Card declined / no funds -> let VIP lapse and notify (per policy: no grace period)
        sub_id = obj.get("subscription"); cust_id = obj.get("customer")
        u = (await db.users.find_one({"stripe_subscription_id": sub_id})) if sub_id else None
        if not u and cust_id:
            u = await db.users.find_one({"stripe_customer_id": cust_id})
        if u:
            await db.users.update_one({"id": u["id"]}, {"$set": {"vip_auto_renew": False}})
            await notify(u["id"], "vip_renew_failed", "VIP renewal failed",
                         "We couldn't charge your card, so your VIP will expire at the end of the period. Update your card or buy VIP again to keep access.",
                         {}, email=True)
    elif t == "customer.subscription.deleted":
        sub_id = obj.get("id")
        u = await db.users.find_one({"stripe_subscription_id": sub_id}) if sub_id else None
        if u:
            await db.users.update_one({"id": u["id"]}, {"$set": {"vip_auto_renew": False, "stripe_subscription_id": None}})
    return {"status": "ok"}

# ---------- Health ----------
@api.get("/")
async def root():
    return {"service": "GiftsDates", "ok": True}

# ==================== Invite-on-a-Date (v2 state machine) ====================
PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "")
WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@giftsdates.com")
ADMIN_EMAIL_LIST = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]
DATE_WINDOW_HOURS = 3
INVITE_MIN_COINS = 150
DATES_LINK = f"{PUBLIC_APP_URL}/dates"

def _email_cta_html(title, body, link, cta="View on GiftsDates", footer=None, rtl=False):
    from html import escape as _esc
    cta = _esc(cta)
    base = _email_html(title, body, footer, rtl)
    if not link:
        return base
    btn = (f'<div style="text-align:center;margin:6px 0 2px"><a href="{link}" style="display:inline-block;'
           f'background:#e11d48;color:#fff;text-decoration:none;padding:12px 24px;border-radius:999px;'
           f'font-weight:700;font-family:Arial">{cta} &rarr;</a></div>')
    return base.replace('<div style="font-size:11px;color:#8a8598', btn + '<div style="font-size:11px;color:#8a8598')

def _now(): return datetime.now(timezone.utc)
def _iso(dt=None): return (dt or _now()).isoformat()
def _pdt(s):
    try: return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except Exception: return None

async def _admin_ids():
    return [u["id"] async for u in db.users.find({"email": {"$in": ADMIN_EMAIL_LIST}}, {"id": 1})]

async def _log_status(did, status, by):
    await db.dates.update_one({"id": did}, {"$set": {"status": status, "updated_at": _iso()},
                                            "$push": {"status_log": {"status": status, "at": _iso(), "by": by}}})
    await _close_date_cards(did)

async def _mini(uid):
    u = await db.users.find_one({"id": uid}, {"_id": 0, "id": 1, "name": 1, "photos": 1, "age": 1, "city": 1, "country": 1})
    if not u: return None
    ph = u.get("photos") or []
    return {"id": u["id"], "name": u.get("name"), "age": u.get("age"), "city": u.get("city"),
            "country": u.get("country"), "photo": ph[0] if ph else None}

BUSY_STATUSES = ["DATE_CONFIRMED", "DATE_COMPLETED_PENDING_VERIFICATION", "PHOTO_VERIFICATION_PENDING"]

async def _conflict(uid, start, end, exclude):
    docs = await db.dates.find({"status": {"$in": BUSY_STATUSES}, "id": {"$ne": exclude},
                                "$or": [{"inviter_id": uid}, {"recipient_id": uid}]}, {"_id": 0, "location": 1}).to_list(300)
    for x in docs:
        loc = x.get("location") or {}
        s, e = _pdt(loc.get("scheduled_start")), _pdt(loc.get("scheduled_end"))
        if s and e and start < e and s < end:
            return True
    return False

async def _complete(d, status):
    hold = int(d.get("total_hold", 0) or 0)
    if hold > 0 and not d.get("paid_out"):
        await db.users.update_one({"id": d["recipient_id"]}, {"$inc": {"withdrawable": hold}})
        await record_txn(d["recipient_id"], "DATE_COMPLETION", hold, d["id"], "Date completed — coins released")
    await db.dates.update_one({"id": d["id"]}, {"$set": {"paid_out": True}})
    await _log_status(d["id"], status, "system")

async def _refund(d, mode, status):
    hold = int(d.get("total_hold", 0) or 0)
    inv, rec = d["inviter_id"], d["recipient_id"]
    if hold > 0 and not d.get("refunded"):
        if mode == "full_inviter":
            await db.users.update_one({"id": inv}, {"$inc": {"coins": hold}})
            await record_txn(inv, "DATE_REFUND", hold, d["id"], "Full refund (recipient cancelled)")
        else:  # date coins 50/25/25; a paid taxi fee is always refunded in full
            tr = d.get("transportation") or {}
            taxi = min(hold, int(tr.get("taxi_amount") or 0)) if tr.get("type") == "taxi" and tr.get("status") == "confirmed" else 0
            base = hold - taxi
            r_inv, r_rec = base // 2, base // 4
            fee = base - r_inv - r_rec
            r_inv += taxi
            await db.users.update_one({"id": inv}, {"$inc": {"coins": r_inv}})
            await record_txn(inv, "DATE_REFUND", r_inv, d["id"], "50% refund" + (f" + full taxi refund ({taxi})" if taxi else ""))
            await db.users.update_one({"id": rec}, {"$inc": {"withdrawable": r_rec}})
            await record_txn(rec, "RECIPIENT_COMPENSATION", r_rec, d["id"], "25% inconvenience compensation")
            await record_txn("PLATFORM", "PLATFORM_FEE", fee, d["id"], "25% platform fee")
    await db.dates.update_one({"id": d["id"]}, {"$set": {"refunded": True}})

_NEXT = {
    "INVITATION_SENT": ("Invitation sent", "Waiting for {o} to choose a date option.", "Choose one of the proposed date options."),
    "DATE_ACTIVITY_SELECTED": ("Date option chosen", "Propose a meeting location, date and time.", "Waiting for {o} to propose the location."),
    "LOCATION_PROPOSED": ("Location proposed", "Waiting for {o} to confirm the location or request a taxi.", "Confirm the location, or request a taxi."),
    "TAXI_REQUESTED": ("Taxi requested", "Confirm & pay the taxi, or offer a pickup instead.", "Waiting for {o}'s transportation decision."),
    "PICKUP_ADDRESS_PENDING": ("Pickup offered", "Waiting for {o} to share a pickup address.", "Share your pickup address."),
    "PICKUP_ADDRESS_SELECTED": ("Pickup address shared", "Confirm pickup, or pay the taxi instead.", "Waiting for {o} to confirm the pickup."),
    "DATE_CONFIRMED": ("Date confirmed", "Your date is confirmed — see the details below.", "Your date is confirmed — see the details below."),
    "DATE_COMPLETED_PENDING_VERIFICATION": ("Date finished", "Submit a photo (24h after start) or it auto-completes after 72h.", "Submit a photo (24h after start) or it auto-completes after 72h."),
    "PHOTO_VERIFICATION_PENDING": ("Verification submitted", "Waiting for admin review.", "Waiting for admin review."),
    "COMPLETED": ("Completed", "This date is completed.", "This date is completed."),
    "COMPLETED_AUTO": ("Completed", "Auto-completed after 72h.", "Auto-completed after 72h."),
    "CANCELLED": ("Cancelled", "This date was cancelled.", "This date was cancelled."),
    "CANCELLED_TRANSPORTATION": ("Cancelled", "Cancelled over transportation.", "Cancelled over transportation."),
    "REPORTED": ("Reported", "Under review by our team.", "Under review by our team."),
    "UNDER_ADMIN_REVIEW": ("Under review", "Our team is reviewing this date.", "Our team is reviewing this date."),
    "REFUNDED": ("Refunded", "This date was refunded.", "This date was refunded."),
}

def _serialize(d, viewer_id, other_mini):
    inv = d["inviter_id"] == viewer_id
    label, inv_step, rec_step = _NEXT.get(d["status"], (d["status"], "", ""))
    step = (inv_step if inv else rec_step).replace("{o}", (other_mini or {}).get("name") or "the other person")
    loc = d.get("location") or {}
    start = _pdt(loc.get("scheduled_start"))
    windows = {}
    if start:
        windows = {"lock_at": _iso(start - timedelta(minutes=30)), "report_open": _iso(start),
                   "report_close": _iso(start + timedelta(hours=DATE_WINDOW_HOURS)), "verify_at": _iso(start + timedelta(hours=24)),
                   "auto_complete_at": _iso(start + timedelta(hours=72))}
    trans = dict(d.get("transportation") or {})
    if not inv:  # hide pickup address from inviter? pickup is recipient's; recipient sees it, inviter sees only after selected. keep as-is
        pass
    return {"id": d["id"], "role": "inviter" if inv else "recipient", "status": d["status"], "status_label": label,
            "next_step": step, "other": other_mini, "options": d.get("options"), "chosen_idea": d.get("chosen_idea"),
            "selected_activity": d.get("selected_activity") or (d.get("chosen_idea") or {}).get("name"),
            "activity_option_1": d.get("activity_option_1"), "activity_option_2": d.get("activity_option_2"), "activity_option_3": d.get("activity_option_3"),
            "proposed_start": d.get("proposed_start"), "proposed_end": d.get("proposed_end"),
            "coins": d.get("coins"), "total_hold": d.get("total_hold"), "gift": d.get("gift"),
            "location": loc, "transportation": trans, "report": bool(d.get("report")) and (d["report"].get("status") or "open") == "open",
            "report_info": _report_view(d.get("report"), viewer_id),
            "verification": (d.get("verification") or {}).get("status"), "windows": windows,
            "decline_reason": d.get("decline_reason"), "declined_by_me": d.get("declined_by") == viewer_id,
            "server_now": _iso(), "created_at": d.get("created_at")}

class InviteCreateReq(BaseModel):
    recipient_id: str
    activity_option_1: str
    activity_option_2: str
    activity_option_3: str
    scheduled_start: str  # ISO day+time the inviter picks from the recipient's availability
    local_day: Optional[str] = None  # YYYY-MM-DD availability day chosen
    local_time: Optional[str] = None  # HH:MM start in the inviter's local clock
    coins: int
    gift_id: Optional[str] = None
    safety_ack: bool = False
class ChooseIdeaReq(BaseModel):
    idea_id: str
class InviteLocationReq(BaseModel):
    address_confirmed: bool = False
    venue: str
    address: Optional[str] = ""
    city: Optional[str] = ""
    meeting_point: Optional[str] = ""
    country: Optional[str] = ""
    postal_code: Optional[str] = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    scheduled_start: Optional[str] = None
class InviteTaxiReq(BaseModel):
    amount: int
class PickupAddrReq(BaseModel):
    address_confirmed: bool = False
    pickup_address: Optional[str] = ""
    venue: Optional[str] = ""
    street: Optional[str] = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    city: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
class GeoVerifyReq(BaseModel):
    address: Optional[str] = ""
    city: Optional[str] = ""
    postal_code: Optional[str] = ""
    country: Optional[str] = ""

_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_norm_pc = lambda s: re.sub(r"[^0-9a-z]", "", (s or "").lower())

def _fold(s: str) -> str:
    import unicodedata
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower())

_GENERIC = {"avenue", "ave", "av", "street", "str", "st", "road", "rd", "rue", "boulevard", "blvd", "drive", "dr", "lane", "ln", "chemin", "strasse", "via", "calle", "the", "north", "south", "east", "west"}

def _street_ok(req_street: str, found_street: str, found_no: str = "") -> bool:
    """The street name the user typed must appear in the map result; a different house number is rejected."""
    words = [_fold(w) for w in re.split(r"[\s,.'’\-]+", req_street or "")]
    names = [w for w in words if len(w) >= 3 and not w.isdigit() and w not in _GENERIC]
    fs = _fold(found_street)
    if names and not any(w in fs for w in names): return False
    nums = re.findall(r"\d+[a-z]?", (req_street or "").lower())
    if found_no and nums and _fold(found_no) not in [_fold(n) for n in nums] and re.sub(r"\D", "", found_no) not in nums: return False
    return True

async def _photon_lookup(client, street, city, postal, country):
    """Fuzzy OSM search (handles abbreviations/apostrophes); returns a Nominatim-shaped hit or None."""
    r = await client.get("https://photon.komoot.io/api/", params={"q": f"{street}, {city}, {postal}, {country}", "limit": 5, "lang": "en"})
    for f in (r.json() or {}).get("features", []):
        p = f.get("properties") or {}
        if not p.get("street") and p.get("type") != "street": continue
        if not _street_ok(street, p.get("street") or p.get("name"), p.get("housenumber") or ""): continue
        if _fold(p.get("country")) != _fold(country): continue
        if _fold(city) not in (_fold(p.get("city")) + _fold(p.get("county")) + _fold(p.get("district")) + _fold(p.get("name"))): continue
        pc = _norm_pc(p.get("postcode"))
        if pc and _norm_pc(postal)[:3] != pc[:3]: continue
        lng, lat = f["geometry"]["coordinates"]
        name = ", ".join(x for x in [p.get("name") if p.get("type") != "house" else None, " ".join(x for x in [p.get("housenumber"), p.get("street")] if x), p.get("city"), p.get("state"), p.get("postcode"), p.get("country")] if x)
        return {"lat": lat, "lon": lng, "display_name": name}
    return None

async def _geocode_address(street: str, city: str, postal: str, country: str, venue: str = "", confirmed: bool = False) -> dict:
    """Checks that the address exists on the map (OpenStreetMap). Raises 400 with a code when it doesn't."""
    street, city, postal, country = [(x or "").strip() for x in (street, city, postal, country)]
    if not all([street, city, postal, country]) or (venue is not None and not (venue or "").strip()):
        raise HTTPException(400, "ADDRESS_FIELDS_REQUIRED")
    if not re.search(r"\d", street):
        raise HTTPException(400, "ADDRESS_NUMBER_REQUIRED")
    key = "|".join(x.lower() for x in (street, city, postal, country))
    hit = await db.geo_cache.find_one({"key": key, "ok": True}, {"_id": 0})
    if hit:
        return {**hit["result"], "unverified": False}
    queries = [{"street": street, "city": city, "postalcode": postal, "country": country},
               {"street": street, "city": city, "country": country},
               {"q": f"{street}, {city}, {postal}, {country}"}]
    found = None
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "GiftsDates/1.0 (support@giftsdates.com)"}) as client:
            try:
                found = await _photon_lookup(client, street, city, postal, country)
            except Exception as e:
                logging.warning(f"photon failed: {e}")
            for q in ([] if found else queries):
                try:
                    r = await client.get(_NOMINATIM, params={**q, "format": "json", "addressdetails": 1, "limit": 5})
                    items = r.json() or []
                except Exception as e:
                    logging.warning(f"nominatim failed: {e}"); break
                for it in items:
                    a = it.get("address") or {}
                    if not a.get("road") and not a.get("pedestrian") and not a.get("house_number"): continue
                    if not _street_ok(street, a.get("road") or a.get("pedestrian") or "", a.get("house_number") or ""): continue
                    pc = _norm_pc(a.get("postcode"))
                    if pc and _norm_pc(postal)[:3] != pc[:3]: continue
                    found = it; break
                if found: break
    except Exception as e:
        logging.warning(f"geocode failed: {e}")
        if confirmed: return {"lat": None, "lng": None, "display_name": "", "unverified": True}
        raise HTTPException(503, "ADDRESS_CHECK_UNAVAILABLE")
    if not found:
        # user explicitly confirmed the address is correct and accepted the risk
        if confirmed: return {"lat": None, "lng": None, "display_name": "", "unverified": True}
        raise HTTPException(400, "ADDRESS_NOT_FOUND")
    res = {"lat": float(found["lat"]), "lng": float(found["lon"]), "display_name": found.get("display_name", ""), "unverified": False}
    await db.geo_cache.insert_one({"key": key, "ok": True, "result": res, "created_at": _iso()})
    return res

async def _apply_geo(req, venue=None):
    """Validate a request's address fields against the map and overwrite lat/lng with the geocoder's."""
    geo = await _geocode_address(req.address, req.city, req.postal_code, req.country, venue=venue, confirmed=getattr(req, "address_confirmed", False))
    req.lat, req.lng = geo["lat"], geo["lng"]
    if hasattr(req, "unverified"): req.unverified = geo["unverified"]
    return geo

@api.post("/geo/verify")
async def geo_verify(req: GeoVerifyReq, user=Depends(get_current_user)):
    return {"ok": True, **(await _geocode_address(req.address, req.city, req.postal_code, req.country, venue=None))}
class DateMsgReq(BaseModel):
    text: str

async def _recipient_slot_or_400(rec, start_dt, local_day=None, local_time=None):
    """Validate start_dt is a bookable 2.5h date inside the recipient's availability and
    not already busy or locked. Returns (start_iso, end_iso) for the full 3h locked block."""
    if not start_dt: raise HTTPException(400, "Invalid start time")
    day = (local_day or start_dt.strftime("%Y-%m-%d"))[:10]
    wins = day_windows(rec, day)
    if wins is not None and not wins: raise HTTPException(400, "DAY_UNAVAILABLE")
    if wins and fit_start(wins, _hm_to_min(local_time or start_dt.strftime("%H:%M"))) is None:
        raise HTTPException(400, f"TIME_UNAVAILABLE:{wins_label(wins)}")
    await _assert_slot_free(rec, day, _hm_to_min(local_time or start_dt.strftime("%H:%M")), start_dt)
    block_end = start_dt + timedelta(hours=DATE_WINDOW_HOURS)
    for ls in (rec.get("locked_slots") or []):
        ls_s, ls_e = _pdt(ls.get("start")), _pdt(ls.get("end"))
        if ls_s and f"{ls.get('date') or ls_s.strftime('%Y-%m-%d')}|{ls_s.strftime('%H:%M')}" in set(rec.get("unlocked_slots") or []): continue
        if ls_s and ls_e and start_dt < ls_e and ls_s < block_end:
            raise HTTPException(400, "SLOT_LOCKED")
    if await _conflict(rec["id"], start_dt, block_end, "___new___"):
        raise HTTPException(400, "TIME_CONFLICT")
    return _iso(start_dt), _iso(block_end)

@api.post("/invites")
async def create_invite(req: InviteCreateReq, user=Depends(get_current_user)):
    if req.recipient_id == user["id"]: raise HTTPException(400, "Cannot invite yourself")
    if not req.safety_ack: raise HTTPException(400, "SAFETY_ACK_REQUIRED")
    rec = await db.users.find_one({"id": req.recipient_id}, {"_id": 0, "id": 1, "name": 1, "date_price": 1, "locked_slots": 1, "unlocked_slots": 1, **AVAIL_FIELDS})
    if not rec: raise HTTPException(404, "Recipient not found")
    # 3 mandatory custom date-idea options typed by the inviter (no predefined catalog)
    opts_text = [(req.activity_option_1 or "").strip(), (req.activity_option_2 or "").strip(), (req.activity_option_3 or "").strip()]
    if any(not o for o in opts_text): raise HTTPException(400, "ACTIVITIES_REQUIRED")
    opts_text = [o[:120] for o in opts_text]
    # inviter picks a specific day + time from the recipient's availability
    proposed_start, proposed_end = await _recipient_slot_or_400(rec, _pdt(req.scheduled_start), req.local_day, req.local_time)
    floor = max(INVITE_MIN_COINS, int(rec.get("date_price") or 0))
    if req.coins < floor: raise HTTPException(400, f"MIN_COINS:{floor}")
    if ((user.get("coins") or 0) + (user.get("withdrawable") or 0)) < req.coins: raise HTTPException(400, "Insufficient coins")
    options = [{"idea_id": f"opt{n}", "name": text, "order": n} for n, text in enumerate(opts_text, start=1)]
    await spend_coins(user["id"], req.coins)
    await record_txn(user["id"], "DATE_PAYMENT", -req.coins, None, "Date invitation escrow")
    gift = None
    if req.gift_id:
        g = next((x for x in (await get_settings())["gifts"] if x["id"] == req.gift_id), None)
        if g and ((user.get("coins") or 0) + (user.get("withdrawable") or 0)) >= g["cost"]:
            await spend_coins(user["id"], g["cost"])
            await record_txn(user["id"], "DATE_PAYMENT", -g["cost"], None, f"Gift: {g['id']}")
            net = round(g["cost"] * (1 - (await get_settings())["commission"]), 2)
            await db.users.update_one({"id": req.recipient_id}, {"$inc": {"withdrawable": net}})
            gift = {"id": g["id"], "icon": g.get("icon"), "cost": g["cost"]}
    did = str(uuid.uuid4())
    doc = {"id": did, "inviter_id": user["id"], "recipient_id": req.recipient_id, "options": options,
           "activity_option_1": opts_text[0], "activity_option_2": opts_text[1], "activity_option_3": opts_text[2],
           "proposed_start": proposed_start, "proposed_end": proposed_end,
           "local_day": (req.local_day or proposed_start)[:10], "local_time": req.local_time or _pdt(proposed_start).strftime("%H:%M"),
           "chosen_idea": None, "selected_activity": None, "coins": req.coins, "total_hold": req.coins, "gift": gift,
           "location": None, "transportation": None, "status": "INVITATION_SENT",
           "status_log": [{"status": "INVITATION_SENT", "at": _iso(), "by": user["id"]}], "report": None,
           "verification": None, "paid_out": False, "refunded": False, "reminders": {},
           "created_at": _iso(), "updated_at": _iso(), "expires_at": _iso(_now() + timedelta(days=7))}
    await db.dates.insert_one(doc)
    await notify(req.recipient_id, "date_request", "You received a new date invitation",
                 f"{user['name']} invited you on a date ({proposed_start[:16].replace('T', ' ')}) with {len(options)} option(s). Choose one to confirm, or reject.",
                 {"date_id": did}, email=True, link=DATES_LINK, cta="View Invitation",
                 sms=True, sms_body=f"GiftsDates: {user['name']} invited you on a date with {len(options)} options. Choose one to confirm, or reject:")
    await _date_chat_card(user["id"], req.recipient_id, "invite", did, "invite", "💌 Date invitation", req.recipient_id,
                          {"when": proposed_start, "coins": req.coins, "options": [{"id": o["idea_id"], "name": o["name"]} for o in options]})
    return {"id": did, "status": "INVITATION_SENT"}

async def _get_party(did, uid, role=None):
    d = await db.dates.find_one({"id": did}, {"_id": 0})
    if not d: raise HTTPException(404, "Not found")
    if uid not in (d["inviter_id"], d["recipient_id"]): raise HTTPException(403, "Forbidden")
    if role == "inviter" and d["inviter_id"] != uid: raise HTTPException(403, "Only the inviter can do this")
    if role == "recipient" and d["recipient_id"] != uid: raise HTTPException(403, "Only the recipient can do this")
    return d

@api.post("/invites/{did}/choose")
async def invite_choose(did: str, req: ChooseIdeaReq, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "recipient")
    if d["status"] != "INVITATION_SENT": raise HTTPException(400, "Cannot choose now")
    opt = next((o for o in d["options"] if o["idea_id"] == req.idea_id), None)
    if not opt: raise HTTPException(400, "Invalid option")
    await db.dates.update_one({"id": did}, {"$set": {"chosen_idea": {"idea_id": opt["idea_id"], "name": opt["name"]}, "selected_activity": opt["name"]}})
    await _log_status(did, "DATE_ACTIVITY_SELECTED", user["id"])
    await notify(d["inviter_id"], "date_accepted", "Your date invitation was accepted",
                 f"{user['name']} chose: {opt['name']}. Now propose a meeting location.", {"date_id": did}, email=True, link=DATES_LINK, cta="View Date",
                 sms=True, sms_body=f"GiftsDates: {user['name']} accepted your date and chose {opt['name']}. Open the app to confirm & propose a location:")
    await db.messages.update_many({"ref_id": did, "type": "date_card", "event": "invite"}, {"$set": {"data.chosen": opt["name"]}})
    await _date_chat_card(user["id"], d["inviter_id"], "invite", did, "accepted", f"✅ Invitation accepted · {opt['name']}", data={"option": opt["name"]})
    return {"ok": True, "status": "DATE_ACTIVITY_SELECTED"}

@api.post("/invites/{did}/location")
async def invite_location(did: str, req: InviteLocationReq, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "inviter")
    if d["status"] not in ("DATE_ACTIVITY_SELECTED", "LOCATION_PROPOSED"): raise HTTPException(400, "Cannot set location now")
    # date & time were fixed upfront at invitation; the inviter only adds the venue here
    start = _pdt(d.get("proposed_start") or req.scheduled_start)
    if not start: raise HTTPException(400, "Invalid start time")
    end = _pdt(d.get("proposed_end")) or (start + timedelta(hours=DATE_WINDOW_HOURS))
    if await _conflict(user["id"], start, end, did) or await _conflict(d["recipient_id"], start, end, did):
        raise HTTPException(400, "TIME_CONFLICT")
    geo = await _geocode_address(req.address, req.city, req.postal_code, req.country, venue=req.venue, confirmed=req.address_confirmed)
    loc = {"unverified": geo["unverified"], "venue": req.venue.strip(), "address": req.address.strip(), "city": req.city.strip(), "meeting_point": req.meeting_point or "",
           "country": req.country.strip(), "postal_code": req.postal_code.strip(), "lat": geo["lat"], "lng": geo["lng"],
           "scheduled_start": _iso(start), "scheduled_end": _iso(end)}
    await db.dates.update_one({"id": did}, {"$set": {"location": loc}})
    await _log_status(did, "LOCATION_PROPOSED", user["id"])
    await notify(d["recipient_id"], "date_location", "A meeting location has been proposed",
                 f"{user['name']} proposed {req.venue}. Confirm it or request a taxi.", {"date_id": did}, email=True, link=DATES_LINK, cta="View Date",
                 sms=True, sms_body=f"GiftsDates: {user['name']} proposed {req.venue}. Open the app to confirm the date or request a taxi:")
    await _date_chat_card(user["id"], d["recipient_id"], "invite", did, "location", f"📍 Meeting place · {loc['venue']}", d["recipient_id"],
                          {"when": loc["scheduled_start"], "location": _loc_card(loc)})
    return {"ok": True, "status": "LOCATION_PROPOSED"}

@api.post("/invites/{did}/location/confirm")
async def invite_location_confirm(did: str, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "recipient")
    if d["status"] != "LOCATION_PROPOSED": raise HTTPException(400, "Nothing to confirm")
    await _log_status(did, "DATE_CONFIRMED", user["id"])
    for uid in (d["inviter_id"], d["recipient_id"]):
        await notify(uid, "date_accepted", "Your date is confirmed", "The meeting location was confirmed. See details in Dates.", {"date_id": did}, email=True, link=DATES_LINK, cta="View Date")
    await _date_chat_card(user["id"], d["inviter_id"], "invite", did, "confirmed", "✅ Meeting place confirmed — date confirmed")
    return {"ok": True, "status": "DATE_CONFIRMED"}

@api.post("/invites/{did}/location/reject")
async def invite_location_reject(did: str, reason: Optional[str] = None, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "recipient")
    if d["status"] != "LOCATION_PROPOSED": raise HTTPException(400, "Nothing to reject")
    # Invited person rejects the proposed location -> full refund back to the inviter
    await _refund(d, "full_inviter", "CANCELLED")
    # ...and their availability for that day+time is locked (shown as locked in the calendar)
    lock_s = (d.get("location") or {}).get("scheduled_start") or d.get("proposed_start")
    lock_e = (d.get("location") or {}).get("scheduled_end") or d.get("proposed_end")
    if lock_s:
        await db.users.update_one({"id": d["recipient_id"]}, {"$push": {"locked_slots": {
            "date": lock_s[:10], "start": lock_s, "end": lock_e, "reason": "rejected_location",
            "date_id": did, "locked_at": _iso()}}})
    await _log_status(did, "CANCELLED", user["id"])
    await notify(d["inviter_id"], "date_declined", "Your date location was rejected",
                 f"{user['name']} rejected the proposed location. All coins were refunded to you.", {"date_id": did}, email=True, link=DATES_LINK, cta="View Details")
    reason = _decline_reason(reason) or "Meeting place rejected"
    await db.dates.update_one({"id": did}, {"$set": {"decline_reason": reason, "declined_by": user["id"]}})
    await _date_chat_card(user["id"], d["inviter_id"], "invite", did, "declined", "❌ Meeting place rejected — coins refunded", data={"reason": reason})
    return {"ok": True, "status": "CANCELLED"}


@api.post("/invites/{did}/taxi/request")
async def invite_taxi_request(did: str, req: InviteTaxiReq, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "recipient")
    if d["status"] != "LOCATION_PROPOSED": raise HTTPException(400, "Cannot request taxi now")
    if req.amount <= 0: raise HTTPException(400, "Invalid amount")
    await db.dates.update_one({"id": did}, {"$set": {"transportation": {"type": "taxi", "taxi_amount": int(req.amount), "status": "requested", "requested_by": user["id"]}}})
    await _log_status(did, "TAXI_REQUESTED", user["id"])
    await notify(d["inviter_id"], "date_taxi", "Transportation request received",
                 f"{user['name']} requested a taxi fee of 🪙{req.amount}. Confirm & pay, or offer a pickup.", {"date_id": did}, email=True, link=DATES_LINK, cta="Review Request")
    return {"ok": True, "status": "TAXI_REQUESTED"}

@api.post("/invites/{did}/taxi/confirm")
async def invite_taxi_confirm(did: str, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "inviter")
    if d["status"] not in ("TAXI_REQUESTED", "PICKUP_ADDRESS_SELECTED"): raise HTTPException(400, "Cannot confirm taxi now")
    amount = int((d.get("transportation") or {}).get("taxi_amount") or 0)
    if amount > 0:
        if ((user.get("coins") or 0) + (user.get("withdrawable") or 0)) < amount: raise HTTPException(400, "Insufficient coins")
        await spend_coins(user["id"], amount)
        await record_txn(user["id"], "DATE_PAYMENT", -amount, did, "Taxi fee escrow")
        await db.dates.update_one({"id": did}, {"$inc": {"total_hold": amount}})
    await db.dates.update_one({"id": did}, {"$set": {"transportation.type": "taxi", "transportation.status": "confirmed", "transportation.confirmed_by": user["id"]}})
    await _log_status(did, "DATE_CONFIRMED", user["id"])
    for uid in (d["inviter_id"], d["recipient_id"]):
        await notify(uid, "date_taxi", "Transportation confirmed", "Taxi confirmed — your date is confirmed.", {"date_id": did}, email=True, link=DATES_LINK, cta="View Date")
    return {"ok": True, "status": "DATE_CONFIRMED"}

@api.post("/invites/{did}/pickup/offer")
async def invite_pickup_offer(did: str, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "inviter")
    if d["status"] not in ("TAXI_REQUESTED", "PICKUP_ADDRESS_SELECTED"): raise HTTPException(400, "Cannot offer pickup now")
    await db.dates.update_one({"id": did}, {"$set": {"transportation.type": "pickup", "transportation.status": "awaiting_address"}})
    await _log_status(did, "PICKUP_ADDRESS_PENDING", user["id"])
    await notify(d["recipient_id"], "date_taxi", "Pickup offered", f"{user['name']} offered to pick you up. Share your pickup address.", {"date_id": did}, email=True, link=DATES_LINK, cta="View Date")
    return {"ok": True, "status": "PICKUP_ADDRESS_PENDING"}

@api.post("/invites/{did}/pickup/address")
async def invite_pickup_address(did: str, req: PickupAddrReq, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "recipient")
    if d["status"] != "PICKUP_ADDRESS_PENDING": raise HTTPException(400, "Cannot submit pickup now")
    street = (req.street or "").strip()
    geo = await _geocode_address(street, req.city, req.postal_code, req.country, venue=req.venue, confirmed=req.address_confirmed)
    full = ", ".join(x.strip() for x in [req.venue, street, req.city, req.postal_code, req.country] if x and x.strip())
    _pu = {"transportation.pickup_address": full, "transportation.status": "address_selected",
           "transportation.pickup_venue": req.venue.strip(), "transportation.pickup_street": street,
           "transportation.pickup_lat": geo["lat"], "transportation.pickup_lng": geo["lng"],
           "transportation.pickup_city": req.city.strip(), "transportation.pickup_country": req.country.strip(),
           "transportation.pickup_postal_code": req.postal_code.strip(), "transportation.pickup_unverified": geo["unverified"]}
    await db.dates.update_one({"id": did}, {"$set": _pu})
    await _log_status(did, "PICKUP_ADDRESS_SELECTED", user["id"])
    await notify(d["inviter_id"], "date_taxi", "Pickup address shared", f"{user['name']} shared a pickup address. Confirm pickup or pay taxi instead.", {"date_id": did}, email=True, link=DATES_LINK, cta="View Date")
    return {"ok": True, "status": "PICKUP_ADDRESS_SELECTED"}

@api.post("/invites/{did}/pickup/reject")
async def invite_pickup_reject(did: str, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "recipient")
    if d["status"] != "PICKUP_ADDRESS_PENDING": raise HTTPException(400, "Nothing to reject")
    # Invited person rejects the date after a pickup was offered -> all coins go back to the inviter
    await _refund(d, "full_inviter", "CANCELLED")
    # ...and their availability for that day+time is locked (shown as locked in the calendar)
    lock_s = (d.get("location") or {}).get("scheduled_start") or d.get("proposed_start")
    lock_e = (d.get("location") or {}).get("scheduled_end") or d.get("proposed_end")
    if lock_s:
        await db.users.update_one({"id": d["recipient_id"]}, {"$push": {"locked_slots": {
            "date": lock_s[:10], "start": lock_s, "end": lock_e, "reason": "rejected_date",
            "date_id": did, "locked_at": _iso()}}})
    await _log_status(did, "CANCELLED", user["id"])
    await notify(d["inviter_id"], "date_declined", "Your date was rejected",
                 f"{user['name']} rejected the date. All coins were refunded to you.", {"date_id": did}, email=True, link=DATES_LINK, cta="View Details")
    return {"ok": True, "status": "CANCELLED"}


@api.post("/invites/{did}/pickup/confirm")
async def invite_pickup_confirm(did: str, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "inviter")
    if d["status"] != "PICKUP_ADDRESS_SELECTED": raise HTTPException(400, "Nothing to confirm")
    await db.dates.update_one({"id": did}, {"$set": {"transportation.type": "pickup", "transportation.status": "confirmed", "transportation.confirmed_by": user["id"]}})
    await _log_status(did, "DATE_CONFIRMED", user["id"])
    for uid in (d["inviter_id"], d["recipient_id"]):
        await notify(uid, "date_accepted", "Your date is confirmed", "Pickup confirmed — your date is confirmed.", {"date_id": did}, email=True, link=DATES_LINK, cta="View Date")
    return {"ok": True, "status": "DATE_CONFIRMED"}

@api.post("/invites/{did}/pickup/switch-to-taxi")
async def invite_pickup_switch_to_taxi(did: str, user=Depends(get_current_user)):
    """Inviter changes their mind after a confirmed pickup and sends taxi money instead."""
    d = await _get_party(did, user["id"], "inviter")
    tr = d.get("transportation") or {}
    if d["status"] != "DATE_CONFIRMED" or tr.get("type") != "pickup": raise HTTPException(400, "Only a confirmed pickup can be switched to a taxi")
    start = _pdt((d.get("location") or {}).get("scheduled_start"))
    if start and _now() >= start: raise HTTPException(400, "LOCKED")  # allowed right up to the start time
    amount = int(tr.get("taxi_amount") or 0)
    if amount <= 0: raise HTTPException(400, "No taxi fee was requested for this date")
    if ((user.get("coins") or 0) + (user.get("withdrawable") or 0)) < amount: raise HTTPException(400, "Insufficient coins")
    await spend_coins(user["id"], amount)
    await record_txn(user["id"], "DATE_PAYMENT", -amount, did, "Taxi fee escrow (switched from pickup)")
    await db.dates.update_one({"id": did}, {"$inc": {"total_hold": amount}, "$set": {
        "transportation.type": "taxi", "transportation.status": "confirmed",
        "transportation.switched_from_pickup": True, "transportation.switched_at": _iso()},
        "$unset": {k: "" for k in ("transportation.pickup_address", "transportation.pickup_lat", "transportation.pickup_lng",
                                    "transportation.pickup_city", "transportation.pickup_country", "transportation.pickup_postal_code")}})
    await notify(d["recipient_id"], "date_taxi", "Taxi money sent instead of pickup",
                 f"{user['name']} won't pick you up after all and sent you 🪙{amount} for a taxi instead. Your date is still confirmed.",
                 {"date_id": did}, email=True, link=DATES_LINK, cta="View Date")
    return {"ok": True, "status": "DATE_CONFIRMED", "taxi_amount": amount}

@api.post("/invites/{did}/transport/refuse")
async def invite_transport_refuse(did: str, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "inviter")
    if d["status"] not in ("TAXI_REQUESTED", "PICKUP_ADDRESS_SELECTED", "PICKUP_ADDRESS_PENDING"): raise HTTPException(400, "Cannot refuse now")
    await _refund(d, "split", "CANCELLED_TRANSPORTATION")
    await _log_status(did, "CANCELLED_TRANSPORTATION", user["id"])
    for uid in (d["inviter_id"], d["recipient_id"]):
        await notify(uid, "date_declined", "Your date has been cancelled", "The date was cancelled over transportation. Refund applied (50/25/25).", {"date_id": did}, email=True, link=DATES_LINK, cta="View Details")
    return {"ok": True, "status": "CANCELLED_TRANSPORTATION"}

@api.post("/invites/{did}/cancel")
async def invite_cancel(did: str, reason: Optional[str] = None, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"])
    if d["status"] in ("COMPLETED", "COMPLETED_AUTO", "CANCELLED", "CANCELLED_TRANSPORTATION", "REFUNDED"): raise HTTPException(400, "Already closed")
    if d["status"] in ("REPORTED", "UNDER_ADMIN_REVIEW") or (d.get("report") and (d["report"].get("status") or "open") == "open"):
        raise HTTPException(400, "UNDER_REVIEW")
    start = _pdt((d.get("location") or {}).get("scheduled_start"))
    if start and d["status"] in ("DATE_CONFIRMED",) and _now() >= start - timedelta(minutes=30):
        raise HTTPException(400, "LOCKED")
    if d["recipient_id"] == user["id"]:
        await _refund(d, "full_inviter", "CANCELLED")
        # invited person rejected -> lock that day+time in their availability (permanent)
        lock_s = (d.get("location") or {}).get("scheduled_start") or d.get("proposed_start")
        lock_e = (d.get("location") or {}).get("scheduled_end") or d.get("proposed_end")
        if lock_s:
            await db.users.update_one({"id": d["recipient_id"]}, {"$push": {"locked_slots": {
                "date": lock_s[:10], "start": lock_s, "end": lock_e, "reason": "rejected_date",
                "date_id": did, "locked_at": _iso()}}})
    else:
        await _refund(d, "split", "CANCELLED")
    await _log_status(did, "CANCELLED", user["id"])
    other = d["recipient_id"] if user["id"] == d["inviter_id"] else d["inviter_id"]
    reason = _decline_reason(reason)
    if reason: await db.dates.update_one({"id": did}, {"$set": {"decline_reason": reason, "declined_by": user["id"]}})
    await notify(other, "date_declined", "Your date has been cancelled", "The other person cancelled the date. Any applicable refund was processed." + _reason_line(reason), {"date_id": did}, email=True, link=DATES_LINK, cta="View Details")
    await _date_chat_card(user["id"], other, "invite", did, "declined", "❌ Date declined" if d["status"] == "INVITATION_SENT" else "❌ Date cancelled", data={"reason": reason})
    return {"ok": True, "status": "CANCELLED"}

@api.post("/invites/{did}/report")
async def invite_report(did: str, req: InviteReportReq, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"])
    if d.get("report") and (d["report"].get("status") or "open") == "open": raise HTTPException(409, "ALREADY_REPORTED")
    if d["status"] not in ("DATE_CONFIRMED", "DATE_COMPLETED_PENDING_VERIFICATION", "PHOTO_VERIFICATION_PENDING"): raise HTTPException(400, "Report not available")
    start = _pdt((d.get("location") or {}).get("scheduled_start"))
    if not start: raise HTTPException(400, "Report not available yet")
    if not (start <= _now() <= start + timedelta(hours=DATE_WINDOW_HOURS)):
        raise HTTPException(400, "REPORT_WINDOW_CLOSED")
    if len((req.details or "").strip()) < 10: raise HTTPException(400, "Please describe what happened (min 10 chars)")
    role = "inviter" if user["id"] == d["inviter_id"] else "recipient"
    rep = {"reporter_id": user["id"], "reporter_role": role, "reasons": req.reasons, "details": req.details.strip(), "evidence": req.evidence,
           "photos": await _report_photos(user, req.photos), "status": "open", "created_at": _iso(),
           "reply_deadline": _iso(_now() + timedelta(hours=REPORT_REPLY_HOURS)), "prev_status": d["status"]}
    await db.dates.update_one({"id": did}, {"$set": {"report": rep}})
    other = d["recipient_id"] if user["id"] == d["inviter_id"] else d["inviter_id"]
    await notify(other, "date_request", "Your date was reported — reply within 24h", _reported_msg(role), {"date_id": did}, email=True, link=DATES_LINK, cta="Reply now")
    await _log_status(did, "REPORTED", user["id"])
    for aid in await _admin_ids():
        await notify(aid, "date_request", "Date report submitted", f"A date ({did}) was reported. Review the case in admin.", {"date_id": did}, email=True, link=f"{PUBLIC_APP_URL}/admin", cta="View Case")
    return {"ok": True, "status": "REPORTED"}

@api.post("/invites/{did}/verify")
async def invite_verify(did: str, file: UploadFile = File(...), confirm: bool = Form(False), note: str = Form(""), user=Depends(get_current_user)):
    d = await _get_party(did, user["id"])
    start = _pdt((d.get("location") or {}).get("scheduled_start"))
    if not start or _now() < start + timedelta(hours=24): raise HTTPException(400, "VERIFY_NOT_YET")
    if not confirm: raise HTTPException(400, "Confirmation required")
    ct = (file.content_type or "").lower()
    ext = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp"}.get(ct)
    if not ext: raise HTTPException(400, "Only JPEG/PNG/WEBP images allowed")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024: raise HTTPException(400, "Max 15MB")
    path = f"giftsdates/dateverify/{did}/{uuid.uuid4()}.{ext}"
    put_object(path, data, ct)
    ver = {"user_id": user["id"], "photo": path, "note": note, "status": "pending", "submitted_at": _iso()}
    await db.dates.update_one({"id": did}, {"$set": {"verification": ver}})
    await _log_status(did, "PHOTO_VERIFICATION_PENDING", user["id"])
    inv = await _mini(d["inviter_id"]); rec = await _mini(d["recipient_id"])
    detail = (f"Date confirmation submitted.<br>Date ID: {did}<br>Activity: {(d.get('chosen_idea') or {}).get('name')}<br>"
              f"When: {(d.get('location') or {}).get('scheduled_start')}<br>Where: {(d.get('location') or {}).get('venue')}, {(d.get('location') or {}).get('address')}<br>"
              f"Coins: {d.get('total_hold')}<br>Inviter: {inv}<br>Recipient: {rec}<br>Submitted: {_iso()}")
    await send_email(to=SUPPORT_EMAIL, subject=f"Date confirmation submitted · {did}", html=_email_cta_html("Date confirmation submitted", detail, f"{PUBLIC_APP_URL}/admin", "Review Confirmation"))
    for aid in await _admin_ids():
        await notify(aid, "date_request", "Date confirmation submitted", f"Photo verification pending for date {did}.", {"date_id": did}, email=False)
    return {"ok": True, "status": "PHOTO_VERIFICATION_PENDING"}

@api.post("/invites/{did}/acknowledge")
async def invite_ack(did: str, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"])
    await db.dates.update_one({"id": did}, {"$push": {"acknowledgements": {"by": user["id"], "at": _iso(),
                              "text": "I confirm I have no complaints regarding this date, its cancellation, refund, or the agreed arrangements."}}})
    return {"ok": True}

@api.get("/invites/{did}/slots")
async def invite_slots(did: str, day: str, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"], "inviter")
    try:
        base = datetime.fromisoformat(day).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    except Exception:
        raise HTTPException(400, "Invalid day")
    day_end = base + timedelta(days=1)
    busy = []
    for uid in {d["inviter_id"], d["recipient_id"]}:
        docs = await db.dates.find({"status": {"$in": BUSY_STATUSES}, "id": {"$ne": did},
                                    "$or": [{"inviter_id": uid}, {"recipient_id": uid}]}, {"_id": 0, "location": 1}).to_list(300)
        for x in docs:
            loc = x.get("location") or {}
            s, e = _pdt(loc.get("scheduled_start")), _pdt(loc.get("scheduled_end"))
            if s and e and s < day_end and e > base:
                busy.append((s, e))
    slots = []
    for h in range(10, 20):  # starts 10:00..19:00, +3h ends by 22:00
        st = base.replace(hour=h)
        en = st + timedelta(hours=DATE_WINDOW_HOURS)
        conflict = any(bs < en and st < be for bs, be in busy)
        slots.append({"time": f"{h:02d}:00", "start": _iso(st), "available": not conflict})
    return {"day": day, "busy": [{"start": _iso(s), "end": _iso(e)} for s, e in busy], "slots": slots, "duration_hours": DATE_WINDOW_HOURS}

async def _mirror_to_main_chat(from_id, to_id, text, did):
    """Copy a date-chat message into the regular conversation between the two people."""
    conv = await db.conversations.find_one({"users": {"$all": [from_id, to_id]}}, {"id": 1})
    cid = conv["id"] if conv else (await ensure_match(from_id, to_id, "date"))[0]
    now = _iso()
    await db.messages.insert_one({"id": str(uuid.uuid4()), "conversation_id": cid, "from_id": from_id, "text": text,
                                  "type": "text", "date_id": did, "created_at": now})
    await db.conversations.update_one({"id": cid}, {"$set": {"last_message": text, "last_at": now}})

DATE_CHAT_STATUSES = {"DATE_CONFIRMED", "DATE_COMPLETED_PENDING_VERIFICATION", "PHOTO_VERIFICATION_PENDING",
                      "COMPLETED", "COMPLETED_AUTO", "REPORTED", "UNDER_ADMIN_REVIEW"}

@api.get("/invites/{did}/messages")
async def invite_messages(did: str, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"])
    msgs = await db.date_messages.find({"date_id": did}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return {"messages": msgs, "chat_enabled": d["status"] in DATE_CHAT_STATUSES}

@api.post("/invites/{did}/messages")
async def invite_send_message(did: str, req: DateMsgReq, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"])
    if d["status"] not in DATE_CHAT_STATUSES:
        raise HTTPException(400, "CHAT_NOT_AVAILABLE")
    text = (req.text or "").strip()[:1000]
    if not text:
        raise HTTPException(400, "Empty message")
    msg = {"id": str(uuid.uuid4()), "date_id": did, "from_id": user["id"], "text": text, "created_at": _iso()}
    await db.date_messages.insert_one(dict(msg))
    other = d["recipient_id"] if d["inviter_id"] == user["id"] else d["inviter_id"]
    await _mirror_to_main_chat(user["id"], other, text, did)
    await notify(other, "date_message", "New date message", f"{user.get('name')}: {text[:80]}",
                 {"date_id": did}, email=False, link=DATES_LINK, cta="Open chat")
    return {"ok": True, "message": msg}

def _six_months():
    now = datetime.now(timezone.utc)
    months, y, m = [], now.year, now.month
    for _ in range(6):
        months.insert(0, f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return months

async def _regular_earnings(uid: str) -> dict:
    months = _six_months()
    by = {k: 0 for k in months}
    def add(ts, n):
        k = str(ts or "")[:7]
        if k in by: by[k] += int(n or 0)
    async for tx in db.coin_transactions.find({"user_id": uid, "type": {"$in": ["DATE_COMPLETION", "RECIPIENT_COMPENSATION"]}}, {"_id": 0, "amount": 1, "created_at": 1}):
        add(tx.get("created_at"), tx.get("amount"))
    held = 0
    async for d in db.date_bookings.find({"to_id": uid, "vip": {"$ne": True}}, {"_id": 0, "status": 1, "coins": 1, "released_net": 1, "released_at": 1, "scheduled_at": 1}):
        if d["status"] == "released": add(d.get("released_at") or d.get("scheduled_at"), d.get("released_net"))
        elif d["status"] in ("escrow", "accepted", "confirmed"): held += int(d.get("coins") or 0)
    async for d in db.dates.find({"recipient_id": uid, "status": {"$in": ["DATE_CONFIRMED", "DATE_COMPLETED_PENDING_VERIFICATION", "PHOTO_VERIFICATION_PENDING"]}}, {"_id": 0, "total_hold": 1, "coins": 1}):
        held += int(d.get("total_hold") or d.get("coins") or 0)
    return {"month": months[-1], "earned": by[months[-1]], "held": held, "by_month": [{"month": k, "earned": by[k]} for k in months]}

@api.get("/dates/earnings")
async def dates_earnings(user=Depends(get_current_user)):
    """Coins earned from regular dates (invites + bookings) this month, last 6 months, and coins still held."""
    return await _regular_earnings(user["id"])

@api.get("/earnings/total")
async def earnings_total(user=Depends(get_current_user)):
    """All income in one place: regular dates + VIP dates + private VIP section unlocks."""
    reg = await _regular_earnings(user["id"])
    vip_raw = await db.vip_sched.find({"vip_id": user["id"]}, {"_id": 0}).to_list(2000)
    vip = await _vs_earnings(user["id"], vip_raw)
    months = _six_months()
    unl = {k: 0 for k in months}
    unlock_all = 0
    async for tx in db.coin_transactions.find({"user_id": user["id"], "type": "vip_unlock_earned"}, {"_id": 0, "amount": 1, "created_at": 1}):
        unlock_all += int(tx.get("amount") or 0)
        k = str(tx.get("created_at") or "")[:7]
        if k in unl: unl[k] += int(tx.get("amount") or 0)
    rb = {x["month"]: x["earned"] for x in reg["by_month"]}
    vb = {x["month"]: x["earned"] for x in vip["by_month"]}
    gifts = {k: 0 for k in months}
    async for tx in db.transactions.find({"type": "gift", "to_id": user["id"], "gift_id": {"$ne": "taxi"}, "created_at": {"$gte": months[0]}}, {"_id": 0, "net": 1, "created_at": 1}):
        k = str(tx.get("created_at") or "")[:7]
        if k in gifts: gifts[k] += int(tx.get("net") or 0)
    by_month = [{"month": k, "earned": rb.get(k, 0) + vb.get(k, 0) + unl[k] + gifts[k]} for k in months]
    cur = months[-1]
    return {"month": cur, "earned": by_month[-1]["earned"], "held": reg["held"] + vip["held"],
            "six_month_total": sum(x["earned"] for x in by_month),
            "breakdown": {"regular": rb.get(cur, 0), "vip": vb.get(cur, 0), "unlocks": unl[cur], "gifts": gifts[cur]},
            "by_month": by_month}

@api.get("/invites")
async def list_invites(user=Depends(get_current_user)):
    docs = await db.dates.find({"$or": [{"inviter_id": user["id"]}, {"recipient_id": user["id"]}]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    incoming, outgoing = [], []
    for d in docs:
        other_id = d["recipient_id"] if d["inviter_id"] == user["id"] else d["inviter_id"]
        s = _serialize(d, user["id"], await _mini(other_id))
        (outgoing if d["inviter_id"] == user["id"] else incoming).append(s)
    return {"incoming": incoming, "outgoing": outgoing}

@api.get("/invites/cancelled")
async def list_cancelled_invites(user=Depends(get_current_user)):
    """All cancelled or refused dates for the current user, with their coin outcome."""
    statuses = ["CANCELLED", "CANCELLED_TRANSPORTATION", "REFUNDED"]
    docs = await db.dates.find(
        {"$or": [{"inviter_id": user["id"]}, {"recipient_id": user["id"]}], "status": {"$in": statuses}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(300)
    items = []
    for d in docs:
        other_id = d["recipient_id"] if d["inviter_id"] == user["id"] else d["inviter_id"]
        s = _serialize(d, user["id"], await _mini(other_id))
        # coins credited back to THIS user for this date (refund / compensation)
        my_txns = await db.coin_transactions.find(
            {"user_id": user["id"], "date_id": d["id"]}, {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        s["refund_amount"] = sum(int(t.get("amount", 0) or 0) for t in my_txns if t.get("type") in ("DATE_REFUND", "RECIPIENT_COMPENSATION"))
        s["refund_txns"] = my_txns
        items.append(s)
    return {"items": items, "total": len(items)}


@api.get("/invites/{did}")
async def get_invite(did: str, user=Depends(get_current_user)):
    d = await _get_party(did, user["id"])
    other_id = d["recipient_id"] if d["inviter_id"] == user["id"] else d["inviter_id"]
    return _serialize(d, user["id"], await _mini(other_id))

# ---------- One-time welcome Spin & Win (fires once, right after registration) ----------
@api.get("/spin/status")
async def spin_status(user=Depends(get_current_user)):
    done = bool(user.get("welcome_spin_done"))
    return {"eligible": not done, "prizes": [_spin_public(p) for p in SPIN_PRIZES]}

@api.post("/spin/claim")
async def spin_claim(user=Depends(get_current_user)):
    if user.get("welcome_spin_done"):
        raise HTTPException(400, "Spin already used")
    p = _pick_spin_prize()
    reward = _spin_public(p)
    upd = {"welcome_spin_done": True}
    # Tier expiry is exactly 7 days from the time of registration.
    reg = user.get("created_at")
    try:
        base = datetime.fromisoformat(reg.replace("Z", "+00:00")) if reg else _now()
    except Exception:
        base = _now()
    if p["type"] == "coins":
        await db.users.update_one({"id": user["id"]}, {"$inc": {"coins": int(p["coins"])}, "$set": upd})
        await record_txn(user["id"], "SPIN_WIN", int(p["coins"]), None, "Welcome Spin & Win")
        reward["coins"] = int(p["coins"])
    elif p["type"] in ("premium_lite", "premium", "vip"):
        field = {"premium_lite": "premium_lite_until", "premium": "premium_until", "vip": "vip_until"}[p["type"]]
        expires_at = (base + timedelta(days=int(p.get("days", 7)))).isoformat()
        upd[field] = expires_at
        await db.users.update_one({"id": user["id"]}, {"$set": upd})
        reward["expires_at"] = expires_at
    else:  # "none" — no jackpot: credit 5 coins as a thank-you/compensation
        await db.users.update_one({"id": user["id"]}, {"$inc": {"coins": 5}, "$set": upd})
        await record_txn(user["id"], "SPIN_WIN", 5, None, "Welcome Spin — consolation coins")
        reward["coins"] = 5
    await db.spin_history.insert_one({"id": str(uuid.uuid4()), "user_id": user["id"], "reward": reward,
                                      "spin_date": _iso(), "status": "completed", "created_at": _iso()})
    return {"prize": reward}

@api.post("/spin/dismiss")
async def spin_dismiss(user=Depends(get_current_user)):
    """Closing the wheel without spinning permanently disables it for this account."""
    if not user.get("welcome_spin_done"):
        await db.users.update_one({"id": user["id"]}, {"$set": {"welcome_spin_done": True}})
    return {"ok": True}

# ---------- Admin: dates dashboard ----------
async def _require_admin(user):
    if (user.get("email") or "").lower() not in ADMIN_EMAIL_LIST: raise HTTPException(403, "Admin only")

@api.get("/admin/dates")
async def admin_dates(status: Optional[str] = None, user=Depends(get_current_user)):
    await _require_admin(user)
    q = {"status": status} if status else {}
    docs = await db.dates.find(q, {"_id": 0}).sort("updated_at", -1).to_list(300)
    out = []
    for d in docs:
        d["inviter"] = await _mini(d["inviter_id"]); d["recipient"] = await _mini(d["recipient_id"])
        out.append(d)
    return {"dates": out}

@api.post("/admin/dates/{did}/verify")
async def admin_verify(did: str, approve: bool = True, user=Depends(get_current_user)):
    await _require_admin(user)
    d = await db.dates.find_one({"id": did}, {"_id": 0})
    if not d: raise HTTPException(404, "Not found")
    if approve:
        await db.dates.update_one({"id": did}, {"$set": {"verification.status": "approved", "verification.reviewed_by": user["id"], "verification.reviewed_at": _iso()}})
        await _complete(d, "COMPLETED")
    else:
        await db.dates.update_one({"id": did}, {"$set": {"verification.status": "rejected", "verification.reviewed_by": user["id"]}})
        await _log_status(did, "UNDER_ADMIN_REVIEW", user["id"])
    await db.date_admin_log.insert_one({"id": str(uuid.uuid4()), "date_id": did, "admin_id": user["id"], "action": "verify_approve" if approve else "verify_reject", "at": _iso()})
    return {"ok": True}

@api.post("/admin/dates/{did}/resolve")
async def admin_resolve(did: str, action: str, user=Depends(get_current_user)):
    await _require_admin(user)
    d = await db.dates.find_one({"id": did}, {"_id": 0})
    if not d: raise HTTPException(404, "Not found")
    if d["status"] in ("COMPLETED", "COMPLETED_AUTO", "REFUNDED", "CANCELLED", "CANCELLED_TRANSPORTATION") or d.get("paid_out") or d.get("refunded"):
        raise HTTPException(400, "Coins already settled")
    rep = d.get("report") or {}
    if action == "dismiss":  # report closed without moving coins; the date continues as before
        if not rep: raise HTTPException(400, "No report")
        await db.dates.update_one({"id": did}, {"$set": {"report.status": "dismissed", "report.outcome": "dismiss", "report.resolved_at": _iso(), "report.resolved_by": user["id"]}})
        await _log_status(did, rep.get("prev_status") or "DATE_CONFIRMED", user["id"])
        for uid in (d["inviter_id"], d["recipient_id"]):
            await notify(uid, "date_request", "Date report closed", "Support reviewed the report and closed it. The date continues as normal.", {"date_id": did}, email=True, link=DATES_LINK, cta="View Date")
        await db.date_admin_log.insert_one({"id": str(uuid.uuid4()), "date_id": did, "admin_id": user["id"], "action": action, "at": _iso()})
        return {"ok": True}
    role = rep.get("reporter_role")
    if action in ("reporter_wins", "other_wins"):
        if not role: raise HTTPException(400, "No report")
        inviter_wins = (role == "inviter") == (action == "reporter_wins")
        action = "refund_inviter" if inviter_wins else "payout_recipient"
    if action == "payout_recipient": await _complete(d, "COMPLETED")
    elif action in ("refund_inviter", "split"):
        await _refund(d, "full_inviter" if action == "refund_inviter" else "split", "REFUNDED")
        await _log_status(did, "REFUNDED", user["id"])
    else: raise HTTPException(400, "Unknown action")
    if d.get("report"):
        await db.dates.update_one({"id": did}, {"$set": {"report.status": "resolved", "report.outcome": action, "report.resolved_at": _iso(), "report.resolved_by": user["id"]}})
    await db.date_admin_log.insert_one({"id": str(uuid.uuid4()), "date_id": did, "admin_id": user["id"], "action": action, "at": _iso()})
    return {"ok": True}

# ---------- Cron endpoints ----------
async def _report_window_alerts():
    """When a report's 24h reply window ends, tell admins the case is ready for a decision (coins never move automatically)."""
    for coll, key, f in ((db.dates, "date_id", "report"), (db.date_bookings, "booking_id", "report"), (db.vip_sched, "booking_id", "no_show_report")):
        async for x in coll.find({f"{f}.status": {"$in": [None, "open"]}, f"{f}.reply_deadline": {"$lte": _iso()}, f"{f}.admin_alerted": {"$ne": True}}, {"_id": 0, "id": 1, f: 1}):
            await coll.update_one({"id": x["id"]}, {"$set": {f"{f}.admin_alerted": True}})
            replied = bool(x[f].get("reply"))
            body = (f"The 24h reply window for report {x['id']} has ended " + ("— the other side replied. Please compare both sides and decide." if replied
                    else "with no reply. Default outcome: the reporter wins. Please confirm the decision in admin."))
            for aid in await _admin_ids():
                await notify(aid, "date_request", "Report ready for decision", body, {key: x["id"]}, email=True, link=f"{PUBLIC_APP_URL}/admin", cta="Decide")

async def _run_lifecycle():
    now = _now()
    await _report_window_alerts()
    docs = await db.dates.find({"status": "DATE_CONFIRMED"}, {"_id": 0}).to_list(500)
    for d in docs:
        start = _pdt((d.get("location") or {}).get("scheduled_start"))
        if not start: continue
        when = _reminder_when(start, d.get("location") or {})
        async def snd(flag, title, body, email=True):
            res = await db.dates.update_one({"id": d["id"], f"reminders.{flag}": {"$ne": True}}, {"$set": {f"reminders.{flag}": True}})
            if not res.modified_count: return
            for uid in (d["inviter_id"], d["recipient_id"]):
                await notify(uid, "date_reminder", title, body, {"date_id": d["id"]}, email=email, link=DATES_LINK, cta="View Date", sms=False)
        if start - timedelta(hours=24) <= now < start - timedelta(hours=1): await snd("h24", "Your date is tomorrow", f"Reminder: your date is on {when}. Check the details and use the date chat to coordinate.")
        elif start - timedelta(hours=1) <= now < start: await snd("h1", "Your date starts in 1 hour", f"Your date starts in about 1 hour ({when}). Cancellation and date coin actions lock 30 minutes before the start.")
        elif start <= now < start + timedelta(hours=3): await snd("started", "Your date has started", "Enjoy — be respectful and safe.", email=False)
        elif now >= start + timedelta(hours=3): await snd("h3", "Your scheduled date window has ended", "Photo confirmation unlocks 24h after the start.", email=False)
        if start - timedelta(minutes=15) <= now < start: await snd("m15", "Your date starts in 15 minutes", f"Get ready — your date starts in 15 minutes ({when}). Share your live location if you want help finding each other.", email=False)
        if start + timedelta(minutes=DATE_SLOT_MINUTES - 15) <= now < start + timedelta(minutes=DATE_SLOT_MINUTES): await snd("end15", "Your date ends in 15 minutes", "Your date is about to finish — 15 minutes left.", email=False)
        if now > start + timedelta(hours=72) and not d.get("report") and not (d.get("verification") or {}).get("status") == "pending" and not d.get("paid_out"):
            await _complete(d, "COMPLETED_AUTO")

def _reminder_when(start, loc):
    place = ", ".join(x for x in (loc.get("venue"), loc.get("city")) if x)
    return f"{start.strftime('%a %d %b %Y, %H:%M')} UTC" + (f" at {place}" if place else "")

async def _run_booking_reminders():
    """24h/1h (in-app + email) and 15-min start/end (in-app) reminders for accepted/confirmed bookings."""
    now = _now()
    docs = await db.date_bookings.find({"status": {"$in": ["accepted", "confirmed"]}}, {"_id": 0}).to_list(1000)
    for b in docs:
        start = _pdt(b.get("scheduled_at"))
        if not start: continue
        if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
        when = _reminder_when(start, b)
        idea = f" Plan: {b['selected_activity']}." if b.get("selected_activity") else ""
        end = start + timedelta(minutes=DATE_SLOT_MINUTES)
        due = []
        if start - timedelta(hours=24) <= now < start - timedelta(hours=1): due.append(("h24", "Your date is tomorrow", f"Reminder: your date is on {when}.{idea}", True))
        if start - timedelta(hours=1) <= now < start: due.append(("h1", "Your date starts in 1 hour", f"Reminder: your date is on {when}.{idea}", True))
        if start - timedelta(minutes=15) <= now < start: due.append(("m15", "Your date starts in 15 minutes", f"Get ready — your date starts in 15 minutes ({when}). Share your live location if you want help finding each other.", False))
        if end - timedelta(minutes=15) <= now < end: due.append(("end15", "Your date ends in 15 minutes", "Your date is about to finish — 15 minutes left.", False))
        for flag, title, body, email in due:
            res = await db.date_bookings.update_one({"id": b["id"], f"reminders.{flag}": {"$ne": True}}, {"$set": {f"reminders.{flag}": True}})
            if not res.modified_count: continue
            for uid in (b["from_id"], b["to_id"]):
                await notify(uid, "date_reminder", title, body, {"booking_id": b["id"]}, email=email, link=DATES_LINK, cta="View Date", sms=False)

async def _date_lifecycle_loop():
    """Internal background loop: fires date reminders to both parties for confirmed
    dates (24h/3h/1h/30m/start/end) and auto-completes finished dates. Runs every 60s."""
    import asyncio
    await asyncio.sleep(20)
    while True:
        try:
            await _run_lifecycle()
            await _run_booking_reminders()
        except Exception as ex:
            logging.error(f"date-lifecycle loop error: {ex}")
        await asyncio.sleep(60)

async def _run_account_purge():
    """Permanently delete accounts whose 30-day PENDING_DELETION grace period has expired."""
    now_iso = datetime.now(timezone.utc).isoformat()
    due = await db.users.find({"account_status": "PENDING_DELETION",
                               "deletion_scheduled_at": {"$lte": now_iso}},
                              {"_id": 0, "id": 1}).to_list(500)
    for u in due:
        try:
            await _purge_user(u["id"])
            logging.info(f"account-purge: permanently deleted user {u['id']}")
        except Exception as ex:
            logging.error(f"account-purge failed for {u['id']}: {ex}")
    return len(due)

async def _account_purge_loop():
    """Internal background worker that purges expired accounts hourly."""
    import asyncio
    await asyncio.sleep(30)
    while True:
        try:
            await _run_account_purge()
        except Exception as ex:
            logging.error(f"account-purge loop error: {ex}")
        await asyncio.sleep(3600)  # hourly

async def _run_spin_reminders():
    # Monthly Spin & Win has been removed in favor of a one-time welcome spin
    # that fires right after registration, so recurring reminders are disabled.
    return

def _cron_auth(authorization):
    import hmac
    if not WEBHOOK_CRON_SECRET: raise HTTPException(503, "cron not configured")
    tok = authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else ""
    if not hmac.compare_digest(tok, WEBHOOK_CRON_SECRET): raise HTTPException(401, "unauthorized")

@api.post("/cron/tick")
async def cron_tick(authorization: Optional[str] = Header(None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    import asyncio
    _cron_auth(authorization)
    asyncio.create_task(_run_lifecycle())
    asyncio.create_task(_run_booking_reminders())
    asyncio.create_task(_vs_tick())
    return {"accepted": True}

@api.post("/cron/spin")
async def cron_spin(authorization: Optional[str] = Header(None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    import asyncio
    _cron_auth(authorization)
    asyncio.create_task(_run_spin_reminders())
    return {"accepted": True}

@api.post("/cron/purge-accounts")
async def cron_purge_accounts(authorization: Optional[str] = Header(None)):
    # Permanently purge accounts whose 30-day deletion grace period has expired.
    import asyncio
    _cron_auth(authorization)
    asyncio.create_task(_run_account_purge())
    return {"accepted": True}

app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
