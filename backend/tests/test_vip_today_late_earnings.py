"""Backend tests for iteration-21: Today agenda data, earnings tile, and Running Late endpoint."""
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

ADMIN = ("giftsdates@gmail.com", "Admin@GD24!")
VIP = ("testuser@giftsdates.com", "Test@12345")
VIP_ID = "b486a9ec-21a5-46f2-ac7b-4bd42fcb91e6"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def db():
    assert MONGO_URL and DB_NAME, "MONGO_URL/DB_NAME required"
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def vip_tok():
    return _login(*VIP)


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- /vip/schedule/me earnings ----------
class TestEarnings:
    def test_me_returns_earnings_structure(self, vip_tok):
        r = requests.get(f"{BASE_URL}/api/vip/schedule/me", headers=h(vip_tok), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "earnings" in data
        e = data["earnings"]
        assert set(e.keys()) >= {"month", "earned", "held"}
        assert e["month"] == datetime.now(timezone.utc).strftime("%Y-%m")
        assert isinstance(e["earned"], int) and e["earned"] >= 0
        assert isinstance(e["held"], int) and e["held"] >= 0

    def test_earnings_match_mongo(self, vip_tok, db):
        r = requests.get(f"{BASE_URL}/api/vip/schedule/me", headers=h(vip_tok), timeout=15)
        data = r.json()
        bookings = data["pending"] + data["confirmed"] + data["past"]
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        expected_earned = sum(int(b.get("coins") or 0) for b in bookings if b["status"] == "completed" and str(b.get("completed_at", "")).startswith(month))
        expected_earned += sum(int(b.get("compensation") or 0) for b in bookings if b["status"] == "cancelled" and str(b.get("cancelled_at", "")).startswith(month))
        expected_held = sum(int(b.get("coins") or 0) for b in bookings if b["status"] in ("pending", "confirmed"))
        for d in db.date_bookings.find({"to_id": VIP_ID, "vip": True}):
            if d.get("status") == "released" and str(d.get("released_at", "")).startswith(month):
                expected_earned += int(d.get("released_net") or 0)
            elif d.get("status") in ("escrow", "accepted", "confirmed"):
                expected_held += int(d.get("coins") or 0)
        assert data["earnings"]["earned"] == expected_earned
        assert data["earnings"]["held"] == expected_held


# ---------- /vip/schedule/bookings/{id}/late ----------
class TestRunningLate:
    @pytest.fixture(scope="class")
    def booking_id(self, db):
        """Find or set up a confirmed booking for the VIP whose start is near now."""
        now = datetime.now(timezone.utc)
        target_date = now.strftime("%Y-%m-%d")
        start_dt = (now + timedelta(minutes=30))
        end_dt = (now + timedelta(hours=2))
        start_hm = start_dt.strftime("%H:%M")
        end_hm = end_dt.strftime("%H:%M")
        # Pick an existing booking for this VIP and mutate it
        b = db.vip_sched.find_one({"vip_id": VIP_ID})
        assert b, "No vip_sched doc exists for VIP; cannot run late tests"
        # Save original for restore
        self_orig = {k: b.get(k) for k in ("date", "start", "end", "status", "tz", "late")}
        db.vip_sched.update_one({"id": b["id"]}, {"$set": {"date": target_date, "start": start_hm, "end": end_hm, "status": "confirmed", "tz": "UTC"}, "$unset": {"late": ""}})
        yield b["id"]
        # restore after class
        set_doc = {k: v for k, v in self_orig.items() if v is not None and k != "late"}
        unset_doc = {} if self_orig.get("late") is not None else {"late": ""}
        if set_doc:
            db.vip_sched.update_one({"id": b["id"]}, {"$set": set_doc})
        if unset_doc:
            db.vip_sched.update_one({"id": b["id"]}, {"$unset": unset_doc})

    def test_client_forbidden(self, admin_tok, booking_id):
        r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{booking_id}/late", headers=h(admin_tok), json={"minutes": 10}, timeout=15)
        assert r.status_code == 403

    def test_bad_minutes(self, vip_tok, booking_id):
        r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{booking_id}/late", headers=h(vip_tok), json={"minutes": 7}, timeout=15)
        assert r.status_code == 400
        assert r.json().get("detail") == "BAD_MINUTES"

    def test_404_unknown(self, vip_tok):
        r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/nonexistent-id/late", headers=h(vip_tok), json={"minutes": 10}, timeout=15)
        assert r.status_code == 404

    def test_happy_path_and_notification(self, vip_tok, admin_tok, booking_id, db):
        r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{booking_id}/late", headers=h(vip_tok), json={"minutes": 10}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["late"]["minutes"] == 10
        assert "at" in data["late"]
        # Mongo persistence
        doc = db.vip_sched.find_one({"id": booking_id})
        assert doc["late"]["minutes"] == 10
        # Also returned from /me
        me = requests.get(f"{BASE_URL}/api/vip/schedule/me", headers=h(vip_tok), timeout=15).json()
        found = next((b for b in me["confirmed"] if b["id"] == booking_id), None)
        assert found and found["late"]["minutes"] == 10
        # Notification to client (requester = admin for this seed booking)
        time.sleep(0.5)
        nr = requests.get(f"{BASE_URL}/api/notifications", headers=h(admin_tok), timeout=15)
        assert nr.status_code == 200
        notifs = nr.json() if isinstance(nr.json(), list) else nr.json().get("notifications") or nr.json().get("items") or []
        late_notifs = [n for n in notifs if n.get("type") == "vs_late" and (n.get("data") or {}).get("booking_id") == booking_id]
        assert late_notifs, f"vs_late notification missing for booking {booking_id}"

    def test_all_valid_minutes(self, vip_tok, booking_id):
        for m in (5, 10, 15, 20, 30, 45, 60):
            r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{booking_id}/late", headers=h(vip_tok), json={"minutes": m}, timeout=15)
            assert r.status_code == 200, f"minutes={m} => {r.status_code} {r.text}"
            assert r.json()["late"]["minutes"] == m

    def test_not_confirmed_rejected(self, vip_tok, booking_id, db):
        db.vip_sched.update_one({"id": booking_id}, {"$set": {"status": "pending"}})
        try:
            r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{booking_id}/late", headers=h(vip_tok), json={"minutes": 10}, timeout=15)
            assert r.status_code == 400
            assert r.json().get("detail") == "NOT_DATE_TIME"
        finally:
            db.vip_sched.update_one({"id": booking_id}, {"$set": {"status": "confirmed"}})

    def test_outside_window_rejected(self, vip_tok, booking_id, db):
        # Push start to >3h in the future
        future = datetime.now(timezone.utc) + timedelta(hours=5)
        db.vip_sched.update_one({"id": booking_id}, {"$set": {"date": future.strftime("%Y-%m-%d"), "start": future.strftime("%H:%M"), "end": (future + timedelta(hours=1)).strftime("%H:%M")}})
        try:
            r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{booking_id}/late", headers=h(vip_tok), json={"minutes": 10}, timeout=15)
            assert r.status_code == 400
            assert r.json().get("detail") == "NOT_DATE_TIME"
        finally:
            # Reset to in-window
            now = datetime.now(timezone.utc)
            db.vip_sched.update_one({"id": booking_id}, {"$set": {"date": now.strftime("%Y-%m-%d"), "start": (now + timedelta(minutes=30)).strftime("%H:%M"), "end": (now + timedelta(hours=2)).strftime("%H:%M")}})
