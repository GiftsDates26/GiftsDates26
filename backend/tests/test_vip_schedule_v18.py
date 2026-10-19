"""Iteration 18 backend tests for the VIP calendar / availability / extend / reminder flow.

Covers:
- POST /api/vip/schedule/availability/bulk — one block per date per range
- POST /api/vip/schedule/availability/weekly — generates blocks for N weeks
- GET  /api/vip/schedule/{vip}/slots — returns rates {'1','2','3'} and extra_hour_price
- Cancelled/declined vip_sched + cancelled date_bookings don't appear in `taken`
- POST /api/vip/schedule/bookings/{bid}/extend — NOT_IN_PROGRESS when not running
- POST /api/vip/schedule/bookings/{bid}/extend — happy path (seed in-progress booking)
- POST /api/vip/book/{bid}/extend — happy path for price-list VIP booking in progress
- Reminders: seed a confirmed booking starting in ~55 min and run _vs_tick → reminder_1h_sent + notifications
"""
import os
import uuid
import asyncio
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


@pytest.fixture(scope="session")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def user_token():
    return _login(USER_EMAIL, USER_PASS)


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="session")
def user_id(user_token):
    return requests.get(f"{API}/auth/me", headers=_hdr(user_token), timeout=20).json()["id"]


@pytest.fixture(scope="session")
def admin_id(admin_token):
    return requests.get(f"{API}/auth/me", headers=_hdr(admin_token), timeout=20).json()["id"]


