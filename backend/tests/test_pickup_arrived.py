"""Tests for VIP pickup proposal + arrival check-in (iteration 20)."""
import os, re, datetime, time as _t
import pytest, requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
ADMIN = ("giftsdates@gmail.com", "Admin@GD24!")
VIP = ("testuser@giftsdates.com", "Test@12345")
VIP_ID = "b486a9ec-21a5-46f2-ac7b-4bd42fcb91e6"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    r.raise_for_status()
    return r.json()["token"]


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def vip_tok():
    return _login(*VIP)


@pytest.fixture(scope="module")
def mongo():
    from pymongo import MongoClient
    url = os.environ["MONGO_URL"]
    dbname = os.environ["DB_NAME"]
    c = MongoClient(url)
    return c[dbname]


def _find_or_create_pending(admin_tok, mongo):
    """Find a pending booking from admin to the VIP, or create one on an available slot."""
    # Try existing seed
    b = mongo.vip_sched.find_one({"id": "36f0a2ab-6351-45cd-8ba2-8cb6b6dd200f"})
    if b and b.get("status") == "pending" and not (b.get("pickup") or {}).get("status") == "proposed":
        return b["id"]
    # Clear a stale pickup on seed booking so we can propose again
    if b and b.get("status") == "pending":
        mongo.vip_sched.update_one({"id": b["id"]}, {"$unset": {"pickup": ""}})
        return b["id"]
    # Else: try to create via slots
    r = requests.get(f"{API}/vip/schedule/{VIP_ID}/slots", headers=_hdr(admin_tok), timeout=20)
    r.raise_for_status()
    slots = [s for s in r.json().get("slots", []) if s.get("state") == "available"]
    if not slots:
        pytest.skip("No available VIP slots to create a pending booking")
    s = slots[0]
    r = requests.post(f"{API}/vip/schedule/{VIP_ID}/book",
                      headers=_hdr(admin_tok),
                      json={"date": s["start"][:10], "start": s["start"][11:16],
                            "end": s["end"][11:16], "length": 1, "place": "own"}, timeout=20)
    r.raise_for_status()
    return r.json()["booking_id"]


# ---------- Pickup propose ----------
class TestPickupPropose:
    def test_non_vip_forbidden(self, admin_tok, mongo):
        bid = _find_or_create_pending(admin_tok, mongo)
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/propose",
                          headers=_hdr(admin_tok),
                          json={"address": "1 Downing St", "time": "17:00"}, timeout=20)
        assert r.status_code == 403, r.text

    def test_address_required(self, vip_tok, admin_tok, mongo):
        bid = _find_or_create_pending(admin_tok, mongo)
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/propose",
                          headers=_hdr(vip_tok),
                          json={"address": "   "}, timeout=20)
        assert r.status_code == 400
        assert "ADDRESS_REQUIRED" in r.text

    def test_propose_ok_and_duplicate_rejected(self, vip_tok, admin_tok, mongo):
        bid = _find_or_create_pending(admin_tok, mongo)
        # Ensure no pickup pending
        mongo.vip_sched.update_one({"id": bid}, {"$unset": {"pickup": ""}})
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/propose",
                          headers=_hdr(vip_tok),
                          json={"address": "221B Baker Street", "city": "London",
                                "postal_code": "NW1 6XE", "country": "UK",
                                "lat": 51.5237, "lng": -0.1585,
                                "time": "16:30", "note": "Meet at the door"}, timeout=20)
        assert r.status_code == 200, r.text
        p = r.json()["pickup"]
        assert p["status"] == "proposed" and p["address"] == "221B Baker Street" and p["time"] == "16:30"
        # Verify persistence
        b = mongo.vip_sched.find_one({"id": bid})
        assert b["pickup"]["status"] == "proposed"
        # Requester got notification
        notif = list(mongo.notifications.find({"user_id": b["requester_id"], "type": "vs_pickup"}).sort("created_at", -1).limit(3))
        assert any((n.get("data") or {}).get("booking_id") == bid for n in notif)
        # Duplicate
        r2 = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/propose",
                           headers=_hdr(vip_tok),
                           json={"address": "Other"}, timeout=20)
        assert r2.status_code == 400 and "PICKUP_PENDING" in r2.text


