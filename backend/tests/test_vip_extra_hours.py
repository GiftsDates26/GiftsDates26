"""Backend tests for VIP Extra-Hours feature (iteration_17).

Covers:
- GET /api/meta returns extra_hour_min_coins=250
- PUT /api/vip/profile clamps price_extra_hour to >=250
- POST /api/vip/book adds extra_hours * extra_price to coins, stores extra_hours/extra_coins
- POST /api/vip/schedule/{vip_id}/book: BAD_DURATION on half-hour, 4h booking charges base + 3*extra
- GET /api/vip/schedule/{vip_id}/slots returns extra_hour_price
- POST /api/vip/schedule/bookings/{bid}/reschedule → SAME_DURATION when hours unchanged, ok when different
- Insufficient coins → 400
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "giftsdates@gmail.com"
ADMIN_PASS = "Admin@GD24!"
USER_EMAIL = "testuser@giftsdates.com"
USER_PASS = "Test@12345"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def db():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def user_token():
    return _login(USER_EMAIL, USER_PASS)


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _me(tok):
    r = requests.get(f"{API}/auth/me", headers=_hdr(tok), timeout=20)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="session")
def user_id(user_token):
    return _me(user_token)["id"]


@pytest.fixture(scope="session")
def admin_id(admin_token):
    return _me(admin_token)["id"]


def _set_coins(db, uid, coins):
    db.users.update_one({"id": uid}, {"$set": {"coins": int(coins), "escrow": 0}})


def _future_date(days=7):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


# ---------- tests ----------

# meta
def test_meta_extra_hour_min_coins():
    r = requests.get(f"{API}/meta", timeout=20)
    assert r.status_code == 200
    assert r.json().get("extra_hour_min_coins") == 250


# PUT /vip/profile clamps
def test_vip_profile_extra_hour_clamped(user_token, user_id, db):
    # try 100 (below min) → should save as 250
    payload = {"price_hour": 500, "price_2h": 900, "price_3h": 1200,
               "price_extra_hour": 100, "services": [], "places": [],
               "availability": [], "published": True}
    r = requests.put(f"{API}/vip/profile", json=payload, headers=_hdr(user_token), timeout=20)
    assert r.status_code == 200, r.text
    u = db.users.find_one({"id": user_id}, {"_id": 0, "vip.prices": 1})
    assert u["vip"]["prices"]["extra"] == 250

    # 300 should pass through
    payload["price_extra_hour"] = 300
    r = requests.put(f"{API}/vip/profile", json=payload, headers=_hdr(user_token), timeout=20)
    assert r.status_code == 200
    u = db.users.find_one({"id": user_id}, {"_id": 0, "vip.prices": 1})
    assert u["vip"]["prices"]["extra"] == 300


# /vip/book extra hours charge
def test_vip_book_adds_extra_coins(user_token, user_id, admin_id, db):
    # Make sure admin has extra price (default via function = 250 since probably no vip profile)
    _set_coins(db, user_id, 100000)
    payload = {"target_id": admin_id, "coins": 500, "extra_hours": 2,
               "venue": "VIP", "city": "Test", "place": "own",
               "scheduled_at": datetime.now(timezone.utc).isoformat()}
    r = requests.post(f"{API}/vip/book", json=payload, headers=_hdr(user_token), timeout=20)
    assert r.status_code == 200, r.text
    bid = r.json()["booking_id"]
    doc = db.date_bookings.find_one({"id": bid}, {"_id": 0})
    # extra price for admin (no vip profile) = 250
    assert doc["extra_hours"] == 2
    assert doc["extra_coins"] == 500
    assert doc["coins"] == 500 + 500  # base 500 + 2*250 extra


# availability setup helpers
@pytest.fixture
def avail_block(user_token, user_id, db):
    """Create a fresh availability block covering 10:00-20:00 on a future date."""
    date = _future_date(14)
    # Clear any existing bookings/avail for cleanliness on this date
    db.vip_avail.delete_many({"vip_id": user_id, "date": date})
    db.vip_sched.delete_many({"vip_id": user_id, "date": date})
    r = requests.post(f"{API}/vip/schedule/availability",
                      json={"date": date, "start": "10:00", "end": "20:00", "slot_len": 60},
                      headers=_hdr(user_token), timeout=20)
    assert r.status_code == 200, r.text
    yield {"date": date, "aid": r.json()["id"]}
    # cleanup
    db.vip_sched.delete_many({"vip_id": user_id, "date": date})
    db.vip_avail.delete_many({"id": r.json()["id"]})


def test_slots_returns_extra_hour_price(admin_token, user_id, user_token, db, avail_block):
    # ensure extra price = 300 (set in previous test but re-apply for safety)
    payload = {"price_hour": 500, "price_2h": 900, "price_3h": 1200,
               "price_extra_hour": 300, "services": [], "places": [],
               "availability": [], "published": True}
    requests.put(f"{API}/vip/profile", json=payload, headers=_hdr(user_token), timeout=20)
    r = requests.get(f"{API}/vip/schedule/{user_id}/slots", headers=_hdr(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("extra_hour_price") == 300


def test_vs_book_bad_duration(admin_token, admin_id, user_id, db, avail_block):
    _set_coins(db, admin_id, 50000)
    # half hour -> BAD_DURATION
    r = requests.post(f"{API}/vip/schedule/{user_id}/book",
                      json={"date": avail_block["date"], "start": "10:00", "end": "10:30", "coins": 500},
                      headers=_hdr(admin_token), timeout=20)
    assert r.status_code == 400
    assert "BAD_DURATION" in r.text


def test_vs_book_4h_charges_extra(admin_token, admin_id, user_id, user_token, db, avail_block):
    # ensure extra = 300
    requests.put(f"{API}/vip/profile",
                 json={"price_hour": 500, "price_2h": 900, "price_3h": 1200,
                       "price_extra_hour": 300, "services": [], "places": [],
                       "availability": [], "published": True},
                 headers=_hdr(user_token), timeout=20)
    _set_coins(db, admin_id, 50000)
    base_coins = 1500  # client sends base
    r = requests.post(f"{API}/vip/schedule/{user_id}/book",
                      json={"date": avail_block["date"], "start": "11:00", "end": "15:00",
                            "coins": base_coins},
                      headers=_hdr(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    bid = r.json()["booking_id"]
    doc = db.vip_sched.find_one({"id": bid}, {"_id": 0})
    assert doc["extra_hours"] == 3
    assert doc["extra_coins"] == 3 * 300
    assert doc["coins"] == base_coins + 3 * 300  # server adds extra on top


def test_vs_reschedule_same_duration(admin_token, admin_id, user_id, user_token, db, avail_block):
    requests.put(f"{API}/vip/profile",
                 json={"price_hour": 500, "price_2h": 900, "price_3h": 1200,
                       "price_extra_hour": 300, "services": [], "places": [],
                       "availability": [], "published": True},
                 headers=_hdr(user_token), timeout=20)
    _set_coins(db, admin_id, 50000)
    # Create 2h booking (1 extra hour)
    r = requests.post(f"{API}/vip/schedule/{user_id}/book",
                      json={"date": avail_block["date"], "start": "12:00", "end": "14:00", "coins": 900},
                      headers=_hdr(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    bid = r.json()["booking_id"]

    # Reschedule with DIFFERENT duration (3h) -> SAME_DURATION error (duration must be preserved)
    r2 = requests.post(f"{API}/vip/schedule/bookings/{bid}/reschedule",
                       json={"date": avail_block["date"], "start": "16:00", "end": "19:00"},
                       headers=_hdr(admin_token), timeout=20)
    assert r2.status_code == 400
    assert "SAME_DURATION" in r2.text

    # Reschedule with SAME duration (2h) different time -> OK
    r3 = requests.post(f"{API}/vip/schedule/bookings/{bid}/reschedule",
                       json={"date": avail_block["date"], "start": "16:00", "end": "18:00"},
                       headers=_hdr(admin_token), timeout=20)
    assert r3.status_code == 200, r3.text


def test_vs_book_insufficient_coins(admin_token, admin_id, user_id, db, avail_block):
    _set_coins(db, admin_id, 100)  # too little
    r = requests.post(f"{API}/vip/schedule/{user_id}/book",
                      json={"date": avail_block["date"], "start": "10:00", "end": "11:00", "coins": 500},
                      headers=_hdr(admin_token), timeout=20)
    assert r.status_code == 400
    assert "Insufficient" in r.text or "insufficient" in r.text


def test_vs_book_5h_no_upper_limit(admin_token, admin_id, user_id, user_token, db, avail_block):
    requests.put(f"{API}/vip/profile",
                 json={"price_hour": 500, "price_2h": 900, "price_3h": 1200,
                       "price_extra_hour": 300, "services": [], "places": [],
                       "availability": [], "published": True},
                 headers=_hdr(user_token), timeout=20)
    _set_coins(db, admin_id, 50000)
    r = requests.post(f"{API}/vip/schedule/{user_id}/book",
                      json={"date": avail_block["date"], "start": "10:00", "end": "15:00", "coins": 1000},
                      headers=_hdr(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    bid = r.json()["booking_id"]
    doc = db.vip_sched.find_one({"id": bid}, {"_id": 0})
    assert doc["extra_hours"] == 4  # 5h -> 4 extra
    assert doc["extra_coins"] == 4 * 300