def _future(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


def _set_coins(db, uid, c):
    db.users.update_one({"id": uid}, {"$set": {"coins": int(c), "escrow": 0}})


# ---------------- Availability bulk & weekly ----------------
class TestBulkWeekly:
    def test_bulk_creates_one_block_per_day_per_range(self, user_token, user_id, db):
        d1, d2 = _future(30), _future(31)
        # Clean
        db.vip_avail.delete_many({"vip_id": user_id, "date": {"$in": [d1, d2]}})
        r = requests.post(f"{API}/vip/schedule/availability/bulk", headers=_hdr(user_token), timeout=20,
                          json={"dates": [d1, d2],
                                "ranges": [{"start": "12:00", "end": "14:00"}, {"start": "19:00", "end": "23:00"}],
                                "slot_len": 60, "tz": "UTC"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["created"] == 4, data
        rows = list(db.vip_avail.find({"vip_id": user_id, "date": {"$in": [d1, d2]}}))
        assert len(rows) == 4
        pairs = sorted((x["date"], x["start"], x["end"]) for x in rows)
        assert pairs == sorted([(d1, "12:00", "14:00"), (d1, "19:00", "23:00"),
                                (d2, "12:00", "14:00"), (d2, "19:00", "23:00")])
        # cleanup
        db.vip_avail.delete_many({"vip_id": user_id, "date": {"$in": [d1, d2]}})

    def test_weekly_creates_for_weekdays(self, user_token, user_id, db):
        today = datetime.now(timezone.utc).date()
        # cleanup future recurring blocks we'll create
        future = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(14)]
        db.vip_avail.delete_many({"vip_id": user_id, "date": {"$in": future}, "recurring": True})
        # Pick Monday(0) and Friday(4) 18:00-23:00 for 2 weeks
        r = requests.post(f"{API}/vip/schedule/availability/weekly", headers=_hdr(user_token), timeout=20,
                          json={"weekly": {"0": [{"start": "18:00", "end": "23:00"}],
                                           "4": [{"start": "18:00", "end": "23:00"}]},
                                "weeks": 2, "slot_len": 60, "tz": "UTC"})
        assert r.status_code == 200, r.text
        created = r.json()["created"]
        # 2 weeks * 2 weekdays = up to 4; could be 3 if today is after one of them this week
        assert 2 <= created <= 4
        rows = list(db.vip_avail.find({"vip_id": user_id, "date": {"$in": future}, "recurring": True}))
        assert len(rows) == created
        for row in rows:
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
            assert d.weekday() in (0, 4)
            assert row["start"] == "18:00" and row["end"] == "23:00"
        db.vip_avail.delete_many({"vip_id": user_id, "date": {"$in": future}, "recurring": True})

    def test_bulk_rejects_empty(self, user_token):
        r = requests.post(f"{API}/vip/schedule/availability/bulk", headers=_hdr(user_token), timeout=20,
                          json={"dates": [], "ranges": []})
        assert r.status_code == 400
        assert "NOTHING_TO_ADD" in r.text

    def test_weekly_rejects_empty(self, user_token):
        r = requests.post(f"{API}/vip/schedule/availability/weekly", headers=_hdr(user_token), timeout=20,
                          json={"weekly": {}})
        assert r.status_code == 400
        assert "NO_WEEKDAYS" in r.text


# ---------------- Slots endpoint shape ----------------
class TestSlotsShape:
    def test_slots_returns_rates_and_extra(self, admin_token, user_token, user_id, db):
        # ensure prices
        requests.put(f"{API}/vip/profile", json={"price_hour": 500, "price_2h": 900, "price_3h": 1200,
                                                 "price_extra_hour": 300, "services": [], "places": [],
                                                 "availability": [], "published": True},
                     headers=_hdr(user_token), timeout=20)
        # publish one availability window so days are present
        d = _future(21)
        db.vip_avail.delete_many({"vip_id": user_id, "date": d})
        requests.post(f"{API}/vip/schedule/availability/bulk", headers=_hdr(user_token), timeout=20,
                      json={"dates": [d], "ranges": [{"start": "10:00", "end": "20:00"}], "slot_len": 60, "tz": "UTC"})
        r = requests.get(f"{API}/vip/schedule/{user_id}/slots", headers=_hdr(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["rates"] == {"1": 500, "2": 900, "3": 1200}
        assert body["extra_hour_price"] == 300
        assert body["durations"] == [60, 120, 180]
        assert body["buffer"] == 15
        db.vip_avail.delete_many({"vip_id": user_id, "date": d})


# ---------------- Cancelled/declined bookings not in `taken` ----------------
class TestTakenFiltering:
    def test_cancelled_vip_sched_not_in_taken(self, admin_token, user_token, user_id, admin_id, db):
        d = _future(22)
        db.vip_avail.delete_many({"vip_id": user_id, "date": d})
        db.vip_sched.delete_many({"vip_id": user_id, "date": d})
        requests.post(f"{API}/vip/schedule/availability/bulk", headers=_hdr(user_token), timeout=20,
                      json={"dates": [d], "ranges": [{"start": "10:00", "end": "22:00"}], "slot_len": 60, "tz": "UTC"})
        _set_coins(db, admin_id, 50000)
        r = requests.post(f"{API}/vip/schedule/{user_id}/book", headers=_hdr(admin_token), timeout=20,
                         json={"date": d, "start": "13:00", "end": "14:00", "coins": 500, "tz": "UTC"})
        assert r.status_code == 200, r.text
        bid = r.json().get("booking_id") or r.json().get("id")
        # Verify it shows up as taken
        slots = requests.get(f"{API}/vip/schedule/{user_id}/slots", headers=_hdr(admin_token), timeout=20).json()
        day = [x for x in slots["days"] if x["date"] == d][0]
        assert any(t["from"] == "13:00" for t in day["taken"])
        # Cancel by setting status directly
        db.vip_sched.update_one({"id": bid}, {"$set": {"status": "cancelled"}})
        slots2 = requests.get(f"{API}/vip/schedule/{user_id}/slots", headers=_hdr(admin_token), timeout=20).json()
        day2 = [x for x in slots2["days"] if x["date"] == d][0]
        assert not any(t["from"] == "13:00" for t in day2["taken"]), day2["taken"]
        # Now declined
        db.vip_sched.update_one({"id": bid}, {"$set": {"status": "declined"}})
        slots3 = requests.get(f"{API}/vip/schedule/{user_id}/slots", headers=_hdr(admin_token), timeout=20).json()
        day3 = [x for x in slots3["days"] if x["date"] == d][0]
        assert not any(t["from"] == "13:00" for t in day3["taken"])
        # cleanup
        db.vip_sched.delete_many({"id": bid})
        db.vip_avail.delete_many({"vip_id": user_id, "date": d})


# ---------------- Extend endpoints ----------------
class TestExtend:
    def test_extend_not_in_progress(self, admin_token, user_token, user_id, admin_id, db):
        d = _future(23)
        db.vip_avail.delete_many({"vip_id": user_id, "date": d})
        db.vip_sched.delete_many({"vip_id": user_id, "date": d})
        requests.post(f"{API}/vip/schedule/availability/bulk", headers=_hdr(user_token), timeout=20,
                      json={"dates": [d], "ranges": [{"start": "10:00", "end": "22:00"}], "slot_len": 60, "tz": "UTC"})
        _set_coins(db, admin_id, 50000)
        r = requests.post(f"{API}/vip/schedule/{user_id}/book", headers=_hdr(admin_token), timeout=20,
                         json={"date": d, "start": "15:00", "end": "16:00", "coins": 500, "tz": "UTC"})
        bid = r.json().get("booking_id")
        # pending -> cannot extend
        r2 = requests.post(f"{API}/vip/schedule/bookings/{bid}/extend", headers=_hdr(admin_token), timeout=20,
                           json={"hours": 1})
        assert r2.status_code == 400
        assert "NOT_IN_PROGRESS" in r2.text
        db.vip_sched.delete_many({"id": bid})
        db.vip_avail.delete_many({"vip_id": user_id, "date": d})

    def test_extend_in_progress_charges_coins(self, admin_token, admin_id, user_token, user_id, db):
        """Seed an in-progress confirmed booking and extend by 1 hour."""
        now = datetime.now(timezone.utc)
        d = now.strftime("%Y-%m-%d")
        start_hm = (now - timedelta(minutes=30)).strftime("%H:%M")
        end_hm = (now + timedelta(hours=1)).strftime("%H:%M")
        bid = f"TEST_extend_{uuid.uuid4()}"
        # Clear any blocking date_bookings for user_id today to avoid SLOT_TAKEN
        db.date_bookings.delete_many({"$or": [{"from_id": user_id}, {"to_id": user_id}],
                                      "status": {"$in": ["accepted", "confirmed", "escrow", "pending"]},
                                      "scheduled_at": {"$regex": f"^{d}"}})
        # Make sure VIP extra price is 300
        requests.put(f"{API}/vip/profile", json={"price_hour": 500, "price_2h": 900, "price_3h": 1200,
                                                 "price_extra_hour": 300, "services": [], "places": [],
                                                 "availability": [], "published": True},
                     headers=_hdr(user_token), timeout=20)
        db.vip_sched.insert_one({
            "id": bid, "vip_id": user_id, "requester_id": admin_id, "date": d,
            "start": start_hm, "end": end_hm, "status": "confirmed", "tz": "UTC",
            "coins": 500, "hours": 1, "extra_hours": 0, "extra_coins": 0,
            "lock_start": start_hm, "lock_end": end_hm,
            "scheduled_at": f"{d}T{start_hm}:00", "created_at": now.isoformat(),
        })
        _set_coins(db, admin_id, 50000)
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/extend", headers=_hdr(admin_token), timeout=20,
                         json={"hours": 1})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["cost"] == 300
        doc = db.vip_sched.find_one({"id": bid}, {"_id": 0})
        assert doc["extra_hours"] == 1
        assert doc["extra_coins"] == 300
        assert doc["coins"] == 500 + 300
        # cleanup
        db.vip_sched.delete_many({"id": bid})

    def test_vip_book_extend_in_progress(self, admin_token, admin_id, user_token, user_id, db):
        """Create date_bookings doc with vip=True in progress, then extend."""
        now = datetime.now(timezone.utc)
        bid = f"TEST_vbext_{uuid.uuid4()}"
        start_iso = (now - timedelta(minutes=20)).isoformat()
        db.date_bookings.insert_one({
            "id": bid, "from_id": admin_id, "to_id": user_id, "status": "confirmed",
            "vip": True, "duration_min": 60, "coins": 500,
            "scheduled_at": start_iso, "slot_from": now.strftime("%H:%M"),
            "created_at": now.isoformat(),
        })
        _set_coins(db, admin_id, 50000)
        # Ensure extra price at 300
        requests.put(f"{API}/vip/profile", json={"price_hour": 500, "price_2h": 900, "price_3h": 1200,
                                                 "price_extra_hour": 300, "services": [], "places": [],
                                                 "availability": [], "published": True},
                     headers=_hdr(user_token), timeout=20)
        r = requests.post(f"{API}/vip/book/{bid}/extend", headers=_hdr(admin_token), timeout=20,
                         json={"hours": 2})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["cost"] == 600
        assert body["duration_min"] == 60 + 120
        doc = db.date_bookings.find_one({"id": bid}, {"_id": 0})
        assert doc["extra_hours"] == 2
        assert doc["extra_coins"] == 600
        db.date_bookings.delete_many({"id": bid})


# ---------------- Reminders via _vs_tick ----------------
class TestReminders:
    def test_1h_reminder_fires_and_notifies_both(self, admin_token, admin_id, user_id, user_token, db):
        """Seed a confirmed booking starting in ~55 minutes, trigger _vs_tick, verify flag + notifications."""
        # The _vs_reminder_loop runs every 60s automatically; we also import and call _vs_tick directly for determinism.
        now = datetime.now(timezone.utc)
        start = now + timedelta(minutes=55)
        bid = f"TEST_rem_{uuid.uuid4()}"
        d = start.strftime("%Y-%m-%d")
        start_hm = start.strftime("%H:%M")
        end_hm = (start + timedelta(hours=1)).strftime("%H:%M")
        db.vip_sched.insert_one({
            "id": bid, "vip_id": user_id, "requester_id": admin_id, "date": d,
            "start": start_hm, "end": end_hm, "status": "confirmed", "tz": "UTC",
            "coins": 500, "hours": 1, "scheduled_at": f"{d}T{start_hm}:00",
            "reminder_24_sent": True, "reminder_1h_sent": False,
            "created_at": now.isoformat(),
        })
        # Trigger _vs_tick directly through the running server by importing module
        import sys, importlib
        sys.path.insert(0, "/app/backend")
        srv = importlib.import_module("server")
        asyncio.get_event_loop().run_until_complete(srv._vs_tick())
        doc = db.vip_sched.find_one({"id": bid}, {"_id": 0})
        assert doc["reminder_1h_sent"] is True, doc
        # Both parties should have an in-app notification with ntype vs_reminder & booking id
        for uid in (user_id, admin_id):
            n = db.notifications.find_one({"user_id": uid, "type": "vs_reminder", "data.booking_id": bid})
            assert n, f"missing vs_reminder notification for {uid}"
        # cleanup
        db.vip_sched.delete_many({"id": bid})
        db.notifications.delete_many({"data.booking_id": bid})