# ---------- Pickup accept / decline ----------
class TestPickupAnswer:
    def test_decline_keeps_pending_and_allows_repropose(self, vip_tok, admin_tok, mongo):
        bid = _find_or_create_pending(admin_tok, mongo)
        mongo.vip_sched.update_one({"id": bid}, {"$unset": {"pickup": ""}})
        # propose
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/propose",
                      headers=_hdr(vip_tok), json={"address": "A St"}, timeout=20).raise_for_status()
        # decline
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/decline",
                         headers=_hdr(admin_tok), timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"
        b = mongo.vip_sched.find_one({"id": bid})
        assert b["status"] == "pending" and b["pickup"]["status"] == "declined"
        # VIP notified of decline
        n = list(mongo.notifications.find({"user_id": VIP_ID, "type": "vs_pickup"}).sort("created_at", -1).limit(1))
        assert n and (n[0].get("data") or {}).get("booking_id") == bid
        # Re-propose should now be allowed (declined != proposed)
        r2 = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/propose",
                           headers=_hdr(vip_tok), json={"address": "B St", "time": "17:00"}, timeout=20)
        assert r2.status_code == 200, r2.text

    def test_accept_confirms_booking(self, vip_tok, admin_tok, mongo):
        bid = _find_or_create_pending(admin_tok, mongo)
        # Reset to pending + fresh proposal
        mongo.vip_sched.update_one({"id": bid}, {"$set": {"status": "pending"}, "$unset": {"pickup": "", "confirmed_at": "", "auto_confirmed": ""}})
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/propose",
                      headers=_hdr(vip_tok), json={"address": "Accept St", "time": "17:00"}, timeout=20).raise_for_status()
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/accept",
                          headers=_hdr(admin_tok), timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "confirmed"
        b = mongo.vip_sched.find_one({"id": bid})
        assert b["status"] == "confirmed" and b["pickup"]["status"] == "accepted"


# ---------- Arrived ----------
class TestArrived:
    def test_not_date_time_rejected(self, admin_tok, vip_tok, mongo):
        # Use a confirmed booking far in future (seeded 59cd396e... Oct 17 12:00)
        bid = "59cd396e-4b32-43b1-87fa-6ef7f11cebdd"
        b = mongo.vip_sched.find_one({"id": bid})
        if not b or b.get("status") != "confirmed":
            pytest.skip("No far-future confirmed booking available")
        # Set date far in future to guarantee outside window
        mongo.vip_sched.update_one({"id": bid}, {"$set": {"date": "2099-01-01", "start": "10:00", "end": "11:00"}, "$unset": {"arrived_at": ""}})
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/arrived",
                          headers=_hdr(admin_tok), timeout=20)
        assert r.status_code == 400 and "NOT_DATE_TIME" in r.text
        # restore
        mongo.vip_sched.update_one({"id": bid}, {"$set": {"date": "2025-10-17", "start": "12:00", "end": "13:00"}})

    def test_arrival_in_window_notifies_vip_and_is_idempotent(self, admin_tok, vip_tok, mongo):
        # Use the seed booking directly (status may already be confirmed from accept test)
        bid = "36f0a2ab-6351-45cd-8ba2-8cb6b6dd200f"
        if not mongo.vip_sched.find_one({"id": bid}):
            bid = _find_or_create_pending(admin_tok, mongo)
        # Force confirmed and set start to ~30min from now
        now = datetime.datetime.now(datetime.timezone.utc)
        start_dt = now + datetime.timedelta(minutes=30)
        end_dt = now + datetime.timedelta(minutes=90)
        mongo.vip_sched.update_one({"id": bid}, {"$set": {
            "status": "confirmed",
            "date": start_dt.strftime("%Y-%m-%d"),
            "start": start_dt.strftime("%H:%M"),
            "end": end_dt.strftime("%H:%M"),
            "location": {"address": "Test Place"}
        }, "$unset": {"arrived_at": "", "pickup": ""}})
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/arrived",
                          headers=_hdr(admin_tok), timeout=20)
        assert r.status_code == 200, r.text
        at = r.json()["arrived_at"]
        assert at
        b = mongo.vip_sched.find_one({"id": bid})
        assert b["arrived_at"] == at
        # VIP notification
        _t.sleep(0.3)
        r2 = requests.get(f"{API}/notifications", headers=_hdr(vip_tok), timeout=20)
        assert r2.status_code == 200
        items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
        assert any(n.get("type") == "vs_arrived" and (n.get("data") or {}).get("booking_id") == bid for n in items), f"No vs_arrived notif for VIP: {items[:3]}"
        # Idempotent second call
        r3 = requests.post(f"{API}/vip/schedule/bookings/{bid}/arrived",
                           headers=_hdr(admin_tok), timeout=20)
        assert r3.status_code == 200 and r3.json()["arrived_at"] == at
